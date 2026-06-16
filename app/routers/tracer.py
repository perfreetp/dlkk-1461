from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.tracer import (
    TracerCreate, TracerUpdate, TracerResponse,
    TracerBatchCreate, TracerBatchUpdate, TracerBatchResponse,
    TracerUsageCreate, TracerUsageResponse
)
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger
from app.models.tracer import Tracer, TracerBatch, TracerUsage
from app.exceptions import ResourceNotFound, ValidationError

router = APIRouter()
logger = get_logger("router_tracer")


@router.get("/tracers", response_model=ApiResponse[PaginatedResponse[TracerResponse]])
def list_tracers(
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取示踪剂列表"""
    query = db.query(Tracer)
    if is_active is not None:
        query = query.filter(Tracer.is_active == is_active)

    total = query.count()
    tracers = query.offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(
        data=PaginatedResponse(
            items=[TracerResponse.model_validate(t) for t in tracers],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.post("/tracers", response_model=ApiResponse[TracerResponse])
def create_tracer(
    tracer_data: TracerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist"]))
):
    """创建示踪剂"""
    existing = db.query(Tracer).filter(Tracer.code == tracer_data.code).first()
    if existing:
        raise ValidationError(f"示踪剂编码已存在: {tracer_data.code}")

    tracer = Tracer(**tracer_data.model_dump())
    db.add(tracer)
    db.commit()
    db.refresh(tracer)

    logger.info(f"创建示踪剂: {tracer.name} (ID: {tracer.id})")
    return ApiResponse(data=TracerResponse.model_validate(tracer), message="示踪剂创建成功")


@router.put("/tracers/{tracer_id}", response_model=ApiResponse[TracerResponse])
def update_tracer(
    tracer_id: int,
    update_data: TracerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist"]))
):
    """更新示踪剂信息"""
    tracer = db.query(Tracer).filter(Tracer.id == tracer_id).first()
    if not tracer:
        raise ResourceNotFound(f"示踪剂不存在: {tracer_id}")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(tracer, field, value)

    db.commit()
    db.refresh(tracer)
    return ApiResponse(data=TracerResponse.model_validate(tracer), message="示踪剂更新成功")


@router.get("/batches", response_model=ApiResponse[PaginatedResponse[TracerBatchResponse]])
def list_tracer_batches(
    hospital_id: Optional[int] = None,
    tracer_id: Optional[int] = None,
    is_expired: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取示踪剂批次列表"""
    from datetime import datetime
    query = db.query(TracerBatch)
    if hospital_id:
        query = query.filter(TracerBatch.hospital_id == hospital_id)
    if tracer_id:
        query = query.filter(TracerBatch.tracer_id == tracer_id)

    total = query.count()
    batches = query.offset(pagination.offset).limit(pagination.limit).all()

    for batch in batches:
        batch.is_expired = batch.expiry_time < datetime.utcnow() if batch.expiry_time else False

    return ApiResponse(
        data=PaginatedResponse(
            items=[TracerBatchResponse.model_validate(b) for b in batches],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.post("/batches", response_model=ApiResponse[TracerBatchResponse])
def create_tracer_batch(
    batch_data: TracerBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist"]))
):
    """创建示踪剂批次"""
    existing = db.query(TracerBatch).filter(
        TracerBatch.batch_no == batch_data.batch_no
    ).first()
    if existing:
        raise ValidationError(f"批次号已存在: {batch_data.batch_no}")

    batch = TracerBatch(**batch_data.model_dump())
    batch.remaining_activity_mbq = batch.initial_activity_mbq
    db.add(batch)
    db.commit()
    db.refresh(batch)

    logger.info(f"创建示踪剂批次: {batch.batch_no} (ID: {batch.id})")
    return ApiResponse(data=TracerBatchResponse.model_validate(batch), message="批次创建成功")


@router.put("/batches/{batch_id}", response_model=ApiResponse[TracerBatchResponse])
def update_tracer_batch(
    batch_id: int,
    update_data: TracerBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist"]))
):
    """更新示踪剂批次"""
    batch = db.query(TracerBatch).filter(TracerBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"批次不存在: {batch_id}")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(batch, field, value)

    db.commit()
    db.refresh(batch)
    return ApiResponse(data=TracerBatchResponse.model_validate(batch), message="批次更新成功")


@router.get("/inventory/{hospital_id}", response_model=ApiResponse)
def get_tracer_inventory(
    hospital_id: int,
    tracer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取示踪剂库存"""
    from datetime import datetime
    query = db.query(TracerBatch).filter(
        TracerBatch.hospital_id == hospital_id,
        TracerBatch.status == "received"
    )
    if tracer_id:
        query = query.filter(TracerBatch.tracer_id == tracer_id)

    batches = query.all()
    inventory = []
    now = datetime.utcnow()

    for batch in batches:
        is_expired = batch.expiry_time < now if batch.expiry_time else False
        inventory.append({
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "tracer_id": batch.tracer_id,
            "tracer_name": batch.tracer.name if batch.tracer else None,
            "remaining_activity_mbq": batch.remaining_activity_mbq,
            "initial_activity_mbq": batch.initial_activity_mbq,
            "received_time": batch.received_time,
            "expiry_time": batch.expiry_time,
            "is_expired": is_expired,
            "status": batch.status
        })

    return ApiResponse(data={
        "inventory": inventory,
        "total_batches": len(inventory),
        "total_activity_mbq": sum(i["remaining_activity_mbq"] or 0 for i in inventory)
    })


@router.post("/usage", response_model=ApiResponse[TracerUsageResponse])
def record_tracer_usage(
    usage_data: TracerUsageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist", "technician"]))
):
    """记录示踪剂使用"""
    from app.models.drug_waste import DrugWaste

    batch = db.query(TracerBatch).filter(
        TracerBatch.id == usage_data.tracer_batch_id
    ).first()
    if not batch:
        raise ResourceNotFound(f"批次不存在: {usage_data.tracer_batch_id}")

    usage = TracerUsage(
        **usage_data.model_dump(),
        recorded_by=current_user.real_name
    )
    db.add(usage)

    batch.remaining_activity_mbq = (batch.remaining_activity_mbq or 0) - (usage_data.used_activity_mbq or 0)

    if usage_data.wasted_activity_mbq and usage_data.wasted_activity_mbq > 0:
        waste = DrugWaste(
            hospital_id=batch.hospital_id,
            tracer_id=batch.tracer_id,
            tracer_batch_id=batch.id,
            appointment_id=usage_data.appointment_id,
            wasted_activity_mbq=usage_data.wasted_activity_mbq,
            waste_reason=usage_data.waste_reason or "usage_waste",
            recorded_by=current_user.real_name
        )
        db.add(waste)

    db.commit()
    db.refresh(usage)

    return ApiResponse(data=TracerUsageResponse.model_validate(usage), message="使用记录已添加")


@router.get("/usage/statistics", response_model=ApiResponse)
def get_tracer_usage_statistics(
    hospital_id: Optional[int] = None,
    tracer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取示踪剂使用统计"""
    from app.services import ReportService
    service = ReportService(db)
    stats = service.get_tracer_usage_statistics(hospital_id, tracer_id, start_date, end_date)
    return ApiResponse(data=stats)


@router.post("/batches/{batch_id}/receive", response_model=ApiResponse[TracerBatchResponse])
def receive_tracer_batch(
    batch_id: int,
    received_activity_mbq: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "pharmacist"]))
):
    """确认接收示踪剂批次"""
    from datetime import datetime
    batch = db.query(TracerBatch).filter(TracerBatch.id == batch_id).first()
    if not batch:
        raise ResourceNotFound(f"批次不存在: {batch_id}")

    batch.status = "received"
    batch.received_time = datetime.utcnow()
    batch.initial_activity_mbq = received_activity_mbq
    batch.remaining_activity_mbq = received_activity_mbq
    batch.received_by = current_user.real_name

    db.commit()
    db.refresh(batch)
    return ApiResponse(data=TracerBatchResponse.model_validate(batch), message="批次已确认接收")


@router.get("/wastage/records", response_model=ApiResponse)
def get_drug_wastage_records(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取药物浪费记录"""
    from app.models.drug_waste import DrugWaste

    query = db.query(DrugWaste)
    if hospital_id:
        query = query.filter(DrugWaste.hospital_id == hospital_id)
    if start_date:
        query = query.filter(DrugWaste.created_at >= start_date)
    if end_date:
        query = query.filter(DrugWaste.created_at <= end_date)

    records = query.order_by(DrugWaste.created_at.desc()).all()
    return ApiResponse(data={
        "records": records,
        "total": len(records),
        "total_wasted_mbq": sum(r.wasted_activity_mbq or 0 for r in records)
    })
