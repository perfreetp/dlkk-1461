from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Appointment, StatusRecord, Patient, Hospital, Equipment, TracerBatch, TracerUsage, DrugWasteRecord
from app.schemas import (
    CheckInRequest, InjectionRequest, ScanStartRequest,
    CompletionRequest, CancellationRequest, StatusRecordCreate,
    AppointmentStatus
)
from app.utils import get_logger
from app.exceptions import (
    AppointmentNotFound, InvalidStatusTransition,
    ValidationError, ResourceNotAvailable
)

logger = get_logger("status_service")


class StatusService:
    """模块3: 状态回传服务 - 记录五类关键节点（签到/注射/入机/完成/取消）"""

    def __init__(self, db: Session):
        self.db = db

    def _validate_status_transition(self, appointment: Appointment, target_status: str) -> None:
        """验证状态流转是否合法"""
        valid_transitions = {
            "pending": ["confirmed", "cancelled", "no_show", "checked_in", "injected", "scanning", "completed"],
            "confirmed": ["checked_in", "cancelled", "no_show", "injected", "scanning", "completed"],
            "checked_in": ["injected", "cancelled", "scanning", "completed"],
            "injected": ["scanning", "cancelled", "completed"],
            "scanning": ["completed", "cancelled"],
            "completed": [],
            "cancelled": [],
            "no_show": []
        }

        current_status = appointment.status
        if target_status not in valid_transitions.get(current_status, []):
            raise InvalidStatusTransition(
                current=current_status,
                target=target_status
            )

    def _update_appointment_status(
        self,
        appointment: Appointment,
        new_status: str,
        status_time: datetime
    ) -> None:
        """更新预约状态和状态变更时间"""
        self._validate_status_transition(appointment, new_status)
        appointment.status = new_status
        appointment.status_changed_at = status_time

    def _create_status_record(
        self,
        appointment_id: int,
        status_type: str,
        status_code: str,
        status_name: str,
        occurred_at: datetime,
        recorded_by: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        **extra_fields
    ) -> StatusRecord:
        """创建状态记录"""
        record_data = {
            "appointment_id": appointment_id,
            "status_type": status_type,
            "status_code": status_code,
            "status_name": status_name,
            "occurred_at": occurred_at,
            "recorded_by": recorded_by,
            "location": location,
            "notes": notes,
            **extra_fields
        }

        record = StatusRecord(**record_data)
        self.db.add(record)
        self.db.flush()

        return record

    def _get_appointment(self, appointment_id: int) -> Appointment:
        """获取预约信息，不存在则抛出异常"""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()

        if not appointment:
            raise AppointmentNotFound(str(appointment_id))

        return appointment

    def check_in(self, request: CheckInRequest) -> Appointment:
        """
        记录患者签到
        验证：预约状态、患者信息、禁食要求、血糖
        """
        appointment = self._get_appointment(request.appointment_id)
        checkin_time = request.checkin_time or datetime.utcnow()

        self._update_appointment_status(appointment, "checked_in", checkin_time)
        appointment.checkin_time = checkin_time

        if request.blood_glucose is not None:
            appointment.blood_glucose = request.blood_glucose
            if request.blood_glucose > 11.1:
                logger.warning(
                    f"预约 {appointment.appointment_no} 患者血糖过高: {request.blood_glucose}mmol/L"
                )

        extra_fields = {
            "blood_glucose": request.blood_glucose,
            "blood_pressure_systolic": request.blood_pressure_systolic,
            "blood_pressure_diastolic": request.blood_pressure_diastolic,
            "heart_rate": request.heart_rate,
            "spo2": request.spo2
        }

        record = self._create_status_record(
            appointment_id=appointment.id,
            status_type="checkin",
            status_code="CHECKED_IN",
            status_name="患者签到",
            occurred_at=checkin_time,
            recorded_by=request.recorded_by,
            location=request.location,
            notes=request.notes,
            **extra_fields
        )

        self.db.commit()
        self.db.refresh(appointment)

        logger.info(
            f"患者签到成功: 预约={appointment.appointment_no}, "
            f"时间={checkin_time}, 记录人={request.recorded_by}"
        )

        return appointment

    def record_injection(self, request: InjectionRequest) -> Appointment:
        """
        记录示踪剂注射
        支持两种模式：
        1. 基础提交：仅appointment_id，更新到injected并返回关键时间点
        2. 完整药物批次提交：带批次号或示踪剂ID和剂量，校验批次有效性和剩余活度
        """
        appointment = self._get_appointment(request.appointment_id)
        injection_time = request.injection_time or datetime.utcnow()
        effective_dose = request.get_effective_dose_mbq()
        effective_site = request.get_effective_injection_site()
        effective_recorded_by = request.get_effective_recorded_by()
        waste_activity = request.waste_activity or 0

        tracer_batch = None
        if request.tracer_batch_no:
            tracer_batch = self.db.query(TracerBatch).filter(
                TracerBatch.batch_no == request.tracer_batch_no
            ).first()

            if not tracer_batch:
                raise ValidationError(f"示踪剂批次不存在: {request.tracer_batch_no}")

            if tracer_batch.is_expired():
                raise ResourceNotAvailable(f"示踪剂批次已过期: {request.tracer_batch_no}")

            if effective_dose is not None:
                total_consume = effective_dose + waste_activity
                if tracer_batch.remaining_activity < total_consume:
                    raise ResourceNotAvailable(
                        f"示踪剂活度不足，剩余: {tracer_batch.remaining_activity}MBq, "
                        f"需要: {total_consume}MBq (注射{effective_dose} + 浪费{waste_activity})"
                    )
        elif request.tracer_id:
            from app.models import Tracer
            tracer_obj = self.db.query(Tracer).filter(Tracer.id == request.tracer_id).first()
            if tracer_obj:
                tracer_batches = self.db.query(TracerBatch).filter(
                    TracerBatch.tracer_id == tracer_obj.id,
                    TracerBatch.status == "available"
                ).order_by(TracerBatch.calibration_time.desc()).all()

                if effective_dose is not None:
                    total_consume = effective_dose + waste_activity
                    for batch in tracer_batches:
                        if batch.remaining_activity >= total_consume and not batch.is_expired():
                            tracer_batch = batch
                            break

                    if tracer_batch is None and tracer_batches:
                        raise ResourceNotAvailable(
                            f"示踪剂活度不足，最大可用批次剩余: "
                            f"{max(b.remaining_activity for b in tracer_batches)}MBq, "
                            f"需要: {total_consume}MBq"
                        )
                    elif tracer_batch is None:
                        raise ResourceNotAvailable(f"示踪剂ID {request.tracer_id} 无可用批次")
                elif tracer_batches:
                    tracer_batches = [b for b in tracer_batches if not b.is_expired()]
                    if tracer_batches:
                        tracer_batch = tracer_batches[0]

        self._update_appointment_status(appointment, "injected", injection_time)
        appointment.injection_time = injection_time

        if effective_dose:
            appointment.tracer_dose_mbq = effective_dose

        if request.blood_glucose is not None:
            appointment.blood_glucose = request.blood_glucose

        if tracer_batch and effective_dose is not None and effective_dose > 0:
            total_consume = effective_dose + waste_activity

            if tracer_batch.remaining_activity < total_consume:
                raise ResourceNotAvailable(
                    f"示踪剂活度不足，剩余: {tracer_batch.remaining_activity}MBq, "
                    f"需要: {total_consume}MBq"
                )

            tracer_batch.used_activity_mbq = (tracer_batch.used_activity_mbq or 0) + effective_dose
            if waste_activity > 0:
                tracer_batch.wasted_activity_mbq = (tracer_batch.wasted_activity_mbq or 0) + waste_activity

            if tracer_batch.remaining_activity <= 0:
                tracer_batch.status = "used"

            tracer_usage = TracerUsage(
                appointment_id=appointment.id,
                tracer_id=tracer_batch.tracer_id,
                batch_id=tracer_batch.id,
                dose_mbq=effective_dose,
                injection_time=injection_time,
                injection_site=effective_site,
                administered_by=request.administered_by,
                remaining_activity=request.remaining_activity,
                waste_activity=waste_activity,
                vein_access=request.vein_access,
                notes=request.notes
            )
            self.db.add(tracer_usage)

            if waste_activity > 0:
                drug_waste = DrugWasteRecord(
                    hospital_id=appointment.hospital_id,
                    tracer_id=tracer_batch.tracer_id,
                    batch_id=tracer_batch.id,
                    waste_date=injection_time.date(),
                    waste_type="injection_residue",
                    total_activity_mbq=tracer_batch.total_activity_mbq,
                    wasted_activity_mbq=waste_activity,
                    used_activity_mbq=tracer_batch.used_activity_mbq or 0,
                    reason="注射残留",
                    reported_by=request.administered_by or effective_recorded_by
                )
                self.db.add(drug_waste)

        extra_fields = {
            "tracer_batch_no": request.tracer_batch_no or (tracer_batch.batch_no if tracer_batch else None),
            "tracer_dose_mbq": effective_dose,
            "tracer_injection_site": effective_site,
            "blood_glucose": request.blood_glucose
        }

        record = self._create_status_record(
            appointment_id=appointment.id,
            status_type="injection",
            status_code="INJECTED",
            status_name="示踪剂注射",
            occurred_at=injection_time,
            recorded_by=effective_recorded_by,
            notes=request.notes,
            **extra_fields
        )

        self.db.commit()

        logger.info(
            f"示踪剂注射完成: 预约={appointment.appointment_no}, "
            f"批次={request.tracer_batch_no or '无'}, 剂量={effective_dose or '无'}MBq"
        )

        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def record_scan_start(self, request: ScanStartRequest) -> Appointment:
        """
        记录扫描开始（入机）
        验证：设备状态、注射后等待时间
        """
        appointment = self._get_appointment(request.appointment_id)
        scan_start_time = request.scan_start_time or datetime.utcnow()

        if appointment.injection_time:
            wait_seconds = (scan_start_time - appointment.injection_time).total_seconds()
            wait_minutes = wait_seconds / 60
            if wait_minutes < 45:
                logger.warning(
                    f"预约 {appointment.appointment_no} 注射后等待时间不足: "
                    f"{wait_minutes:.1f}分钟（建议≥45分钟）"
                )

        if request.equipment_code:
            equipment = self.db.query(Equipment).filter(
                Equipment.code == request.equipment_code
            ).first()
            if equipment and equipment.status != "available":
                raise ResourceNotAvailable(
                    f"设备 {request.equipment_code} 当前不可用，状态: {equipment.status}"
                )

        self._update_appointment_status(appointment, "scanning", scan_start_time)
        appointment.scan_start_time = scan_start_time

        extra_fields = {
            "equipment_code": request.equipment_code,
            "scan_protocol": request.scan_protocol
        }

        record = self._create_status_record(
            appointment_id=appointment.id,
            status_type="scanning",
            status_code="SCAN_STARTED",
            status_name="扫描开始",
            occurred_at=scan_start_time,
            recorded_by=request.recorded_by,
            notes=request.notes,
            **extra_fields
        )

        self.db.commit()

        logger.info(
            f"扫描开始: 预约={appointment.appointment_no}, "
            f"设备={request.equipment_code}, 时间={scan_start_time}"
        )

        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def record_completion(self, request: CompletionRequest) -> Appointment:
        """
        记录检查完成
        记录：扫描时长、图像质量、患者状况
        """
        appointment = self._get_appointment(request.appointment_id)
        completion_time = request.completion_time or datetime.utcnow()

        self._update_appointment_status(appointment, "completed", completion_time)
        appointment.completion_time = completion_time

        if request.scan_end_time:
            appointment.scan_end_time = request.scan_end_time

        if request.scan_duration_seconds:
            appointment.estimated_duration_minutes = request.scan_duration_seconds // 60

        extra_fields = {
            "scan_duration_seconds": request.scan_duration_seconds,
            "equipment_code": appointment.equipment.code if appointment.equipment else None
        }

        record = self._create_status_record(
            appointment_id=appointment.id,
            status_type="completed",
            status_code="COMPLETED",
            status_name="检查完成",
            occurred_at=completion_time,
            recorded_by=request.recorded_by,
            notes=request.notes,
            **extra_fields
        )

        patient = appointment.patient
        if patient:
            patient.consecutive_no_show = 0
            patient.total_completed = (patient.total_completed or 0) + 1

        self.db.commit()

        logger.info(
            f"检查完成: 预约={appointment.appointment_no}, "
            f"时长={request.scan_duration_seconds}秒, "
            f"图像质量={request.image_quality}"
        )

        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def record_cancellation(self, request: CancellationRequest) -> Appointment:
        """
        记录预约取消
        处理：释放资源、更新药物浪费、记录爽约
        """
        appointment = self._get_appointment(request.appointment_id)
        cancelled_at = request.cancelled_at or datetime.utcnow()

        self._update_appointment_status(appointment, "cancelled", cancelled_at)
        appointment.cancelled_at = cancelled_at
        appointment.cancelled_by = request.cancelled_by
        appointment.cancellation_reason = request.cancellation_reason

        is_no_show = self._is_no_show(appointment, cancelled_at)
        if is_no_show:
            appointment.sub_status = "no_show"
            patient = appointment.patient
            if patient:
                patient.consecutive_no_show += 1
                patient.total_no_show += 1

        if appointment.tracer_batch_id and appointment.status in ["confirmed", "checked_in"]:
            self._handle_cancelled_drug_waste(appointment, cancelled_at, request.cancelled_by)

        record = self._create_status_record(
            appointment_id=appointment.id,
            status_type="cancelled",
            status_code="CANCELLED",
            status_name="预约取消",
            occurred_at=cancelled_at,
            recorded_by=request.cancelled_by,
            notes=f"取消原因: {request.cancellation_reason}\n备注: {request.notes or ''}"
        )

        self.db.commit()
        self.db.refresh(appointment)

        logger.info(
            f"预约取消: 预约={appointment.appointment_no}, "
            f"原因={request.cancellation_reason}, 是否爽约={is_no_show}"
        )

        return appointment

    def get_appointment_status_history(self, appointment_id: int) -> List[Dict[str, Any]]:
        """获取预约的状态变更历史"""
        records = self.db.query(StatusRecord).filter(
            StatusRecord.appointment_id == appointment_id
        ).order_by(StatusRecord.occurred_at).all()

        return [
            {
                "id": r.id,
                "status_type": r.status_type,
                "status_name": r.status_name,
                "occurred_at": r.occurred_at,
                "recorded_by": r.recorded_by,
                "notes": r.notes
            }
            for r in records
        ]

    def get_daily_status_summary(
        self,
        hospital_id: int,
        summary_date: date
    ) -> Dict[str, Any]:
        """获取某日的状态汇总"""
        records = self.db.query(StatusRecord).join(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                StatusRecord.occurred_at >= datetime.combine(summary_date, datetime.min.time()),
                StatusRecord.occurred_at < datetime.combine(
                    summary_date + datetime.timedelta(days=1),
                    datetime.min.time()
                )
            )
        ).all()

        summary = {
            "total_checkins": 0,
            "total_injections": 0,
            "total_scans_started": 0,
            "total_completed": 0,
            "total_cancelled": 0,
            "avg_wait_time_minutes": 0.0,
            "avg_scan_time_minutes": 0.0
        }

        wait_times = []
        scan_times = []

        for r in records:
            if r.status_type == "checkin":
                summary["total_checkins"] += 1
            elif r.status_type == "injection":
                summary["total_injections"] += 1
            elif r.status_type == "scanning":
                summary["total_scans_started"] += 1
            elif r.status_type == "completed":
                summary["total_completed"] += 1
                if r.scan_duration_seconds:
                    scan_times.append(r.scan_duration_seconds / 60)
            elif r.status_type == "cancelled":
                summary["total_cancelled"] += 1

        if scan_times:
            summary["avg_scan_time_minutes"] = sum(scan_times) / len(scan_times)

        return summary

    def _is_no_show(self, appointment: Appointment, cancelled_at: datetime) -> bool:
        """判断是否为爽约"""
        if appointment.appointment_date and appointment.time_slot:
            slot_hour = 9 if "上午" in appointment.time_slot else 14
            appointment_datetime = datetime.combine(
                appointment.appointment_date,
                datetime.min.time().replace(hour=slot_hour)
            )
            if cancelled_at > appointment_datetime:
                return True
        return False

    def _handle_cancelled_drug_waste(
        self,
        appointment: Appointment,
        cancelled_at: datetime,
        recorded_by: Optional[str]
    ) -> None:
        """处理取消预约导致的药物浪费"""
        if appointment.tracer_dose_mbq and appointment.tracer_batch_id:
            waste = DrugWasteRecord(
                hospital_id=appointment.hospital_id,
                tracer_id=appointment.tracer_type,
                tracer_batch_id=appointment.tracer_batch_id,
                waste_activity_mbq=appointment.tracer_dose_mbq,
                waste_reason="patient_no_show" if appointment.sub_status == "no_show" else "cancellation",
                appointment_id=appointment.id,
                recorded_at=cancelled_at,
                recorded_by=recorded_by
            )
            self.db.add(waste)

    def _calculate_estimated_wait(self, appointment: Appointment) -> int:
        """计算预计等待时间（分钟）"""
        prior_appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.hospital_id == appointment.hospital_id,
                Appointment.appointment_date == appointment.appointment_date,
                Appointment.status.in_(["checked_in", "injected"]),
                Appointment.queue_number < (appointment.queue_number or 999)
            )
        ).count()
        return prior_appointments * 45

    def _calculate_rest_time(self, appointment: Appointment) -> int:
        """计算注射后需要休息的时间（分钟）"""
        if appointment.injection_time:
            elapsed = (datetime.utcnow() - appointment.injection_time).total_seconds() / 60
            return max(0, 45 - int(elapsed))
        return 45

    def _calculate_estimated_scan_time(self, injection_time: datetime) -> datetime:
        """计算预计扫描时间"""
        return datetime.fromtimestamp(
            injection_time.timestamp() + 45 * 60
        )

    def _calculate_turnaround_time(self, appointment: Appointment) -> int:
        """计算总周转时间（分钟）"""
        if appointment.checkin_time and appointment.completion_time:
            return int((appointment.completion_time - appointment.checkin_time).total_seconds() / 60)
        return 0
