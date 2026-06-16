from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class HospitalBase(BaseModel):
    code: str = Field(..., max_length=20, description="院区编码")
    name: str = Field(..., max_length=100, description="院区名称")
    short_name: Optional[str] = Field(default=None, max_length=50, description="院区简称")
    address: Optional[str] = Field(default=None, max_length=255, description="地址")
    city: Optional[str] = Field(default=None, max_length=50, description="城市")
    district: Optional[str] = Field(default=None, max_length=50, description="行政区")
    longitude: Optional[float] = Field(default=None, description="经度")
    latitude: Optional[float] = Field(default=None, description="纬度")
    contact_person: Optional[str] = Field(default=None, max_length=50, description="联系人")
    contact_phone: Optional[str] = Field(default=None, max_length=20, description="联系电话")
    daily_capacity: int = Field(default=20, ge=0, description="日检查容量")
    is_active: bool = Field(default=True, description="是否启用")
    is_referral_accepting: bool = Field(default=True, description="是否接受转诊")
    description: Optional[str] = Field(default=None, description="备注说明")


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    short_name: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=50)
    district: Optional[str] = Field(default=None, max_length=50)
    longitude: Optional[float] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    contact_person: Optional[str] = Field(default=None, max_length=50)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    daily_capacity: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    is_referral_accepting: Optional[bool] = Field(default=None)
    description: Optional[str] = Field(default=None)


class HospitalSimple(BaseModel):
    id: int
    code: str
    name: str
    short_name: Optional[str]
    city: Optional[str]
    district: Optional[str]
    daily_capacity: int
    is_active: bool

    class Config:
        from_attributes = True


class HospitalResponse(HospitalBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
