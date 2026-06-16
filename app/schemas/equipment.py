from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class EquipmentStatus(str, Enum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"
    CALIBRATION = "calibration"


class EquipmentBase(BaseModel):
    hospital_id: int = Field(..., description="所属院区ID")
    code: str = Field(..., max_length=50, description="设备编码")
    name: str = Field(..., max_length=100, description="设备名称")
    model: Optional[str] = Field(default=None, max_length=50, description="设备型号")
    manufacturer: Optional[str] = Field(default=None, max_length=50, description="生产厂商")
    serial_number: Optional[str] = Field(default=None, max_length=100, description="序列号")
    equipment_type: str = Field(default="petct", max_length=20, description="设备类型")
    room_number: Optional[str] = Field(default=None, max_length=20, description="机房编号")
    daily_capacity: int = Field(default=15, ge=0, description="日检查容量")
    scan_duration_minutes: int = Field(default=30, ge=10, description="单例扫描时长(分钟)")
    setup_duration_minutes: int = Field(default=10, ge=0, description="准备时长(分钟)")
    is_active: bool = Field(default=True, description="是否启用")
    description: Optional[str] = Field(default=None, description="备注")


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=50)
    manufacturer: Optional[str] = Field(default=None, max_length=50)
    room_number: Optional[str] = Field(default=None, max_length=20)
    status: Optional[EquipmentStatus] = Field(default=None)
    status_reason: Optional[str] = Field(default=None, max_length=255)
    daily_capacity: Optional[int] = Field(default=None, ge=0)
    scan_duration_minutes: Optional[int] = Field(default=None, ge=10)
    setup_duration_minutes: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    maintenance_date: Optional[date] = Field(default=None)
    description: Optional[str] = Field(default=None)


class EquipmentStatusUpdate(BaseModel):
    status: EquipmentStatus = Field(..., description="新状态")
    status_reason: Optional[str] = Field(default=None, max_length=255, description="状态说明")
    estimated_duration_minutes: Optional[int] = Field(default=None, description="预计持续时间(分钟)")
    operator: Optional[str] = Field(default=None, description="操作人")
    notes: Optional[str] = Field(default=None, description="备注")


class EquipmentResponse(EquipmentBase):
    id: int
    status: EquipmentStatus
    status_reason: Optional[str]
    status_updated_at: Optional[datetime]
    maintenance_date: Optional[date]
    installation_date: Optional[date]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


EquipmentStatusUpdateRequest = EquipmentStatusUpdate


class MaintenanceRecordCreate(BaseModel):
    equipment_id: int = Field(..., description="设备ID")
    maintenance_type: str = Field(..., max_length=50, description="维护类型")
    description: str = Field(..., description="维护描述")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    operator: Optional[str] = Field(default=None, max_length=50, description="操作人")
    cost: Optional[float] = Field(default=None, ge=0, description="费用")
    notes: Optional[str] = Field(default=None, description="备注")


class MaintenanceRecordResponse(MaintenanceRecordCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
