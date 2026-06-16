from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models import (
    Appointment, Hospital, Equipment, TracerBatch,
    ScheduleTemplate, SupportPlan, Patient, Notification
)
from app.schemas import (
    BatchRescheduleRequest, BatchRescheduleResult, RescheduleResult,
    EquipmentDowntimeRequest, DrugDelayRequest, EmergencyPlusRequest,
    RescheduleReason, RescheduleStrategy, AppointmentCreate,
    AppointmentCategorizeResponse
)
from app.utils import (
    get_logger, generate_appointment_no, calculate_priority_score,
    categorize_workflow, get_preparation_notes
)
from app.exceptions import (
    ResourceNotAvailable, ValidationError, AppointmentNotFound
)
from app.config import get_settings

settings = get_settings()
logger = get_logger("reschedule_service")


class RescheduleService:
    """模块4: 异常重排服务 - 设备停机/药物延迟/突发加号时批量重排队列"""

    def __init__(self, db: Session):
        self.db = db
        from app.services import SchedulingService, AppointmentService, NotificationService
        self.scheduling_service = SchedulingService(db)
        self.appointment_service = AppointmentService(db)
        self.notification_service = NotificationService(db)

    def handle_equipment_downtime(
        self,
        request: EquipmentDowntimeRequest
    ) -> BatchRescheduleResult:
        """
        处理设备停机
        自动识别受影响预约并批量重排
        """
        equipment = self.db.query(Equipment).filter(
            Equipment.id == request.equipment_id
        ).first()

        if not equipment:
            raise ValidationError(f"设备不存在: {request.equipment_id}")

        old_status = equipment.status
        equipment.status = request.downtime_type
        equipment.status_reason = request.reason
        equipment.status_updated_at = datetime.utcnow()

        affected_appointments = self._find_affected_by_equipment(
            equipment_id=request.equipment_id,
            start_time=request.start_time,
            end_time=request.end_time
        )

        logger.warning(
            f"设备停机: {equipment.code} ({request.downtime_type}), "
            f"时间: {request.start_time} ~ {request.end_time}, "
            f"受影响预约数: {len(affected_appointments)}, "
            f"原因: {request.reason}"
        )

        if request.auto_reschedule and affected_appointments:
            batch_request = BatchRescheduleRequest(
                appointment_ids=[a.id for a in affected_appointments],
                hospital_id=equipment.hospital_id,
                equipment_id=request.equipment_id,
                affected_date=request.start_time.date(),
                reason=RescheduleReason.EQUIPMENT_DOWNTIME,
                reason_detail=request.reason,
                strategy=request.reschedule_strategy,
                target_date=request.end_time.date() + timedelta(days=1),
                allow_cross_hospital=request.allow_cross_hospital,
                notify_patient=True,
                notify_hospital=True,
                operator=request.operator,
                dry_run=False
            )

            result = self.batch_reschedule(batch_request)
            result.estimated_impact_minutes = int(
                (request.end_time - request.start_time).total_seconds() / 60
            )
            return result

        return self._create_empty_result(
            affected_appointments,
            RescheduleReason.EQUIPMENT_DOWNTIME,
            request.reschedule_strategy
        )

    def handle_drug_delay(
        self,
        request: DrugDelayRequest
    ) -> BatchRescheduleResult:
        """
        处理药物到货延迟
        顺延注射时间或批量改期
        """
        tracer_batch = None
        if request.tracer_batch_id:
            tracer_batch = self.db.query(TracerBatch).filter(
                TracerBatch.id == request.tracer_batch_id
            ).first()

            if not tracer_batch:
                raise ValidationError(f"药物批次不存在: {request.tracer_batch_id}")

            if request.new_arrival_time:
                tracer_batch.arrival_time = request.new_arrival_time
                tracer_batch.status = "in_transit"

        hospital_id = request.hospital_id
        if not hospital_id and request.affected_hospital_ids:
            hospital_id = request.affected_hospital_ids[0]

        has_explicit_ids = request.affected_appointment_ids and len(request.affected_appointment_ids) > 0

        if has_explicit_ids:
            affected_appointments = self.db.query(Appointment).filter(
                Appointment.id.in_(request.affected_appointment_ids)
            ).all()
        else:
            affected_appointments = self._find_affected_by_drug_delay(
                hospital_id=hospital_id or 0,
                tracer_id=request.tracer_id or 0,
                expected_delay_minutes=request.expected_delay_minutes,
                affected_appointment_ids=None
            )

        logger.warning(
            f"药物到货延迟: 批次={tracer_batch.batch_no if tracer_batch else '无'}, "
            f"延迟{request.expected_delay_minutes}分钟, "
            f"受影响预约数: {len(affected_appointments)}, "
            f"原因: {request.reason}"
        )

        if request.shift_injection_times and not request.auto_reschedule:
            return self._shift_injection_times(
                affected_appointments,
                request.expected_delay_minutes,
                request.reason,
                request.operator
            )

        if request.auto_reschedule:
            target_date = request.target_date
            if not target_date:
                target_date = request.affected_date
            if not target_date and request.expected_delay_minutes and request.expected_delay_minutes > 120:
                target_date = date.today() + timedelta(days=1)

            batch_request = BatchRescheduleRequest(
                appointment_ids=list(request.affected_appointment_ids) if has_explicit_ids else [a.id for a in affected_appointments],
                hospital_id=hospital_id,
                target_hospital_id=request.target_hospital_id,
                affected_date=request.affected_date or date.today(),
                target_date=target_date,
                reason=RescheduleReason.DRUG_DELAY,
                reason_detail=request.reason,
                strategy=request.reschedule_strategy,
                allow_cross_hospital=request.allow_cross_hospital if hasattr(request, 'allow_cross_hospital') else True,
                notify_patient=request.notify_patients if hasattr(request, 'notify_patients') else True,
                notify_hospital=True,
                operator=request.operator,
                dry_run=False
            )

            result = self.batch_reschedule(batch_request)
            result.estimated_impact_minutes = request.expected_delay_minutes
            return result

        return self._create_empty_result(
            affected_appointments,
            RescheduleReason.DRUG_DELAY,
            request.reschedule_strategy
        )

    def handle_emergency_plus(
        self,
        request: EmergencyPlusRequest
    ) -> Dict[str, Any]:
        """
        处理突发加号
        创建加号预约并调整现有队列顺序
        """
        patient = self.db.query(Patient).filter(
            Patient.id == request.patient_id
        ).first()

        if not patient:
            raise ValidationError(f"患者不存在: {request.patient_id}")

        hospital = self.db.query(Hospital).filter(
            Hospital.id == request.hospital_id
        ).first()

        if not hospital:
            raise ValidationError(f"院区不存在: {request.hospital_id}")

        appointment_data = AppointmentCreate(
            patient_id=request.patient_id,
            hospital_id=request.hospital_id,
            exam_purpose=request.exam_purpose,
            urgency_level=request.urgency_level,
            is_inpatient=request.is_inpatient,
            needs_anesthesia=request.needs_anesthesia,
            appointment_date=request.target_date,
            time_slot=request.target_time_slot,
            equipment_id=request.preferred_equipment_id,
            clinical_diagnosis=request.clinical_diagnosis,
            referring_department=request.referring_department,
            referring_doctor=request.referring_doctor,
            is_plus_sign=True,
            plus_sign_reason=request.plus_sign_reason
        )

        appointment, categorization = self.appointment_service.create_appointment(
            appointment_data
        )

        resource_allocation = self.scheduling_service.allocate_resources(
            appointment, categorization
        )

        if not resource_allocation["allocated"]:
            self.db.rollback()
            raise ResourceNotAvailable(
                f"加号失败，无法分配资源: {'; '.join(resource_allocation.get('warnings', []))}"
            )

        appointment.equipment_id = resource_allocation["equipment_id"]
        appointment.time_slot = resource_allocation["time_slot"]
        appointment.queue_number = resource_allocation["queue_number"]
        appointment.tracer_batch_id = resource_allocation["tracer_batch_id"]
        appointment.status = "confirmed"

        shift_result = {}
        if request.auto_shift_queue:
            shift_result = self._shift_queue_after_plus(
                hospital_id=request.hospital_id,
                target_date=request.target_date,
                new_queue_number=appointment.queue_number,
                strategy=request.reschedule_strategy,
                plus_appointment_id=appointment.id
            )

        self.db.commit()

        logger.info(
            f"突发加号成功: 预约={appointment.appointment_no}, "
            f"队列号={appointment.queue_number}, "
            f"紧急度={request.urgency_level}, "
            f"原因={request.plus_sign_reason}"
        )

        preparation_notes = get_preparation_notes(
            tracer_type=appointment.tracer_type or "fdg",
            needs_anesthesia=request.needs_anesthesia,
            is_inpatient=request.is_inpatient
        )

        return {
            "success": True,
            "appointment_id": appointment.id,
            "appointment_no": appointment.appointment_no,
            "queue_number": appointment.queue_number,
            "queue_position": appointment.queue_number,
            "time_slot": appointment.time_slot,
            "equipment_id": appointment.equipment_id,
            "priority_score": categorization.priority_score,
            "category": categorization.category,
            "preparation_notes": preparation_notes,
            "shift_impact": shift_result,
            "affected_count": shift_result.get("total_affected", 0) if shift_result else 0,
            "estimated_checkin_time": self._calculate_checkin_time(appointment)
        }

    def batch_reschedule(
        self,
        request: BatchRescheduleRequest
    ) -> BatchRescheduleResult:
        """
        批量重排预约
        支持多种重排策略
        每个传入的预约ID都会出现在结果明细中
        """
        rescheduleable_statuses = ["pending", "confirmed", "checked_in"]

        if request.appointment_ids:
            all_ids = list(request.appointment_ids)
            all_appointments = self.db.query(Appointment).filter(
                Appointment.id.in_(all_ids)
            ).all()
            apt_map = {a.id: a for a in all_appointments}

            appointments = []
            skipped_results = []
            failed_results = []

            for apt_id in all_ids:
                apt = apt_map.get(apt_id)
                if not apt:
                    failed_results.append(
                        RescheduleResult(
                            appointment_id=apt_id,
                            appointment_no="",
                            patient_name="未知",
                            success=False,
                            status="failed",
                            message="预约不存在",
                            errors=["预约不存在"]
                        )
                    )
                elif apt.status not in rescheduleable_statuses:
                    skipped_results.append(
                        RescheduleResult(
                            appointment_id=apt.id,
                            appointment_no=apt.appointment_no,
                            patient_name=apt.patient.name if apt.patient else "未知",
                            success=False,
                            status="skipped",
                            message=f"状态{apt.status}不可重排",
                            errors=[f"状态{apt.status}不可重排"]
                        )
                    )
                else:
                    appointments.append(apt)
        else:
            appointments = self._get_appointments_for_reschedule(request)
            skipped_results = []
            failed_results = []

        if not appointments and not skipped_results and not failed_results:
            return BatchRescheduleResult(
                total_count=0,
                success_count=0,
                failed_count=0,
                skipped_count=0,
                total=0,
                success=0,
                failed=0,
                skipped=0,
                reason=request.reason,
                strategy=request.strategy,
                results=[],
                success_details=[],
                summary={"message": "没有需要重排的预约"}
            )

        sorted_appointments = self._sort_appointments(
            appointments, request.strategy
        )

        results: List[RescheduleResult] = []
        success_count = 0
        runtime_failed_count = 0
        skipped_count = len(skipped_results)
        input_failed_count = len(failed_results)
        affected_hospitals = set()

        for appointment in sorted_appointments:
            try:
                result = self._reschedule_single_appointment(
                    appointment=appointment,
                    request=request
                )
                if result.success:
                    success_count += 1
                    affected_hospitals.add(result.new_hospital_id or appointment.hospital_id)

                    if request.notify_patient and not request.dry_run:
                        self._send_reschedule_notification(appointment, result)

                    if request.notify_hospital and not request.dry_run:
                        self._send_hospital_notification(appointment, result)
                else:
                    runtime_failed_count += 1
                results.append(result)
            except Exception as e:
                logger.error(f"重排预约 {appointment.id} 失败: {str(e)}")
                runtime_failed_count += 1
                results.append(
                    RescheduleResult(
                        appointment_id=appointment.id,
                        appointment_no=appointment.appointment_no,
                        patient_name=appointment.patient.name if appointment.patient else "未知",
                        success=False,
                        status="failed",
                        message=f"重排失败: {str(e)}",
                        errors=[str(e)]
                    )
                )

        all_results = skipped_results + failed_results + results
        total_failed = input_failed_count + runtime_failed_count
        total_count = len(all_results)

        if not request.dry_run:
            self.db.commit()

        summary = self._generate_reschedule_summary(
            results=all_results,
            request=request,
            success_count=success_count,
            failed_count=total_failed
        )

        return BatchRescheduleResult(
            total_count=total_count,
            success_count=success_count,
            failed_count=total_failed,
            skipped_count=skipped_count,
            total=total_count,
            success=success_count,
            failed=total_failed,
            skipped=skipped_count,
            reason=request.reason,
            strategy=request.strategy,
            results=all_results,
            success_details=self._build_success_details(all_results),
            failed_details=self._build_failed_details(all_results),
            skipped_details=self._build_skipped_details(all_results),
            affected_hospitals=list(affected_hospitals),
            summary=summary,
            warnings=self._generate_warnings(all_results)
        )

    def _reschedule_single_appointment(
        self,
        appointment: Appointment,
        request: BatchRescheduleRequest
    ) -> RescheduleResult:
        """重排单个预约"""
        old_date = appointment.appointment_date
        old_time_slot = appointment.time_slot
        old_hospital_id = appointment.hospital_id
        old_queue_number = appointment.queue_number
        old_equipment_id = appointment.equipment_id

        if appointment.status in ["completed", "cancelled", "scanning", "injected"]:
            return RescheduleResult(
                appointment_id=appointment.id,
                appointment_no=appointment.appointment_no,
                patient_name=appointment.patient.name if appointment.patient else "未知",
                success=False,
                status="skipped",
                message=f"当前状态 {appointment.status} 不支持重排",
                old_date=old_date,
                old_time_slot=old_time_slot,
                old_hospital_id=old_hospital_id,
                old_queue_number=old_queue_number,
                old_equipment_id=old_equipment_id,
                errors=[f"状态不允许重排: {appointment.status}"]
            )

        target_hospital_id = request.target_hospital_id or appointment.hospital_id
        target_date = request.target_date or appointment.appointment_date

        if request.allow_cross_hospital and target_hospital_id == appointment.hospital_id:
            alternative_hospital = self._find_alternative_hospital(
                appointment=appointment,
                target_date=target_date,
                source_hospital_id=appointment.hospital_id
            )
            if alternative_hospital:
                target_hospital_id = alternative_hospital.id

        allocation = self.scheduling_service.allocate_resources_for_reschedule(
            appointment=appointment,
            target_hospital_id=target_hospital_id,
            target_date=target_date,
            preferred_equipment_id=request.new_equipment_id
        )

        if not allocation["allocated"]:
            return RescheduleResult(
                appointment_id=appointment.id,
                appointment_no=appointment.appointment_no,
                patient_name=appointment.patient.name if appointment.patient else "未知",
                success=False,
                status="failed",
                message="无法分配资源",
                old_date=old_date,
                old_time_slot=old_time_slot,
                old_hospital_id=old_hospital_id,
                old_queue_number=old_queue_number,
                old_equipment_id=old_equipment_id,
                errors=allocation.get("warnings", [])
            )

        if not request.dry_run:
            appointment.appointment_date = allocation.get("appointment_date", appointment.appointment_date)
            appointment.hospital_id = allocation.get("hospital_id", appointment.hospital_id)
            appointment.equipment_id = allocation.get("equipment_id")
            appointment.time_slot = allocation.get("time_slot")
            appointment.queue_number = allocation.get("queue_number")
            if allocation.get("tracer_batch_id"):
                appointment.tracer_batch_id = allocation["tracer_batch_id"]
            appointment.status = "confirmed"
            appointment.sub_status = "rescheduled"
            appointment.status_changed_at = datetime.utcnow()

            if allocation.get("hospital_id", appointment.hospital_id) != old_hospital_id:
                appointment.is_referral = True
                appointment.referral_reason = request.reason_detail

        new_hospital = self.db.query(Hospital).filter(
            Hospital.id == allocation["hospital_id"]
        ).first()

        return RescheduleResult(
            appointment_id=appointment.id,
            appointment_no=appointment.appointment_no,
            patient_name=appointment.patient.name if appointment.patient else "未知",
            success=True,
            status="success",
            message="重排成功",
            old_date=old_date,
            old_time_slot=old_time_slot,
            old_hospital_id=old_hospital_id,
            old_queue_number=old_queue_number,
            old_equipment_id=old_equipment_id,
            new_date=allocation["appointment_date"],
            new_time_slot=allocation["time_slot"],
            new_hospital_id=allocation["hospital_id"],
            new_hospital_name=new_hospital.name if new_hospital else None,
            new_queue_number=allocation["queue_number"],
            new_equipment_id=allocation.get("equipment_id"),
            notification_sent=request.notify_patient and not request.dry_run
        )

    def _find_affected_by_equipment(
        self,
        equipment_id: int,
        start_time: datetime,
        end_time: datetime
    ) -> List[Appointment]:
        """查找受设备停机影响的预约"""
        return self.db.query(Appointment).filter(
            and_(
                Appointment.equipment_id == equipment_id,
                Appointment.status.in_(["pending", "confirmed", "checked_in"]),
                func.date(Appointment.appointment_date) >= start_time.date(),
                func.date(Appointment.appointment_date) <= end_time.date()
            )
        ).order_by(Appointment.priority_score.desc()).all()

    def _find_affected_by_drug_delay(
        self,
        hospital_id: int,
        tracer_id: int,
        expected_delay_minutes: int,
        affected_appointment_ids: Optional[List[int]] = None
    ) -> List[Appointment]:
        """查找受药物延迟影响的预约"""
        if affected_appointment_ids:
            return self.db.query(Appointment).filter(
                and_(
                    Appointment.id.in_(affected_appointment_ids),
                    Appointment.status.in_(["pending", "confirmed", "checked_in"])
                )
            ).order_by(Appointment.priority_score.desc()).all()

        query = self.db.query(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                Appointment.status.in_(["pending", "confirmed", "checked_in"]),
                Appointment.appointment_date == date.today()
            )
        )

        if tracer_id:
            from app.models import Tracer
            tracer = self.db.query(Tracer).filter(Tracer.id == tracer_id).first()
            if tracer:
                query = query.filter(Appointment.tracer_type == tracer.tracer_type)

        return query.order_by(Appointment.injection_time).all()

    def _get_appointments_for_reschedule(
        self,
        request: BatchRescheduleRequest
    ) -> List[Appointment]:
        """获取需要重排的预约列表"""
        query = self.db.query(Appointment).filter(
            Appointment.status.in_(["pending", "confirmed", "checked_in"])
        )

        if request.appointment_ids:
            query = query.filter(Appointment.id.in_(request.appointment_ids))
        else:
            if request.hospital_id:
                query = query.filter(Appointment.hospital_id == request.hospital_id)
            if request.equipment_id:
                query = query.filter(Appointment.equipment_id == request.equipment_id)
            if request.affected_date:
                query = query.filter(
                    func.date(Appointment.appointment_date) == request.affected_date
                )

        return query.order_by(Appointment.priority_score.desc()).all()

    def _sort_appointments(
        self,
        appointments: List[Appointment],
        strategy: RescheduleStrategy
    ) -> List[Appointment]:
        """根据策略排序预约"""
        if strategy == RescheduleStrategy.PRIORITY_FIRST:
            return sorted(
                appointments,
                key=lambda a: (-a.priority_score, a.appointment_date or date.max)
            )
        elif strategy == RescheduleStrategy.EARLIEST_FIRST:
            return sorted(
                appointments,
                key=lambda a: (a.appointment_date or date.max, a.queue_number or 999)
            )
        elif strategy == RescheduleStrategy.MINIMIZE_IMPACT:
            return sorted(
                appointments,
                key=lambda a: (
                    -a.priority_score,
                    -(1 if a.is_inpatient else 0),
                    a.appointment_date or date.max
                )
            )
        elif strategy == RescheduleStrategy.MAINTAIN_ORDER:
            return sorted(
                appointments,
                key=lambda a: (a.appointment_date or date.max, a.queue_number or 999)
            )
        elif strategy == RescheduleStrategy.NEAREST_HOSPITAL:
            return sorted(
                appointments,
                key=lambda a: (-a.priority_score, a.appointment_date or date.max)
            )
        else:
            return appointments

    def _shift_injection_times(
        self,
        appointments: List[Appointment],
        delay_minutes: int,
        reason: str,
        operator: Optional[str]
    ) -> BatchRescheduleResult:
        """顺延注射时间"""
        results: List[RescheduleResult] = []
        success_count = 0

        for appointment in appointments:
            if appointment.injection_time:
                old_injection_time = appointment.injection_time
                new_injection_time = old_injection_time + timedelta(minutes=delay_minutes)
                appointment.injection_time = new_injection_time

                results.append(
                    RescheduleResult(
                        appointment_id=appointment.id,
                        appointment_no=appointment.appointment_no,
                        patient_name=appointment.patient.name if appointment.patient else "未知",
                        success=True,
                        message=f"注射时间顺延{delay_minutes}分钟",
                        old_date=appointment.appointment_date,
                        old_time_slot=appointment.time_slot,
                        new_date=appointment.appointment_date,
                        new_time_slot=appointment.time_slot,
                        notification_sent=False
                    )
                )
                success_count += 1

                self.notification_service.create_notification(
                    appointment_id=appointment.id,
                    notification_type="time_shift",
                    title="注射时间调整通知",
                    content=f"因{reason}，您的注射时间已从{old_injection_time}调整为{new_injection_time}",
                    channel="sms",
                    recipient=appointment.patient.phone if appointment.patient else None
                )

        self.db.commit()

        return BatchRescheduleResult(
            total_count=len(appointments),
            success_count=success_count,
            failed_count=len(appointments) - success_count,
            skipped_count=0,
            total=len(appointments),
            success=success_count,
            failed=len(appointments) - success_count,
            skipped=0,
            reason=RescheduleReason.DRUG_DELAY,
            strategy=RescheduleStrategy.MINIMIZE_IMPACT,
            results=results,
            success_details=self._build_success_details(results),
            estimated_impact_minutes=delay_minutes,
            summary={"message": f"已顺延{success_count}个预约的注射时间，平均延迟{delay_minutes}分钟"}
        )

    def _shift_queue_after_plus(
        self,
        hospital_id: int,
        target_date: date,
        new_queue_number: int,
        strategy: RescheduleStrategy,
        plus_appointment_id: int
    ) -> Dict[str, Any]:
        """加号后调整队列顺序"""
        affected = self.db.query(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                Appointment.appointment_date == target_date,
                Appointment.queue_number >= new_queue_number,
                Appointment.id != plus_appointment_id,
                Appointment.status.in_(["pending", "confirmed"])
            )
        ).all()

        shifted_count = 0
        for apt in affected:
            if strategy == RescheduleStrategy.MAINTAIN_ORDER:
                apt.queue_number += 1
                shifted_count += 1
            elif strategy == RescheduleStrategy.PRIORITY_FIRST:
                if apt.priority_score < 80:
                    apt.queue_number += 1
                    shifted_count += 1

        return {
            "total_affected": len(affected),
            "shifted_count": shifted_count,
            "strategy": strategy.value
        }

    def _find_alternative_hospital(
        self,
        appointment: Appointment,
        target_date: date,
        source_hospital_id: int
    ) -> Optional[Hospital]:
        """查找可用的替代院区"""
        from app.services import ReferralService
        referral_service = ReferralService(self.db)

        patient = appointment.patient
        if not patient:
            return None

        try:
            auto_assign = referral_service.auto_assign_referral(
                appointment_id=appointment.id,
                patient_id=patient.id,
                source_hospital_id=source_hospital_id,
                target_date=target_date,
                exam_purpose=appointment.exam_purpose,
                urgency_level=appointment.urgency_level,
                needs_anesthesia=appointment.needs_anesthesia,
                tracer_type=appointment.tracer_type
            )

            if auto_assign.recommendations:
                top_rec = auto_assign.recommendations[0]
                return self.db.query(Hospital).filter(
                    Hospital.id == top_rec["hospital_id"]
                ).first()
        except Exception as e:
            logger.warning(f"查找替代院区失败: {e}")

        return None

    def _send_reschedule_notification(
        self,
        appointment: Appointment,
        result: RescheduleResult
    ) -> None:
        """发送改期通知给患者"""
        if not appointment.patient:
            return

        content = (
            f"尊敬的{appointment.patient.name}患者，\n"
            f"您的PET-CT检查时间已调整：\n"
            f"原时间：{result.old_date} {result.old_time_slot}\n"
            f"新时间：{result.new_date} {result.new_time_slot}\n"
            f"新院区：{result.new_hospital_name or '同院区'}\n"
            f"新队列号：{result.new_queue_number}\n"
            f"如有疑问请联系我们。"
        )

        self.notification_service.create_notification(
            appointment_id=appointment.id,
            notification_type="reschedule",
            title="检查时间调整通知",
            content=content,
            channel="sms",
            recipient=appointment.patient.phone
        )

    def _send_hospital_notification(
        self,
        appointment: Appointment,
        result: RescheduleResult
    ) -> None:
        """发送改期通知给院区"""
        content = (
            f"预约改期通知：\n"
            f"预约号：{result.appointment_no}\n"
            f"患者：{result.patient_name}\n"
            f"原安排：{result.old_date} {result.old_time_slot}\n"
            f"新安排：{result.new_date} {result.new_time_slot} "
            f"({result.new_hospital_name or '同院区'})\n"
            f"新队列号：{result.new_queue_number}"
        )

        self.notification_service.create_notification(
            appointment_id=appointment.id,
            notification_type="hospital_notice",
            title="院区预约改期通知",
            content=content,
            channel="system",
            recipient=f"hospital_{result.new_hospital_id or appointment.hospital_id}"
        )

    def _create_empty_result(
        self,
        appointments: List[Appointment],
        reason: RescheduleReason,
        strategy: RescheduleStrategy
    ) -> BatchRescheduleResult:
        """创建空结果"""
        results = [
            RescheduleResult(
                appointment_id=a.id,
                appointment_no=a.appointment_no,
                patient_name=a.patient.name if a.patient else "未知",
                success=False,
                message="未执行自动重排",
                old_date=a.appointment_date,
                old_time_slot=a.time_slot,
                old_hospital_id=a.hospital_id
            )
            for a in appointments
        ]

        return BatchRescheduleResult(
            total_count=len(appointments),
            success_count=0,
            failed_count=0,
            skipped_count=len(appointments),
            total=len(appointments),
            success=0,
            failed=0,
            skipped=len(appointments),
            reason=reason,
            strategy=strategy,
            results=results,
            success_details=[],
            summary={"message": "自动重排未启用，请手动处理"},
            warnings=["自动重排功能未启用，需要手动处理受影响预约"]
        )

    def _build_success_details(
        self,
        results: List[RescheduleResult]
    ) -> List[Dict[str, Any]]:
        """从结果中构造成功详情"""
        success_details = []
        for result in results:
            if result.success:
                success_details.append({
                    "appointment_id": result.appointment_id,
                    "appointment_no": result.appointment_no,
                    "patient_name": result.patient_name,
                    "new_date": result.new_date,
                    "new_time_slot": result.new_time_slot,
                    "new_hospital_id": result.new_hospital_id,
                    "new_hospital_name": result.new_hospital_name,
                    "new_queue_number": result.new_queue_number,
                    "new_equipment_id": result.new_equipment_id,
                    "notification_sent": result.notification_sent,
                    "message": result.message
                })
        return success_details

    def _build_failed_details(
        self,
        results: List[RescheduleResult]
    ) -> List[Dict[str, Any]]:
        """从结果中构造失败详情"""
        failed_details = []
        for result in results:
            if not result.success and result.status == "failed":
                failed_details.append({
                    "appointment_id": result.appointment_id,
                    "appointment_no": result.appointment_no,
                    "patient_name": result.patient_name,
                    "message": result.message,
                    "errors": result.errors
                })
        return failed_details

    def _build_skipped_details(
        self,
        results: List[RescheduleResult]
    ) -> List[Dict[str, Any]]:
        """从结果中构造跳过详情"""
        skipped_details = []
        for result in results:
            if not result.success and result.status == "skipped":
                skipped_details.append({
                    "appointment_id": result.appointment_id,
                    "appointment_no": result.appointment_no,
                    "patient_name": result.patient_name,
                    "reason": result.message
                })
        return skipped_details

    def _generate_reschedule_summary(
        self,
        results: List[RescheduleResult],
        request: BatchRescheduleRequest,
        success_count: int,
        failed_count: int
    ) -> Dict[str, Any]:
        """生成重排汇总信息"""
        cross_hospital_count = sum(
            1 for r in results
            if r.success and r.old_hospital_id != r.new_hospital_id
        )

        date_changed_count = sum(
            1 for r in results
            if r.success and r.old_date != r.new_date
        )

        return {
            "total_processed": len(results),
            "success_rate": f"{(success_count / len(results) * 100):.1f}%" if results else "0%",
            "cross_hospital_transfers": cross_hospital_count,
            "date_changes": date_changed_count,
            "reason": request.reason.value,
            "strategy": request.strategy.value,
            "operator": request.operator,
            "dry_run": request.dry_run
        }

    def _generate_warnings(
        self,
        results: List[RescheduleResult]
    ) -> List[str]:
        """生成警告信息"""
        warnings = []
        high_priority_failed = [
            r for r in results
            if not r.success and "高优先级" in (r.message or "")
        ]

        if high_priority_failed:
            warnings.append(
                f"有{len(high_priority_failed)}个高优先级预约重排失败，需要紧急处理"
            )

        failed_results = [r for r in results if not r.success]
        if failed_results:
            warnings.append(
                f"共有{len(failed_results)}个预约重排失败，请查看详情并手动处理"
            )

        return warnings

    def _calculate_checkin_time(self, appointment: Appointment) -> Optional[datetime]:
        """计算预计签到时间"""
        if appointment.appointment_date and appointment.time_slot:
            hour = 8 if "上午" in appointment.time_slot else 13
            return datetime.combine(
                appointment.appointment_date,
                datetime.min.time().replace(hour=hour)
            )
        return None
