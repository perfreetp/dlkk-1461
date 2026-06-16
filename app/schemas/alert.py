from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class AlertType(str, Enum):
    CONSECUTIVE_NO_SHOW = "consecutive_no_show"
    CHECKIN_TIMEOUT = "checkin_timeout"
    DRUG_WASTE_HIGH = "drug_waste_high"
    EQUIPMENT_FAILURE = "equipment_failure"
    DRUG_DELAY = "drug_delay"
    QUEUE_OVERLOAD = "queue_overload"
    REFERRAL_DELAY = "referral_delay"
    ANESTHESIA_CONFLICT = "anesthesia_conflict"
    BLOOD_GLUCOSE_ABNORMAL = "blood_glucose_abnormal"


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    alert_code: Optional[str]
    severity: AlertSeverity
    hospital_id: Optional[int]
    patient_id: Optional[int]
    appointment_id: Optional[int]
    equipment_id: Optional[int]
    tracer_batch_id: Optional[int]
    title: str
    message: str
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]
    unit: Optional[str]
    status: AlertStatus
    status_changed_at: datetime
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    escalation_level: int
    escalation_notified: bool
    generated_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(..., max_length=50, description="确认人")
    notes: Optional[str] = Field(default=None, description="备注")


class AlertResolveRequest(BaseModel):
    resolved_by: str = Field(..., max_length=50, description="处理人")
    resolution_notes: str = Field(..., description="处理说明")
    auto_resolve: bool = Field(default=False, description="是否自动解除")


class AlertQueryParams(BaseModel):
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    alert_type: Optional[AlertType] = Field(default=None, description="预警类型")
    severity: Optional[AlertSeverity] = Field(default=None, description="严重程度")
    status: Optional[AlertStatus] = Field(default=None, description="状态")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    patient_id: Optional[int] = Field(default=None, description="患者ID")
    equipment_id: Optional[int] = Field(default=None, description="设备ID")
    escalation_level: Optional[int] = Field(default=None, ge=1, le=3, description="升级级别")
    only_active: bool = Field(default=False, description="仅显示未处理")
