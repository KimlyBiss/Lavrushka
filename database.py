from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, unique=True)
    first_name = Column(String(64))
    username = Column(String(64))
    playlists = relationship('Playlist', back_populates='owner')

class Playlist(Base):
    __tablename__ = 'playlists'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship('User', back_populates='playlists', overlaps="user")
    tracks = relationship('Track', back_populates='playlist')
    name = Column(String(100))
    description = Column(Text)
    cover_url = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)
    duration = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    user = relationship("User", back_populates="playlists")  # Двусторонняя связь
    tracks = relationship('Track', back_populates='playlist')

class Track(Base):
    __tablename__ = 'tracks'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    file_id = Column(String(300))
    duration = Column(Integer, default=0)
    playlist_id = Column(Integer, ForeignKey('playlists.id'))
    playlist = relationship("Playlist", back_populates="tracks")

# Пересоздаем базу
engine = create_engine('sqlite:///music.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)