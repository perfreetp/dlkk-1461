from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Float, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Appointment(BaseModel):
    __tablename__ = "appointments"

    appointment_no = Column(String(50), unique=True, index=True, nullable=False, comment="预约编号")

    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, comment="患者ID")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="院区ID")
    equipment_id = Column(Integer, ForeignKey("equipment.id"), comment="设备ID")
    creator_id = Column(Integer, ForeignKey("users.id"), comment="创建人ID")

    referring_department = Column(String(100), comment="申请科室")
    referring_doctor = Column(String(50), comment="申请医生")
    clinical_diagnosis = Column(String(255), comment="临床诊断")

    exam_purpose = Column(String(50), nullable=False, comment="检查目的: initial_staging/restaging/therapy_response/surveillance/other")
    urgency_level = Column(String(20), default="normal", comment="紧急程度: emergency/urgent/normal/elective")

    is_inpatient = Column(Boolean, default=False, comment="是否住院患者")
    inpatient_no = Column(String(50), comment="住院号")
    ward = Column(String(50), comment="病区")
    bed_no = Column(String(20), comment="床号")

    needs_anesthesia = Column(Boolean, default=False, comment="是否需要麻醉")
    anesthesia_type = Column(String(50), comment="麻醉方式")
    needs_escort = Column(Boolean, default=False, comment="是否需要陪同")

    tracer_type = Column(String(20), default="fdg", comment="示踪剂类型")
    tracer_dose_mbq = Column(Float, comment="示踪剂剂量(MBq)")
    tracer_batch_id = Column(Integer, comment="示踪剂批次ID")

    appointment_date = Column(Date, nullable=False, comment="预约日期")
    checkin_time = Column(DateTime, comment="签到时间")
    injection_time = Column(DateTime, comment="注射时间")
    scan_start_time = Column(DateTime, comment="扫描开始时间")
    scan_end_time = Column(DateTime, comment="扫描结束时间")
    completion_time = Column(DateTime, comment="完成时间")

    queue_number = Column(Integer, comment="队列号")
    time_slot = Column(String(20), comment="时间段: 上午/下午/具体时段")
    estimated_duration_minutes = Column(Integer, default=45, comment="预计时长(分钟)")

    status = Column(String(20), default="pending", comment="状态: pending/confirmed/checked_in/injected/scanning/completed/cancelled/no_show")
    sub_status = Column(String(50), comment="子状态")
    status_changed_at = Column(DateTime, default=datetime.utcnow, comment="状态变更时间")

    is_referral = Column(Boolean, default=False, comment="是否转诊")
    referral_source = Column(String(100), comment="转诊来源")
    referral_reason = Column(String(255), comment="转诊原因")

    cancellation_reason = Column(String(255), comment="取消原因")
    cancelled_by = Column(String(50), comment="取消人")
    cancelled_at = Column(DateTime, comment="取消时间")

    is_plus_sign = Column(Boolean, default=False, comment="是否加号")
    plus_sign_reason = Column(String(255), comment="加号原因")

    fasting_hours = Column(Integer, default=6, comment="禁食时间(小时)")
    blood_glucose = Column(Float, comment="血糖值")
    hydration_status = Column(String(50), comment="水化情况")

    preparation_notes = Column(Text, comment="准备事项")
    exam_notes = Column(Text, comment="检查备注")
    clinical_notes = Column(Text, comment="临床备注")

    workflow_category = Column(String(50), comment="工作流分类: 肿瘤评估/神经/心血管/其他")
    priority_score = Column(Integer, default=50, comment="优先级评分 0-100")

    patient = relationship("Patient", back_populates="appointments")
    hospital = relationship("Hospital", back_populates="appointments")
    equipment = relationship("Equipment", back_populates="appointments")
    creator = relationship("User", back_populates="created_appointments", foreign_keys=[creator_id])
    status_records = relationship("StatusRecord", back_populates="appointment", order_by="StatusRecord.occurred_at")
    tracer_usages = relationship("TracerUsage", back_populates="appointment")
    notifications = relationship("Notification", back_populates="appointment")
    referral = relationship("Referral", back_populates="appointment", uselist=False)

    def __repr__(self):
        return f"<Appointment(id={self.id}, no='{self.appointment_no}', status='{self.status}')>"
