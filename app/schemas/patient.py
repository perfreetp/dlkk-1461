from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class PatientBase(BaseModel):
    medical_record_no: Optional[str] = Field(default=None, max_length=50, description="病历号")
    id_card_no: Optional[str] = Field(default=None, max_length=20, description="身份证号")
    name: str = Field(..., max_length=50, description="姓名")
    gender: str = Field(..., max_length=10, description="性别")
    birth_date: Optional[date] = Field(default=None, description="出生日期")
    age: Optional[int] = Field(default=None, ge=0, description="年龄")
    phone: Optional[str] = Field(default=None, max_length=20, description="联系电话")
    alternate_phone: Optional[str] = Field(default=None, max_length=20, description="备用电话")
    address: Optional[str] = Field(default=None, max_length=255, description="住址")
    city: Optional[str] = Field(default=None, max_length=50, description="所在城市")
    district: Optional[str] = Field(default=None, max_length=50, description="所在区县")
    weight_kg: Optional[int] = Field(default=None, ge=0, description="体重(kg)")
    height_cm: Optional[int] = Field(default=None, ge=0, description="身高(cm)")
    blood_type: Optional[str] = Field(default=None, max_length=5, description="血型")
    is_inpatient: bool = Field(default=False, description="是否住院")
    inpatient_no: Optional[str] = Field(default=None, max_length=50, description="住院号")
    ward: Optional[str] = Field(default=None, max_length=50, description="病区")
    bed_no: Optional[str] = Field(default=None, max_length=20, description="床号")
    diabetes_type: Optional[str] = Field(default=None, max_length=20, description="糖尿病类型")
    has_allergy: bool = Field(default=False, description="有无过敏史")
    allergy_details: Optional[str] = Field(default=None, max_length=255, description="过敏史详情")
    is_ambulatory: bool = Field(default=True, description="是否可自行活动")
    needs_escort: bool = Field(default=False, description="是否需要陪同")
    needs_anesthesia: bool = Field(default=False, description="是否需要麻醉")
    blood_glucose: Optional[float] = Field(default=None, description="血糖值")
    creatinine: Optional[float] = Field(default=None, description="肌酐值")
    egfr: Optional[float] = Field(default=None, description="eGFR")
    notes: Optional[str] = Field(default=None, description="备注")


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[str] = Field(default=None, max_length=10)
    birth_date: Optional[date] = Field(default=None)
    age: Optional[int] = Field(default=None, ge=0)
    phone: Optional[str] = Field(default=None, max_length=20)
    alternate_phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=50)
    district: Optional[str] = Field(default=None, max_length=50)
    weight_kg: Optional[int] = Field(default=None, ge=0)
    height_cm: Optional[int] = Field(default=None, ge=0)
    is_inpatient: Optional[bool] = Field(default=None)
    inpatient_no: Optional[str] = Field(default=None, max_length=50)
    ward: Optional[str] = Field(default=None, max_length=50)
    bed_no: Optional[str] = Field(default=None, max_length=20)
    diabetes_type: Optional[str] = Field(default=None, max_length=20)
    has_allergy: Optional[bool] = Field(default=None)
    allergy_details: Optional[str] = Field(default=None, max_length=255)
    is_ambulatory: Optional[bool] = Field(default=None)
    needs_escort: Optional[bool] = Field(default=None)
    needs_anesthesia: Optional[bool] = Field(default=None)
    blood_glucose: Optional[float] = Field(default=None)
    creatinine: Optional[float] = Field(default=None)
    egfr: Optional[float] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None)


class PatientSimple(BaseModel):
    id: int
    medical_record_no: Optional[str]
    name: str
    gender: str
    age: Optional[int]
    phone: Optional[str]
    is_inpatient: bool
    status: str

    class Config:
        from_attributes = True


class PatientResponse(PatientBase):
    id: int
    consecutive_no_show: int
    total_appointments: int
    total_completed: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
