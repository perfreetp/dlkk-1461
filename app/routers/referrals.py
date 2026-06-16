from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.referral import (
    ReferralCreate, ReferralUpdate, ReferralResponse,
    ReferralAutoAssignRequest, ReferralAutoAssignResponse,
    ReferralQueryParams, ReferralStatus, ReferralNetworkStatus
)
from app.services import ReferralService
from app.utils.auth import get_current_active_user
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_referrals")


@router.get("", response_model=ApiResponse[PaginatedResponse[ReferralResponse]])
def list_referrals(
    query_params: ReferralQueryParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取转诊列表"""
    service = ReferralService(db)
    referrals, total = service.get_referrals(
        query_params=query_params,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[ReferralResponse.model_validate(r) for r in referrals],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{referral_id}", response_model=ApiResponse[ReferralResponse])
def get_referral(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取转诊详情"""
    service = ReferralService(db)
    referral = service.get_referral_by_id(referral_id)
    return ApiResponse(data=ReferralResponse.model_validate(referral))


@router.post("", response_model=ApiResponse[ReferralResponse])
def create_referral(
    referral_data: ReferralCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建转诊申请"""
    service = ReferralService(db)
    referral = service.create_referral(referral_data, current_user.id)
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="转诊申请创建成功")


@router.put("/{referral_id}", response_model=ApiResponse[ReferralResponse])
def update_referral(
    referral_id: int,
    update_data: ReferralUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新转诊信息"""
    service = ReferralService(db)
    referral = service.update_referral(referral_id, update_data)
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="转诊信息更新成功")


@router.post("/auto-assign", response_model=ApiResponse[ReferralAutoAssignResponse])
def auto_assign_referral(
    request: ReferralAutoAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """同城转诊智能分配 - 自动给出就近院区与可接纳时段"""
    service = ReferralService(db)
    result = service.auto_assign_referral(
        patient_id=request.patient_id,
        patient_lat=request.patient_lat,
        patient_lng=request.patient_lng,
        preferred_date=request.preferred_date,
        exam_purpose=request.exam_purpose,
        urgency_level=request.urgency_level,
        needs_anesthesia=request.needs_anesthesia,
        tracer_type=request.tracer_type,
        exclude_hospital_ids=request.exclude_hospital_ids
    )
    return ApiResponse(data=result, message="智能分配完成")


@router.post("/{referral_id}/accept", response_model=ApiResponse[ReferralResponse])
def accept_referral(
    referral_id: int,
    accepted_by: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """接受转诊"""
    service = ReferralService(db)
    referral = service.accept_referral(
        referral_id=referral_id,
        accepted_by=accepted_by or current_user.real_name,
        notes=notes
    )
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="转诊已接受")


@router.post("/{referral_id}/decline", response_model=ApiResponse[ReferralResponse])
def decline_referral(
    referral_id: int,
    decline_reason: str,
    declined_by: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """拒绝转诊"""
    service = ReferralService(db)
    referral = service.decline_referral(
        referral_id=referral_id,
        decline_reason=decline_reason,
        declined_by=declined_by or current_user.real_name
    )
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="转诊已拒绝")


@router.post("/{referral_id}/complete", response_model=ApiResponse[ReferralResponse])
def complete_referral(
    referral_id: int,
    appointment_id: Optional[int] = None,
    completion_notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """完成转诊"""
    service = ReferralService(db)
    referral = service.complete_referral(
        referral_id=referral_id,
        appointment_id=appointment_id,
        completion_notes=completion_notes,
        completed_by=current_user.real_name
    )
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="转诊已完成")


@router.put("/{referral_id}/status", response_model=ApiResponse[ReferralResponse])
def update_referral_status(
    referral_id: int,
    status: ReferralStatus,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新转诊状态"""
    service = ReferralService(db)
    referral = service.update_referral_status(
        referral_id=referral_id,
        status=status,
        reason=reason,
        operator=current_user.real_name
    )
    return ApiResponse(data=ReferralResponse.model_validate(referral), message="状态更新成功")


@router.get("/network/status", response_model=ApiResponse[ReferralNetworkStatus])
def get_referral_network_status(
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取转诊网络整体状态"""
    service = ReferralService(db)
    status = service.get_referral_network_status(target_date)
    return ApiResponse(data=status)


@router.get("/alternatives/{referral_id}", response_model=ApiResponse)
def get_alternative_hospitals(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取转诊备选院区列表"""
    service = ReferralService(db)
    alternatives = service.get_alternative_hospitals(referral_id)
    return ApiResponse(data={"alternatives": alternatives, "total": len(alternatives)})


@router.get("/patient/{patient_id}", response_model=ApiResponse)
def get_patient_referral_history(
    patient_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者转诊历史"""
    service = ReferralService(db)
    history = service.get_patient_referral_history(patient_id, start_date, end_date)
    return ApiResponse(data={"history": history, "total": len(history)})


@router.post("/batch/auto-assign", response_model=ApiResponse)
def batch_auto_assign(
    referral_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量智能分配转诊"""
    service = ReferralService(db)
    results = service.batch_auto_assign(referral_ids)
    return ApiResponse(data=results, message=f"批量分配完成，成功{results.get('success', 0)}条")
