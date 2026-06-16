from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.hospital import (
    HospitalCreate, HospitalUpdate, HospitalResponse,
    HospitalCapacityUpdateRequest, HospitalStatusResponse
)
from app.services import AppointmentService
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger
from app.models.hospital import Hospital
from app.exceptions import HospitalNotFound

router = APIRouter()
logger = get_logger("router_hospitals")


@router.get("", response_model=ApiResponse[PaginatedResponse[HospitalResponse]])
def list_hospitals(
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取院区列表"""
    query = db.query(Hospital)
    if is_active is not None:
        query = query.filter(Hospital.is_active == is_active)

    total = query.count()
    hospitals = query.offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(
        data=PaginatedResponse(
            items=[HospitalResponse.model_validate(h) for h in hospitals],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{hospital_id}", response_model=ApiResponse[HospitalResponse])
def get_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取院区详情"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HospitalNotFound(str(hospital_id))
    return ApiResponse(data=HospitalResponse.model_validate(hospital))


@router.post("", response_model=ApiResponse[HospitalResponse])
def create_hospital(
    hospital_data: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """创建院区"""
    existing = db.query(Hospital).filter(
        (Hospital.code == hospital_data.code) | (Hospital.name == hospital_data.name)
    ).first()
    if existing:
        raise ValueError(f"院区编码或名称已存在: {hospital_data.code}")

    hospital = Hospital(**hospital_data.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    logger.info(f"创建院区: {hospital.name} (ID: {hospital.id})")
    return ApiResponse(data=HospitalResponse.model_validate(hospital), message="院区创建成功")


@router.put("/{hospital_id}", response_model=ApiResponse[HospitalResponse])
def update_hospital(
    hospital_id: int,
    update_data: HospitalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """更新院区信息"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HospitalNotFound(str(hospital_id))

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)

    db.commit()
    db.refresh(hospital)
    return ApiResponse(data=HospitalResponse.model_validate(hospital), message="院区信息更新成功")


@router.delete("/{hospital_id}", response_model=ApiResponse)
def delete_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """删除院区（软删除）"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HospitalNotFound(str(hospital_id))

    hospital.is_active = False
    db.commit()
    return ApiResponse(message="院区已停用")


@router.put("/{hospital_id}/capacity", response_model=ApiResponse[HospitalResponse])
def update_hospital_capacity(
    hospital_id: int,
    request: HospitalCapacityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """更新院区容量配置"""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HospitalNotFound(str(hospital_id))

    hospital.daily_capacity = request.daily_capacity
    hospital.morning_capacity = request.morning_capacity
    hospital.afternoon_capacity = request.afternoon_capacity
    hospital.operating_hours_start = request.operating_hours_start
    hospital.operating_hours_end = request.operating_hours_end
    hospital.slot_duration_minutes = request.slot_duration_minutes

    db.commit()
    db.refresh(hospital)
    return ApiResponse(data=HospitalResponse.model_validate(hospital), message="容量配置更新成功")


@router.get("/{hospital_id}/status", response_model=ApiResponse)
def get_hospital_real_time_status(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取院区实时状态"""
    service = AppointmentService(db)
    status = service.get_hospital_realtime_status(hospital_id)
    return ApiResponse(data=status)


@router.get("/all/summary", response_model=ApiResponse)
def get_all_hospitals_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取所有院区摘要信息"""
    hospitals = db.query(Hospital).filter(Hospital.is_active == True).all()
    summary = []
    for h in hospitals:
        summary.append({
            "id": h.id,
            "name": h.name,
            "code": h.code,
            "address": h.address,
            "phone": h.phone,
            "daily_capacity": h.daily_capacity,
            "latitude": h.latitude,
            "longitude": h.longitude
        })
    return ApiResponse(data={"hospitals": summary, "total": len(summary)})
