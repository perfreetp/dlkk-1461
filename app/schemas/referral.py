from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field


class ReferralBase(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    patient_id: int = Field(..., description="患者ID")
    source_hospital_id: int = Field(..., description="转出院区ID")
    target_hospital_id: int = Field(..., description="转入院区ID")
    referral_reason: Optional[str] = Field(default=None, max_length=255, description="转诊原因")
    referral_type: str = Field(default="auto", max_length=20, description="转诊类型")
    original_appointment_date: Optional[date] = Field(default=None, description="原预约日期")
    original_hospital_id: Optional[int] = Field(default=None, description="原预约院区ID")
    distance_km: Optional[float] = Field(default=None, description="距离(公里)")
    travel_time_minutes: Optional[int] = Field(default=None, description="预计行程时间(分钟)")
    proposed_date: Optional[date] = Field(default=None, description="建议日期")
    proposed_time_slot: Optional[str] = Field(default=None, max_length=20, description="建议时段")
    patient_preference: Optional[str] = Field(default=None, max_length=255, description="患者偏好")
    clinical_notes: Optional[str] = Field(default=None, description="临床备注")
    coordination_notes: Optional[str] = Field(default=None, description="协调备注")


class ReferralCreate(ReferralBase):
    pass


class ReferralUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20)
    target_hospital_id: Optional[int] = Field(default=None)
    proposed_date: Optional[date] = Field(default=None)
    proposed_time_slot: Optional[str] = Field(default=None)
    accepted_by: Optional[str] = Field(default=None, max_length=50)
    declined_reason: Optional[str] = Field(default=None, max_length=255)
    declined_by: Optional[str] = Field(default=None, max_length=50)
    coordination_notes: Optional[str] = Field(default=None)
    is_completed: Optional[bool] = Field(default=None)


class ReferralResponse(ReferralBase):
    id: int
    referral_no: str
    status: str
    status_changed_at: datetime
    accepted_by: Optional[str]
    accepted_at: Optional[datetime]
    declined_reason: Optional[str]
    declined_by: Optional[str]
    is_completed: bool
    completed_at: Optional[datetime]
    auto_assigned: bool
    assignment_score: Optional[int]
    assignment_reason: Optional[str]
    alternative_dates: Optional[str]
    traffic_condition: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReferralQueryParams(BaseModel):
    source_hospital_id: Optional[int] = Field(default=None, description="转出院区ID")
    target_hospital_id: Optional[int] = Field(default=None, description="转入院区ID")
    patient_id: Optional[int] = Field(default=None, description="患者ID")
    status: Optional[str] = Field(default=None, description="状态")
    referral_type: Optional[str] = Field(default=None, description="转诊类型")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    auto_assigned: Optional[bool] = Field(default=None, description="是否系统自动分配")
    only_pending: bool = Field(default=False, description="仅显示待处理")


class ReferralAutoAssignResponse(BaseModel):
    referral_no: str = Field(..., description="转诊编号")
    appointment_id: int = Field(..., description="预约ID")
    patient_id: int = Field(..., description="患者ID")
    recommended_hospital_id: int = Field(..., description="推荐院区ID")
    recommended_hospital_name: str = Field(..., description="推荐院区名称")
    distance_km: float = Field(..., description="距离(公里)")
    travel_time_minutes: int = Field(..., description="预计行程时间(分钟)")
    assignment_score: int = Field(..., description="分配评分 0-100")
    assignment_reason: str = Field(..., description="分配理由")
    available_dates: List[date] = Field(..., description="可用日期列表")
    alternative_hospitals: List[dict] = Field(default_factory=list, description="备选院区列表")
    traffic_condition: str = Field(default="normal", description="交通状况")
    notes: Optional[str] = Field(default=None, description="备注")
