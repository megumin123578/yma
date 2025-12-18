from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from python_backend.api.auth.database import get_db
from python_backend.api.auth.models import User
from python_backend.api.auth.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
)
from python_backend.api.auth.schemas import (
    UserCreate,
    UserLogin,
    ChangePassword,
    TokenWithUser,
)
from python_backend.api.auth.auth_utils import get_current_user

router = APIRouter(
    prefix="/api/auth",
    tags=["Auth"]
)

@router.post("/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    print("REGISTER DATA:", data)

    user = db.query(User).filter(User.username == data.username).first()
    if user:
        return {
            "success": False,
            "message": "User already existed!!!"
        }

    new_user = User(
        username=data.username,
        password=hash_password(data.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "success": True,
        "message": "Register success"
    }



@router.post("/login", response_model=TokenWithUser)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.username})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user, 
    }
    
@router.post("/change-password")
def change_password(
    data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password = hash_password(data.new_password)

    db.commit()
    db.refresh(current_user)

    return {"message": "Password changed successfully"}

