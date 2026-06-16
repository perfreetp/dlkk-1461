from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from pydantic import BaseModel, Field
from enum import Enum


class RescheduleReason(str, Enum):
    EQUIPMENT_DOWNTIME = "equipment_downtime"
    DRUG_DELAY = "drug_delay"
    EMERGENCY_PLUS = "emergency_plus"
    PATIENT_REQUEST = "patient_request"
    HOSPITAL_REQUEST = "hospital_request"
    WEATHER_ISSUE = "weather_issue"
    OTHER = "other"


class RescheduleStrategy(str, Enum):
    PRIORITY_FIRST = "priority_first"
    EARLIEST_FIRST = "earliest_first"
    MINIMIZE_IMPACT = "minimize_impact"
    MAINTAIN_ORDER = "maintain_order"
    NEAREST_HOSPITAL = "nearest_hospital"


class RescheduleRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    new_date: Optional[date] = Field(default=None, description="新日期")
    new_time_slot: Optional[str] = Field(default=None, description="新时段")
    new_hospital_id: Optional[int] = Field(default=None, description="新院区ID")
    new_equipment_id: Optional[int] = Field(default=None, description="新设备ID")
    reason: RescheduleReason = Field(..., description="改期原因")
    reason_detail: Optional[str] = Field(default=None, max_length=255, description="原因详情")
    notify_patient: bool = Field(default=True, description="是否通知患者")
    notify_hospital: bool = Field(default=True, description="是否通知院区")
    operator: Optional[str] = Field(default=None, description="操作人")
    notes: Optional[str] = Field(default=None, description="备注")


class RescheduleResult(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    appointment_no: str = Field(..., description="预约编号")
    patient_name: str = Field(..., description="患者姓名")
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    old_date: Optional[date] = Field(default=None, description="原日期")
    old_time_slot: Optional[str] = Field(default=None, description="原时段")
    old_hospital_id: Optional[int] = Field(default=None, description="原院区ID")
    new_date: Optional[date] = Field(default=None, description="新日期")
    new_time_slot: Optional[str] = Field(default=None, description="新时段")
    new_hospital_id: Optional[int] = Field(default=None, description="新院区ID")
    new_hospital_name: Optional[str] = Field(default=None, description="新院区名称")
    new_queue_number: Optional[int] = Field(default=None, description="新队列号")
    notification_sent: bool = Field(default=False, description="是否已发送通知")
    errors: Optional[List[str]] = Field(default=None, description="错误信息")


class BatchRescheduleRequest(BaseModel):
    appointment_ids: Optional[List[int]] = Field(default=None, description="预约ID列表")
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    equipment_id: Optional[int] = Field(default=None, description="设备ID")
    affected_date: Optional[date] = Field(default=None, description="受影响日期")
    reason: RescheduleReason = Field(..., description="改期原因")
    reason_detail: str = Field(..., max_length=255, description="原因详情")
    strategy: RescheduleStrategy = Field(default=RescheduleStrategy.PRIORITY_FIRST, description="重排策略")
    target_date: Optional[date] = Field(default=None, description="目标日期")
    target_hospital_id: Optional[int] = Field(default=None, description="目标院区ID")
    allow_cross_hospital: bool = Field(default=True, description="是否允许跨院区")
    notify_patient: bool = Field(default=True, description="是否通知患者")
    notify_hospital: bool = Field(default=True, description="是否通知院区")
    operator: Optional[str] = Field(default=None, description="操作人")
    dry_run: bool = Field(default=False, description="是否仅模拟")


class EquipmentDowntimeRequest(BaseModel):
    equipment_id: int = Field(..., description="设备ID")
    start_time: datetime = Field(..., description="停机开始时间")
    end_time: datetime = Field(..., description="停机结束时间")
    downtime_type: str = Field(default="maintenance", max_length=50, description="停机类型")
    reason: str = Field(..., max_length=255, description="停机原因")
    auto_reschedule: bool = Field(default=True, description="是否自动改期受影响预约")
    reschedule_strategy: RescheduleStrategy = Field(default=RescheduleStrategy.PRIORITY_FIRST, description="改期策略")
    allow_cross_hospital: bool = Field(default=True, description="是否允许跨院区")
    operator: Optional[str] = Field(default=None, description="操作人")
    notes: Optional[str] = Field(default=None, description="备注")


class DrugDelayRequest(BaseModel):
    tracer_batch_id: int = Field(..., description="药物批次ID")
    hospital_id: int = Field(..., description="院区ID")
    tracer_id: int = Field(..., description="示踪剂ID")
    expected_delay_minutes: int = Field(..., gt=0, description="预计延迟(分钟)")
    new_arrival_time: Optional[datetime] = Field(default=None, description="新到货时间")
    reason: str = Field(..., max_length=255, description="延迟原因")
    affected_appointment_ids: Optional[List[int]] = Field(default=None, description="受影响预约ID列表")
    auto_reschedule: bool = Field(default=True, description="是否自动改期")
    reschedule_strategy: RescheduleStrategy = Field(default=RescheduleStrategy.MINIMIZE_IMPACT, description="改期策略")
    shift_injection_times: bool = Field(default=True, description="是否顺延注射时间")
    operator: Optional[str] = Field(default=None, description="操作人")
    notes: Optional[str] = Field(default=None, description="备注")


class EmergencyPlusRequest(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    patient_id: int = Field(..., description="患者ID")
    exam_purpose: str = Field(..., max_length=50, description="检查目的")
    urgency_level: str = Field(default="emergency", max_length=20, description="紧急程度")
    clinical_diagnosis: Optional[str] = Field(default=None, max_length=255, description="临床诊断")
    plus_sign_reason: str = Field(..., max_length=255, description="加号原因")
    target_date: date = Field(..., description="加号日期")
    target_time_slot: Optional[str] = Field(default=None, description="加号时段")
    preferred_equipment_id: Optional[int] = Field(default=None, description="偏好设备ID")
    needs_anesthesia: bool = Field(default=False, description="是否需要麻醉")
    is_inpatient: bool = Field(default=False, description="是否住院")
    referring_department: Optional[str] = Field(default=None, max_length=100, description="申请科室")
    referring_doctor: Optional[str] = Field(default=None, max_length=50, description="申请医生")
    auto_shift_queue: bool = Field(default=True, description="是否自动调整队列")
    reschedule_strategy: RescheduleStrategy = Field(default=RescheduleStrategy.MAINTAIN_ORDER, description="队列调整策略")
    operator: Optional[str] = Field(default=None, description="操作人")
    notes: Optional[str] = Field(default=None, description="备注")


class BatchRescheduleResult(BaseModel):
    total_count: int = Field(..., description="总记录数")
    success_count: int = Field(..., description="成功数")
    failed_count: int = Field(..., description="失败数")
    skipped_count: int = Field(default=0, description="跳过数")
    reason: RescheduleReason = Field(..., description="改期原因")
    strategy: RescheduleStrategy = Field(..., description="重排策略")
    results: List[RescheduleResult] = Field(..., description="详细结果")
    affected_hospitals: List[int] = Field(default_factory=list, description="受影响院区ID")
    estimated_impact_minutes: int = Field(default=0, description="预计影响时间(分钟)")
    summary: Dict[str, Any] = Field(default_factory=dict, description="汇总信息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")
