from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.exceptions import ValidationError
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.appointment import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    AppointmentCategorizeResponse, AppointmentQueryParams,
    AppointmentBatchCreate, PlusSignRequest, AppointmentStatus,
    AppointmentListResponse, ExamPurpose, UrgencyLevel
)
from app.schemas.reschedule import RescheduleRequest, RescheduleResult
from app.services import AppointmentService, RescheduleService
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_appointment")


@router.get("", response_model=ApiResponse[PaginatedResponse[AppointmentListResponse]])
def list_appointments(
    query_params: AppointmentQueryParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预约列表，支持多维度筛选"""
    service = AppointmentService(db)
    appointments, total = service.get_appointments(
        query_params=query_params,
        offset=pagination.offset,
        limit=pagination.limit
    )

    items = []
    for apt in appointments:
        item = AppointmentListResponse.model_validate(apt)
        if apt.patient:
            item.patient_name = apt.patient.name
        if apt.hospital:
            item.hospital_name = apt.hospital.name
        if apt.equipment:
            item.equipment_name = apt.equipment.name
        items.append(item)

    return ApiResponse(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{appointment_id}", response_model=ApiResponse[AppointmentResponse])
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预约详情"""
    service = AppointmentService(db)
    appointment = service.get_appointment_by_id(appointment_id)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment))


class _CategorizeRequest(BaseModel):
    appointment_ids: Optional[List[int]] = None
    patient_id: Optional[int] = None
    hospital_id: Optional[int] = None
    exam_purpose: Optional[ExamPurpose] = None
    appointment_date: Optional[date] = None
    urgency_level: Optional[UrgencyLevel] = None
    is_inpatient: Optional[bool] = None
    needs_anesthesia: Optional[bool] = None
    tracer_type: Optional[str] = None


@router.post("/categorize", response_model=ApiResponse)
def categorize_appointment(
    request_data: _CategorizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """预约请求多维度归类（检查目的、紧急度、住院/麻醉等）"""
    service = AppointmentService(db)

    if request_data.appointment_ids:
        results = []
        for apt_id in request_data.appointment_ids:
            apt = service.get_appointment_by_id(apt_id)
            if apt:
                apt_create = AppointmentCreate(
                    patient_id=apt.patient_id,
                    hospital_id=apt.hospital_id,
                    exam_purpose=apt.exam_purpose,
                    appointment_date=apt.appointment_date,
                    urgency_level=apt.urgency_level,
                    is_inpatient=apt.is_inpatient,
                    needs_anesthesia=apt.needs_anesthesia,
                    tracer_type=apt.tracer_type
                )
                patient = service._get_patient(apt.patient_id)
                result = service.categorize_appointment(apt_create, patient)
                result_dict = result.model_dump()
                result_dict["appointment_id"] = apt_id
                results.append(result_dict)
        return ApiResponse(data=results, message="批量归类完成")

    elif request_data.patient_id and request_data.hospital_id and request_data.exam_purpose and request_data.appointment_date:
        apt_create = AppointmentCreate(
            patient_id=request_data.patient_id,
            hospital_id=request_data.hospital_id,
            exam_purpose=request_data.exam_purpose,
            appointment_date=request_data.appointment_date,
            urgency_level=request_data.urgency_level or UrgencyLevel.NORMAL,
            is_inpatient=request_data.is_inpatient or False,
            needs_anesthesia=request_data.needs_anesthesia or False,
            tracer_type=request_data.tracer_type or "fdg"
        )
        patient = service._get_patient(request_data.patient_id)
        result = service.categorize_appointment(apt_create, patient)
        return ApiResponse(data=result, message="归类完成")

    else:
        raise ValidationError("请提供appointment_ids或完整的预约信息")


@router.post("", response_model=ApiResponse[AppointmentResponse])
def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建预约，自动归类并分配优先级"""
    service = AppointmentService(db)
    appointment, categorize_result = service.create_appointment(appointment_data, current_user)
    return ApiResponse(
        data=AppointmentResponse.model_validate(appointment),
        message=f"预约创建成功，优先级评分: {categorize_result.priority_score}"
    )


@router.post("/batch", response_model=ApiResponse)
def batch_create_appointments(
    batch_data: AppointmentBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量创建预约"""
    service = AppointmentService(db)
    result = service.batch_create_appointments(batch_data, current_user)
    return ApiResponse(data=result, message=f"批量创建完成，成功{result['success']}条，失败{result['failed']}条")


@router.put("/{appointment_id}", response_model=ApiResponse[AppointmentResponse])
def update_appointment(
    appointment_id: int,
    update_data: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新预约信息"""
    service = AppointmentService(db)
    appointment = service.update_appointment(appointment_id, update_data)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="更新成功")


@router.post("/plus-sign", response_model=ApiResponse[AppointmentResponse])
def create_plus_sign(
    plus_request: PlusSignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建加号预约"""
    service = RescheduleService(db)
    appointment = service.handle_emergency_plus(plus_request)
    return ApiResponse(
        data=AppointmentResponse.model_validate(appointment),
        message="加号成功，队列已自动调整"
    )


@router.post("/{appointment_id}/reschedule", response_model=ApiResponse[RescheduleResult])
def reschedule_appointment(
    appointment_id: int,
    reschedule_data: RescheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """改期单个预约"""
    reschedule_data.appointment_id = appointment_id
    service = RescheduleService(db)
    result = service.single_reschedule(reschedule_data)
    return ApiResponse(data=result, message="改期操作完成")


@router.put("/{appointment_id}/status", response_model=ApiResponse[AppointmentResponse])
def update_appointment_status(
    appointment_id: int,
    status: AppointmentStatus,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新预约状态"""
    service = AppointmentService(db)
    appointment = service.update_status(appointment_id, status, reason, current_user.real_name)
    return ApiResponse(data=AppointmentResponse.model_validate(appointment), message="状态更新成功")


@router.get("/queue/{hospital_id}/{appointment_date}", response_model=ApiResponse)
def get_daily_queue(
    hospital_id: int,
    appointment_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取某日排队队列"""
    service = AppointmentService(db)
    queue = service.get_daily_queue(hospital_id, appointment_date)
    return ApiResponse(data={"queue": queue, "total": len(queue)})


@router.get("/statistics/daily", response_model=ApiResponse)
def get_daily_statistics(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预约每日统计"""
    service = AppointmentService(db)
    stats = service.get_daily_statistics(hospital_id, start_date, end_date)
    return ApiResponse(data=stats)
