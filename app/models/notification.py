from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    appointment_id = Column(Integer, ForeignKey("appointments.id"), comment="预约ID")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), comment="院区ID")
    user_id = Column(Integer, ForeignKey("users.id"), comment="接收人ID")

    notification_type = Column(String(50), nullable=False, comment="通知类型: receipt/reschedule/preparation/alert/cancel")
    notification_subtype = Column(String(50), comment="子类型")
    title = Column(String(200), nullable=False, comment="通知标题")

    content = Column(Text, nullable=False, comment="通知内容")
    template_id = Column(String(50), comment="模板ID")
    template_data = Column(Text, comment="模板数据(JSON)")

    recipient_type = Column(String(20), default="patient", comment="接收方类型: patient/hospital/staff/dispatcher")
    recipient_name = Column(String(100), comment="接收人姓名")
    recipient_phone = Column(String(20), comment="接收人电话")
    recipient_email = Column(String(100), comment="接收人邮箱")

    channel = Column(String(20), default="system", comment="发送渠道: system/sms/email/app")
    priority = Column(String(20), default="normal", comment="优先级: low/normal/high/urgent")

    status = Column(String(20), default="pending", comment="状态: pending/sent/delivered/failed/read")
    sent_at = Column(DateTime, comment="发送时间")
    delivered_at = Column(DateTime, comment="送达时间")
    read_at = Column(DateTime, comment="阅读时间")

    failure_reason = Column(String(255), comment="失败原因")
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")

    generated_by = Column(String(50), comment="生成人")
    generated_at = Column(DateTime, default=datetime.utcnow, comment="生成时间")

    notes = Column(Text, comment="备注")

    appointment = relationship("Appointment", back_populates="notifications")
    hospital = relationship("Hospital")
    user = relationship("User")

    def __repr__(self):
        return f"<Notification(id={self.id}, type='{self.notification_type}', status='{self.status}')>"
