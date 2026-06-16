from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Alert(BaseModel):
    __tablename__ = "alerts"

    alert_type = Column(String(50), nullable=False, comment="预警类型: no_show_timeout/drug_waste/equipment_failure/consecutive_no_show")
    alert_code = Column(String(50), comment="预警编码")
    severity = Column(String(20), default="warning", comment="严重程度: info/warning/error/critical")

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), comment="关联院区ID")
    patient_id = Column(Integer, ForeignKey("patients.id"), comment="关联患者ID")
    appointment_id = Column(Integer, ForeignKey("appointments.id"), comment="关联预约ID")
    equipment_id = Column(Integer, ForeignKey("equipment.id"), comment="关联设备ID")
    tracer_batch_id = Column(Integer, comment="关联药物批次ID")

    title = Column(String(200), nullable=False, comment="预警标题")
    message = Column(Text, nullable=False, comment="预警详情")

    metric_name = Column(String(50), comment="指标名称")
    metric_value = Column(Float, comment="指标值")
    threshold_value = Column(Float, comment="阈值")
    unit = Column(String(20), comment="单位")

    status = Column(String(20), default="open", comment="状态: open/acknowledged/in_progress/resolved/ignored")
    status_changed_at = Column(DateTime, default=datetime.utcnow, comment="状态变更时间")

    acknowledged_by = Column(String(50), comment="确认人")
    acknowledged_at = Column(DateTime, comment="确认时间")
    resolved_by = Column(String(50), comment="处理人")
    resolved_at = Column(DateTime, comment="处理时间")
    resolution_notes = Column(Text, comment="处理说明")

    auto_resolve = Column(Boolean, default=False, comment="是否自动解除")
    auto_resolve_condition = Column(String(255), comment="自动解除条件")
    escalation_level = Column(Integer, default=1, comment="升级级别 1-3")
    escalation_notified = Column(Boolean, default=False, comment="是否已升级通知")

    generated_at = Column(DateTime, default=datetime.utcnow, comment="生成时间")
    notes = Column(Text, comment="备注")

    hospital = relationship("Hospital")
    patient = relationship("Patient")
    appointment = relationship("Appointment")
    equipment = relationship("Equipment")

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity}', status='{self.status}')>"
