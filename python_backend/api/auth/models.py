from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
from python_backend.api.auth.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    smmstore_api_key = Column(String, nullable=True)


class RivalChannel(Base):
    __tablename__ = "rival_channels"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_rival_user_channel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    channel_name = Column(String, nullable=True)
    channel_url = Column(String, nullable=True)


class RivalVideo(Base):
    __tablename__ = "rival_videos"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_rival_user_video"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(String, nullable=False, index=True)
    video_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    published_at = Column(String, nullable=True)
    is_short = Column(Boolean, nullable=False, default=False)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
