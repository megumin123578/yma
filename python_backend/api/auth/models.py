from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
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
    channel_avatar_url = Column(String, nullable=True)
