from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models import Appointment, Patient, DrugWasteRecord, Equipment, Alert, Hospital, TracerBatch
from app.schemas import (
    AlertQueryParams, AlertAcknowledgeRequest, AlertResolveRequest,
    AlertType, AlertSeverity, AlertStatus
)
from app.utils import get_logger, safe_divide
from app.exceptions import ValidationError
from app.config import get_settings

settings = get_settings()
logger = get_logger("alert_service")


class AlertService:
    """高风险监控规则服务 - 连续爽约、超时候检、药物浪费偏高预警"""

    def __init__(self, db: Session):
        self.db = db

    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """执行完整的监控周期，扫描所有风险规则"""
        logger.info("开始执行高风险监控周期")

        results = {
            "consecutive_no_show": self.check_consecutive_no_show(),
            "checkin_timeout": self.check_checkin_timeout(),
            "drug_waste_high": self.check_drug_waste_high(),
            "queue_overload": self.check_queue_overload(),
            "equipment_failure": self.check_equipment_failure(),
            "referral_delay": self.check_referral_delay()
        }

        total_alerts = sum(len(r["alerts"]) for r in results.values())
        logger.info(f"监控周期完成，生成预警 {total_alerts} 条")

        return {
            "total_alerts": total_alerts,
            "timestamp": datetime.utcnow(),
            "results": results
        }

    def check_consecutive_no_show(self) -> Dict[str, Any]:
        """检查连续爽约风险"""
        threshold = settings.MAX_CONSECUTIVE_NO_SHOW
        patients = self.db.query(Patient).filter(
            Patient.consecutive_no_show >= threshold
        ).all()

        alerts = []
        for patient in patients:
            existing_alert = self.db.query(Alert).filter(
                and_(
                    Alert.patient_id == patient.id,
                    Alert.alert_type == AlertType.CONSECUTIVE_NO_SHOW.value,
                    Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value])
                )
            ).first()

            if not existing_alert:
                alert = self._create_alert(
                    alert_type=AlertType.CONSECUTIVE_NO_SHOW,
                    severity=AlertSeverity.WARNING if patient.consecutive_no_show < 5 else AlertSeverity.ERROR,
                    patient_id=patient.id,
                    hospital_id=patient.last_hospital_id if hasattr(patient, 'last_hospital_id') else None,
                    title=f"患者连续爽约预警",
                    message=f"患者 {patient.name} 已连续爽约 {patient.consecutive_no_show} 次，达到风险阈值",
                    metric_name="consecutive_no_show",
                    metric_value=patient.consecutive_no_show,
                    threshold_value=threshold,
                    unit="次"
                )
                alerts.append(alert)

        return {
            "rule": "consecutive_no_show",
            "threshold": threshold,
            "total_patients": len(patients),
            "alerts": alerts
        }

    def check_checkin_timeout(self) -> Dict[str, Any]:
        """检查超时候检风险"""
        timeout_minutes = settings.CHECKIN_TIMEOUT_MINUTES
        now = datetime.utcnow()
        today = date.today()

        appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.appointment_date == today,
                Appointment.status.in_(["confirmed"]),
                Appointment.checkin_time.is_(None)
            )
        ).all()

        alerts = []
        for apt in appointments:
            if apt.time_slot and apt.injection_time:
                expected_time = apt.injection_time
                if expected_time and (now - expected_time).total_seconds() / 60 > timeout_minutes:
                    existing_alert = self.db.query(Alert).filter(
                        and_(
                            Alert.appointment_id == apt.id,
                            Alert.alert_type == AlertType.CHECKIN_TIMEOUT.value,
                            Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value])
                        )
                    ).first()

                    if not existing_alert:
                        delay_minutes = int((now - expected_time).total_seconds() / 60)
                        alert = self._create_alert(
                            alert_type=AlertType.CHECKIN_TIMEOUT,
                            severity=AlertSeverity.WARNING if delay_minutes < 60 else AlertSeverity.ERROR,
                            appointment_id=apt.id,
                            patient_id=apt.patient_id,
                            hospital_id=apt.hospital_id,
                            title=f"患者签到超时预警",
                            message=f"预约 {apt.appointment_no} 患者 {apt.patient.name if apt.patient else '未知'} "
                                    f"已超时 {delay_minutes} 分钟未签到",
                            metric_name="checkin_delay",
                            metric_value=delay_minutes,
                            threshold_value=timeout_minutes,
                            unit="分钟"
                        )
                        alerts.append(alert)

        return {
            "rule": "checkin_timeout",
            "threshold_minutes": timeout_minutes,
            "total_overdue": len(appointments),
            "alerts": alerts
        }

    def check_drug_waste_high(self) -> Dict[str, Any]:
        """检查药物浪费偏高风险"""
        threshold = settings.DRUG_WASTE_THRESHOLD
        today = date.today()
        week_ago = today - timedelta(days=7)

        hospital_ids = self.db.query(Hospital.id).filter(Hospital.is_active == True).all()
        hospital_ids = [h[0] for h in hospital_ids]

        alerts = []
        for hospital_id in hospital_ids:
            waste_records = self.db.query(DrugWasteRecord).filter(
                and_(
                    DrugWasteRecord.hospital_id == hospital_id,
                    func.date(DrugWasteRecord.recorded_at) >= week_ago,
                    func.date(DrugWasteRecord.recorded_at) <= today
                )
            ).all()

            if waste_records:
                total_waste = sum(w.waste_activity_mbq for w in waste_records)
                total_used = self._get_total_used_for_period(hospital_id, week_ago, today)
                waste_rate = safe_divide(total_waste, total_waste + total_used)

                if waste_rate > threshold:
                    existing_alert = self.db.query(Alert).filter(
                        and_(
                            Alert.hospital_id == hospital_id,
                            Alert.alert_type == AlertType.DRUG_WASTE_HIGH.value,
                            Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value]),
                            func.date(Alert.generated_at) == today
                        )
                    ).first()

                    if not existing_alert:
                        severity = AlertSeverity.WARNING if waste_rate < threshold * 1.5 else AlertSeverity.ERROR
                        alert = self._create_alert(
                            alert_type=AlertType.DRUG_WASTE_HIGH,
                            severity=severity,
                            hospital_id=hospital_id,
                            title=f"药物浪费率偏高预警",
                            message=f"院区近7天药物浪费率为 {waste_rate*100:.1f}%，"
                                    f"超过阈值 {threshold*100:.1f}%",
                            metric_name="drug_waste_rate",
                            metric_value=waste_rate,
                            threshold_value=threshold,
                            unit="%"
                        )
                        alerts.append(alert)

        return {
            "rule": "drug_waste_high",
            "threshold": threshold,
            "total_hospitals_checked": len(hospital_ids),
            "alerts": alerts
        }

    def check_queue_overload(self) -> Dict[str, Any]:
        """检查队列过载风险"""
        overload_threshold = settings.QUEUE_OVERLOAD_THRESHOLD
        today = date.today()

        hospital_ids = self.db.query(Hospital.id).filter(Hospital.is_active == True).all()
        hospital_ids = [h[0] for h in hospital_ids]

        alerts = []
        for hospital_id in hospital_ids:
            appointments = self.db.query(Appointment).filter(
                and_(
                    Appointment.hospital_id == hospital_id,
                    Appointment.appointment_date == today,
                    Appointment.status.in_(["confirmed", "checked_in"])
                )
            ).all()

            from app.services import ReportService
            report_service = ReportService(self.db)
            capacity = report_service._get_daily_capacity(hospital_id, today)

            if capacity > 0:
                utilization = safe_divide(len(appointments), capacity)
                if utilization > overload_threshold:
                    existing_alert = self.db.query(Alert).filter(
                        and_(
                            Alert.hospital_id == hospital_id,
                            Alert.alert_type == AlertType.QUEUE_OVERLOAD.value,
                            Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value]),
                            func.date(Alert.generated_at) == today
                        )
                    ).first()

                    if not existing_alert:
                        severity = AlertSeverity.WARNING if utilization < overload_threshold * 1.2 else AlertSeverity.ERROR
                        alert = self._create_alert(
                            alert_type=AlertType.QUEUE_OVERLOAD,
                            severity=severity,
                            hospital_id=hospital_id,
                            title=f"检查队列过载预警",
                            message=f"院区今日队列利用率为 {utilization*100:.1f}%，"
                                    f"已预约 {len(appointments)}/{capacity} 人",
                            metric_name="queue_utilization",
                            metric_value=utilization,
                            threshold_value=overload_threshold,
                            unit="%"
                        )
                        alerts.append(alert)

        return {
            "rule": "queue_overload",
            "threshold": overload_threshold,
            "total_hospitals_checked": len(hospital_ids),
            "alerts": alerts
        }

    def check_equipment_failure(self) -> Dict[str, Any]:
        """检查设备故障风险"""
        equipment = self.db.query(Equipment).filter(
            and_(
                Equipment.is_active == True,
                Equipment.status == "out_of_service"
            )
        ).all()

        alerts = []
        for eq in equipment:
            existing_alert = self.db.query(Alert).filter(
                and_(
                    Alert.equipment_id == eq.id,
                    Alert.alert_type == AlertType.EQUIPMENT_FAILURE.value,
                    Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value])
                )
            ).first()

            if not existing_alert:
                downtime_minutes = 0
                if eq.status_updated_at:
                    downtime_minutes = int((datetime.utcnow() - eq.status_updated_at).total_seconds() / 60)

                alert = self._create_alert(
                    alert_type=AlertType.EQUIPMENT_FAILURE,
                    severity=AlertSeverity.CRITICAL if downtime_minutes > 120 else AlertSeverity.ERROR,
                    equipment_id=eq.id,
                    hospital_id=eq.hospital_id,
                    title=f"设备故障预警",
                    message=f"设备 {eq.name} ({eq.code}) 已停机 {downtime_minutes} 分钟，原因: {eq.status_reason}",
                    metric_name="downtime",
                    metric_value=downtime_minutes,
                    threshold_value=60,
                    unit="分钟"
                )
                alerts.append(alert)

        return {
            "rule": "equipment_failure",
            "threshold_minutes": 60,
            "total_equipment_down": len(equipment),
            "alerts": alerts
        }

    def check_referral_delay(self) -> Dict[str, Any]:
        """检查转诊延迟风险"""
        delay_threshold_hours = settings.REFERRAL_DELAY_THRESHOLD_HOURS
        now = datetime.utcnow()

        from app.models import Referral
        referrals = self.db.query(Referral).filter(
            Referral.status == "proposed"
        ).all()

        alerts = []
        for referral in referrals:
            if referral.created_at:
                delay_hours = (now - referral.created_at).total_seconds() / 3600
                if delay_hours > delay_threshold_hours:
                    existing_alert = self.db.query(Alert).filter(
                        and_(
                            Alert.appointment_id == referral.appointment_id,
                            Alert.alert_type == AlertType.REFERRAL_DELAY.value,
                            Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value])
                        )
                    ).first()

                    if not existing_alert:
                        severity = AlertSeverity.WARNING if delay_hours < delay_threshold_hours * 2 else AlertSeverity.ERROR
                        alert = self._create_alert(
                            alert_type=AlertType.REFERRAL_DELAY,
                            severity=severity,
                            appointment_id=referral.appointment_id,
                            patient_id=referral.patient_id,
                            hospital_id=referral.target_hospital_id,
                            title=f"转诊响应延迟预警",
                            message=f"转诊 {referral.referral_no} 已等待 {delay_hours:.1f} 小时未确认",
                            metric_name="referral_delay",
                            metric_value=delay_hours,
                            threshold_value=delay_threshold_hours,
                            unit="小时"
                        )
                        alerts.append(alert)

        return {
            "rule": "referral_delay",
            "threshold_hours": delay_threshold_hours,
            "total_delayed": len(referrals),
            "alerts": alerts
        }

    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        hospital_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        equipment_id: Optional[int] = None,
        tracer_batch_id: Optional[int] = None,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        unit: Optional[str] = None
    ) -> Alert:
        """创建预警记录"""
        alert = Alert(
            alert_type=alert_type.value,
            alert_code=f"{alert_type.value.upper()}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            severity=severity.value,
            hospital_id=hospital_id,
            patient_id=patient_id,
            appointment_id=appointment_id,
            equipment_id=equipment_id,
            tracer_batch_id=tracer_batch_id,
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_value=threshold_value,
            unit=unit,
            status=AlertStatus.OPEN.value,
            escalation_level=self._determine_escalation_level(severity, metric_value, threshold_value),
            generated_at=datetime.utcnow()
        )

        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        logger.warning(
            f"预警生成: {alert.alert_code}, 类型={alert_type.value}, "
            f"严重程度={severity.value}, 标题={title}"
        )

        if alert.escalation_level >= 2:
            self._handle_escalation(alert)

        return alert

    def _determine_escalation_level(
        self,
        severity: AlertSeverity,
        metric_value: Optional[float],
        threshold_value: Optional[float]
    ) -> int:
        """确定升级级别"""
        if severity == AlertSeverity.CRITICAL:
            return 3
        elif severity == AlertSeverity.ERROR:
            if metric_value and threshold_value and metric_value > threshold_value * 2:
                return 3
            return 2
        elif severity == AlertSeverity.WARNING:
            return 1
        else:
            return 1

    def _handle_escalation(self, alert: Alert) -> None:
        """处理预警升级"""
        if not alert.escalation_notified:
            logger.critical(
                f"预警升级: {alert.alert_code}, 级别={alert.escalation_level}, "
                f"需要通知相关管理人员"
            )
            alert.escalation_notified = True
            self.db.commit()

    def acknowledge_alert(
        self,
        alert_id: int,
        request: AlertAcknowledgeRequest
    ) -> Dict[str, Any]:
        """确认预警"""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValidationError(f"预警不存在: {alert_id}")

        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.status_changed_at = datetime.utcnow()
        alert.acknowledged_by = request.acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        if request.notes:
            alert.notes = request.notes

        self.db.commit()
        self.db.refresh(alert)

        logger.info(f"预警已确认: {alert.alert_code}, 确认人={request.acknowledged_by}")

        return {
            "success": True,
            "alert_id": alert.id,
            "alert_code": alert.alert_code,
            "status": alert.status,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at
        }

    def resolve_alert(
        self,
        alert_id: int,
        request: AlertResolveRequest
    ) -> Dict[str, Any]:
        """处理解决预警"""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValidationError(f"预警不存在: {alert_id}")

        alert.status = AlertStatus.RESOLVED.value
        alert.status_changed_at = datetime.utcnow()
        alert.resolved_by = request.resolved_by
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = request.resolution_notes
        alert.auto_resolve = request.auto_resolve

        self.db.commit()
        self.db.refresh(alert)

        logger.info(f"预警已解决: {alert.alert_code}, 处理人={request.resolved_by}")

        return {
            "success": True,
            "alert_id": alert.id,
            "alert_code": alert.alert_code,
            "status": alert.status,
            "resolved_by": alert.resolved_by,
            "resolved_at": alert.resolved_at,
            "resolution_notes": alert.resolution_notes
        }

    def query_alerts(
        self,
        params: AlertQueryParams
    ) -> Dict[str, Any]:
        """查询预警列表"""
        query = self.db.query(Alert)

        if params.hospital_id:
            query = query.filter(Alert.hospital_id == params.hospital_id)
        if params.alert_type:
            query = query.filter(Alert.alert_type == params.alert_type.value)
        if params.severity:
            query = query.filter(Alert.severity == params.severity.value)
        if params.status:
            query = query.filter(Alert.status == params.status.value)
        if params.patient_id:
            query = query.filter(Alert.patient_id == params.patient_id)
        if params.equipment_id:
            query = query.filter(Alert.equipment_id == params.equipment_id)
        if params.escalation_level:
            query = query.filter(Alert.escalation_level == params.escalation_level)
        if params.only_active:
            query = query.filter(Alert.status.in_([
                AlertStatus.OPEN.value,
                AlertStatus.ACKNOWLEDGED.value,
                AlertStatus.IN_PROGRESS.value
            ]))
        if params.start_date:
            query = query.filter(func.date(Alert.generated_at) >= params.start_date)
        if params.end_date:
            query = query.filter(func.date(Alert.generated_at) <= params.end_date)

        total = query.count()
        alerts = query.order_by(desc(Alert.generated_at)).all()

        return {
            "total": total,
            "items": [
                {
                    "id": a.id,
                    "alert_type": a.alert_type,
                    "alert_code": a.alert_code,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "metric_value": a.metric_value,
                    "threshold_value": a.threshold_value,
                    "status": a.status,
                    "hospital_id": a.hospital_id,
                    "patient_id": a.patient_id,
                    "appointment_id": a.appointment_id,
                    "escalation_level": a.escalation_level,
                    "generated_at": a.generated_at
                }
                for a in alerts
            ]
        }

    def get_alert_summary(
        self,
        hospital_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取预警摘要"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        query = self.db.query(Alert).filter(
            and_(
                func.date(Alert.generated_at) >= start_date,
                func.date(Alert.generated_at) <= end_date
            )
        )

        if hospital_id:
            query = query.filter(Alert.hospital_id == hospital_id)

        alerts = query.all()

        summary = {
            "total_alerts": len(alerts),
            "open_alerts": sum(1 for a in alerts if a.status == AlertStatus.OPEN.value),
            "acknowledged_alerts": sum(1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED.value),
            "resolved_alerts": sum(1 for a in alerts if a.status == AlertStatus.RESOLVED.value),
            "critical_alerts": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL.value),
            "error_alerts": sum(1 for a in alerts if a.severity == AlertSeverity.ERROR.value),
            "warning_alerts": sum(1 for a in alerts if a.severity == AlertSeverity.WARNING.value),
            "by_type": {},
            "avg_resolution_time_minutes": 0
        }

        for alert_type in AlertType:
            count = sum(1 for a in alerts if a.alert_type == alert_type.value)
            if count > 0:
                summary["by_type"][alert_type.value] = count

        resolved_alerts = [a for a in alerts if a.status == AlertStatus.RESOLVED.value]
        if resolved_alerts:
            resolution_times = []
            for a in resolved_alerts:
                if a.generated_at and a.resolved_at:
                    resolution_times.append((a.resolved_at - a.generated_at).total_seconds() / 60)
            if resolution_times:
                summary["avg_resolution_time_minutes"] = sum(resolution_times) / len(resolution_times)

        return summary

    def _get_total_used_for_period(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date
    ) -> float:
        """获取某时期内总药物使用量"""
        from app.models import TracerUsage
        usages = self.db.query(TracerUsage).join(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                func.date(TracerUsage.injection_time) >= start_date,
                func.date(TracerUsage.injection_time) <= end_date
            )
        ).all()
        return sum(u.dose_mbq for u in usages)
