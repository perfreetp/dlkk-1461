from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.alert import (
    AlertResponse, AlertQueryParams, AlertAcknowledgeRequest,
    AlertResolveRequest, AlertType, AlertSeverity
)
from app.services import AlertService
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_alerts")


@router.get("", response_model=ApiResponse[PaginatedResponse[AlertResponse]])
def list_alerts(
    query_params: AlertQueryParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预警列表"""
    service = AlertService(db)
    alerts, total = service.get_alerts(
        query_params=query_params,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[AlertResponse.model_validate(a) for a in alerts],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{alert_id}", response_model=ApiResponse[AlertResponse])
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预警详情"""
    service = AlertService(db)
    alert = service.get_alert_by_id(alert_id)
    return ApiResponse(data=AlertResponse.model_validate(alert))


@router.post("/scan", response_model=ApiResponse)
def run_monitoring_scan(
    hospital_id: Optional[int] = None,
    scan_types: Optional[List[AlertType]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """手动执行风险监控扫描"""
    service = AlertService(db)
    results = service.run_monitoring_cycle(hospital_id=hospital_id, scan_types=scan_types)
    return ApiResponse(data=results, message="风险扫描完成")


@router.post("/{alert_id}/acknowledge", response_model=ApiResponse[AlertResponse])
def acknowledge_alert(
    alert_id: int,
    request: AlertAcknowledgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """确认预警（标记为已读）"""
    service = AlertService(db)
    alert = service.acknowledge_alert(alert_id, current_user.real_name, request.acknowledge_notes)
    return ApiResponse(data=AlertResponse.model_validate(alert), message="预警已确认")


@router.post("/{alert_id}/resolve", response_model=ApiResponse[AlertResponse])
def resolve_alert(
    alert_id: int,
    request: AlertResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """解决预警"""
    service = AlertService(db)
    alert = service.resolve_alert(
        alert_id=alert_id,
        resolution=request.resolution,
        resolved_by=current_user.real_name,
        resolution_details=request.resolution_details
    )
    return ApiResponse(data=AlertResponse.model_validate(alert), message="预警已解决")


@router.get("/summary/dashboard", response_model=ApiResponse)
def get_alert_dashboard(
    hospital_id: Optional[int] = None,
    date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取预警仪表盘摘要"""
    service = AlertService(db)
    summary = service.get_alert_dashboard_summary(hospital_id, date)
    return ApiResponse(data=summary)


@router.get("/rules/list", response_model=ApiResponse)
def get_monitoring_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取所有监控规则列表"""
    service = AlertService(db)
    rules = service.get_monitoring_rules()
    return ApiResponse(data={"rules": rules})


@router.post("/{alert_id}/escalate", response_model=ApiResponse[AlertResponse])
def escalate_alert(
    alert_id: int,
    escalation_level: int = Query(..., ge=1, le=3, description="升级级别 1-3"),
    escalation_reason: str = Query(..., description="升级原因"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """升级预警"""
    service = AlertService(db)
    alert = service.escalate_alert(
        alert_id=alert_id,
        escalation_level=escalation_level,
        escalation_reason=escalation_reason,
        escalated_by=current_user.real_name
    )
    return ApiResponse(data=AlertResponse.model_validate(alert), message="预警已升级")


@router.get("/history/{patient_id}", response_model=ApiResponse)
def get_patient_alert_history(
    patient_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者预警历史"""
    service = AlertService(db)
    history = service.get_patient_alert_history(patient_id, start_date, end_date)
    return ApiResponse(data={"history": history, "total": len(history)})
