from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class NotificationType(str, Enum):
    RECEIPT = "receipt"
    RESCHEDULE = "reschedule"
    PREPARATION = "preparation"
    REMINDER = "reminder"
    ALERT = "alert"
    REPORT = "report"
    SYSTEM = "system"


class NotificationChannel(str, Enum):
    SYSTEM = "system"
    SMS = "sms"
    EMAIL = "email"
    WECHAT = "wechat"
    APP = "app"
    PHONE = "phone"


class NotificationBase(BaseModel):
    appointment_id: Optional[int] = Field(default=None, description="预约ID")
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    user_id: Optional[int] = Field(default=None, description="接收人ID")
    notification_type: str = Field(..., max_length=50, description="通知类型")
    notification_subtype: Optional[str] = Field(default=None, max_length=50, description="子类型")
    title: str = Field(..., max_length=200, description="通知标题")
    content: str = Field(..., description="通知内容")
    recipient_type: str = Field(default="patient", max_length=20, description="接收方类型")
    recipient_name: Optional[str] = Field(default=None, max_length=100, description="接收人姓名")
    recipient_phone: Optional[str] = Field(default=None, max_length=20, description="接收人电话")
    recipient_email: Optional[EmailStr] = Field(default=None, max_length=100, description="接收人邮箱")
    channel: str = Field(default="system", max_length=20, description="发送渠道")
    priority: str = Field(default="normal", max_length=20, description="优先级")
    template_id: Optional[str] = Field(default=None, max_length=50, description="模板ID")
    template_data: Optional[Dict[str, Any]] = Field(default=None, description="模板数据")


class NotificationCreate(NotificationBase):
    pass


class NotificationResponse(NotificationBase):
    id: int
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    failure_reason: Optional[str]
    retry_count: int
    generated_by: Optional[str]
    generated_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationSendRequest(BaseModel):
    notification_ids: Optional[list[int]] = Field(default=None, description="通知ID列表")
    channel: Optional[str] = Field(default=None, max_length=20, description="发送渠道")
    force_send: bool = Field(default=False, description="是否强制发送")


class ReceiptGenerateRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    receipt_type: str = Field(default="appointment", max_length=50, description="回执类型")
    include_preparation: bool = Field(default=True, description="是否包含准备事项")
    include_tracer_info: bool = Field(default=True, description="是否包含药物信息")
    language: str = Field(default="zh-CN", max_length=10, description="语言")
    format: str = Field(default="pdf", max_length=10, description="输出格式")


class RescheduleNotificationRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    new_date: str = Field(..., description="新日期")
    new_time: Optional[str] = Field(default=None, description="新时间")
    new_hospital_id: Optional[int] = Field(default=None, description="新院区ID")
    reason: str = Field(..., max_length=255, description="改期原因")
    notify_patient: bool = Field(default=True, description="是否通知患者")
    notify_hospital: bool = Field(default=True, description="是否通知院区")
    notify_department: bool = Field(default=False, description="是否通知科室")


class PreparationReminderRequest(BaseModel):
    appointment_id: Optional[int] = Field(default=None, description="预约ID")
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    reminder_type: str = Field(default="preparation", max_length=50, description="提醒类型")
    lead_time_hours: int = Field(default=24, ge=1, description="提前提醒小时数")
    include_tracer_info: bool = Field(default=True, description="是否包含药物信息")
    include_dietary_instructions: bool = Field(default=True, description="是否包含饮食指导")
    include_medication_instructions: bool = Field(default=True, description="是否包含用药指导")
    channel: Optional[NotificationChannel] = Field(default=None, description="发送渠道")
    language: str = Field(default="zh-CN", max_length=10, description="语言")


    class Config:
        from_attributes = True
