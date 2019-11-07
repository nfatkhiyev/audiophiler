# File: __init__.py
# Audiophiler main flask functions

import hashlib
import os
import random
import subprocess
import json
import requests
import flask_migrate
from flask import Flask, render_template, request, jsonify, redirect
from flask_pyoidc.provider_configuration import *
from flask_pyoidc.flask_pyoidc import OIDCAuthentication
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from csh_ldap import CSHLDAP
from redis import Redis
from rq import Queue
from audiophiler.s3 import *
from audiophiler._version import __version__

app = Flask(__name__)
app.config.update({
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "VERSION": __version__
})

# Get app config from absolute file path
if os.path.exists(os.path.join(os.getcwd(), "config.py")):
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.py"))
else:
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.env.py"))

_config = ProviderConfiguration(
    app.config['OIDC_ISSUER'],
    client_metadata = ClientMetadata(
        app.config['OIDC_CLIENT_CONFIG']['client_id'],
        app.config['OIDC_CLIENT_CONFIG']['client_secret']
    )
)
auth = OIDCAuthentication({'default': _config}, app)

# Get s3 bucket for use in functions and templates
s3_bucket = get_bucket(app.config["S3_URL"], app.config["S3_KEY"],
                app.config["S3_SECRET"], app.config["BUCKET_NAME"])

# Database setup
db = SQLAlchemy(app)
migrate = flask_migrate.Migrate(app, db)

# Import db models after instantiating db object
from audiophiler.models import *
from audiophiler.util import *
from audiophiler.tasks import process_audio_task

# Create CSHLDAP connection
ldap = CSHLDAP(app.config["LDAP_BIND_DN"],
               app.config["LDAP_BIND_PW"])

# Import ldap functions after creating ldap conn
from audiophiler.ldap import ldap_is_eboard, ldap_is_rtp

# Disable SSL certificate verification warning
requests.packages.urllib3.disable_warnings()

#Setup redis fro queue
redis_conn = Redis(app.config['REDIS_HOST'], app.config['REDIS_PORT'], password=app.config['REDIS_PASSWORD'])
q = Queue(connection=redis_conn)

@app.route("/")
@auth.oidc_auth('default')
@audiophiler_auth
def home(auth_dict=None):
    # Retrieve list of files for templating
    db_files = File.query.join(Meta).all()
    harolds = get_harold_list(auth_dict["uid"])
    tour_harolds = get_harold_list("root")
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    return render_template("main.html", db_files=db_files,
                get_date_modified=get_date_modified, s3_bucket=s3_bucket,
                auth_dict=auth_dict, harolds=harolds, tour_harolds=tour_harolds,
                is_rtp=is_rtp, is_eboard=is_eboard, is_tour_page=False)

@app.route("/mine")
@auth.oidc_auth('default')
@audiophiler_auth
def mine(auth_dict=None):
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    # Retrieve list of files for templating
    db_files = File.query.join(Meta).filter_by(author=auth_dict["uid"]).all()
    harolds = get_harold_list(auth_dict["uid"])
    tour_harolds = get_harold_list("root")
    return render_template("main.html", db_files=db_files,
                get_file_s3=get_file_s3, get_date_modified=get_date_modified,
                s3_bucket=s3_bucket, auth_dict=auth_dict, harolds=harolds,
                tour_harolds=tour_harolds, is_rtp=is_rtp, is_eboard=is_eboard, is_tour_page=False)

@app.route("/selected")
@auth.oidc_auth('default')
@audiophiler_auth
def selected(auth_dict=None):
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    #Retrieve list of files for templating
    harolds = get_harold_list(auth_dict["uid"])
    tour_harolds = get_harold_list("root")
    db_files = File.query.join(Meta).filter(File.file_id.in_(harolds)).all()
    return render_template("main.html", db_files=db_files,
                get_date_modified=get_date_modified, s3_bucket=s3_bucket,
                auth_dict=auth_dict, harolds=harolds, tour_harolds=tour_harolds,
                is_rtp=is_rtp, is_eboard=is_eboard, is_tour_page=False)

@app.route("/tour_page")
@auth.oidc_auth('default')
@audiophiler_auth
def tour_page(auth_dict=None):
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    if is_eboard or is_rtp:
        harolds = get_harold_list(auth_dict["uid"])
        tour_harolds = get_harold_list("root")
        db_files = File.query.join(Meta).filter(File.file_id.in_(tour_harolds)).all()
        return render_template("main.html", db_files=db_files,
            get_date_modified=get_date_modified, s3_bucket=s3_bucket,
            auth_dict=auth_dict, harolds=harolds, tour_harolds=tour_harolds,
            is_rtp=is_rtp, is_eboard=is_eboard, is_tour_page=True, is_tour_mode=get_tour_lock_status())

    return "Permission Denied", 403

@app.route("/upload", methods=["GET"])
@auth.oidc_auth('default')
@audiophiler_auth
def upload_page(auth_dict=None):
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    return render_template("upload.html", is_rtp=is_rtp, is_eboard=is_eboard, auth_dict=auth_dict)

