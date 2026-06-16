from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models import Appointment, Notification, Patient, Hospital, Equipment, TracerBatch
from app.schemas import (
    NotificationCreate, NotificationSendRequest,
    ReceiptGenerateRequest, RescheduleNotificationRequest,
    NotificationResponse
)
from app.utils import get_logger, get_preparation_notes, format_datetime
from app.exceptions import ValidationError, AppointmentNotFound
from app.config import get_settings

settings = get_settings()
logger = get_logger("notification_service")


class NotificationService:
    """通知系统服务 - 院区回执、改期通知、准备事项"""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        appointment_id: Optional[int] = None,
        notification_type: str = "system",
        title: str = "",
        content: str = "",
        channel: str = "system",
        recipient: Optional[str] = None,
        hospital_id: Optional[int] = None,
        user_id: Optional[int] = None,
        priority: str = "normal",
        recipient_type: str = "patient",
        recipient_name: Optional[str] = None,
        **kwargs
    ) -> Notification:
        """创建通知记录"""
        notification = Notification(
            appointment_id=appointment_id,
            hospital_id=hospital_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            content=content,
            recipient_type=recipient_type,
            recipient_name=recipient_name,
            recipient_phone=recipient,
            channel=channel,
            priority=priority,
            status="pending",
            retry_count=0,
            generated_by="system",
            generated_at=datetime.utcnow()
        )

        self.db.add(notification)
        self.db.flush()

        logger.info(
            f"创建通知: 类型={notification_type}, 标题={title}, "
            f"渠道={channel}, 接收人={recipient}"
        )

        return notification

    def generate_appointment_receipt(
        self,
        request: ReceiptGenerateRequest
    ) -> Dict[str, Any]:
        """生成院区回执"""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == request.appointment_id
        ).first()

        if not appointment:
            raise AppointmentNotFound(str(request.appointment_id))

        patient = appointment.patient
        hospital = appointment.hospital
        equipment = appointment.equipment

        if not patient or not hospital:
            raise ValidationError("预约信息不完整，无法生成回执")

        preparation_notes = ""
        if request.include_preparation:
            preparation_notes = get_preparation_notes(
                tracer_type=appointment.tracer_type,
                needs_anesthesia=appointment.needs_anesthesia,
                is_inpatient=appointment.is_inpatient,
                diabetes_type=patient.diabetes_type if hasattr(patient, 'diabetes_type') else "",
                fasting_hours=appointment.fasting_hours or 6
            )

        tracer_info = {}
        if request.include_tracer_info and appointment.tracer_batch_id:
            tracer_batch = self.db.query(TracerBatch).filter(
                TracerBatch.id == appointment.tracer_batch_id
            ).first()
            if tracer_batch:
                tracer_info = {
                    "tracer_type": appointment.tracer_type,
                    "batch_no": tracer_batch.batch_no,
                    "dose_mbq": appointment.tracer_dose_mbq,
                    "calibration_time": format_datetime(tracer_batch.calibration_time),
                    "expiry_time": format_datetime(tracer_batch.expiry_time)
                }

        receipt_data = {
            "receipt_no": f"RCP{appointment.appointment_no}",
            "generated_at": datetime.utcnow(),
            "appointment": {
                "appointment_no": appointment.appointment_no,
                "appointment_date": appointment.appointment_date,
                "time_slot": appointment.time_slot,
                "queue_number": appointment.queue_number,
                "estimated_duration_minutes": appointment.estimated_duration_minutes
            },
            "patient": {
                "patient_id": patient.id,
                "name": patient.name,
                "gender": patient.gender if hasattr(patient, 'gender') else "",
                "age": patient.age if hasattr(patient, 'age') else None,
                "phone": patient.phone if hasattr(patient, 'phone') else "",
                "id_card": patient.id_card if hasattr(patient, 'id_card') else ""
            },
            "hospital": {
                "hospital_id": hospital.id,
                "name": hospital.name,
                "address": hospital.address if hasattr(hospital, 'address') else "",
                "phone": hospital.phone if hasattr(hospital, 'phone') else "",
                "department": appointment.referring_department,
                "referring_doctor": appointment.referring_doctor
            },
            "equipment": {
                "code": equipment.code if equipment else "",
                "name": equipment.name if equipment else "",
                "room_number": equipment.room_number if equipment else ""
            } if equipment else {},
            "exam_info": {
                "exam_purpose": appointment.exam_purpose,
                "urgency_level": appointment.urgency_level,
                "clinical_diagnosis": appointment.clinical_diagnosis,
                "is_inpatient": appointment.is_inpatient,
                "needs_anesthesia": appointment.needs_anesthesia,
                "is_referral": appointment.is_referral
            },
            "tracer_info": tracer_info,
            "preparation_notes": preparation_notes,
            "checklist": self._generate_checklist(appointment),
            "contact_info": {
                "service_hotline": getattr(settings, 'SERVICE_HOTLINE', '400-123-4567'),
                "emergency_contact": getattr(settings, 'EMERGENCY_CONTACT', '120')
            }
        }

        receipt_content = self._format_receipt_content(receipt_data, request.language)

        notification = self.create_notification(
            appointment_id=appointment.id,
            notification_type="receipt",
            title="PET-CT检查预约回执",
            content=receipt_content,
            channel="system",
            recipient=patient.phone if hasattr(patient, 'phone') else None,
            hospital_id=appointment.hospital_id,
            recipient_type="patient",
            recipient_name=patient.name
        )
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"生成预约回执: 预约={appointment.appointment_no}, 回执号={receipt_data['receipt_no']}")

        return {
            "success": True,
            "receipt_no": receipt_data["receipt_no"],
            "appointment_id": appointment.id,
            "appointment_no": appointment.appointment_no,
            "format": request.format,
            "language": request.language,
            "data": receipt_data,
            "content": receipt_content,
            "notification_id": notification.id
        }

    def send_reschedule_notification(
        self,
        request: RescheduleNotificationRequest
    ) -> Dict[str, Any]:
        """发送改期通知"""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == request.appointment_id
        ).first()

        if not appointment:
            raise AppointmentNotFound(str(request.appointment_id))

        patient = appointment.patient
        old_hospital = appointment.hospital
        new_hospital = None

        if request.new_hospital_id:
            new_hospital = self.db.query(Hospital).filter(
                Hospital.id == request.new_hospital_id
            ).first()

        results = {
            "appointment_id": appointment.id,
            "appointment_no": appointment.appointment_no,
            "notifications_sent": [],
            "patient_notified": False,
            "hospital_notified": False,
            "department_notified": False
        }

        if request.notify_patient and patient:
            patient_content = self._format_patient_reschedule_content(
                appointment, request, old_hospital, new_hospital
            )

            patient_notification = self.create_notification(
                appointment_id=appointment.id,
                notification_type="reschedule",
                title="PET-CT检查时间调整通知",
                content=patient_content,
                channel="sms",
                recipient=patient.phone if hasattr(patient, 'phone') else None,
                hospital_id=request.new_hospital_id or appointment.hospital_id,
                priority="high",
                recipient_type="patient",
                recipient_name=patient.name
            )
            patient_notification.status = "sent"
            patient_notification.sent_at = datetime.utcnow()
            results["notifications_sent"].append({
                "type": "patient",
                "notification_id": patient_notification.id,
                "channel": "sms",
                "recipient": patient.phone if hasattr(patient, 'phone') else None
            })
            results["patient_notified"] = True

            logger.info(
                f"发送患者改期通知: 预约={appointment.appointment_no}, "
                f"患者={patient.name}"
            )

        if request.notify_hospital:
            hospital_content = self._format_hospital_reschedule_content(
                appointment, request, old_hospital, new_hospital
            )

            hospital_notification = self.create_notification(
                appointment_id=appointment.id,
                notification_type="hospital_notice",
                title="院区预约改期通知",
                content=hospital_content,
                channel="system",
                recipient=f"hospital_{request.new_hospital_id or appointment.hospital_id}",
                hospital_id=request.new_hospital_id or appointment.hospital_id,
                priority="normal",
                recipient_type="hospital"
            )
            hospital_notification.status = "sent"
            hospital_notification.sent_at = datetime.utcnow()
            results["notifications_sent"].append({
                "type": "hospital",
                "notification_id": hospital_notification.id,
                "channel": "system",
                "hospital_id": request.new_hospital_id or appointment.hospital_id
            })
            results["hospital_notified"] = True

            logger.info(
                f"发送院区改期通知: 预约={appointment.appointment_no}, "
                f"院区={new_hospital.name if new_hospital else old_hospital.name if old_hospital else '未知'}"
            )

        if request.notify_department and appointment.referring_department:
            dept_content = self._format_department_reschedule_content(
                appointment, request
            )

            dept_notification = self.create_notification(
                appointment_id=appointment.id,
                notification_type="department_notice",
                title="科室预约改期通知",
                content=dept_content,
                channel="system",
                recipient=f"dept_{appointment.referring_department}",
                hospital_id=appointment.hospital_id,
                priority="normal",
                recipient_type="department"
            )
            dept_notification.status = "sent"
            dept_notification.sent_at = datetime.utcnow()
            results["notifications_sent"].append({
                "type": "department",
                "notification_id": dept_notification.id,
                "channel": "system",
                "department": appointment.referring_department
            })
            results["department_notified"] = True

        self.db.commit()

        return results

    def send_preparation_reminder(
        self,
        appointment_id: int,
        hours_before: int = 24
    ) -> Dict[str, Any]:
        """发送检查前准备提醒"""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()

        if not appointment:
            raise AppointmentNotFound(str(appointment_id))

        patient = appointment.patient
        if not patient:
            raise ValidationError("患者信息不存在")

        preparation_notes = get_preparation_notes(
            tracer_type=appointment.tracer_type,
            needs_anesthesia=appointment.needs_anesthesia,
            is_inpatient=appointment.is_inpatient,
            diabetes_type=patient.diabetes_type if hasattr(patient, 'diabetes_type') else ""
        )

        reminder_content = (
            f"尊敬的{patient.name}患者，您好！\n"
            f"您的PET-CT检查将于{hours_before}小时后进行：\n"
            f"检查时间：{appointment.appointment_date} {appointment.time_slot}\n"
            f"院区：{appointment.hospital.name if appointment.hospital else ''}\n"
            f"队列号：{appointment.queue_number}\n\n"
            f"【检查前注意事项】\n"
            f"{preparation_notes}\n\n"
            f"请准时到达，如有疑问请联系我们。"
        )

        notification = self.create_notification(
            appointment_id=appointment.id,
            notification_type="preparation_reminder",
            title="PET-CT检查前准备提醒",
            content=reminder_content,
            channel="sms",
            recipient=patient.phone if hasattr(patient, 'phone') else None,
            hospital_id=appointment.hospital_id,
            priority="normal",
            recipient_type="patient",
            recipient_name=patient.name
        )
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"发送准备提醒: 预约={appointment.appointment_no}, "
            f"提前{hours_before}小时, 患者={patient.name}"
        )

        return {
            "success": True,
            "appointment_id": appointment.id,
            "appointment_no": appointment.appointment_no,
            "notification_id": notification.id,
            "reminder_hours_before": hours_before,
            "content": reminder_content
        }

    def get_notifications(
        self,
        hospital_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """查询通知列表"""
        query = self.db.query(Notification)

        if hospital_id:
            query = query.filter(Notification.hospital_id == hospital_id)
        if appointment_id:
            query = query.filter(Notification.appointment_id == appointment_id)
        if notification_type:
            query = query.filter(Notification.notification_type == notification_type)
        if status:
            query = query.filter(Notification.status == status)
        if start_date:
            query = query.filter(Notification.created_at >= start_date)
        if end_date:
            query = query.filter(Notification.created_at <= end_date)

        total = query.count()
        notifications = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()

        return {
            "total": total,
            "items": [
                {
                    "id": n.id,
                    "appointment_id": n.appointment_id,
                    "notification_type": n.notification_type,
                    "title": n.title,
                    "channel": n.channel,
                    "status": n.status,
                    "recipient": n.recipient_phone,
                    "recipient_type": n.recipient_type,
                    "priority": n.priority,
                    "created_at": n.created_at,
                    "sent_at": n.sent_at
                }
                for n in notifications
            ]
        }

    def _generate_checklist(self, appointment: Appointment) -> List[Dict[str, Any]]:
        """生成检查须知清单"""
        checklist = [
            {"item": "携带有效身份证件", "required": True},
            {"item": "携带既往检查资料", "required": True},
            {"item": "检查前禁食6小时", "required": True},
            {"item": "检查前避免剧烈运动", "required": True},
            {"item": "糖尿病患者请携带降糖药物", "required": appointment.patient.diabetes_type if hasattr(appointment.patient, 'diabetes_type') else False},
            {"item": "需家属陪同", "required": appointment.needs_anesthesia or not appointment.is_inpatient}
        ]

        if appointment.needs_anesthesia:
            checklist.extend([
                {"item": "麻醉评估资料", "required": True},
                {"item": "术前8小时禁食", "required": True},
                {"item": "术前4小时禁饮", "required": True}
            ])

        return checklist

    def _format_receipt_content(
        self,
        receipt_data: Dict[str, Any],
        language: str = "zh-CN"
    ) -> str:
        """格式化回执内容"""
        data = receipt_data
        return f"""
========= PET-CT 检查预约回执 =========
回执号: {data['receipt_no']}
生成时间: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}

【预约信息】
预约编号: {data['appointment']['appointment_no']}
检查日期: {data['appointment']['appointment_date']}
检查时段: {data['appointment']['time_slot']}
队列号码: {data['appointment']['queue_number']}
预计时长: {data['appointment']['estimated_duration_minutes']}分钟

【患者信息】
姓名: {data['patient']['name']}
性别: {data['patient']['gender']}
年龄: {data['patient']['age'] or ''}
联系电话: {data['patient']['phone']}

【院区信息】
院区: {data['hospital']['name']}
地址: {data['hospital']['address']}
联系电话: {data['hospital']['phone']}
申请科室: {data['hospital']['department'] or ''}
申请医生: {data['hospital']['referring_doctor'] or ''}

【检查信息】
检查目的: {data['exam_info']['exam_purpose']}
紧急程度: {data['exam_info']['urgency_level']}
临床诊断: {data['exam_info']['clinical_diagnosis'] or ''}
是否住院: {'是' if data['exam_info']['is_inpatient'] else '否'}
是否麻醉: {'是' if data['exam_info']['needs_anesthesia'] else '否'}

【准备事项】
{data['preparation_notes']}

【检查清单】
{chr(10).join([f"{'□' if not item['required'] else '■'} {item['item']}" for item in data['checklist']])}

【联系方式】
服务热线: {data['contact_info']['service_hotline']}
紧急联系: {data['contact_info']['emergency_contact']}

========= 请妥善保管此回执 =========
        """.strip()

    def _format_patient_reschedule_content(
        self,
        appointment: Appointment,
        request: RescheduleNotificationRequest,
        old_hospital: Optional[Hospital],
        new_hospital: Optional[Hospital]
    ) -> str:
        """格式化患者改期通知内容"""
        patient = appointment.patient
        old_date = appointment.appointment_date
        old_time = appointment.time_slot

        return f"""
尊敬的{patient.name if patient else '患者'}您好！

您的PET-CT检查时间已调整：

原安排：
日期：{old_date} {old_time}
院区：{old_hospital.name if old_hospital else ''}

新安排：
日期：{request.new_date} {request.new_time or '另行通知'}
院区：{new_hospital.name if new_hospital else (old_hospital.name if old_hospital else '同院区')}

改期原因：{request.reason}

请您按新时间准时到达，如有疑问请联系服务热线：{getattr(settings, 'SERVICE_HOTLINE', '400-123-4567')}

给您带来的不便，敬请谅解！
        """.strip()

    def _format_hospital_reschedule_content(
        self,
        appointment: Appointment,
        request: RescheduleNotificationRequest,
        old_hospital: Optional[Hospital],
        new_hospital: Optional[Hospital]
    ) -> str:
        """格式化院区改期通知内容"""
        patient = appointment.patient

        return f"""
【院区预约改期通知】

预约编号：{appointment.appointment_no}
患者姓名：{patient.name if patient else '未知'}

原安排：
院区：{old_hospital.name if old_hospital else ''}
日期：{appointment.appointment_date} {appointment.time_slot}

新安排：
院区：{new_hospital.name if new_hospital else (old_hospital.name if old_hospital else '同院区')}
日期：{request.new_date} {request.new_time or '待定'}

改期原因：{request.reason}

请做好相应准备工作。
        """.strip()

    def _format_department_reschedule_content(
        self,
        appointment: Appointment,
        request: RescheduleNotificationRequest
    ) -> str:
        """格式化科室改期通知内容"""
        patient = appointment.patient

        return f"""
【科室预约改期通知】

科室：{appointment.referring_department}
申请医生：{appointment.referring_doctor or ''}

预约编号：{appointment.appointment_no}
患者姓名：{patient.name if patient else '未知'}
检查目的：{appointment.exam_purpose}
临床诊断：{appointment.clinical_diagnosis or ''}

原检查日期：{appointment.appointment_date}
新检查日期：{request.new_date}

改期原因：{request.reason}
        """.strip()

    def send_bulk_notifications(
        self,
        request: NotificationSendRequest
    ) -> Dict[str, Any]:
        """批量发送通知"""
        query = self.db.query(Notification).filter(Notification.status == "pending")

        if request.notification_ids:
            query = query.filter(Notification.id.in_(request.notification_ids))
        if request.channel:
            query = query.filter(Notification.channel == request.channel)

        notifications = query.all()

        sent_count = 0
        failed_count = 0

        for notification in notifications:
            try:
                notification.status = "sent"
                notification.sent_at = datetime.utcnow()
                sent_count += 1

                logger.info(
                    f"发送通知: ID={notification.id}, 类型={notification.notification_type}, "
                    f"渠道={notification.channel}"
                )
            except Exception as e:
                notification.status = "failed"
                notification.failure_reason = str(e)
                notification.retry_count += 1
                failed_count += 1

                logger.error(f"发送通知失败: ID={notification.id}, 错误={str(e)}")

        self.db.commit()

        return {
            "total_processed": len(notifications),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "notification_ids": [n.id for n in notifications]
        }
