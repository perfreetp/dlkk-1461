from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class StatusRecordBase(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    status_type: str = Field(..., max_length=20, description="状态类型")
    occurred_at: datetime = Field(default_factory=datetime.utcnow, description="发生时间")
    recorded_by: Optional[str] = Field(default=None, max_length=50, description="记录人")
    location: Optional[str] = Field(default=None, max_length=100, description="地点")
    notes: Optional[str] = Field(default=None, description="备注")


class StatusRecordCreate(StatusRecordBase):
    status_code: Optional[str] = Field(default=None, max_length=50)
    status_name: Optional[str] = Field(default=None, max_length=100)
    recorded_by_id: Optional[int] = Field(default=None)
    blood_glucose: Optional[float] = Field(default=None)
    blood_pressure_systolic: Optional[int] = Field(default=None)
    blood_pressure_diastolic: Optional[int] = Field(default=None)
    heart_rate: Optional[int] = Field(default=None)
    spo2: Optional[float] = Field(default=None)
    tracer_batch_no: Optional[str] = Field(default=None, max_length=50)
    tracer_dose_mbq: Optional[float] = Field(default=None)
    tracer_injection_site: Optional[str] = Field(default=None, max_length=50)
    equipment_code: Optional[str] = Field(default=None, max_length=50)
    scan_protocol: Optional[str] = Field(default=None, max_length=100)
    scan_duration_seconds: Optional[int] = Field(default=None)


class StatusRecordResponse(StatusRecordCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CheckInRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    checkin_time: Optional[datetime] = Field(default=None, description="签到时间")
    recorded_by: Optional[str] = Field(default=None, description="记录人")
    location: Optional[str] = Field(default=None, description="签到地点")

    blood_glucose: Optional[float] = Field(default=None, description="血糖值")
    blood_pressure_systolic: Optional[int] = Field(default=None, description="收缩压")
    blood_pressure_diastolic: Optional[int] = Field(default=None, description="舒张压")
    heart_rate: Optional[int] = Field(default=None, description="心率")
    spo2: Optional[float] = Field(default=None, description="血氧饱和度")

    fasting_confirmed: bool = Field(default=True, description="是否确认禁食")
    hydration_completed: bool = Field(default=False, description="是否完成水化")
    notes: Optional[str] = Field(default=None, description="备注")


class InjectionRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    injection_time: Optional[datetime] = Field(default=None, description="注射时间")
    recorded_by: Optional[str] = Field(default=None, description="记录人")
    operator: Optional[str] = Field(default=None, description="操作人(别名recorded_by)")

    tracer_batch_no: Optional[str] = Field(default=None, max_length=50, description="示踪剂批次号")
    tracer_type: str = Field(default="fdg", max_length=20, description="示踪剂类型")
    tracer_name: Optional[str] = Field(default=None, max_length=50, description="示踪剂名称")
    tracer_id: Optional[int] = Field(default=None, description="示踪剂ID")
    tracer_dose_mbq: Optional[float] = Field(default=None, gt=0, description="注射剂量(MBq)")
    dose_mbq: Optional[float] = Field(default=None, gt=0, description="注射剂量(MBq)(别名)")
    tracer_injection_site: Optional[str] = Field(default=None, max_length=50, description="注射部位")
    injection_site: Optional[str] = Field(default=None, max_length=50, description="注射部位(别名)")
    vein_access: Optional[str] = Field(default=None, max_length=50, description="静脉通路")

    administered_by: Optional[str] = Field(default=None, max_length=50, description="注射人员")
    remaining_activity: Optional[float] = Field(default=None, description="剩余活度")
    waste_activity: Optional[float] = Field(default=0, description="浪费活度")

    blood_glucose: Optional[float] = Field(default=None, description="血糖值")
    notes: Optional[str] = Field(default=None, description="备注")

    def get_effective_recorded_by(self) -> Optional[str]:
        return self.recorded_by or self.operator

    def get_effective_dose_mbq(self) -> Optional[float]:
        return self.tracer_dose_mbq or self.dose_mbq

    def get_effective_injection_site(self) -> Optional[str]:
        return self.tracer_injection_site or self.injection_site


class ScanStartRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    scan_start_time: Optional[datetime] = Field(default=None, description="扫描开始时间")
    recorded_by: Optional[str] = Field(default=None, description="记录人")
    equipment_code: Optional[str] = Field(default=None, max_length=50, description="设备编码")
    scan_protocol: Optional[str] = Field(default=None, max_length=100, description="扫描协议")
    patient_position: Optional[str] = Field(default=None, max_length=50, description="患者体位")
    notes: Optional[str] = Field(default=None, description="备注")


class CompletionRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    completion_time: Optional[datetime] = Field(default=None, description="完成时间")
    scan_end_time: Optional[datetime] = Field(default=None, description="扫描结束时间")
    recorded_by: Optional[str] = Field(default=None, description="记录人")

    scan_duration_seconds: Optional[int] = Field(default=None, description="扫描时长(秒)")
    images_acquired: Optional[int] = Field(default=None, description="采集图像数")
    image_quality: Optional[str] = Field(default=None, max_length=20, description="图像质量")

    patient_condition: Optional[str] = Field(default=None, max_length=100, description="患者状况")
    adverse_reaction: bool = Field(default=False, description="是否有不良反应")
    adverse_reaction_details: Optional[str] = Field(default=None, description="不良反应详情")

    next_step: Optional[str] = Field(default=None, max_length=255, description="后续安排")
    notes: Optional[str] = Field(default=None, description="备注")


class CancellationRequest(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    cancelled_at: Optional[datetime] = Field(default=None, description="取消时间")
    cancelled_by: Optional[str] = Field(default=None, description="取消人")

    cancellation_reason: str = Field(..., max_length=255, description="取消原因")
    cancellation_category: Optional[str] = Field(default=None, max_length=50, description="取消分类")

    reschedule_requested: bool = Field(default=False, description="是否要求改期")
    preferred_reschedule_date: Optional[str] = Field(default=None, description="改期偏好日期")

    refund_amount: Optional[float] = Field(default=None, description="退款金额")
    notes: Optional[str] = Field(default=None, description="备注")
