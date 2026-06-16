from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class UserBase(BaseModel):
    username: str = Field(..., max_length=50, description="用户名")
    real_name: str = Field(..., max_length=50, description="真实姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="联系电话")
    email: Optional[EmailStr] = Field(default=None, max_length=100, description="邮箱")
    role: str = Field(..., max_length=20, description="角色")
    hospital_id: Optional[int] = Field(default=None, description="所属院区ID")
    is_active: bool = Field(default=True, description="是否启用")
    is_admin: bool = Field(default=False, description="是否管理员")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class UserUpdate(BaseModel):
    real_name: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=20)
    hospital_id: Optional[int] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    is_admin: Optional[bool] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class Token(BaseModel):
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    user: UserResponse = Field(..., description="用户信息")


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[str] = None
    hospital_id: Optional[int] = None
