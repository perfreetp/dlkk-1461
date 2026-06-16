from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.reschedule import (
    BatchRescheduleRequest, BatchRescheduleResult,
    EquipmentDowntimeRequest, DrugDelayRequest,
    EmergencyPlusRequest
)
from app.services import RescheduleService
from app.utils.auth import get_current_active_user
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_reschedule")


@router.post("/equipment-downtime", response_model=ApiResponse[BatchRescheduleResult])
def handle_equipment_downtime(
    request: EquipmentDowntimeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """处理设备停机 - 自动识别受影响预约并批量重排"""
    service = RescheduleService(db)
    if not request.operator:
        request.operator = current_user.real_name
    result = service.handle_equipment_downtime(request)
    return ApiResponse(
        data=result,
        message=f"设备停机处理完成，影响{result.total_count}条预约"
    )


@router.post("/drug-delay", response_model=ApiResponse[BatchRescheduleResult])
def handle_drug_delay(
    request: DrugDelayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """处理药物到货延迟 - 顺延注射时间或批量改期"""
    service = RescheduleService(db)
    if not request.operator:
        request.operator = current_user.real_name
    result = service.handle_drug_delay(request)
    return ApiResponse(
        data=result,
        message=f"药物延迟处理完成，影响{result.total_count}条预约"
    )


@router.post("/emergency-plus", response_model=ApiResponse[BatchRescheduleResult])
def handle_emergency_plus(
    request: EmergencyPlusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """处理突发加号 - 创建加号并调整现有队列"""
    service = RescheduleService(db)
    if not request.operator:
        request.operator = current_user.real_name
    result = service.handle_emergency_plus(request)
    return ApiResponse(
        data=result,
        message="突发加号处理完成，队列已调整"
    )


@router.post("/batch", response_model=ApiResponse[BatchRescheduleResult])
def batch_reschedule(
    request: BatchRescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量重排预约 - 支持5种重排策略"""
    service = RescheduleService(db)
    if not request.operator:
        request.operator = current_user.real_name
    result = service.batch_reschedule(request)
    return ApiResponse(
        data=result,
        message=f"批量重排完成，成功{result.success_count}条，失败{result.failed_count}条"
    )


@router.post("/simulate", response_model=ApiResponse[BatchRescheduleResult])
def simulate_reschedule(
    request: BatchRescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """模拟重排（不实际执行）"""
    service = RescheduleService(db)
    request.dry_run = True
    if not request.operator:
        request.operator = current_user.real_name
    result = service.batch_reschedule(request)
    return ApiResponse(
        data=result,
        message=f"模拟重排完成，预计影响{result.total_count}条预约"
    )


@router.get("/affected/equipment/{equipment_id}", response_model=ApiResponse)
def get_equipment_downtime_affected(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """预览设备停机影响的预约"""
    service = RescheduleService(db)
    affected = service.preview_equipment_downtime_affected(equipment_id)
    return ApiResponse(data={"affected": affected, "count": len(affected)})


@router.get("/affected/drug/{hospital_id}/{tracer_id}", response_model=ApiResponse)
def get_drug_delay_affected(
    hospital_id: int,
    tracer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """预览药物延迟影响的预约"""
    service = RescheduleService(db)
    affected = service.preview_drug_delay_affected(hospital_id, tracer_id)
    return ApiResponse(data={"affected": affected, "count": len(affected)})


@router.post("/confirm/{reschedule_batch_id}", response_model=ApiResponse)
def confirm_reschedule(
    reschedule_batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """确认执行重排方案"""
    service = RescheduleService(db)
    result = service.confirm_reschedule(reschedule_batch_id, current_user.real_name)
    return ApiResponse(data=result, message="重排方案已确认执行")
