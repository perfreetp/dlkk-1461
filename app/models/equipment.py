from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Equipment(BaseModel):
    __tablename__ = "equipment"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, comment="所属院区ID")
    code = Column(String(50), unique=True, index=True, nullable=False, comment="设备编码")
    name = Column(String(100), nullable=False, comment="设备名称")
    model = Column(String(50), comment="设备型号")
    manufacturer = Column(String(50), comment="生产厂商")
    serial_number = Column(String(100), comment="序列号")

    equipment_type = Column(String(20), default="petct", comment="设备类型: petct/pet/mri/ct")
    room_number = Column(String(20), comment="机房编号")
    location = Column(String(100), comment="设备位置")

    status = Column(String(20), default="available", comment="状态: available/maintenance/out_of_service/calibration")
    status_reason = Column(String(255), comment="状态说明")
    status_updated_at = Column(DateTime, default=datetime.utcnow, comment="状态更新时间")

    daily_capacity = Column(Integer, default=15, comment="日检查容量")
    scan_duration_minutes = Column(Integer, default=30, comment="单例扫描时长(分钟)")
    setup_duration_minutes = Column(Integer, default=10, comment="准备时长(分钟)")

    maintenance_date = Column(DateTime, comment="下次保养日期")
    installation_date = Column(DateTime, comment="安装日期")

    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, comment="备注")

    hospital = relationship("Hospital", back_populates="equipment")
    appointments = relationship("Appointment", back_populates="equipment")

    def __repr__(self):
        return f"<Equipment(id={self.id}, code='{self.code}', name='{self.name}', status='{self.status}')>"
