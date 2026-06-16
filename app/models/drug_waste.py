from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Float, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class DrugWasteRecord(BaseModel):
    __tablename__ = "drug_waste_records"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="院区ID")
    tracer_id = Column(Integer, ForeignKey("tracers.id"), nullable=False, comment="示踪剂ID")
    batch_id = Column(Integer, ForeignKey("tracer_batches.id"), nullable=False, comment="批次ID")

    waste_date = Column(Date, nullable=False, comment="浪费日期")
    waste_type = Column(String(50), nullable=False, comment="浪费类型: expired/patient_no_show/dose_adjustment/quality_issue/other")

    total_activity_mbq = Column(Float, nullable=False, comment="总活度(MBq)")
    wasted_activity_mbq = Column(Float, nullable=False, comment="浪费活度(MBq)")
    used_activity_mbq = Column(Float, default=0, comment="已使用活度(MBq)")

    waste_ratio = Column(Float, comment="浪费比例")
    estimated_cost = Column(Float, comment="预估成本")

    reason = Column(String(255), comment="浪费原因")
    detailed_reason = Column(Text, comment="详细原因")
    contributing_factors = Column(Text, comment="影响因素(JSON)")

    appointment_count = Column(Integer, default=0, comment="关联预约数")
    no_show_count = Column(Integer, default=0, comment="爽约数")
    cancellation_count = Column(Integer, default=0, comment="取消数")

    reported_by = Column(String(50), comment="上报人")
    reviewed_by = Column(String(50), comment="审核人")
    reviewed_at = Column(DateTime, comment="审核时间")

    prevention_measures = Column(Text, comment="预防措施")
    corrective_action = Column(Text, comment="纠正措施")
    action_completed = Column(Boolean, default=False, comment="措施是否完成")

    notes = Column(Text, comment="备注")

    hospital = relationship("Hospital")
    tracer = relationship("Tracer")
    batch = relationship("TracerBatch")

    def __repr__(self):
        return f"<DrugWasteRecord(id={self.id}, date='{self.waste_date}', ratio={self.waste_ratio:.2%})>"
