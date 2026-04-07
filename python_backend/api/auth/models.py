from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Text, DateTime, Boolean
from datetime import datetime, timezone, timedelta
try:
    from python_backend.api.auth.database import Base
except ModuleNotFoundError:
    from api.auth.database import Base


SAIGON_TZ = timezone(timedelta(hours=7))


def _now_saigon_naive() -> datetime:
    return datetime.now(SAIGON_TZ).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    smmstore_api_key = Column(String, nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)


class PasswordChangeRequest(Base):
    __tablename__ = "password_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    requested_by = Column(String, nullable=False, index=True)
    new_password_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    admin_username = Column(String, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    decided_at = Column(DateTime, nullable=True, index=True)


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
    group_name = Column(String, nullable=True)


class RivalChannelGroup(Base):
    __tablename__ = "rival_channel_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", "group_name", name="uq_rival_group"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(String, nullable=False, index=True)
    group_name = Column(String, nullable=False, index=True)


class RivalGroup(Base):
    __tablename__ = "rival_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "group_name", name="uq_rival_group_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    group_name = Column(String, nullable=False, index=True)


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



class SmmstoreScheduledOrder(Base):
    __tablename__ = "smmstore_scheduled_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    run_at = Column(DateTime, nullable=False, index=True)
    service = Column(String, nullable=False)
    link = Column(String, nullable=False)
    quantity = Column(String, nullable=False)
    runs = Column(String, nullable=True)
    interval = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued", index=True)
    remote_order_id = Column(String, nullable=True, index=True)
    charge = Column(String, nullable=True)
    remains = Column(String, nullable=True)
    last_error = Column(Text, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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


class UserScheduleRun(Base):
    __tablename__ = "user_schedule_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("user_schedules.id"), nullable=True, index=True)
    token_name = Column(String, nullable=True)
    token_names = Column(Text, nullable=True)
    run_type = Column(String, nullable=True)
    status = Column(String, nullable=False)  # running | done | error | empty
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    processed = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)


class TokenProgress(Base):
    __tablename__ = "token_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "token_name", name="uq_token_progress_user_token"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_name = Column(String, nullable=False, index=True)
    account_tag = Column(String, nullable=False, index=True)
    run_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    stage = Column(String, nullable=True)
    percent = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (
        UniqueConstraint("state", name="uq_oauth_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_tag = Column(String, nullable=False)
    auto_name = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="pending", index=True)
    token_name = Column(String, nullable=True)
    final_account_tag = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    consumed_at = Column(DateTime, nullable=True, index=True)


class MailOAuthState(Base):
    __tablename__ = "mail_oauth_states"
    __table_args__ = (
        UniqueConstraint("state", name="uq_mail_oauth_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    label_ids_json = Column(Text, nullable=False, default='["INBOX"]')
    account_email = Column(String, nullable=True, index=True)
    token_name = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    consumed_at = Column(DateTime, nullable=True, index=True)


class MailAccount(Base):
    __tablename__ = "mail_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "account_email", name="uq_mail_account_user_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_email = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, default="gmail_api")
    token_name = Column(String, nullable=False, index=True)
    label_ids_json = Column(Text, nullable=False, default='["INBOX"]')
    history_id = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    last_sync_status = Column(String, nullable=True, index=True)
    last_error_message = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserCredential(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "account_tag", name="uq_user_credential_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_tag = Column(String, nullable=False, index=True)
    token_name = Column(String, nullable=True)
    group_name = Column(String, nullable=True, index=True)
    selected_channel_id = Column(String, nullable=True)
    selected_channel_title = Column(String, nullable=True)
    selected_channel_avatar = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserCredentialGroup(Base):
    __tablename__ = "user_credential_groups"
    __table_args__ = (
        UniqueConstraint("user_id", "group_name", name="uq_user_credential_group_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    group_name = Column(String, nullable=False, index=True)
    color = Column(String, nullable=True)


class LiveCounterSnapshot(Base):
    __tablename__ = "live_counter_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_tag = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=True, index=True)
    subscriber_count = Column(Integer, nullable=False, default=0)
    view_count = Column(Integer, nullable=False, default=0)
    video_count = Column(Integer, nullable=False, default=0)
    captured_at = Column(DateTime, default=_now_saigon_naive, nullable=False, index=True)


class VideoLiveCounterSnapshot(Base):
    __tablename__ = "video_live_counter_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_tag = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=True, index=True)
    channel_name = Column(String, nullable=True)
    video_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    position = Column(Integer, nullable=False, default=0)
    view_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    captured_at = Column(DateTime, default=_now_saigon_naive, nullable=False, index=True)
