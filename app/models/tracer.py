from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Tracer(BaseModel):
    __tablename__ = "tracers"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True, comment="所属院区ID")
    code = Column(String(50), nullable=False, comment="药物编码")
    name = Column(String(100), nullable=False, comment="药物名称")
    name_en = Column(String(100), comment="英文名称")
    generic_name = Column(String(100), comment="通用名")

    tracer_type = Column(String(20), default="fdg", comment="示踪剂类型: fdg/fdg_dopa/psma/other")
    half_life_minutes = Column(Float, default=110, comment="半衰期(分钟)")
    default_dose_mbq = Column(Float, default=370, comment="标准剂量(MBq)")
    min_dose_mbq = Column(Float, default=185, comment="最小剂量(MBq)")
    max_dose_mbq = Column(Float, default=740, comment="最大剂量(MBq)")
    dose_per_kg_mbq = Column(Float, default=5.18, comment="每公斤体重剂量(MBq/kg)")
    unit = Column(String(20), default="MBq", comment="剂量单位")
    cost_per_mbq = Column(Float, default=0.5, comment="每MBq成本(元)")

    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, comment="备注")

    hospital = relationship("Hospital", back_populates="tracers")
    batches = relationship("TracerBatch", back_populates="tracer")
    usages = relationship("TracerUsage", back_populates="tracer")

    def __repr__(self):
        return f"<Tracer(id={self.id}, code='{self.code}', name='{self.name}')>"


class TracerBatch(BaseModel):
    __tablename__ = "tracer_batches"

    tracer_id = Column(Integer, ForeignKey("tracers.id"), nullable=False, comment="示踪剂ID")
    batch_no = Column(String(50), nullable=False, comment="批次号")

    total_activity_mbq = Column(Float, nullable=False, comment="总活度(MBq)")
    calibration_activity = Column(Float, nullable=False, comment="刻度活度(MBq)")
    calibration_time = Column(DateTime, nullable=False, comment="刻度时间")

    production_time = Column(DateTime, nullable=False, comment="生产时间")
    expiry_time = Column(DateTime, nullable=False, comment="过期时间")
    arrival_time = Column(DateTime, comment="到货时间")

    status = Column(String(20), default="pending", comment="状态: pending/in_transit/available/used/expired")
    used_activity_mbq = Column(Float, default=0, comment="已使用活度(MBq)")
    wasted_activity_mbq = Column(Float, default=0, comment="浪费活度(MBq)")

    supplier = Column(String(100), comment="供应商")
    lot_number = Column(String(50), comment="批号")

    tracer = relationship("Tracer", back_populates="batches")
    usages = relationship("TracerUsage", back_populates="batch")

    @property
    def remaining_activity(self) -> float:
        """剩余活度 = 总活度 - 已使用 - 已浪费"""
        return self.total_activity_mbq - (self.used_activity_mbq or 0) - (self.wasted_activity_mbq or 0)

    def is_expired(self) -> bool:
        """是否已过期"""
        from datetime import datetime
        return self.expiry_time and self.expiry_time < datetime.utcnow()

    def __repr__(self):
        return f"<TracerBatch(id={self.id}, batch_no='{self.batch_no}', status='{self.status}')>"


class TracerUsage(BaseModel):
    __tablename__ = "tracer_usages"

    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, comment="预约ID")
    tracer_id = Column(Integer, ForeignKey("tracers.id"), nullable=False, comment="示踪剂ID")
    batch_id = Column(Integer, ForeignKey("tracer_batches.id"), nullable=False, comment="批次ID")

    dose_mbq = Column(Float, nullable=False, comment="注射剂量(MBq)")
    injection_time = Column(DateTime, comment="注射时间")
    remaining_activity = Column(Float, comment="剩余活度")
    waste_activity = Column(Float, default=0, comment="浪费活度")

    injection_site = Column(String(50), comment="注射部位")
    vein_access = Column(String(50), comment="静脉通路")

    administered_by = Column(String(50), comment="注射人员")
    notes = Column(Text, comment="备注")

    tracer = relationship("Tracer", back_populates="usages")
    batch = relationship("TracerBatch", back_populates="usages")
    appointment = relationship("Appointment", back_populates="tracer_usages")

    def __repr__(self):
        return f"<TracerUsage(id={self.id}, dose={self.dose_mbq}MBq)>"
