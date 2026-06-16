from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.notification import (
    NotificationResponse, NotificationSendRequest,
    ReceiptGenerateRequest, RescheduleNotificationRequest,
    PreparationReminderRequest, NotificationType, NotificationChannel
)
from app.services import NotificationService
from app.utils.auth import get_current_active_user
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("router_notifications")


@router.get("", response_model=ApiResponse[PaginatedResponse[NotificationResponse]])
def list_notifications(
    hospital_id: Optional[int] = None,
    notification_type: Optional[NotificationType] = None,
    channel: Optional[NotificationChannel] = None,
    is_sent: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取通知列表"""
    service = NotificationService(db)
    notifications, total = service.get_notifications(
        hospital_id=hospital_id,
        notification_type=notification_type,
        channel=channel,
        is_sent=is_sent,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return ApiResponse(
        data=PaginatedResponse(
            items=[NotificationResponse.model_validate(n) for n in notifications],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{notification_id}", response_model=ApiResponse[NotificationResponse])
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取通知详情"""
    service = NotificationService(db)
    notification = service.get_notification_by_id(notification_id)
    return ApiResponse(data=NotificationResponse.model_validate(notification))


@router.post("/receipt", response_model=ApiResponse)
def generate_appointment_receipt(
    request: ReceiptGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成院区回执"""
    service = NotificationService(db)
    receipt = service.generate_appointment_receipt(
        appointment_id=request.appointment_id,
        template=request.template,
        include_preparation=request.include_preparation,
        include_checklist=request.include_checklist
    )
    return ApiResponse(data=receipt, message="回执生成成功")


@router.post("/reschedule", response_model=ApiResponse)
def send_reschedule_notification(
    request: RescheduleNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """发送改期通知"""
    service = NotificationService(db)
    result = service.send_reschedule_notification(
        appointment_id=request.appointment_id,
        old_date=request.old_date,
        old_time_slot=request.old_time_slot,
        new_date=request.new_date,
        new_time_slot=request.new_time_slot,
        new_hospital_name=request.new_hospital_name,
        reason=request.reason,
        channels=request.channels,
        notify_patient=request.notify_patient,
        notify_hospital=request.notify_hospital,
        notify_department=request.notify_department
    )
    return ApiResponse(data=result, message="改期通知已发送")


@router.post("/preparation-reminder", response_model=ApiResponse)
def send_preparation_reminder(
    request: PreparationReminderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """发送检查前准备提醒"""
    service = NotificationService(db)
    result = service.send_preparation_reminder(
        appointment_ids=request.appointment_ids,
        reminder_days_before=request.reminder_days_before,
        channels=request.channels,
        include_custom_message=request.include_custom_message,
        custom_message=request.custom_message
    )
    return ApiResponse(data=result, message=f"准备提醒已发送，成功{result.get('success', 0)}条")


@router.post("/send", response_model=ApiResponse[NotificationResponse])
def send_notification(
    request: NotificationSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """发送自定义通知"""
    service = NotificationService(db)
    notification = service.create_notification(
        recipient_type=request.recipient_type,
        recipient_id=request.recipient_id,
        recipient_phone=request.recipient_phone,
        recipient_email=request.recipient_email,
        notification_type=request.notification_type,
        channel=request.channel,
        title=request.title,
        content=request.content,
        hospital_id=request.hospital_id,
        appointment_id=request.appointment_id,
        priority=request.priority,
        scheduled_send_time=request.scheduled_send_time,
        created_by=current_user.real_name
    )
    return ApiResponse(data=NotificationResponse.model_validate(notification), message="通知已创建")


@router.post("/{notification_id}/resend", response_model=ApiResponse[NotificationResponse])
def resend_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """重发通知"""
    service = NotificationService(db)
    notification = service.resend_notification(notification_id)
    return ApiResponse(data=NotificationResponse.model_validate(notification), message="通知已重发")


@router.get("/receipt/{appointment_id}/print", response_model=ApiResponse)
def get_printable_receipt(
    appointment_id: int,
    template: str = "standard",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取可打印的回执"""
    service = NotificationService(db)
    receipt = service.get_printable_receipt(appointment_id, template)
    return ApiResponse(data=receipt)


@router.post("/batch/send", response_model=ApiResponse)
def batch_send_notifications(
    notification_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量发送通知"""
    service = NotificationService(db)
    result = service.batch_send_notifications(notification_ids)
    return ApiResponse(data=result, message=f"批量发送完成，成功{result.get('success', 0)}条")
