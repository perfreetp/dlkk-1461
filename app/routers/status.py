from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.status_record import (
    CheckInRequest, InjectionRequest, ScanStartRequest,
    CompletionRequest, CancellationRequest, StatusRecordResponse
)
from app.schemas.appointment import AppointmentResponse
from app.services import StatusService
from app.utils.auth import get_current_active_user
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_status")


@router.post("/checkin", response_model=ApiResponse[AppointmentResponse])
def record_checkin(
    request: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """记录患者签到 - 状态回传第一节点"""
    service = StatusService(db)
    if not request.recorded_by:
        request.recorded_by = current_user.real_name
    appointment = service.check_in(request)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="签到成功")


@router.post("/injection", response_model=ApiResponse[AppointmentResponse])
def record_injection(
    request: InjectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """记录示踪剂注射 - 状态回传第二节点"""
    service = StatusService(db)
    if not request.recorded_by:
        request.recorded_by = current_user.real_name
    appointment = service.record_injection(request)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="注射记录成功")


@router.post("/scan-start", response_model=ApiResponse[AppointmentResponse])
def record_scan_start(
    request: ScanStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """记录扫描开始（入机）- 状态回传第三节点"""
    service = StatusService(db)
    if not request.recorded_by:
        request.recorded_by = current_user.real_name
    appointment = service.record_scan_start(request)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="扫描开始记录成功")


@router.post("/completion", response_model=ApiResponse[AppointmentResponse])
def record_completion(
    request: CompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """记录检查完成 - 状态回传第四节点"""
    service = StatusService(db)
    if not request.recorded_by:
        request.recorded_by = current_user.real_name
    appointment = service.record_completion(request)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="检查完成记录成功")


@router.post("/cancellation", response_model=ApiResponse[AppointmentResponse])
def record_cancellation(
    request: CancellationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """记录预约取消 - 状态回传第五节点"""
    service = StatusService(db)
    if not request.cancelled_by:
        request.cancelled_by = current_user.real_name
    appointment = service.record_cancellation(request)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="取消记录成功")


@router.get("/appointment/{appointment_id}", response_model=ApiResponse)
def get_appointment_status_history(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预约的完整状态历史"""
    service = StatusService(db)
    history = service.get_appointment_status_history(appointment_id)
    return ApiResponse(data={"history": history, "total": len(history)})


@router.get("/today/{hospital_id}", response_model=ApiResponse)
def get_today_status_summary(
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取今日状态统计摘要"""
    service = StatusService(db)
    summary = service.get_today_status_summary(hospital_id)
    return ApiResponse(data=summary)


@router.get("/timeline/{appointment_id}", response_model=ApiResponse)
def get_appointment_timeline(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预约时间线（各节点耗时分析）"""
    service = StatusService(db)
    timeline = service.get_appointment_timeline(appointment_id)
    return ApiResponse(data=timeline)


@router.post("/sync", response_model=ApiResponse)
def sync_status_from_hospital(
    status_records: list[dict],
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """从院区同步状态记录（批量）"""
    service = StatusService(db)
    result = service.sync_status_records(hospital_id, status_records)
    return ApiResponse(data=result, message=f"同步完成，成功{result.get('success', 0)}条")
