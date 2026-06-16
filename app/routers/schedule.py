from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.schedule import (
    ScheduleTemplateCreate, ScheduleTemplateUpdate, ScheduleTemplateResponse,
    ShiftAssignmentCreate, ShiftAssignmentUpdate, ShiftAssignmentResponse,
    SupportPlanCreate, SupportPlanUpdate, SupportPlanResponse, SupportPlanApproveRequest,
    ShiftSwapRequest, ShiftSwapApproveRequest, HolidayTemplateGenerateRequest,
    WeeklyScheduleGenerateRequest, TemplateType
)
from app.services import ScheduleManagementService
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_schedule")


@router.get("/templates", response_model=ApiResponse[PaginatedResponse[ScheduleTemplateResponse]])
def list_templates(
    hospital_id: Optional[int] = None,
    template_type: Optional[TemplateType] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取排班模板列表"""
    service = ScheduleManagementService(db)
    templates, total = service.get_templates(
        hospital_id=hospital_id,
        template_type=template_type,
        is_active=is_active,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[ScheduleTemplateResponse.model_validate(t) for t in templates],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/templates/{template_id}", response_model=ApiResponse[ScheduleTemplateResponse])
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取排班模板详情"""
    service = ScheduleManagementService(db)
    template = service.get_template_by_id(template_id)
    return ApiResponse(data=ScheduleTemplateResponse.model_validate(template))


@router.post("/templates", response_model=ApiResponse[ScheduleTemplateResponse])
def create_template(
    template_data: ScheduleTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """创建排班模板"""
    service = ScheduleManagementService(db)
    template = service.create_template(template_data, current_user.id)
    return ApiResponse(data=ScheduleTemplateResponse.model_validate(template), message="模板创建成功")


@router.put("/templates/{template_id}", response_model=ApiResponse[ScheduleTemplateResponse])
def update_template(
    template_id: int,
    update_data: ScheduleTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """更新排班模板"""
    service = ScheduleManagementService(db)
    template = service.update_template(template_id, update_data)
    return ApiResponse(data=ScheduleTemplateResponse.model_validate(template), message="模板更新成功")


@router.delete("/templates/{template_id}", response_model=ApiResponse)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """删除排班模板"""
    service = ScheduleManagementService(db)
    service.delete_template(template_id)
    return ApiResponse(message="模板删除成功")


@router.get("/templates/applicable/{target_date}", response_model=ApiResponse[ScheduleTemplateResponse])
def get_applicable_template(
    target_date: date,
    hospital_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取指定日期适用的排班模板"""
    service = ScheduleManagementService(db)
    template = service.get_applicable_template(hospital_id, target_date)
    return ApiResponse(data=ScheduleTemplateResponse.model_validate(template))


@router.post("/templates/generate-holiday", response_model=ApiResponse[ScheduleTemplateResponse])
def generate_holiday_template(
    request: HolidayTemplateGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """生成节假日排班模板"""
    service = ScheduleManagementService(db)
    template = service.generate_holiday_template(
        hospital_id=request.hospital_id,
        holiday_name=request.holiday_name,
        holiday_date=request.holiday_date,
        capacity_ratio=request.capacity_ratio,
        based_on_template_id=request.based_on_template_id
    )
    return ApiResponse(data=ScheduleTemplateResponse.model_validate(template), message="节假日模板生成成功")


@router.get("/shifts", response_model=ApiResponse[PaginatedResponse[ShiftAssignmentResponse]])
def list_shifts(
    hospital_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取班次分配列表"""
    service = ScheduleManagementService(db)
    shifts, total = service.get_shift_assignments(
        hospital_id=hospital_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[ShiftAssignmentResponse.model_validate(s) for s in shifts],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.post("/shifts", response_model=ApiResponse[ShiftAssignmentResponse])
def create_shift(
    shift_data: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """创建班次分配"""
    service = ScheduleManagementService(db)
    shift = service.create_shift_assignment(shift_data)
    return ApiResponse(data=ShiftAssignmentResponse.model_validate(shift), message="班次分配成功")


@router.put("/shifts/{shift_id}", response_model=ApiResponse[ShiftAssignmentResponse])
def update_shift(
    shift_id: int,
    update_data: ShiftAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """更新班次分配"""
    service = ScheduleManagementService(db)
    shift = service.update_shift_assignment(shift_id, update_data)
    return ApiResponse(data=ShiftAssignmentResponse.model_validate(shift), message="班次更新成功")


@router.post("/shifts/swap/request", response_model=ApiResponse)
def request_shift_swap(
    request: ShiftSwapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """申请换班"""
    service = ScheduleManagementService(db)
    result = service.request_shift_swap(
        requesting_user_id=current_user.id,
        target_user_id=request.target_user_id,
        shift_id_1=request.shift_id_1,
        shift_id_2=request.shift_id_2,
        reason=request.reason
    )
    return ApiResponse(data=result, message="换班申请已提交")


@router.post("/shifts/swap/approve", response_model=ApiResponse)
def approve_shift_swap(
    request: ShiftSwapApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """审批换班"""
    service = ScheduleManagementService(db)
    result = service.approve_shift_swap(
        swap_request_id=request.swap_request_id,
        approved=request.approved,
        approver_id=current_user.id,
        approval_notes=request.approval_notes
    )
    return ApiResponse(data=result, message="换班审批完成")


@router.get("/support-plans", response_model=ApiResponse[PaginatedResponse[SupportPlanResponse]])
def list_support_plans(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    is_approved: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取临时支援方案列表"""
    service = ScheduleManagementService(db)
    plans, total = service.get_support_plans(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        is_approved=is_approved,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[SupportPlanResponse.model_validate(p) for p in plans],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.post("/support-plans", response_model=ApiResponse[SupportPlanResponse])
def create_support_plan(
    plan_data: SupportPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """创建临时支援方案"""
    service = ScheduleManagementService(db)
    plan = service.create_support_plan(plan_data, current_user.id)
    return ApiResponse(data=SupportPlanResponse.model_validate(plan), message="支援方案创建成功")


@router.post("/support-plans/{plan_id}/approve", response_model=ApiResponse[SupportPlanResponse])
def approve_support_plan(
    plan_id: int,
    request: SupportPlanApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """审批临时支援方案"""
    service = ScheduleManagementService(db)
    plan = service.approve_support_plan(
        plan_id=plan_id,
        approved=request.approved,
        approver_id=current_user.id,
        approval_notes=request.approval_notes,
        additional_capacity=request.additional_capacity
    )
    return ApiResponse(data=SupportPlanResponse.model_validate(plan), message="支援方案审批完成")


@router.get("/support-plans/active/{target_date}", response_model=ApiResponse)
def get_active_support_plans(
    target_date: date,
    hospital_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取指定日期有效的支援方案"""
    service = ScheduleManagementService(db)
    plans = service.get_active_support_plans(target_date, hospital_id)
    return ApiResponse(data={"plans": plans, "total": len(plans)})


@router.post("/weekly/generate", response_model=ApiResponse)
def generate_weekly_schedule(
    request: WeeklyScheduleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor"]))
):
    """生成周排班"""
    service = ScheduleManagementService(db)
    schedule = service.generate_weekly_schedule(
        hospital_id=request.hospital_id,
        week_start_date=request.week_start_date,
        user_ids=request.user_ids,
        auto_assign=request.auto_assign
    )
    return ApiResponse(data=schedule, message="周排班生成成功")


@router.get("/weekly/{hospital_id}/{week_start_date}", response_model=ApiResponse)
def get_weekly_schedule(
    hospital_id: int,
    week_start_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取周排班详情"""
    service = ScheduleManagementService(db)
    schedule = service.get_weekly_schedule(hospital_id, week_start_date)
    return ApiResponse(data=schedule)
