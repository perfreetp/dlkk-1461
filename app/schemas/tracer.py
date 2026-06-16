from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field


class TracerBase(BaseModel):
    hospital_id: int = Field(..., description="所属院区ID")
    code: str = Field(..., max_length=50, description="药物编码")
    name: str = Field(..., max_length=100, description="药物名称")
    generic_name: Optional[str] = Field(default=None, max_length=100, description="通用名")
    tracer_type: str = Field(default="fdg", max_length=20, description="示踪剂类型")
    half_life_minutes: int = Field(default=110, ge=1, description="半衰期(分钟)")
    default_dose_mbq: float = Field(default=370, gt=0, description="标准剂量(MBq)")
    is_active: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(default=None, description="备注")


class TracerCreate(TracerBase):
    pass


class TracerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    generic_name: Optional[str] = Field(default=None, max_length=100)
    tracer_type: Optional[str] = Field(default=None, max_length=20)
    half_life_minutes: Optional[int] = Field(default=None, ge=1)
    default_dose_mbq: Optional[float] = Field(default=None, gt=0)
    is_active: Optional[bool] = Field(default=None)
    description: Optional[str] = Field(default=None)


class TracerResponse(TracerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TracerBatchBase(BaseModel):
    tracer_id: int = Field(..., description="示踪剂ID")
    batch_no: str = Field(..., max_length=50, description="批次号")
    total_activity_mbq: float = Field(..., gt=0, description="总活度(MBq)")
    calibration_activity: float = Field(..., gt=0, description="刻度活度(MBq)")
    calibration_time: datetime = Field(..., description="刻度时间")
    production_time: datetime = Field(..., description="生产时间")
    expiry_time: datetime = Field(..., description="过期时间")
    arrival_time: Optional[datetime] = Field(default=None, description="到货时间")
    supplier: Optional[str] = Field(default=None, max_length=100, description="供应商")
    lot_number: Optional[str] = Field(default=None, max_length=50, description="批号")


class TracerBatchCreate(TracerBatchBase):
    pass


class TracerBatchUpdate(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20)
    arrival_time: Optional[datetime] = Field(default=None)
    used_activity_mbq: Optional[float] = Field(default=None, ge=0)
    wasted_activity_mbq: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None)


class TracerBatchResponse(TracerBatchBase):
    id: int
    status: str
    used_activity_mbq: float
    wasted_activity_mbq: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TracerUsageBase(BaseModel):
    appointment_id: int = Field(..., description="预约ID")
    tracer_id: int = Field(..., description="示踪剂ID")
    batch_id: int = Field(..., description="批次ID")
    dose_mbq: float = Field(..., gt=0, description="注射剂量(MBq)")
    injection_time: Optional[datetime] = Field(default=None, description="注射时间")
    remaining_activity: Optional[float] = Field(default=None, description="剩余活度")
    waste_activity: float = Field(default=0, ge=0, description="浪费活度")
    injection_site: Optional[str] = Field(default=None, max_length=50, description="注射部位")
    vein_access: Optional[str] = Field(default=None, max_length=50, description="静脉通路")
    administered_by: Optional[str] = Field(default=None, max_length=50, description="注射人员")
    notes: Optional[str] = Field(default=None, description="备注")


class TracerUsageCreate(TracerUsageBase):
    pass


class TracerUsageResponse(TracerUsageBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
