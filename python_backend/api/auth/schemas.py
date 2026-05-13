from pydantic import BaseModel
from pydantic import ConfigDict
from typing import Optional, List

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    username: str

class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str
    
class UserResponse(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    smmstore_api_key: Optional[str] = None
    is_admin: bool = False

    model_config = ConfigDict(from_attributes=True)

class TokenWithUser(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class UserMe(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    smmstore_api_key: Optional[str] = None
    is_admin: bool = False
    is_owner: bool = False

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    smmstore_api_key: Optional[str] = None


class PasswordChangeRequestOut(BaseModel):
    id: int
    user_id: int
    requested_by: str
    status: str
    admin_user_id: Optional[int] = None
    admin_username: Optional[str] = None
    requested_at: Optional[str] = None
    decided_at: Optional[str] = None


class PasswordChangeDecision(BaseModel):
    action: str


class AdminResetPasswordRequest(BaseModel):
    new_password: str


class AdminUserRoleUpdate(BaseModel):
    is_admin: bool


class AdminUserAccessUpdate(BaseModel):
    projects: List[str] = []
    channels: List[str] = []


class RivalChannelCreate(BaseModel):
    channel_id: str
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    channel_avatar_url: Optional[str] = None
    group_name: Optional[str] = None
    group_names: Optional[List[str]] = None


class RivalChannelOut(BaseModel):
    id: int
    channel_id: str
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None
    channel_avatar_url: Optional[str] = None
    group_name: Optional[str] = None
    group_names: Optional[List[str]] = None

    class Config:
        from_attributes = True
