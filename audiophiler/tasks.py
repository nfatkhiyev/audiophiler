import os
import hashlib
import requests
from flask import Flask
import librosa
import numpy
import ffmpy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from audiophiler.models import Base, Meta, File

from audiophiler.s3 import upload_file, remove_file, get_bucket

app = Flask(__name__)

if os.path.exists(os.path.join(os.getcwd(), "config.py")):
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.py"))
else:
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.env.py"))

s3_bucket = get_bucket(app.config["S3_URL"], app.config["S3_KEY"],
                app.config["S3_SECRET"], app.config["BUCKET_NAME"])

def connect_db():
    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    Base.metadata.bind = engine
    dbsession = sessionmaker(bind=engine)
    db = dbsession()
    return db

def process_audio_task(link, file_id, file_name, author):
    with app.app_context():
        db = connect_db()
        music = requests.get(link, allow_redirects=True)
        open('music', 'wb').write(music.content)
        try:
            convert_media('music','music.wav')
        except:
            print('fuck')

        beat_time_string = process_audio('music.wav')
        meta_model = Meta(file_id, file_name, author, beat_time_string)
        db.add(meta_model)
        db.flush()
        db.commit()
        db.refresh(meta_model)

        file = open('music.wav', 'r').read()

        query = File.query.filter_by(file_id=file_id).first()

        old_file_hash = query.file_hash
        new_file_hash = updated_file_hash(file_id, file)
        update_bucket(old_file_hash, new_file_hash, file)

        query.file_hash = new_file_hash
        query.converted = True

        os.remove("music")
        os.remove("music.wav")

def convert_media(input_string, output_string):
    ff = ffmpy.FFmpeg(
        inputs={input_string: None},
        outputs={output_string: None}
    )
    ff.run()

def process_audio(file_name):
    x, sr = librosa.load(file_name)
    _, beat_times = librosa.beat.beat_track(x, sr=sr, start_bpm=100, units='time')
    string = ""
    for t in beat_times:
        if t > 30:
            beat_times = beat_times[:numpy.where(beat_times == t)[0][0]]
            beat_times.tolist()
            break
    for i in range(0, len(beat_times)-1, 4):
        beat_times.insert(i+1, (3*beat_times[i]+beat_times[i+1])/4)
        beat_times.insert(i+2, (beat_times[i]+beat_times[i+2])/2)
        beat_times.insert(i+3, (beat_times[i]+3*beat_times[i+3])/4)

    for t in beat_times:
        string = string+str(t)+","

    return string[:-1]

def update_bucket(old_file_hash, new_file_hash, file):
    remove_file(s3_bucket, old_file_hash)
    upload_file(s3_bucket, new_file_hash, file)

def updated_file_hash(file_id, file):
    entry = File.query.filter_by(file_id=file_id).first()
    new_file_hash = hashlib.md5(file.read()).hexdigest()
    entry.file_hash = new_file_hash

    return new_file_hash
