from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Date, Text, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class ScheduleTemplate(BaseModel):
    __tablename__ = "schedule_templates"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="院区ID")
    name = Column(String(100), nullable=False, comment="模板名称")
    template_name = Column(String(100), nullable=True, comment="模板名称")
    template_type = Column(String(20), default="normal", comment="模板类型: normal/holiday/special/weekday/weekend")

    effective_date = Column(Date, comment="生效日期")
    expiry_date = Column(Date, comment="失效日期")

    day_of_week = Column(Integer, comment="星期几 0-6, 空表示每天")
    is_weekday = Column(Boolean, comment="是否工作日")

    work_start_time = Column(String(10), default="08:00", comment="上班时间")
    work_end_time = Column(String(10), default="17:00", comment="下班时间")
    lunch_start_time = Column(String(10), default="12:00", comment="午休开始")
    lunch_end_time = Column(String(10), default="13:30", comment="午休结束")

    morning_start = Column(String(10), default="08:00", comment="上午开始时间")
    morning_end = Column(String(10), default="12:00", comment="上午结束时间")
    afternoon_start = Column(String(10), default="13:30", comment="下午开始时间")
    afternoon_end = Column(String(10), default="17:00", comment="下午结束时间")
    slots_per_hour = Column(Integer, default=2, comment="每小时时段数")

    daily_capacity = Column(Integer, default=20, comment="日检查容量")
    morning_capacity = Column(Integer, default=12, comment="上午容量")
    afternoon_capacity = Column(Integer, default=8, comment="下午容量")

    anesthesia_slots = Column(Integer, default=3, comment="麻醉时段数")
    inpatient_slots = Column(Integer, default=8, comment="住院患者时段数")
    emergency_slots = Column(Integer, default=2, comment="急诊预留时段数")

    is_active = Column(Boolean, default=True, comment="是否启用")
    notes = Column(Text, comment="备注")

    hospital = relationship("Hospital", back_populates="schedules")
    shifts = relationship("ShiftAssignment", back_populates="template")

    def __repr__(self):
        return f"<ScheduleTemplate(id={self.id}, name='{self.template_name}', type='{self.template_type}')>"


class ShiftAssignment(BaseModel):
    __tablename__ = "shift_assignments"

    template_id = Column(Integer, ForeignKey("schedule_templates.id"), comment="排班模板ID")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="院区ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="人员ID")

    shift_date = Column(Date, nullable=False, comment="排班日期")
    shift_type = Column(String(20), nullable=False, comment="班次: morning/afternoon/night")
    start_time = Column(String(10), comment="开始时间")
    end_time = Column(String(10), comment="结束时间")

    role = Column(String(50), comment="岗位: 技师/护士/医生/麻醉师")
    equipment_id = Column(Integer, ForeignKey("equipment.id"), comment="负责设备")

    is_active = Column(Boolean, default=True, comment="是否有效")
    swap_requested = Column(Boolean, default=False, comment="是否申请换班")
    swap_user_id = Column(Integer, comment="换班人员ID")

    notes = Column(Text, comment="备注")

    template = relationship("ScheduleTemplate", back_populates="shifts")
    user = relationship("User", foreign_keys=[user_id])
    equipment = relationship("Equipment")

    def __repr__(self):
        return f"<ShiftAssignment(id={self.id}, date='{self.shift_date}', type='{self.shift_type}')>"


class SupportPlan(BaseModel):
    __tablename__ = "support_plans"

    plan_name = Column(String(100), nullable=False, comment="方案名称")
    plan_type = Column(String(20), default="temporary", comment="方案类型: temporary/emergency/holiday")

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="目标院区ID")
    source_hospital_id = Column(Integer, ForeignKey("hospitals.id"), comment="支援来源院区ID")

    start_date = Column(Date, nullable=False, comment="开始日期")
    end_date = Column(Date, nullable=False, comment="结束日期")

    reason = Column(String(255), comment="支援原因")
    scope = Column(String(255), comment="支援范围")

    additional_capacity = Column(Integer, default=0, comment="额外增加容量")
    staff_count = Column(Integer, default=0, comment="支援人数")
    equipment_count = Column(Integer, default=0, comment="支援设备数")

    coordinator = Column(String(50), comment="协调人")
    coordinator_phone = Column(String(20), comment="协调人电话")

    status = Column(String(20), default="draft", comment="状态: draft/active/completed/cancelled")
    approved_by = Column(String(50), comment="审批人")
    approved_at = Column(DateTime, comment="审批时间")

    notes = Column(Text, comment="备注")

    hospital = relationship("Hospital", back_populates="support_plans", foreign_keys=[hospital_id])
    source_hospital = relationship("Hospital", foreign_keys=[source_hospital_id])

    def __repr__(self):
        return f"<SupportPlan(id={self.id}, name='{self.plan_name}', status='{self.status}')>"
