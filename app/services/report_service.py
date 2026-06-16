from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, extract

from app.models import (
    Appointment, Hospital, Equipment, TracerBatch, TracerUsage,
    Referral, StatusRecord, DrugWasteRecord, Alert
)
from app.schemas import (
    ReportQueryParams, ReportExportRequest,
    TurnoverEfficiencyReport, TurnoverEfficiencyItem,
    DrugUtilizationReport, DrugUtilizationItem,
    ReferralCompletionReport, ReferralCompletionItem,
    DailyOperationReport, DailyOperationItem,
    ReportType, ReportFormat
)
from app.utils import get_logger, safe_divide, parse_date_range
from app.exceptions import ValidationError
from app.config import get_settings

settings = get_settings()
logger = get_logger("report_service")


class ReportService:
    """模块5: 运营报表服务 - 周转效率、药物利用率、转诊完成率统计"""

    def __init__(self, db: Session):
        self.db = db

    def generate_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """根据参数生成对应类型的报表"""
        if params.report_type == ReportType.TURNOVER_EFFICIENCY:
            return self.generate_turnover_efficiency_report(params)
        elif params.report_type == ReportType.DRUG_UTILIZATION:
            return self.generate_drug_utilization_report(params)
        elif params.report_type == ReportType.REFERRAL_COMPLETION:
            return self.generate_referral_completion_report(params)
        elif params.report_type == ReportType.DAILY_OPERATION:
            return self.generate_daily_operation_report(params)
        elif params.report_type == ReportType.RISK_ANALYSIS:
            return self.generate_risk_analysis_report(params)
        else:
            raise ValidationError(f"不支持的报表类型: {params.report_type}")

    def generate_turnover_efficiency_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """
        生成周转效率报表
        统计：完成率、爽约率、平均等待时间、设备利用率等
        """
        start_date, end_date = parse_date_range(params.start_date, params.end_date)
        date_list = self._get_date_range(start_date, end_date, params.granularity)

        hospital_ids = self._get_hospital_ids(params.hospital_id)
        items: List[TurnoverEfficiencyItem] = []

        for stat_date in date_list:
            for hospital_id in hospital_ids:
                item = self._calculate_turnover_efficiency_item(
                    hospital_id=hospital_id,
                    stat_date=stat_date,
                    granularity=params.granularity
                )
                if item:
                    items.append(item)

        summary = self._calculate_turnover_summary(items, params)
        trends = self._calculate_turnover_trends(items, params) if params.include_details else None
        hospital_comparison = self._calculate_hospital_comparison(items) if len(hospital_ids) > 1 else None

        report = TurnoverEfficiencyReport(
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow(),
            summary=summary,
            items=items,
            trends=trends,
            hospital_comparison=hospital_comparison
        )

        return report.model_dump()

    def generate_drug_utilization_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """
        生成药物利用率报表
        统计：药物使用率、浪费率、平均剂量、浪费成本等
        """
        start_date, end_date = parse_date_range(params.start_date, params.end_date)
        date_list = self._get_date_range(start_date, end_date, params.granularity)

        hospital_ids = self._get_hospital_ids(params.hospital_id)
        items: List[DrugUtilizationItem] = []

        for stat_date in date_list:
            for hospital_id in hospital_ids:
                daily_items = self._calculate_drug_utilization_items(
                    hospital_id=hospital_id,
                    stat_date=stat_date,
                    granularity=params.granularity
                )
                items.extend(daily_items)

        summary = self._calculate_drug_summary(items, params)
        trends = self._calculate_drug_trends(items, params) if params.include_details else None
        tracer_breakdown = self._calculate_tracer_breakdown(items)
        waste_analysis = self._calculate_waste_analysis(params)

        report = DrugUtilizationReport(
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow(),
            summary=summary,
            items=items,
            trends=trends,
            tracer_breakdown=tracer_breakdown,
            waste_analysis=waste_analysis
        )

        return report.model_dump()

    def generate_referral_completion_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """
        生成转诊完成率报表
        统计：转诊完成率、接受率、平均响应时间、自动分配接受率等
        """
        start_date, end_date = parse_date_range(params.start_date, params.end_date)
        date_list = self._get_date_range(start_date, end_date, params.granularity)

        hospital_ids = self._get_hospital_ids(params.hospital_id)
        items: List[ReferralCompletionItem] = []

        for stat_date in date_list:
            for hospital_id in hospital_ids:
                item = self._calculate_referral_completion_item(
                    hospital_id=hospital_id,
                    stat_date=stat_date,
                    granularity=params.granularity
                )
                if item:
                    items.append(item)

        summary = self._calculate_referral_summary(items, params)
        trends = self._calculate_referral_trends(items, params) if params.include_details else None
        hospital_network = self._calculate_referral_network(items) if len(hospital_ids) > 1 else None
        reason_analysis = self._calculate_referral_reason_analysis(params)

        report = ReferralCompletionReport(
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow(),
            summary=summary,
            items=items,
            trends=trends,
            hospital_network=hospital_network,
            reason_analysis=reason_analysis
        )

        return report.model_dump()

    def generate_daily_operation_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """
        生成每日运营报表
        综合展示院区每日运营情况
        """
        start_date, end_date = parse_date_range(params.start_date, params.end_date)
        date_list = self._get_date_range(start_date, end_date, "daily")

        hospital_ids = self._get_hospital_ids(params.hospital_id)
        items: List[DailyOperationItem] = []

        for stat_date in date_list:
            for hospital_id in hospital_ids:
                item = self._calculate_daily_operation_item(
                    hospital_id=hospital_id,
                    stat_date=stat_date
                )
                if item:
                    items.append(item)

        summary = self._calculate_daily_summary(items)
        kpi_summary = self._calculate_kpi_summary(items)
        alerts_summary = self._calculate_alerts_summary(params)

        report = DailyOperationReport(
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.utcnow(),
            summary=summary,
            items=items,
            kpi_summary=kpi_summary,
            alerts_summary=alerts_summary
        )

        return report.model_dump()

    def generate_risk_analysis_report(
        self,
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """生成风险分析报表"""
        start_date, end_date = parse_date_range(params.start_date, params.end_date)

        alerts = self.db.query(Alert).filter(
            and_(
                Alert.generated_at >= datetime.combine(start_date, datetime.min.time()),
                Alert.generated_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
                (Alert.hospital_id == params.hospital_id) if params.hospital_id else True
            )
        ).all()

        alert_types = {}
        severities = {}
        statuses = {}

        for alert in alerts:
            alert_types[alert.alert_type] = alert_types.get(alert.alert_type, 0) + 1
            severities[alert.severity] = severities.get(alert.severity, 0) + 1
            statuses[alert.status] = statuses.get(alert.status, 0) + 1

        high_risk_patients = self.db.query(Appointment.patient_id).filter(
            and_(
                func.date(Appointment.created_at) >= start_date,
                func.date(Appointment.created_at) <= end_date,
                Appointment.status == "no_show"
            )
        ).group_by(Appointment.patient_id).having(func.count(Appointment.id) >= 3).all()

        return {
            "report_type": "risk_analysis",
            "start_date": start_date,
            "end_date": end_date,
            "generated_at": datetime.utcnow(),
            "summary": {
                "total_alerts": len(alerts),
                "alert_types": alert_types,
                "severities": severities,
                "statuses": statuses,
                "high_risk_patients_count": len(high_risk_patients),
                "open_critical_alerts": sum(
                    1 for a in alerts
                    if a.severity in ["critical", "error"] and a.status in ["open", "acknowledged"]
                )
            },
            "top_risks": self._identify_top_risks(alerts, params)
        }

    def _calculate_turnover_efficiency_item(
        self,
        hospital_id: int,
        stat_date: date,
        granularity: str
    ) -> Optional[TurnoverEfficiencyItem]:
        """计算单院区单日期的周转效率数据"""
        date_filter = self._get_date_filter(stat_date, granularity, "appointment_date")

        appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                date_filter
            )
        ).all()

        if not appointments:
            return None

        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        hospital_name = hospital.name if hospital else f"院区{hospital_id}"

        total_count = len(appointments)
        completed_count = sum(1 for a in appointments if a.status == "completed")
        cancelled_count = sum(1 for a in appointments if a.status == "cancelled")
        no_show_count = sum(1 for a in appointments if a.status == "no_show" or a.sub_status == "no_show")

        wait_times = []
        scan_times = []
        turnover_times = []

        for a in appointments:
            if a.checkin_time and a.injection_time:
                wait_times.append((a.injection_time - a.checkin_time).total_seconds() / 60)
            if a.scan_start_time and a.scan_end_time:
                scan_times.append((a.scan_end_time - a.scan_start_time).total_seconds() / 60)
            if a.checkin_time and a.completion_time:
                turnover_times.append((a.completion_time - a.checkin_time).total_seconds() / 60)

        hour_counts = {}
        for a in appointments:
            if a.checkin_time:
                hour = a.checkin_time.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

        peak_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None
        peak_count = hour_counts.get(peak_hour, 0) if peak_hour else 0

        equipment_utilization = self._calculate_equipment_utilization(hospital_id, stat_date)
        daily_capacity = self._get_daily_capacity(hospital_id, stat_date)

        return TurnoverEfficiencyItem(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            stat_date=stat_date,
            total_appointments=total_count,
            completed_count=completed_count,
            cancelled_count=cancelled_count,
            no_show_count=no_show_count,
            completion_rate=safe_divide(completed_count, total_count),
            no_show_rate=safe_divide(no_show_count, total_count),
            avg_wait_time_minutes=sum(wait_times) / len(wait_times) if wait_times else 0.0,
            avg_scan_time_minutes=sum(scan_times) / len(scan_times) if scan_times else 0.0,
            avg_turnover_minutes=sum(turnover_times) / len(turnover_times) if turnover_times else 0.0,
            equipment_utilization_rate=equipment_utilization,
            daily_capacity_utilization=safe_divide(total_count, daily_capacity),
            peak_hour=f"{peak_hour}:00" if peak_hour else None,
            peak_count=peak_count
        )

    def _calculate_drug_utilization_items(
        self,
        hospital_id: int,
        stat_date: date,
        granularity: str
    ) -> List[DrugUtilizationItem]:
        """计算单院区单日期的药物利用数据（按药物分类）"""
        date_filter = self._get_date_filter(stat_date, granularity, "injection_time")

        usages = self.db.query(TracerUsage).join(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                date_filter
            )
        ).all()

        if not usages:
            return []

        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        hospital_name = hospital.name if hospital else f"院区{hospital_id}"

        tracer_groups: Dict[int, List[TracerUsage]] = {}
        for usage in usages:
            tracer_groups.setdefault(usage.tracer_id, []).append(usage)

        items = []
        for tracer_id, tracer_usages in tracer_groups.items():
            tracer = self.db.query(TracerBatch.tracer).filter(
                TracerBatch.tracer_id == tracer_id
            ).first()

            if not tracer:
                continue

            total_used = sum(u.dose_mbq for u in tracer_usages)
            total_wasted = sum(u.waste_activity or 0 for u in tracer_usages)
            total_received = total_used + total_wasted

            waste_records = self.db.query(DrugWasteRecord).filter(
                and_(
                    DrugWasteRecord.hospital_id == hospital_id,
                    DrugWasteRecord.tracer_id == tracer_id,
                    DrugWasteRecord.waste_date == stat_date
                )
            ).all()

            noshow_waste = sum(
                w.wasted_activity_mbq for w in waste_records
                if w.waste_type == "patient_no_show"
            )
            expired_waste = sum(
                w.wasted_activity_mbq for w in waste_records
                if w.waste_type == "expired"
            )

            avg_dose = total_used / len(tracer_usages) if tracer_usages else 0

            items.append(
                DrugUtilizationItem(
                    hospital_id=hospital_id,
                    hospital_name=hospital_name,
                    stat_date=stat_date,
                    tracer_id=tracer_id,
                    tracer_name=tracer[0].name if hasattr(tracer[0], 'name') else f"药物{tracer_id}",
                    total_received_mbq=total_received,
                    total_used_mbq=total_used,
                    total_wasted_mbq=total_wasted,
                    utilization_rate=safe_divide(total_used, total_received),
                    waste_rate=safe_divide(total_wasted, total_received),
                    waste_rate_noshow=safe_divide(noshow_waste, total_received),
                    waste_rate_expired=safe_divide(expired_waste, total_received),
                    average_dose_mbq=avg_dose,
                    patient_count=len(tracer_usages),
                    batch_count=len(set(u.batch_id for u in tracer_usages)),
                    cost_estimate=total_used * 0.05,
                    waste_cost=total_wasted * 0.05
                )
            )

        return items

    def _calculate_referral_completion_item(
        self,
        hospital_id: int,
        stat_date: date,
        granularity: str
    ) -> Optional[ReferralCompletionItem]:
        """计算单院区单日期的转诊完成数据"""
        if granularity == "daily":
            date_filter_out = func.date(Referral.created_at) == stat_date
            date_filter_in = func.date(Referral.created_at) == stat_date
        elif granularity == "weekly":
            week_start = stat_date - timedelta(days=stat_date.weekday())
            week_end = week_start + timedelta(days=6)
            date_filter_out = and_(
                func.date(Referral.created_at) >= week_start,
                func.date(Referral.created_at) <= week_end
            )
            date_filter_in = date_filter_out
        elif granularity == "monthly":
            date_filter_out = and_(
                extract('year', Referral.created_at) == stat_date.year,
                extract('month', Referral.created_at) == stat_date.month
            )
            date_filter_in = date_filter_out
        else:
            date_filter_out = func.date(Referral.created_at) == stat_date
            date_filter_in = date_filter_out

        referrals_out = self.db.query(Referral).filter(
            and_(
                Referral.source_hospital_id == hospital_id,
                date_filter_out
            )
        ).all()

        referrals_in = self.db.query(Referral).filter(
            and_(
                Referral.target_hospital_id == hospital_id,
                date_filter_in
            )
        ).all()

        all_referrals = referrals_out + referrals_in
        if not all_referrals:
            return None

        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        hospital_name = hospital.name if hospital else f"院区{hospital_id}"

        total_out = len(referrals_out)
        total_in = len(referrals_in)
        completed = sum(1 for r in all_referrals if r.status == "completed")
        accepted = sum(1 for r in all_referrals if r.status in ["accepted", "completed"])
        declined = sum(1 for r in all_referrals if r.status == "declined")
        pending = sum(1 for r in all_referrals if r.status == "proposed")

        response_times = []
        for r in all_referrals:
            if r.created_at and r.accepted_at:
                response_times.append((r.accepted_at - r.created_at).total_seconds() / 60)

        travel_times = [r.travel_time_minutes for r in all_referrals if r.travel_time_minutes]

        auto_assign_count = sum(1 for r in all_referrals if r.auto_assigned)
        auto_assign_accepted = sum(
            1 for r in all_referrals
            if r.auto_assigned and r.status in ["accepted", "completed"]
        )

        reason_counts = {}
        for r in all_referrals:
            if r.referral_reason:
                reason_counts[r.referral_reason] = reason_counts.get(r.referral_reason, 0) + 1

        top_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return ReferralCompletionItem(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            stat_date=stat_date,
            total_referrals_out=total_out,
            total_referrals_in=total_in,
            completed_referrals=completed,
            accepted_referrals=accepted,
            declined_referrals=declined,
            pending_referrals=pending,
            completion_rate=safe_divide(completed, len(all_referrals)),
            acceptance_rate=safe_divide(accepted, len(all_referrals)),
            avg_response_time_minutes=sum(response_times) / len(response_times) if response_times else 0.0,
            avg_travel_time_minutes=sum(travel_times) / len(travel_times) if travel_times else 0.0,
            auto_assign_count=auto_assign_count,
            auto_assign_acceptance_rate=safe_divide(auto_assign_accepted, auto_assign_count),
            top_reasons=top_reasons
        )

    def _calculate_daily_operation_item(
        self,
        hospital_id: int,
        stat_date: date
    ) -> Optional[DailyOperationItem]:
        """计算单院区单日运营数据"""
        appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.hospital_id == hospital_id,
                func.date(Appointment.appointment_date) == stat_date
            )
        ).all()

        if not appointments:
            return None

        hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
        hospital_name = hospital.name if hospital else f"院区{hospital_id}"

        capacity = self._get_daily_capacity(hospital_id, stat_date)
        morning_capacity = capacity // 2
        afternoon_capacity = capacity - morning_capacity

        morning = [a for a in appointments if a.time_slot and "上午" in a.time_slot]
        afternoon = [a for a in appointments if a.time_slot and "下午" in a.time_slot]

        alerts = self.db.query(Alert).filter(
            and_(
                Alert.hospital_id == hospital_id,
                func.date(Alert.generated_at) == stat_date
            )
        ).all()

        equipment_downtime = self._calculate_equipment_downtime(hospital_id, stat_date)

        queue_times = []
        for a in appointments:
            if a.checkin_time and a.injection_time:
                queue_times.append((a.injection_time - a.checkin_time).total_seconds() / 60)

        return DailyOperationItem(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            stat_date=stat_date,
            morning_capacity=morning_capacity,
            afternoon_capacity=afternoon_capacity,
            total_capacity=capacity,
            morning_booked=len(morning),
            afternoon_booked=len(afternoon),
            total_booked=len(appointments),
            morning_utilization=safe_divide(len(morning), morning_capacity),
            afternoon_utilization=safe_divide(len(afternoon), afternoon_capacity),
            total_utilization=safe_divide(len(appointments), capacity),
            emergency_count=sum(1 for a in appointments if a.urgency_level == "emergency"),
            urgent_count=sum(1 for a in appointments if a.urgency_level == "urgent"),
            inpatient_count=sum(1 for a in appointments if a.is_inpatient),
            anesthesia_count=sum(1 for a in appointments if a.needs_anesthesia),
            plus_sign_count=sum(1 for a in appointments if a.is_plus_sign),
            avg_queue_time=sum(queue_times) / len(queue_times) if queue_times else 0.0,
            equipment_available_hours=self._calculate_equipment_available_hours(hospital_id, stat_date),
            equipment_downtime_minutes=equipment_downtime,
            alerts_count=len(alerts),
            alerts_resolved_count=sum(1 for a in alerts if a.status == "resolved")
        )

    def _get_date_range(
        self,
        start_date: date,
        end_date: date,
        granularity: str
    ) -> List[date]:
        """根据时间粒度生成日期列表"""
        dates = []
        current = start_date
        while current <= end_date:
            if granularity == "daily":
                dates.append(current)
                current += timedelta(days=1)
            elif granularity == "weekly":
                dates.append(current)
                current += timedelta(weeks=1)
            elif granularity == "monthly":
                dates.append(current)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            else:
                dates.append(current)
                current += timedelta(days=1)
        return dates

    def _get_hospital_ids(self, hospital_id: Optional[int]) -> List[int]:
        """获取院区ID列表"""
        if hospital_id:
            return [hospital_id]
        hospitals = self.db.query(Hospital.id).filter(Hospital.is_active == True).all()
        return [h[0] for h in hospitals]

    def _get_date_filter(self, stat_date: date, granularity: str, field_name: str):
        """生成日期过滤条件"""
        if granularity == "daily":
            return func.date(getattr(Appointment, field_name, None) or Appointment.appointment_date) == stat_date
        elif granularity == "weekly":
            week_start = stat_date - timedelta(days=stat_date.weekday())
            week_end = week_start + timedelta(days=6)
            return and_(
                func.date(getattr(Appointment, field_name, None) or Appointment.appointment_date) >= week_start,
                func.date(getattr(Appointment, field_name, None) or Appointment.appointment_date) <= week_end
            )
        elif granularity == "monthly":
            return and_(
                extract('year', getattr(Appointment, field_name, None) or Appointment.appointment_date) == stat_date.year,
                extract('month', getattr(Appointment, field_name, None) or Appointment.appointment_date) == stat_date.month
            )
        return func.date(getattr(Appointment, field_name, None) or Appointment.appointment_date) == stat_date

    def _get_daily_capacity(self, hospital_id: int, stat_date: date) -> int:
        """获取院区某日容量"""
        from app.models import ScheduleTemplate, SupportPlan

        weekday = stat_date.weekday()
        is_weekend = weekday >= 5

        template = self.db.query(ScheduleTemplate).filter(
            and_(
                ScheduleTemplate.hospital_id == hospital_id,
                ScheduleTemplate.is_active == True
            )
        ).order_by(
            case(
                (ScheduleTemplate.template_type == "holiday" and self._is_holiday(stat_date), 1),
                (ScheduleTemplate.template_type == "weekend" if is_weekend else "weekday", 2),
                else_=3
            )
        ).first()

        base_capacity = template.daily_capacity if template else 15

        support_plans = self.db.query(SupportPlan).filter(
            and_(
                SupportPlan.hospital_id == hospital_id,
                SupportPlan.start_date <= stat_date,
                SupportPlan.end_date >= stat_date,
                SupportPlan.is_active == True
            )
        ).all()

        additional_capacity = sum(p.additional_capacity for p in support_plans)

        return base_capacity + additional_capacity

    def _is_holiday(self, stat_date: date) -> bool:
        """判断是否为节假日（简化实现）"""
        from app.models import ScheduleTemplate
        templates = self.db.query(ScheduleTemplate).filter(
            ScheduleTemplate.template_type == "holiday",
            ScheduleTemplate.is_active == True
        ).all()
        for t in templates:
            if t.special_dates:
                dates = t.special_dates.split(',')
                if stat_date.strftime("%Y-%m-%d") in dates:
                    return True
        return False

    def _calculate_equipment_utilization(self, hospital_id: int, stat_date: date) -> float:
        """计算设备利用率"""
        equipment = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True
        ).all()

        if not equipment:
            return 0.0

        total_available_hours = len(equipment) * 8
        total_used_hours = 0

        for eq in equipment:
            appointments = self.db.query(Appointment).filter(
                and_(
                    Appointment.equipment_id == eq.id,
                    func.date(Appointment.appointment_date) == stat_date,
                    Appointment.status == "completed"
                )
            ).all()
            total_used_hours += sum(a.estimated_duration_minutes for a in appointments) / 60

        return safe_divide(total_used_hours, total_available_hours)

    def _calculate_equipment_downtime(self, hospital_id: int, stat_date: date) -> int:
        """计算设备停机时间（分钟）"""
        equipment = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True,
            Equipment.status != "available"
        ).all()
        return len(equipment) * 480

    def _calculate_equipment_available_hours(self, hospital_id: int, stat_date: date) -> float:
        """计算设备可用小时数"""
        equipment = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True
        ).all()
        downtime_minutes = self._calculate_equipment_downtime(hospital_id, stat_date)
        return len(equipment) * 8 - downtime_minutes / 60

    def _calculate_turnover_summary(
        self,
        items: List[TurnoverEfficiencyItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算周转效率汇总"""
        if not items:
            return {
                "total_appointments": 0,
                "total_completed": 0,
                "total_no_show": 0,
                "overall_completion_rate": 0.0,
                "completion_rate": 0.0,
                "overall_no_show_rate": 0.0,
                "no_show_rate": 0.0,
                "avg_wait_time_minutes": 0.0,
                "avg_scan_time_minutes": 0.0,
                "avg_turnover_minutes": 0.0,
                "avg_equipment_utilization": 0.0,
                "total_hospitals": 0,
                "total_days": 0
            }

        total_appointments = sum(i.total_appointments for i in items)
        total_completed = sum(i.completed_count for i in items)
        total_no_show = sum(i.no_show_count for i in items)

        return {
            "total_appointments": total_appointments,
            "total_completed": total_completed,
            "total_no_show": total_no_show,
            "overall_completion_rate": safe_divide(total_completed, total_appointments),
            "completion_rate": safe_divide(total_completed, total_appointments),
            "overall_no_show_rate": safe_divide(total_no_show, total_appointments),
            "no_show_rate": safe_divide(total_no_show, total_appointments),
            "avg_wait_time_minutes": sum(i.avg_wait_time_minutes for i in items) / len(items),
            "avg_scan_time_minutes": sum(i.avg_scan_time_minutes for i in items) / len(items),
            "avg_turnover_minutes": sum(i.avg_turnover_minutes for i in items) / len(items),
            "avg_equipment_utilization": sum(i.equipment_utilization_rate for i in items) / len(items),
            "total_hospitals": len(set(i.hospital_id for i in items)),
            "total_days": len(set(i.stat_date for i in items))
        }

    def _calculate_drug_summary(
        self,
        items: List[DrugUtilizationItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算药物利用汇总"""
        if not items:
            return {
                "total_received_mbq": 0.0,
                "total_used_mbq": 0.0,
                "total_wasted_mbq": 0.0,
                "overall_utilization_rate": 0.0,
                "utilization_rate": 0.0,
                "overall_waste_rate": 0.0,
                "waste_rate": 0.0,
                "total_patients": 0,
                "total_cost_estimate": 0.0,
                "total_waste_cost": 0.0,
                "total_tracers": 0
            }

        total_received = sum(i.total_received_mbq for i in items)
        total_used = sum(i.total_used_mbq for i in items)
        total_wasted = sum(i.total_wasted_mbq for i in items)
        total_patients = sum(i.patient_count for i in items)

        return {
            "total_received_mbq": total_received,
            "total_used_mbq": total_used,
            "total_wasted_mbq": total_wasted,
            "overall_utilization_rate": safe_divide(total_used, total_received),
            "utilization_rate": safe_divide(total_used, total_received),
            "overall_waste_rate": safe_divide(total_wasted, total_received),
            "waste_rate": safe_divide(total_wasted, total_received),
            "total_patients": total_patients,
            "total_cost_estimate": sum(i.cost_estimate for i in items),
            "total_waste_cost": sum(i.waste_cost for i in items),
            "total_tracers": len(set(i.tracer_id for i in items))
        }

    def _calculate_referral_summary(
        self,
        items: List[ReferralCompletionItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算转诊完成汇总"""
        if not items:
            return {
                "total_referrals_out": 0,
                "total_referrals_in": 0,
                "total_referrals": 0,
                "total_completed": 0,
                "overall_completion_rate": 0.0,
                "completion_rate": 0.0,
                "overall_acceptance_rate": 0.0,
                "acceptance_rate": 0.0,
                "avg_response_time_minutes": 0.0,
                "auto_assign_total": 0,
                "auto_assign_acceptance_rate": 0.0
            }

        total_out = sum(i.total_referrals_out for i in items)
        total_in = sum(i.total_referrals_in for i in items)
        total_completed = sum(i.completed_referrals for i in items)
        total = total_out + total_in

        return {
            "total_referrals_out": total_out,
            "total_referrals_in": total_in,
            "total_referrals": total,
            "total_completed": total_completed,
            "overall_completion_rate": safe_divide(total_completed, total),
            "completion_rate": safe_divide(total_completed, total),
            "overall_acceptance_rate": sum(i.acceptance_rate for i in items) / len(items),
            "acceptance_rate": sum(i.acceptance_rate for i in items) / len(items),
            "avg_response_time_minutes": sum(i.avg_response_time_minutes for i in items) / len(items),
            "auto_assign_total": sum(i.auto_assign_count for i in items),
            "auto_assign_acceptance_rate": sum(i.auto_assign_acceptance_rate for i in items) / len(items) if items else 0
        }

    def _calculate_daily_summary(self, items: List[DailyOperationItem]) -> Dict[str, Any]:
        """计算每日运营汇总"""
        if not items:
            return {}

        return {
            "total_capacity": sum(i.total_capacity for i in items),
            "total_booked": sum(i.total_booked for i in items),
            "overall_utilization": safe_divide(sum(i.total_booked for i in items), sum(i.total_capacity for i in items)),
            "total_emergency": sum(i.emergency_count for i in items),
            "total_urgent": sum(i.urgent_count for i in items),
            "total_inpatient": sum(i.inpatient_count for i in items),
            "total_plus_sign": sum(i.plus_sign_count for i in items)
        }

    def _calculate_kpi_summary(self, items: List[DailyOperationItem]) -> Dict[str, Any]:
        """计算KPI摘要"""
        if not items:
            return {}

        return {
            "avg_daily_utilization": sum(i.total_utilization for i in items) / len(items),
            "avg_morning_utilization": sum(i.morning_utilization for i in items) / len(items),
            "avg_afternoon_utilization": sum(i.afternoon_utilization for i in items) / len(items),
            "avg_queue_time_minutes": sum(i.avg_queue_time for i in items) / len(items),
            "avg_equipment_available_hours": sum(i.equipment_available_hours for i in items) / len(items),
            "avg_plus_sign_count": sum(i.plus_sign_count for i in items) / len(items)
        }

    def _calculate_alerts_summary(self, params: ReportQueryParams) -> Dict[str, Any]:
        """计算预警摘要"""
        alerts = self.db.query(Alert).filter(
            and_(
                func.date(Alert.generated_at) >= params.start_date,
                func.date(Alert.generated_at) <= params.end_date,
                (Alert.hospital_id == params.hospital_id) if params.hospital_id else True
            )
        ).all()

        return {
            "total_alerts": len(alerts),
            "open_alerts": sum(1 for a in alerts if a.status == "open"),
            "resolved_alerts": sum(1 for a in alerts if a.status == "resolved"),
            "critical_alerts": sum(1 for a in alerts if a.severity == "critical"),
            "consecutive_no_show_alerts": sum(1 for a in alerts if a.alert_type == "consecutive_no_show"),
            "drug_waste_alerts": sum(1 for a in alerts if a.alert_type == "drug_waste"),
            "timeout_alerts": sum(1 for a in alerts if a.alert_type == "no_show_timeout")
        }

    def _calculate_turnover_trends(
        self,
        items: List[TurnoverEfficiencyItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算周转效率趋势"""
        dates = sorted(set(i.stat_date for i in items))
        completion_rates = []
        no_show_rates = []

        for d in dates:
            day_items = [i for i in items if i.stat_date == d]
            if day_items:
                total = sum(i.total_appointments for i in day_items)
                completed = sum(i.completed_count for i in day_items)
                no_show = sum(i.no_show_count for i in day_items)
                completion_rates.append(safe_divide(completed, total))
                no_show_rates.append(safe_divide(no_show, total))

        return {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "completion_rates": completion_rates,
            "no_show_rates": no_show_rates
        }

    def _calculate_drug_trends(
        self,
        items: List[DrugUtilizationItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算药物利用趋势"""
        dates = sorted(set(i.stat_date for i in items))
        utilization_rates = []
        waste_rates = []

        for d in dates:
            day_items = [i for i in items if i.stat_date == d]
            if day_items:
                total_received = sum(i.total_received_mbq for i in day_items)
                total_used = sum(i.total_used_mbq for i in day_items)
                total_wasted = sum(i.total_wasted_mbq for i in day_items)
                utilization_rates.append(safe_divide(total_used, total_received))
                waste_rates.append(safe_divide(total_wasted, total_received))

        return {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "utilization_rates": utilization_rates,
            "waste_rates": waste_rates
        }

    def _calculate_referral_trends(
        self,
        items: List[ReferralCompletionItem],
        params: ReportQueryParams
    ) -> Dict[str, Any]:
        """计算转诊趋势"""
        dates = sorted(set(i.stat_date for i in items))
        referral_counts = []
        completion_rates = []

        for d in dates:
            day_items = [i for i in items if i.stat_date == d]
            if day_items:
                total = sum(i.total_referrals_out + i.total_referrals_in for i in day_items)
                completed = sum(i.completed_referrals for i in day_items)
                referral_counts.append(total)
                completion_rates.append(safe_divide(completed, total))

        return {
            "dates": [d.strftime("%Y-%m-%d") for d in dates],
            "referral_counts": referral_counts,
            "completion_rates": completion_rates
        }

    def _calculate_hospital_comparison(
        self,
        items: List[TurnoverEfficiencyItem]
    ) -> Dict[str, Any]:
        """计算院区间对比"""
        hospitals = {}
        for item in items:
            if item.hospital_id not in hospitals:
                hospitals[item.hospital_id] = {
                    "hospital_name": item.hospital_name,
                    "total_appointments": 0,
                    "total_completed": 0,
                    "avg_completion_rate": [],
                    "avg_no_show_rate": []
                }
            hospitals[item.hospital_id]["total_appointments"] += item.total_appointments
            hospitals[item.hospital_id]["total_completed"] += item.completed_count
            hospitals[item.hospital_id]["avg_completion_rate"].append(item.completion_rate)
            hospitals[item.hospital_id]["avg_no_show_rate"].append(item.no_show_rate)

        result = {}
        for h_id, data in hospitals.items():
            result[h_id] = {
                "hospital_name": data["hospital_name"],
                "total_appointments": data["total_appointments"],
                "completion_rate": safe_divide(data["total_completed"], data["total_appointments"]),
                "avg_completion_rate": sum(data["avg_completion_rate"]) / len(data["avg_completion_rate"]),
                "avg_no_show_rate": sum(data["avg_no_show_rate"]) / len(data["avg_no_show_rate"])
            }

        return result

    def _calculate_tracer_breakdown(
        self,
        items: List[DrugUtilizationItem]
    ) -> Dict[str, Any]:
        """计算药物分类统计"""
        tracers = {}
        for item in items:
            key = str(item.tracer_id)
            if key not in tracers:
                tracers[key] = {
                    "tracer_name": item.tracer_name,
                    "total_used_mbq": 0,
                    "total_wasted_mbq": 0,
                    "patient_count": 0
                }
            tracers[key]["total_used_mbq"] += item.total_used_mbq
            tracers[key]["total_wasted_mbq"] += item.total_wasted_mbq
            tracers[key]["patient_count"] += item.patient_count

        for t_id, data in tracers.items():
            data["utilization_rate"] = safe_divide(
                data["total_used_mbq"],
                data["total_used_mbq"] + data["total_wasted_mbq"]
            )

        return tracers

    def _calculate_waste_analysis(self, params: ReportQueryParams) -> Dict[str, Any]:
        """计算浪费原因分析"""
        waste_records = self.db.query(DrugWasteRecord).filter(
            and_(
                DrugWasteRecord.waste_date >= params.start_date,
                DrugWasteRecord.waste_date <= params.end_date,
                (DrugWasteRecord.hospital_id == params.hospital_id) if params.hospital_id else True
            )
        ).all()

        reasons = {}
        for w in waste_records:
            reason = w.waste_type or "unknown"
            if reason not in reasons:
                reasons[reason] = {"count": 0, "total_activity_mbq": 0}
            reasons[reason]["count"] += 1
            reasons[reason]["total_activity_mbq"] += w.wasted_activity_mbq

        return {
            "total_waste_records": len(waste_records),
            "total_waste_activity_mbq": sum(w.wasted_activity_mbq for w in waste_records),
            "reasons": reasons,
            "top_reasons": sorted(
                reasons.items(),
                key=lambda x: x[1]["total_activity_mbq"],
                reverse=True
            )[:5]
        }

    def _calculate_referral_network(
        self,
        items: List[ReferralCompletionItem]
    ) -> Dict[str, Any]:
        """计算转诊网络分析"""
        hospitals = set()
        for item in items:
            hospitals.add(item.hospital_id)

        hospital_names = {}
        for h_id in hospitals:
            h = self.db.query(Hospital).filter(Hospital.id == h_id).first()
            hospital_names[h_id] = h.name if h else f"院区{h_id}"

        network_data = []
        for source_id in hospitals:
            for target_id in hospitals:
                if source_id != target_id:
                    referrals = self.db.query(Referral).filter(
                        and_(
                            Referral.source_hospital_id == source_id,
                            Referral.target_hospital_id == target_id,
                            func.date(Referral.created_at) >= params.start_date if 'params' in locals() else True,
                            func.date(Referral.created_at) <= params.end_date if 'params' in locals() else True
                        )
                    ).count()
                    if referrals > 0:
                        network_data.append({
                            "source_hospital_id": source_id,
                            "source_hospital_name": hospital_names[source_id],
                            "target_hospital_id": target_id,
                            "target_hospital_name": hospital_names[target_id],
                            "referral_count": referrals
                        })

        return {
            "hospitals": [{"id": h, "name": hospital_names[h]} for h in hospitals],
            "referral_paths": network_data
        }

    def _calculate_referral_reason_analysis(self, params: ReportQueryParams) -> Dict[str, Any]:
        """计算转诊原因分析"""
        referrals = self.db.query(Referral).filter(
            and_(
                func.date(Referral.created_at) >= params.start_date,
                func.date(Referral.created_at) <= params.end_date,
                (Referral.source_hospital_id == params.hospital_id or
                 Referral.target_hospital_id == params.hospital_id) if params.hospital_id else True
            )
        ).all()

        reasons = {}
        for r in referrals:
            reason = r.referral_reason or "unknown"
            if reason not in reasons:
                reasons[reason] = {"count": 0, "completed": 0}
            reasons[reason]["count"] += 1
            if r.status == "completed":
                reasons[reason]["completed"] += 1

        for reason, data in reasons.items():
            data["completion_rate"] = safe_divide(data["completed"], data["count"])

        return {
            "total_referrals": len(referrals),
            "reasons": reasons
        }

    def _identify_top_risks(
        self,
        alerts: List[Alert],
        params: ReportQueryParams
    ) -> List[Dict[str, Any]]:
        """识别主要风险"""
        open_alerts = [a for a in alerts if a.status in ["open", "acknowledged"]]
        sorted_alerts = sorted(
            open_alerts,
            key=lambda a: {"critical": 0, "error": 1, "warning": 2, "info": 3}.get(a.severity, 4)
        )

        return [
            {
                "alert_id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "metric_value": a.metric_value,
                "threshold_value": a.threshold_value,
                "generated_at": a.generated_at
            }
            for a in sorted_alerts[:10]
        ]

    def get_kpi_dashboard(
        self,
        hospital_id: Optional[int] = None,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """获取KPI仪表盘数据"""
        target_date = target_date or date.today()
        start_date = target_date - timedelta(days=6)
        end_date = target_date

        turnover_params = ReportQueryParams(
            report_type="turnover_efficiency",
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )
        turnover_data = self.generate_turnover_efficiency_report(turnover_params)

        drug_params = ReportQueryParams(
            report_type="drug_utilization",
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )
        drug_data = self.generate_drug_utilization_report(drug_params)

        referral_params = ReportQueryParams(
            report_type="referral_completion",
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )
        referral_data = self.generate_referral_completion_report(referral_params)

        today_params = ReportQueryParams(
            report_type="daily_operation",
            hospital_id=hospital_id,
            start_date=target_date,
            end_date=target_date,
            granularity="daily"
        )
        today_data = self.generate_daily_operation_report(today_params)

        turnover_summary = turnover_data.get("summary", {})
        drug_summary = drug_data.get("summary", {})
        referral_summary = referral_data.get("summary", {})

        result = {
            "date": target_date,
            "hospital_id": hospital_id,
            "completion_rate": turnover_summary.get("overall_completion_rate", 0),
            "no_show_rate": turnover_summary.get("overall_no_show_rate", 0),
            "avg_turnover_minutes": turnover_summary.get("avg_turnover_minutes", 0),
            "drug_utilization_rate": drug_summary.get("overall_utilization_rate", 0),
            "referral_completion_rate": referral_summary.get("overall_completion_rate", 0),
            "last_7_days": {
                "total_appointments": turnover_summary.get("total_appointments", 0),
                "completion_rate": turnover_summary.get("overall_completion_rate", 0),
                "no_show_rate": turnover_summary.get("overall_no_show_rate", 0),
                "drug_utilization_rate": drug_summary.get("overall_utilization_rate", 0),
                "referral_completion_rate": referral_summary.get("overall_completion_rate", 0),
            },
            "today": today_data.get("summary", {}),
            "trends": {
                "completion_rates": turnover_data.get("trends", {}).get("completion_rates", []) if turnover_data.get("trends") else [],
                "drug_utilization_rates": drug_data.get("trends", {}).get("utilization_rates", []) if drug_data.get("trends") else [],
            }
        }

        return result

    def export_report(
        self,
        params: ReportExportRequest
    ) -> Dict[str, Any]:
        """导出报表"""
        report_params = ReportQueryParams(
            report_type=params.report_type,
            hospital_id=params.hospital_id,
            start_date=params.start_date,
            end_date=params.end_date,
            granularity=params.granularity,
            include_details=True
        )

        report_data = self.generate_report(report_params)

        return {
            "export_format": params.export_format,
            "report_type": params.report_type,
            "total_records": len(report_data.get("items", [])),
            "data": report_data,
            "export_time": datetime.utcnow()
        }

    def get_hospital_comparison_report(
        self,
        start_date: date,
        end_date: date,
        metric_type: str = "turnover"
    ) -> Dict[str, Any]:
        """获取院区对比报表"""
        if metric_type == "turnover":
            report_type = "turnover_efficiency"
        elif metric_type == "drug":
            report_type = "drug_utilization"
        elif metric_type == "referral":
            report_type = "referral_completion"
        else:
            report_type = "turnover_efficiency"

        params = ReportQueryParams(
            report_type=report_type,
            hospital_id=None,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )

        report_data = self.generate_report(params)

        return {
            "metric_type": metric_type,
            "start_date": start_date,
            "end_date": end_date,
            "hospital_comparison": report_data.get("hospital_comparison", {}),
            "items": report_data.get("items", [])
        }

    def get_trend_data(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        metric: str = "completion_rate"
    ) -> Dict[str, Any]:
        """获取趋势数据"""
        end_date = end_date or date.today()
        start_date = start_date or (end_date - timedelta(days=29))

        params = ReportQueryParams(
            report_type="turnover_efficiency",
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )

        report_data = self.generate_turnover_efficiency_report(params)
        items = report_data.get("items", [])

        trend_data = []
        for item in items:
            if metric == "completion_rate":
                value = item.completion_rate if hasattr(item, 'completion_rate') else 0
            elif metric == "no_show_rate":
                value = item.no_show_rate if hasattr(item, 'no_show_rate') else 0
            elif metric == "avg_wait_time":
                value = item.avg_wait_time_minutes if hasattr(item, 'avg_wait_time_minutes') else 0
            else:
                value = 0

            trend_data.append({
                "date": item.stat_date,
                "value": value
            })

        return {
            "metric": metric,
            "start_date": start_date,
            "end_date": end_date,
            "hospital_id": hospital_id,
            "trend_data": trend_data
        }
