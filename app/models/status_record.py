from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class StatusRecord(BaseModel):
    __tablename__ = "status_records"

    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, comment="预约ID")
    status_type = Column(String(20), nullable=False, comment="状态类型: checkin/injection/scanning/completed/cancelled")
    status_code = Column(String(50), comment="状态编码")
    status_name = Column(String(100), comment="状态名称")

    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="发生时间")
    recorded_by = Column(String(50), comment="记录人")
    recorded_by_id = Column(Integer, ForeignKey("users.id"), comment="记录人ID")

    location = Column(String(100), comment="地点")
    notes = Column(Text, comment="备注")

    blood_glucose = Column(Float, comment="血糖值")
    blood_pressure_systolic = Column(Integer, comment="收缩压")
    blood_pressure_diastolic = Column(Integer, comment="舒张压")
    heart_rate = Column(Integer, comment="心率")
    spo2 = Column(Float, comment="血氧饱和度")

    tracer_batch_no = Column(String(50), comment="示踪剂批次号")
    tracer_dose_mbq = Column(Float, comment="注射剂量(MBq)")
    tracer_injection_site = Column(String(50), comment="注射部位")

    equipment_code = Column(String(50), comment="设备编码")
    scan_protocol = Column(String(100), comment="扫描协议")
    scan_duration_seconds = Column(Integer, comment="扫描时长(秒)")

    appointment = relationship("Appointment", back_populates="status_records")
    recorder = relationship("User", foreign_keys=[recorded_by_id])

    def __repr__(self):
        return f"<StatusRecord(id={self.id}, appointment_id={self.appointment_id}, type='{self.status_type}')>"
