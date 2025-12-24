from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Text, DateTime
from datetime import datetime
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


class SmmstoreAnalyticsCache(Base):
    __tablename__ = "smmstore_analytics_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_smmstore_user_month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    month = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserHiddenChannel(Base):
    __tablename__ = "user_hidden_channels"
    __table_args__ = (
        UniqueConstraint("user_id", "account_tag", name="uq_hidden_user_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_tag = Column(String, nullable=False, index=True)


class UserSchedule(Base):
    __tablename__ = "user_schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_name = Column(String, nullable=True)
    mode = Column(String, nullable=False)  # daily | interval
    time_of_day = Column(String, nullable=True)  # HH:MM
    every_minutes = Column(Integer, nullable=True)
    enabled = Column(Integer, nullable=False, default=1)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
