from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Float, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Referral(BaseModel):
    __tablename__ = "referrals"

    referral_no = Column(String(50), unique=True, index=True, nullable=False, comment="转诊编号")
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, comment="预约ID")
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, comment="患者ID")

    source_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="转出院区ID")
    target_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="转入院区ID")

    referral_reason = Column(String(255), comment="转诊原因")
    referral_type = Column(String(20), default="auto", comment="转诊类型: auto/manual/emergency")

    original_appointment_date = Column(Date, comment="原预约日期")
    original_hospital_id = Column(Integer, comment="原预约院区ID")

    distance_km = Column(Float, comment="距离(公里)")
    travel_time_minutes = Column(Integer, comment="预计行程时间(分钟)")
    traffic_condition = Column(String(50), comment="交通状况")

    proposed_date = Column(Date, comment="建议日期")
    proposed_time_slot = Column(String(20), comment="建议时段")
    alternative_dates = Column(Text, comment="备选日期(JSON)")

    status = Column(String(20), default="proposed", comment="状态: proposed/accepted/declined/completed/cancelled")
    status_changed_at = Column(DateTime, default=datetime.utcnow, comment="状态变更时间")

    accepted_by = Column(String(50), comment="确认人")
    accepted_at = Column(DateTime, comment="确认时间")
    declined_reason = Column(String(255), comment="拒绝原因")
    declined_by = Column(String(50), comment="拒绝人")

    patient_preference = Column(String(255), comment="患者偏好")
    clinical_notes = Column(Text, comment="临床备注")
    coordination_notes = Column(Text, comment="协调备注")

    is_completed = Column(Boolean, default=False, comment="是否完成")
    completed_at = Column(DateTime, comment="完成时间")

    auto_assigned = Column(Boolean, default=True, comment="是否系统自动分配")
    assignment_score = Column(Integer, comment="分配评分")
    assignment_reason = Column(String(255), comment="分配理由")

    appointment = relationship("Appointment", back_populates="referral")
    patient = relationship("Patient", back_populates="referrals")
    source_hospital = relationship("Hospital", foreign_keys=[source_hospital_id])
    target_hospital = relationship("Hospital", foreign_keys=[target_hospital_id])

    def __repr__(self):
        return f"<Referral(id={self.id}, no='{self.referral_no}', status='{self.status}')>"
