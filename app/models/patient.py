from sqlalchemy import Column, String, Boolean, Integer, Date, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Patient(BaseModel):
    __tablename__ = "patients"

    medical_record_no = Column(String(50), unique=True, index=True, comment="病历号")
    id_card = Column(String(20), index=True, comment="身份证号")
    id_card_no = Column(String(20), index=True, comment="身份证号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(String(10), nullable=False, comment="性别: male/female/other")
    birth_date = Column(Date, comment="出生日期")
    age = Column(Integer, comment="年龄")

    phone = Column(String(20), comment="联系电话")
    alternate_phone = Column(String(20), comment="备用电话")
    address = Column(String(255), comment="住址")
    city = Column(String(50), comment="所在城市")
    district = Column(String(50), comment="所在区县")

    weight_kg = Column(Integer, comment="体重(kg)")
    height_cm = Column(Integer, comment="身高(cm)")
    blood_type = Column(String(5), comment="血型")

    is_inpatient = Column(Boolean, default=False, comment="是否住院")
    inpatient_no = Column(String(50), comment="住院号")
    ward = Column(String(50), comment="病区")
    bed_no = Column(String(20), comment="床号")

    has_diabetes = Column(Boolean, default=False, comment="有无糖尿病")
    diabetes_type = Column(String(20), comment="糖尿病类型")
    has_allergy = Column(Boolean, default=False, comment="有无过敏史")
    has_allergies = Column(Boolean, default=False, comment="有无过敏史")
    allergy_details = Column(String(255), comment="过敏史详情")

    is_ambulatory = Column(Boolean, default=True, comment="是否可自行活动")
    needs_escort = Column(Boolean, default=False, comment="是否需要陪同")
    needs_anesthesia = Column(Boolean, default=False, comment="是否需要麻醉")

    blood_glucose = Column(Float, comment="血糖值")
    creatinine = Column(Float, comment="肌酐值")
    egfr = Column(Float, comment="eGFR")

    consecutive_no_show = Column(Integer, default=0, comment="连续爽约次数")
    total_appointments = Column(Integer, default=0, comment="总预约次数")
    total_completed = Column(Integer, default=0, comment="完成次数")

    status = Column(String(20), default="normal", comment="状态: normal/blocked")
    is_active = Column(Boolean, default=True, comment="是否启用")
    notes = Column(Text, comment="备注")

    appointments = relationship("Appointment", back_populates="patient")
    referrals = relationship("Referral", back_populates="patient")

    def __repr__(self):
        return f"<Patient(id={self.id}, name='{self.name}', mr_no='{self.medical_record_no}')>"
