from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User
from python_backend.api.auth.schemas import UserCreate, UserLogin, Token
from python_backend.api.auth.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)

@router.post("/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        print("REGISTER DATA:", data)

        user = db.query(User).filter(User.username == data.username).first()
        if user:
            raise HTTPException(status_code=400, detail="User exists")

        new_user = User(
            username=data.username,
            password=hash_password(data.password)
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {"message": "Register success"}

    except Exception as e:
        print("REGISTER ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer"
    }
