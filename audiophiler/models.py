# File: models.py
# Audiophiler sqlalchemy database models

from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

from audiophiler import db

Base = declarative_base()

class File(db.Model):
    __tablename__ = "files"
    file_id = Column(Integer, primary_key=True)
    file_hash = Column(Text, nullable=False)
    converted = Column(Boolean, default=False)

    def __init__(self, file_hash):
        self.file_hash = file_hash

class Meta(db.Model):
    __tablename__="meta"
    meta_id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.file_id'))
    name = Column(Text, nullable=False)
    author = Column(Text, nullable=False)
    beat_times = Column(Text, nullable=False)

    def __init__(self, file_id, name, author, beat_times):
        self.file_id = file_id
        self.name = name
        self.author = author
        self.beat_times = beat_times

class Harold(db.Model):
    __tablename__ = "harolds"
    harold_id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.file_id'))
    owner = Column(Text, nullable=False)

    def __init__(self, file_id, owner):
        self.file_id = file_id
        self.owner = owner

class Auth(db.Model):
    __tablename__ = "auth"
    id = Column(Integer, primary_key=True)
    auth_key = Column(Text, nullable=False)

    def __init__(self, auth_key):
        self.auth_key = auth_key

class Tour(db.Model):
    __tablename__ = "tour"
    tour_lock = Column(Boolean, primary_key=True, default=False)
