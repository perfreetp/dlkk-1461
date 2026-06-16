from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.services import SchedulingService
from app.utils.auth import get_current_active_user
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_scheduling")


@router.get("/capacity/{hospital_id}", response_model=ApiResponse)
def get_hospital_capacity(
    hospital_id: int,
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取院区容量实时状态"""
    service = SchedulingService(db)
    status = service.get_hospital_capacity_status(hospital_id, target_date)
    return ApiResponse(data=status, message="容量状态获取成功")


@router.get("/capacity/network", response_model=ApiResponse)
def get_network_capacity(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取整个医联体网络容量状态"""
    service = SchedulingService(db)
    status = service.get_network_capacity_status(target_date)
    return ApiResponse(data=status, message="网络容量状态获取成功")


@router.post("/allocate/batch", response_model=ApiResponse)
def batch_allocate_resources(
    hospital_id: int,
    target_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量分配某日某院所有待分配预约的资源"""
    service = SchedulingService(db)
    result = service.batch_allocate_resources(hospital_id, target_date)
    return ApiResponse(data=result, message=f"批量分配完成，成功{result.get('success', 0)}条")


@router.post("/allocate/{appointment_id}", response_model=ApiResponse)
def allocate_resources(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """为预约分配号源、设备时段、示踪剂窗口"""
    service = SchedulingService(db)
    result = service.allocate_resources(appointment_id)
    return ApiResponse(data=result, message="资源分配完成")


@router.get("/slots/{hospital_id}/{target_date}", response_model=ApiResponse)
def get_available_slots(
    hospital_id: int,
    target_date: date,
    tracer_type: Optional[str] = None,
    needs_anesthesia: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取可用时段列表"""
    service = SchedulingService(db)
    slots = service.get_available_time_slots(
        hospital_id=hospital_id,
        target_date=target_date,
        tracer_type=tracer_type,
        needs_anesthesia=needs_anesthesia
    )
    return ApiResponse(data={"items": slots, "total": len(slots)})


@router.get("/tracer/windows/{hospital_id}/{target_date}", response_model=ApiResponse)
def get_tracer_windows(
    hospital_id: int,
    target_date: date,
    tracer_type: str = "fdg",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取示踪剂使用窗口"""
    service = SchedulingService(db)
    windows = service.get_tracer_usage_windows(hospital_id, target_date, tracer_type)
    return ApiResponse(data={"windows": windows})


@router.post("/daily/plan/{hospital_id}/{target_date}", response_model=ApiResponse)
def generate_daily_plan(
    hospital_id: int,
    target_date: date,
    auto_confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成每日排班计划"""
    service = SchedulingService(db)
    plan = service.generate_daily_scheduling_plan(hospital_id, target_date, auto_confirm)
    return ApiResponse(data=plan, message="每日计划生成完成")


@router.get("/equipment/load/{hospital_id}", response_model=ApiResponse)
def get_equipment_load(
    hospital_id: int,
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取设备负载情况"""
    service = SchedulingService(db)
    load = service.get_equipment_load_status(hospital_id, target_date)
    return ApiResponse(data=load)


@router.post("/queue/optimize/{hospital_id}/{target_date}", response_model=ApiResponse)
def optimize_queue(
    hospital_id: int,
    target_date: date,
    strategy: str = "priority_first",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """优化排队队列顺序"""
    service = SchedulingService(db)
    result = service.optimize_queue_order(hospital_id, target_date, strategy)
    return ApiResponse(data=result, message="队列优化完成")
