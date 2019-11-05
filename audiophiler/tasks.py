import requests
from flask import Flask
from rq import get_current_job
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Meta

import librosa
import ffmpy

app = Flask(__name__)

if os.path.exists(os.path.join(os.getcwd(), "config.py")):
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.py"))
else:
    app.config.from_pyfile(os.path.join(os.getcwd(), "config.env.py"))

def connect_db():
    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    Base.metadata.bind() = engine
    dbsession = sessionmaker(bind=engine)
    db = dbsession()
    return db

def process_audio_task(file_id, file_name, author):
    with app.app_context():
        db = conntect_db()
        file = requests.get(link, allow_redirects=True)
        open('music', 'wb').write(music.content)
        conver_media('music','music.wav')
        beat_time_string = process_audio('music.wav')
        db = connect_db
        meta_model = Meta(file_id, file_name, author, beat_time_string)
        db.session.add(meta_model)
        db.session.flush()
        db.session.commit()
        db.session.refresh(meta_model)


def conver_media(input, output):
    ff = ffmpy.FFmpeg(
        inputs={input: None},
        outputs={output: None}
    )
    ff.run()

def process_audio(file_name)
    x, sr = librosa.load(file_name)
    _, beat_times = librosa.beat_track(x, sr=sr, start_bpm=100, units='time')
    string = ""
    for t in beat_times:
        if t > 30:
            beat_times = beat_times[:beat_times.index(t)]
            break
    for i in range(0, len(beat_times)-1, 4):
        beat_times.insert(i+1, (3*beat_times[i]+beat_times[i+1])/4)
        beat_times.insert(i+2, (beat_times[i]+beat_times[i+2])/2)
        beat_times.insert(i+3, (beat_times[i]+3*beat_times[i+3])/4)

    for t in beat_times:
        string = string+str(t)+","

    return string[:-1]
