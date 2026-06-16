from sqlalchemy import Column, String, Boolean, Integer, Float, Text, Time
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Hospital(BaseModel):
    __tablename__ = "hospitals"

    code = Column(String(20), unique=True, index=True, nullable=False, comment="院区编码")
    name = Column(String(100), nullable=False, comment="院区名称")
    short_name = Column(String(50), comment="院区简称")
    address = Column(String(255), comment="地址")
    city = Column(String(50), comment="城市")
    district = Column(String(50), comment="行政区")

    longitude = Column(Float, comment="经度")
    latitude = Column(Float, comment="纬度")

    contact_person = Column(String(50), comment="联系人")
    contact_phone = Column(String(20), comment="联系电话")
    phone = Column(String(20), comment="联系电话")

    daily_capacity = Column(Integer, default=20, comment="日检查容量")
    morning_capacity = Column(Integer, default=10, comment="上午容量")
    afternoon_capacity = Column(Integer, default=10, comment="下午容量")
    operating_hours_start = Column(String(10), default="08:00", comment="运营开始时间")
    operating_hours_end = Column(String(10), default="17:00", comment="运营结束时间")
    slot_duration_minutes = Column(Integer, default=30, comment="时段时长(分钟)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_referral_accepting = Column(Boolean, default=True, comment="是否接受转诊")

    description = Column(Text, comment="备注说明")

    staff = relationship("User", back_populates="hospital")
    equipment = relationship("Equipment", back_populates="hospital")
    appointments = relationship("Appointment", back_populates="hospital")
    tracers = relationship("Tracer", back_populates="hospital")
    schedules = relationship("ScheduleTemplate", back_populates="hospital")
    support_plans = relationship("SupportPlan", back_populates="hospital", foreign_keys="SupportPlan.hospital_id")

    def __repr__(self):
        return f"<Hospital(id={self.id}, code='{self.code}', name='{self.name}')>"
