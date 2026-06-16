from typing import Optional, List
from datetime import date, datetime, time
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ExamPurpose(str, Enum):
    INITIAL_STAGING = "initial_staging"
    RESTAGING = "restaging"
    THERAPY_RESPONSE = "therapy_response"
    SURVEILLANCE = "surveillance"
    OTHER = "other"


class UrgencyLevel(str, Enum):
    EMERGENCY = "emergency"
    URGENT = "urgent"
    NORMAL = "normal"
    ELECTIVE = "elective"


class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    INJECTED = "injected"
    SCANNING = "scanning"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentBase(BaseModel):
    patient_id: int = Field(..., description="患者ID")
    hospital_id: int = Field(..., description="院区ID")
    equipment_id: Optional[int] = Field(default=None, description="设备ID")

    referring_department: Optional[str] = Field(default=None, max_length=100, description="申请科室")
    referring_doctor: Optional[str] = Field(default=None, max_length=50, description="申请医生")
    clinical_diagnosis: Optional[str] = Field(default=None, max_length=255, description="临床诊断")

    exam_purpose: ExamPurpose = Field(..., description="检查目的")
    urgency_level: UrgencyLevel = Field(default=UrgencyLevel.NORMAL, description="紧急程度")

    is_inpatient: bool = Field(default=False, description="是否住院患者")
    inpatient_no: Optional[str] = Field(default=None, max_length=50, description="住院号")
    ward: Optional[str] = Field(default=None, max_length=50, description="病区")
    bed_no: Optional[str] = Field(default=None, max_length=20, description="床号")

    needs_anesthesia: bool = Field(default=False, description="是否需要麻醉")
    anesthesia_type: Optional[str] = Field(default=None, max_length=50, description="麻醉方式")
    needs_escort: bool = Field(default=False, description="是否需要陪同")

    tracer_type: str = Field(default="fdg", max_length=20, description="示踪剂类型")
    tracer_dose_mbq: Optional[float] = Field(default=None, description="示踪剂剂量(MBq)")

    appointment_date: date = Field(..., description="预约日期")
    time_slot: Optional[str] = Field(default=None, max_length=20, description="时间段")
    estimated_duration_minutes: int = Field(default=45, ge=15, description="预计时长(分钟)")

    is_referral: bool = Field(default=False, description="是否转诊")
    referral_source: Optional[str] = Field(default=None, max_length=100, description="转诊来源")
    referral_reason: Optional[str] = Field(default=None, max_length=255, description="转诊原因")

    is_plus_sign: bool = Field(default=False, description="是否加号")
    plus_sign_reason: Optional[str] = Field(default=None, max_length=255, description="加号原因")

    fasting_hours: int = Field(default=6, ge=0, description="禁食时间(小时)")
    preparation_notes: Optional[str] = Field(default=None, description="准备事项")
    exam_notes: Optional[str] = Field(default=None, description="检查备注")
    clinical_notes: Optional[str] = Field(default=None, description="临床备注")


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentBatchCreate(BaseModel):
    appointments: List[AppointmentCreate]
    auto_assign: bool = Field(default=True, description="是否自动分配资源")


class AppointmentUpdate(BaseModel):
    equipment_id: Optional[int] = Field(default=None)
    exam_purpose: Optional[ExamPurpose] = Field(default=None)
    urgency_level: Optional[UrgencyLevel] = Field(default=None)
    appointment_date: Optional[date] = Field(default=None)
    time_slot: Optional[str] = Field(default=None, max_length=20)
    queue_number: Optional[int] = Field(default=None)
    status: Optional[AppointmentStatus] = Field(default=None)
    preparation_notes: Optional[str] = Field(default=None)
    exam_notes: Optional[str] = Field(default=None)
    tracer_dose_mbq: Optional[float] = Field(default=None)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus = Field(..., description="新状态")
    reason: Optional[str] = Field(default=None, description="变更原因")
    operator: Optional[str] = Field(default=None, description="操作人")


class PlusSignRequest(BaseModel):
    patient_id: int = Field(..., description="患者ID")
    hospital_id: int = Field(..., description="院区ID")
    appointment_date: date = Field(..., description="预约日期")
    exam_purpose: ExamPurpose = Field(..., description="检查目的")
    urgency_level: UrgencyLevel = Field(default=UrgencyLevel.URGENT, description="紧急程度")
    reason: str = Field(..., max_length=255, description="加号原因")
    clinical_diagnosis: Optional[str] = Field(default=None, max_length=255)
    referring_department: Optional[str] = Field(default=None, max_length=100)


class AppointmentCategorizeResponse(BaseModel):
    category: str = Field(..., description="分类结果")
    priority_score: int = Field(..., description="优先级评分 0-100")
    recommended_queue: str = Field(..., description="推荐队列")
    workflow_category: str = Field(..., description="工作流分类")
    resource_requirements: dict = Field(..., description="资源需求")
    estimated_wait_time_minutes: int = Field(..., description="预计等待时间(分钟)")
    special_handling: List[str] = Field(default_factory=list, description="特殊处理要求")


class AppointmentQueryParams(BaseModel):
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    equipment_id: Optional[int] = Field(default=None, description="设备ID")
    patient_id: Optional[int] = Field(default=None, description="患者ID")
    status: Optional[AppointmentStatus] = Field(default=None, description="状态")
    urgency_level: Optional[UrgencyLevel] = Field(default=None, description="紧急程度")
    exam_purpose: Optional[ExamPurpose] = Field(default=None, description="检查目的")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    is_inpatient: Optional[bool] = Field(default=None, description="是否住院")
    needs_anesthesia: Optional[bool] = Field(default=None, description="是否需要麻醉")
    is_referral: Optional[bool] = Field(default=None, description="是否转诊")
    is_plus_sign: Optional[bool] = Field(default=None, description="是否加号")
    search_keyword: Optional[str] = Field(default=None, description="搜索关键词")


class AppointmentResponse(AppointmentBase):
    id: int
    appointment_no: str
    status: AppointmentStatus
    queue_number: Optional[int]
    priority_score: int
    workflow_category: Optional[str]

    checkin_time: Optional[datetime]
    injection_time: Optional[datetime]
    scan_start_time: Optional[datetime]
    scan_end_time: Optional[datetime]
    completion_time: Optional[datetime]

    cancellation_reason: Optional[str]
    cancelled_by: Optional[str]
    cancelled_at: Optional[datetime]

    blood_glucose: Optional[float]

    creator_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentListResponse(AppointmentResponse):
    patient_name: Optional[str] = Field(default=None, description="患者姓名")
    hospital_name: Optional[str] = Field(default=None, description="院区名称")
    equipment_name: Optional[str] = Field(default=None, description="设备名称")
