from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_db
from app.models import User, Equipment
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.equipment import (
    EquipmentCreate, EquipmentUpdate, EquipmentResponse,
    EquipmentStatusUpdateRequest, MaintenanceRecordCreate, MaintenanceRecordResponse
)
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger
from app.exceptions import EquipmentNotFound

router = APIRouter()
logger = get_logger("router_equipment")


@router.get("", response_model=ApiResponse[PaginatedResponse[EquipmentResponse]])
def list_equipment(
    hospital_id: Optional[int] = None,
    equipment_type: Optional[str] = None,
    status: Optional[str] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取设备列表"""
    query = db.query(Equipment)
    if hospital_id:
        query = query.filter(Equipment.hospital_id == hospital_id)
    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)
    if status:
        query = query.filter(Equipment.status == status)
    if is_active is not None:
        query = query.filter(Equipment.is_active == is_active)

    total = query.count()
    equipment = query.offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(
        data=PaginatedResponse(
            items=[EquipmentResponse.model_validate(e) for e in equipment],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{equipment_id}", response_model=ApiResponse[EquipmentResponse])
def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取设备详情"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise EquipmentNotFound(str(equipment_id))
    return ApiResponse(data=EquipmentResponse.model_validate(equipment))


@router.post("", response_model=ApiResponse[EquipmentResponse])
def create_equipment(
    equipment_data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """创建设备"""
    existing = db.query(Equipment).filter(
        Equipment.code == equipment_data.code
    ).first()
    if existing:
        raise ValueError(f"设备编码已存在: {equipment_data.code}")

    equipment = Equipment(**equipment_data.model_dump())
    db.add(equipment)
    db.commit()
    db.refresh(equipment)

    logger.info(f"创建设备: {equipment.name} (ID: {equipment.id})")
    return ApiResponse(data=EquipmentResponse.model_validate(equipment), message="设备创建成功")


@router.put("/{equipment_id}", response_model=ApiResponse[EquipmentResponse])
def update_equipment(
    equipment_id: int,
    update_data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """更新设备信息"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise EquipmentNotFound(str(equipment_id))

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)

    db.commit()
    db.refresh(equipment)
    return ApiResponse(data=EquipmentResponse.model_validate(equipment), message="设备信息更新成功")


@router.put("/{equipment_id}/status", response_model=ApiResponse[EquipmentResponse])
def update_equipment_status(
    equipment_id: int,
    request: EquipmentStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor", "technician"]))
):
    """更新设备状态"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise EquipmentNotFound(str(equipment_id))

    old_status = equipment.status
    equipment.status = request.status
    equipment.status_updated_at = datetime.utcnow()
    equipment.last_maintenance_date = request.last_maintenance_date
    equipment.next_maintenance_date = request.next_maintenance_date

    if request.notes:
        equipment.status_notes = request.notes

    db.commit()
    db.refresh(equipment)

    logger.info(f"设备状态更新: {equipment.code} {old_status} -> {request.status}")
    return ApiResponse(data=EquipmentResponse.model_validate(equipment), message="设备状态更新成功")


@router.delete("/{equipment_id}", response_model=ApiResponse)
def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """删除设备（软删除）"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise EquipmentNotFound(str(equipment_id))

    equipment.is_active = False
    db.commit()
    return ApiResponse(message="设备已停用")


@router.get("/{equipment_id}/utilization", response_model=ApiResponse)
def get_equipment_utilization(
    equipment_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取设备利用率统计"""
    from app.services import ReportService
    service = ReportService(db)
    utilization = service.get_equipment_utilization(equipment_id, start_date, end_date)
    return ApiResponse(data=utilization)


@router.get("/status/summary", response_model=ApiResponse)
def get_equipment_status_summary(
    hospital_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取设备状态汇总"""
    query = db.query(Equipment)
    if hospital_id:
        query = query.filter(Equipment.hospital_id == hospital_id)

    equipment_list = query.filter(Equipment.is_active == True).all()
    summary = {
        "total": len(equipment_list),
        "available": sum(1 for e in equipment_list if e.status == "available"),
        "maintenance": sum(1 for e in equipment_list if e.status == "maintenance"),
        "out_of_service": sum(1 for e in equipment_list if e.status == "out_of_service"),
        "by_hospital": {}
    }

    for e in equipment_list:
        h_id = str(e.hospital_id)
        if h_id not in summary["by_hospital"]:
            summary["by_hospital"][h_id] = {"total": 0, "available": 0, "maintenance": 0, "out_of_service": 0}
        summary["by_hospital"][h_id]["total"] += 1
        if e.status in summary["by_hospital"][h_id]:
            summary["by_hospital"][h_id][e.status] += 1

    return ApiResponse(data=summary)


@router.post("/{equipment_id}/maintenance", response_model=ApiResponse[MaintenanceRecordResponse])
def add_maintenance_record(
    equipment_id: int,
    record_data: MaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor", "technician"]))
):
    """添加维护记录"""
    from app.models.equipment import MaintenanceRecord

    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise EquipmentNotFound(str(equipment_id))

    record = MaintenanceRecord(
        equipment_id=equipment_id,
        **record_data.model_dump(),
        performed_by=current_user.real_name
    )
    db.add(record)

    equipment.last_maintenance_date = record_data.maintenance_date
    db.commit()
    db.refresh(record)

    return ApiResponse(data=MaintenanceRecordResponse.model_validate(record), message="维护记录已添加")


@router.get("/{equipment_id}/maintenance", response_model=ApiResponse)
def get_maintenance_history(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取维护历史"""
    from app.models.equipment import MaintenanceRecord

    records = db.query(MaintenanceRecord).filter(
        MaintenanceRecord.equipment_id == equipment_id
    ).order_by(MaintenanceRecord.maintenance_date.desc()).all()

    return ApiResponse(data={
        "records": [MaintenanceRecordResponse.model_validate(r) for r in records],
        "total": len(records)
    })
