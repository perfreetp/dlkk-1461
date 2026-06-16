from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.schemas.user import UserLogin, Token, UserCreate, UserResponse
from app.schemas.common import ApiResponse
from app.utils.auth import authenticate_user, create_access_token, get_password_hash, get_current_active_user
from app.models import User
from app.exceptions import AuthenticationError

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=ApiResponse[Token])
def login(form_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise AuthenticationError(detail="用户名或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
            "hospital_id": user.hospital_id,
            "is_admin": user.is_admin
        },
        expires_delta=access_token_expires
    )

    return ApiResponse(
        data=Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user)
        ),
        message="登录成功"
    )


@router.post("/register", response_model=ApiResponse[UserResponse])
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    hashed_password = get_password_hash(user_data.password)
    user = User(
        **user_data.model_dump(exclude={"password"}),
        password_hash=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return ApiResponse(data=UserResponse.model_validate(user), message="注册成功")


@router.get("/me", response_model=ApiResponse[UserResponse])
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return ApiResponse(data=UserResponse.model_validate(current_user))


@router.post("/logout", response_model=ApiResponse)
def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出"""
    return ApiResponse(message="登出成功")