@app.route("/upload", methods=["POST"])
@auth.oidc_auth('default')
@audiophiler_auth
def upload(auth_dict=None):
    uploaded_files = [t[1] for t in request.files.items()]
    upload_status = {}
    upload_status["error"] = []
    upload_status["success"] = []

    for f in uploaded_files:
        # Sanitize file name
        filename = secure_filename(f.filename).partition(".")[0]
        author = auth_dict["uid"]
        # Hash the file contents (read file in ram)
        # File contents cannot be read in chunks (this is a flaw in boto file objects)
        file_hash = hashlib.md5(f.read()).hexdigest()
        # Reset file pointer to avoid EOF
        f.seek(0)

        # Check if file hash is the same as any files already in the db
        if File.query.filter_by(file_hash=file_hash).first():
            upload_status["error"].append(filename)
            break

        # Add file info to db
        file_model = File(file_hash)
        if file_model is None:
            upload_status["error"].append(filename)
            break

        # Upload file to s3
        upload_file(s3_bucket, file_hash, f)

        # Add file_model to DB and flush
        db.session.add(file_model)
        db.session.flush()
        db.session.commit()
        db.session.refresh(file_model)

        #Get file_id
        file_id = File.query.last().file_id

        #Add the conversion to the queue
        q.enqueue(process_audio_task, redirect(get_file_s3(s3_bucket, file_hash)), file_id, filename, author)

        # Set success status info
        #THIS IS TO BE CHANGED
        upload_status["success"].append({
            "name": filename,
            "file_hash": file_model.file_hash
        })

    return jsonify(upload_status)

@app.route("/delete/<string:file_id>", methods=["POST"])
@auth.oidc_auth('default')
@audiophiler_auth
def delete_file(file_id, auth_dict=None):
    # Find file model in db
    file_model = File.query.filter(File.file_id == file_id).first()
    meta_model = Meta.query.filter(Meta.file_id == file_id).first()

    file_hash = file_model.file_hash

    if file_model or meta_model is None:
        return "File Not Found", 404

    if not auth_dict["uid"] == meta_model.author:
        if not (ldap_is_eboard(auth_dict["uid"]) or ldap_is_rtp(auth_dict["uid"])):
            return "Permission Denied", 403

    # Delete file model
    db.session.delete(file_model)
    db.session.delete(meta_model)
    db.session.flush()
    db.session.commit()
    # Delete harold model
    remove_harold(file_id)
    # Delete file from s3
    remove_file(s3_bucket, file_hash)

    return "OK go for it", 200

@app.route("/get_file_url/<string:file_id>")
@auth.oidc_auth('default')
@audiophiler_auth
def get_s3_url(file_id, auth_dict=None):
    # Endpoint to return a presigned url to the s3 asset
    file_hash = File.query.filter_by(file_id=file_id).first().file_hash
    return redirect(get_file_s3(s3_bucket, file_hash))

@app.route("/set_harold/<string:file_id>", methods=["POST"])
@auth.oidc_auth('default')
@audiophiler_auth
def set_harold(file_id, auth_dict=None):
    is_tour = request.json["tour"]
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    if is_tour == "true":
        if (is_rtp or is_eboard):
            uid = "root"
        else:
            return "Not Authorized", 403
    else:
        uid = auth_dict["uid"]
    harold_model = Harold(file_id, uid)
    db.session.add(harold_model)
    db.session.flush()
    db.session.commit()
    db.session.refresh(harold_model)
    return "OK", 200

@app.route("/delete_harold/<string:file_id>", methods=["POST"])
@auth.oidc_auth('default')
@audiophiler_auth
def remove_harold(file_id, auth_dict=None):
    is_tour = request.json["tour"]
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    if is_tour == "true":
        if is_rtp or is_eboard:
            uid = "root"
        else:
            return "Not Authorized", 403
    else:
        uid = auth_dict["uid"]
    harold_model = Harold.query.filter(
        Harold.file_id == file_id,
        Harold.owner == uid
        ).all()
    if harold_model is None:
        return "File Not Found", 404

    for model in harold_model:
        db.session.delete(model)
        db.session.flush()
        db.session.commit()

    return "OK go for it", 200

# This is a post route since auth_key is required
@app.route("/get_harold/<string:uid>", methods=["POST"])
def get_harold(uid, auth_dict=None):
    data_dict = request.get_json()
    if data_dict["auth_key"]:
        auth_models = Auth.query.all()
        for auth_obj in auth_models:
            if auth_obj.auth_key == data_dict["auth_key"]:
                harold_file_id = None
                if not get_tour_lock_status():
                    harolds_list = get_harold_list(uid)
                    if len(harolds_list) == 0:
                        harold_file_id = get_random_harold()
                    else:
                        harold_file_id = random.choice(harolds_list)
                else:
                    harold_file_id = random.choice(get_harold_list('root'))
                harold_file_hash = File.query.filter_by(file_id=harold_file_id).first().file_hash
                return get_file_s3(s3_bucket, harold_file_hash)

    return "Permission denied", 403

@app.route("/lock", methods=["POST"])
@auth.oidc_auth('default')
@audiophiler_auth
def toggle_tour_mode(auth_dict=None):
    is_rtp = ldap_is_rtp(auth_dict["uid"])
    is_eboard = ldap_is_eboard(auth_dict["uid"])
    if is_rtp or is_eboard:
        admin_query = Tour.query.first()
        if request.json["state"] == "t":
            admin_query.tour_lock = True
        elif request.json["state"] == "f":
            admin_query.tour_lock = False
        db.session.flush()
        db.session.commit()

        return "Tour Mode toggled", 200

    return "Permisssion Denied", 403

@app.route("/logout")
@auth.oidc_logout
def logout():
    return redirect("/", 302)

#return a list of file_ids filtered by owner
def get_harold_list(uid):
    harold_list = Harold.query.filter_by(owner=uid).all()
    #harolds = [harold.file_hash for harold in harold_list]
    harolds = [File.query.filter_by(file_id=harold.file_id).all().file_id for harold in harold_list]

    return harolds

def get_random_harold():
    query = Harold.query
    row_count = int(query.count())
    randomized_entry = query.offset(int(row_count*random.random())).first()

    return randomized_entry.file_id
