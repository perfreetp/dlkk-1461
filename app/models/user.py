from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    real_name = Column(String(50), nullable=False, comment="真实姓名")
    phone = Column(String(20), comment="联系电话")
    email = Column(String(100), comment="邮箱")

    role = Column(String(20), nullable=False, comment="角色: admin/dispatcher/doctor/staff")
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), comment="所属院区ID")

    is_active = Column(Boolean, default=True, comment="是否启用")
    is_admin = Column(Boolean, default=False, comment="是否管理员")

    hospital = relationship("Hospital", back_populates="staff")
    created_appointments = relationship("Appointment", back_populates="creator", foreign_keys="Appointment.creator_id")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
