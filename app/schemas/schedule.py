from typing import Optional, List
from datetime import datetime, date, time
from pydantic import BaseModel, Field
from enum import Enum


class TemplateType(str, Enum):
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    SPECIAL = "special"
    NORMAL = "normal"


class ScheduleTemplateBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    template_name: str = Field(..., max_length=100, description="模板名称")
    template_type: str = Field(default="normal", max_length=20, description="模板类型")
    effective_date: Optional[date] = Field(default=None, description="生效日期")
    expiry_date: Optional[date] = Field(default=None, description="失效日期")
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6, description="星期几 0-6")
    is_weekday: Optional[bool] = Field(default=None, description="是否工作日")
    work_start_time: time = Field(default="08:00", description="上班时间")
    work_end_time: time = Field(default="17:00", description="下班时间")
    lunch_start_time: Optional[time] = Field(default="12:00", description="午休开始")
    lunch_end_time: Optional[time] = Field(default="13:30", description="午休结束")
    daily_capacity: int = Field(default=20, ge=0, description="日检查容量")
    morning_capacity: int = Field(default=12, ge=0, description="上午容量")
    afternoon_capacity: int = Field(default=8, ge=0, description="下午容量")
    anesthesia_slots: int = Field(default=3, ge=0, description="麻醉时段数")
    inpatient_slots: int = Field(default=8, ge=0, description="住院患者时段数")
    emergency_slots: int = Field(default=2, ge=0, description="急诊预留时段数")
    is_active: bool = Field(default=True, description="是否启用")
    notes: Optional[str] = Field(default=None, description="备注")


class ScheduleTemplateCreate(ScheduleTemplateBase):
    pass


class ScheduleTemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(default=None, max_length=100)
    template_type: Optional[str] = Field(default=None, max_length=20)
    effective_date: Optional[date] = Field(default=None)
    expiry_date: Optional[date] = Field(default=None)
    daily_capacity: Optional[int] = Field(default=None, ge=0)
    morning_capacity: Optional[int] = Field(default=None, ge=0)
    afternoon_capacity: Optional[int] = Field(default=None, ge=0)
    anesthesia_slots: Optional[int] = Field(default=None, ge=0)
    inpatient_slots: Optional[int] = Field(default=None, ge=0)
    emergency_slots: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ScheduleTemplateResponse(ScheduleTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShiftAssignmentBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    user_id: int = Field(..., description="人员ID")
    shift_date: date = Field(..., description="排班日期")
    shift_type: str = Field(..., max_length=20, description="班次")
    start_time: Optional[time] = Field(default=None, description="开始时间")
    end_time: Optional[time] = Field(default=None, description="结束时间")
    role: Optional[str] = Field(default=None, max_length=50, description="岗位")
    equipment_id: Optional[int] = Field(default=None, description="负责设备")
    template_id: Optional[int] = Field(default=None, description="排班模板ID")
    notes: Optional[str] = Field(default=None, description="备注")


class ShiftAssignmentCreate(ShiftAssignmentBase):
    pass


class ShiftAssignmentUpdate(BaseModel):
    shift_type: Optional[str] = Field(default=None, max_length=20)
    start_time: Optional[time] = Field(default=None)
    end_time: Optional[time] = Field(default=None)
    role: Optional[str] = Field(default=None, max_length=50)
    equipment_id: Optional[int] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    swap_requested: Optional[bool] = Field(default=None)
    swap_user_id: Optional[int] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ShiftAssignmentResponse(ShiftAssignmentBase):
    id: int
    is_active: bool
    swap_requested: bool
    swap_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupportPlanBase(BaseModel):
    plan_name: str = Field(..., max_length=100, description="方案名称")
    plan_type: str = Field(default="temporary", max_length=20, description="方案类型")
    hospital_id: int = Field(..., description="目标院区ID")
    source_hospital_id: Optional[int] = Field(default=None, description="支援来源院区ID")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    reason: Optional[str] = Field(default=None, max_length=255, description="支援原因")
    scope: Optional[str] = Field(default=None, max_length=255, description="支援范围")
    additional_capacity: int = Field(default=0, ge=0, description="额外增加容量")
    staff_count: int = Field(default=0, ge=0, description="支援人数")
    equipment_count: int = Field(default=0, ge=0, description="支援设备数")
    coordinator: Optional[str] = Field(default=None, max_length=50, description="协调人")
    coordinator_phone: Optional[str] = Field(default=None, max_length=20, description="协调人电话")
    notes: Optional[str] = Field(default=None, description="备注")


class SupportPlanCreate(SupportPlanBase):
    pass


class SupportPlanUpdate(BaseModel):
    plan_name: Optional[str] = Field(default=None, max_length=100)
    plan_type: Optional[str] = Field(default=None, max_length=20)
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    reason: Optional[str] = Field(default=None, max_length=255)
    additional_capacity: Optional[int] = Field(default=None, ge=0)
    staff_count: Optional[int] = Field(default=None, ge=0)
    equipment_count: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, max_length=20)
    approved_by: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None)


class SupportPlanResponse(SupportPlanBase):
    id: int
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShiftSwapRequest(BaseModel):
    shift_id: int = Field(..., description="需要换班的排班ID")
    target_user_id: int = Field(..., description="目标换班人员ID")
    reason: str = Field(..., max_length=255, description="换班原因")
    preferred_date: Optional[date] = Field(default=None, description="期望换班日期")
    notes: Optional[str] = Field(default=None, description="备注")


class ShiftSwapApproveRequest(BaseModel):
    swap_id: int = Field(..., description="换班申请ID")
    approved: bool = Field(..., description="是否批准")
    approver_notes: Optional[str] = Field(default=None, max_length=255, description="审批意见")


class SupportPlanApproveRequest(BaseModel):
    plan_id: int = Field(..., description="支援方案ID")
    approved: bool = Field(..., description="是否批准")
    approver: str = Field(..., max_length=50, description="审批人")
    approver_notes: Optional[str] = Field(default=None, max_length=255, description="审批意见")


class HolidayTemplateGenerateRequest(BaseModel):
    holiday_name: str = Field(..., max_length=100, description="节假日名称")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    hospital_ids: Optional[List[int]] = Field(default=None, description="院区ID列表，空表示全部")
    template_type: TemplateType = Field(default=TemplateType.HOLIDAY, description="模板类型")
    capacity_factor: float = Field(default=0.5, ge=0, le=1, description="容量系数")
    staff_reduction: int = Field(default=0, ge=0, description="人员减少数量")


class WeeklyScheduleGenerateRequest(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    week_start_date: date = Field(..., description="周开始日期")
    template_id: Optional[int] = Field(default=None, description="使用的模板ID")
    include_weekend: bool = Field(default=True, description="是否包含周末")
    auto_assign_staff: bool = Field(default=True, description="是否自动分配人员")
    notify_staff: bool = Field(default=False, description="是否通知人员")
