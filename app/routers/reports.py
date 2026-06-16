from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
from io import BytesIO

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.reports import (
    ReportType, ReportFormat, ReportQueryParams, ReportExportRequest,
    TurnoverEfficiencyReport, DrugUtilizationReport,
    ReferralCompletionReport, DailyOperationReport
)
from app.services import ReportService
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_reports")


@router.get("/turnover-efficiency", response_model=ApiResponse[TurnoverEfficiencyReport])
def get_turnover_efficiency_report(
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = "daily",
    include_details: bool = False,
    compare_with_previous_period: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成周转效率报表"""
    service = ReportService(db)
    params = ReportQueryParams(
        report_type=ReportType.TURNOVER_EFFICIENCY,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        include_details=include_details
    )
    report = service.generate_turnover_efficiency_report(params)
    return ApiResponse(data=report, message="周转效率报表生成成功")


@router.get("/drug-utilization", response_model=ApiResponse[DrugUtilizationReport])
def get_drug_utilization_report(
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = "daily",
    include_details: bool = False,
    compare_with_previous_period: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成药物利用率报表"""
    service = ReportService(db)
    params = ReportQueryParams(
        report_type=ReportType.DRUG_UTILIZATION,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        include_details=include_details
    )
    report = service.generate_drug_utilization_report(params)
    return ApiResponse(data=report, message="药物利用率报表生成成功")


@router.get("/referral-completion", response_model=ApiResponse[ReferralCompletionReport])
def get_referral_completion_report(
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = "daily",
    include_details: bool = False,
    compare_with_previous_period: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成转诊完成率报表"""
    service = ReportService(db)
    params = ReportQueryParams(
        report_type=ReportType.REFERRAL_COMPLETION,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        include_details=include_details
    )
    report = service.generate_referral_completion_report(params)
    return ApiResponse(data=report, message="转诊完成率报表生成成功")


@router.get("/daily-operation", response_model=ApiResponse[DailyOperationReport])
def get_daily_operation_report(
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = "daily",
    include_details: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成每日运营报表"""
    service = ReportService(db)
    params = ReportQueryParams(
        report_type=ReportType.DAILY_OPERATION,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        include_details=include_details
    )
    report = service.generate_daily_operation_report(params)
    return ApiResponse(data=report, message="每日运营报表生成成功")


@router.get("/risk-analysis", response_model=ApiResponse)
def get_risk_analysis_report(
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成风险分析报表"""
    service = ReportService(db)
    params = ReportQueryParams(
        report_type=ReportType.RISK_ANALYSIS,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        granularity="daily"
    )
    report = service.generate_risk_analysis_report(params)
    return ApiResponse(data=report, message="风险分析报表生成成功")


@router.post("/export")
def export_report(
    export_request: ReportExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出报表（支持Excel/PDF/JSON）"""
    service = ReportService(db)
    file_content, filename, media_type = service.export_report(export_request)

    return StreamingResponse(
        BytesIO(file_content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/kpi-dashboard", response_model=ApiResponse)
def get_kpi_dashboard(
    hospital_id: Optional[int] = None,
    period: Optional[str] = None,
    date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取KPI仪表盘数据"""
    service = ReportService(db)
    dashboard = service.get_kpi_dashboard(hospital_id, date)
    return ApiResponse(data=dashboard)


@router.get("/comparison/hospitals", response_model=ApiResponse)
def get_hospital_comparison(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """院区横向对比报表"""
    service = ReportService(db)
    comparison = service.get_hospital_comparison_report(start_date, end_date)
    return ApiResponse(data=comparison, message="院区对比报表生成成功")


@router.get("/trends/{report_type}", response_model=ApiResponse)
def get_trend_data(
    report_type: ReportType,
    hospital_id: Optional[int] = None,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取趋势数据"""
    service = ReportService(db)
    trends = service.get_trend_data(report_type, hospital_id, start_date, end_date)
    return ApiResponse(data=trends)
