from sqlalchemy import Column, Integer, String
from python_backend.api.auth.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)