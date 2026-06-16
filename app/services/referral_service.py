from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models import (
    Appointment, Hospital, Patient, Referral, Tracer, TracerBatch
)
from app.schemas import (
    ReferralCreate, ReferralUpdate, ReferralResponse,
    ReferralAutoAssignResponse, ReferralQueryParams,
    AppointmentStatus
)
from app.utils import (
    get_logger, generate_referral_no, calculate_distance,
    estimate_travel_time, safe_divide
)
from app.exceptions import ValidationError, HospitalNotFound
from app.config import get_settings

settings = get_settings()
logger = get_logger("referral_service")


class ReferralService:
    """转诊服务 - 同城转诊患者智能分配就近院区与可接纳时段"""

    def __init__(self, db: Session):
        self.db = db

    def auto_assign_referral(
        self,
        appointment_id: int,
        patient_id: int,
        source_hospital_id: int,
        referral_reason: Optional[str] = None,
        patient_city: Optional[str] = None,
        patient_district: Optional[str] = None
    ) -> ReferralAutoAssignResponse:
        """
        自动为转诊患者分配就近院区和可接纳时段
        基于距离、交通、容量、专科能力等多维度评分
        """
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        if not appointment:
            raise ValidationError(f"预约不存在: {appointment_id}")

        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValidationError(f"患者不存在: {patient_id}")

        source_hospital = self.db.query(Hospital).filter(
            Hospital.id == source_hospital_id
        ).first()
        if not source_hospital:
            raise HospitalNotFound(str(source_hospital_id))

        available_hospitals = self._find_available_hospitals(
            source_hospital,
            patient_city or patient.city,
            patient_district or patient.district,
            appointment
        )

        if not available_hospitals:
            return ReferralAutoAssignResponse(
                referral_no=generate_referral_no(source_hospital.code),
                appointment_id=appointment_id,
                patient_id=patient_id,
                recommended_hospital_id=0,
                recommended_hospital_name="暂无可用院区",
                distance_km=999,
                travel_time_minutes=999,
                assignment_score=0,
                assignment_reason="当前同城范围内无可用院区，请协调跨区域支援",
                available_dates=[],
                alternative_hospitals=[],
                notes="建议启动应急支援方案"
            )

        recommended = available_hospitals[0]
        available_dates = self._get_available_dates(recommended["hospital_id"], appointment)

        alternative_hospitals = []
        for h in available_hospitals[1:4]:
            alt_dates = self._get_available_dates(h["hospital_id"], appointment)
            alternative_hospitals.append({
                "hospital_id": h["hospital_id"],
                "hospital_name": h["hospital_name"],
                "distance_km": h["distance_km"],
                "travel_time_minutes": h["travel_time_minutes"],
                "assignment_score": h["score"],
                "assignment_reason": h["reason"],
                "earliest_available": alt_dates[0] if alt_dates else None
            })

        response = ReferralAutoAssignResponse(
            referral_no=generate_referral_no(source_hospital.code),
            appointment_id=appointment_id,
            patient_id=patient_id,
            recommended_hospital_id=recommended["hospital_id"],
            recommended_hospital_name=recommended["hospital_name"],
            distance_km=recommended["distance_km"],
            travel_time_minutes=recommended["travel_time_minutes"],
            assignment_score=recommended["score"],
            assignment_reason=recommended["reason"],
            available_dates=available_dates,
            alternative_hospitals=alternative_hospitals,
            traffic_condition=recommended.get("traffic_condition", "normal")
        )

        logger.info(
            f"转诊智能分配: 患者{patient.name} -> 院区{recommended['hospital_name']}, "
            f"距离{recommended['distance_km']}km, 评分{recommended['score']}"
        )

        return response

    def create_referral(
        self,
        referral_data: ReferralCreate,
        auto_assign: bool = True
    ) -> Referral:
        """创建转诊记录"""
        if auto_assign and not referral_data.target_hospital_id:
            assign_result = self.auto_assign_referral(
                appointment_id=referral_data.appointment_id,
                patient_id=referral_data.patient_id,
                source_hospital_id=referral_data.source_hospital_id,
                referral_reason=referral_data.referral_reason
            )
            referral_data.target_hospital_id = assign_result.recommended_hospital_id
            referral_data.proposed_date = assign_result.available_dates[0] if assign_result.available_dates else None
            referral_data.distance_km = assign_result.distance_km
            referral_data.travel_time_minutes = assign_result.travel_time_minutes
            referral_data.auto_assigned = True
            referral_data.assignment_score = assign_result.assignment_score
            referral_data.assignment_reason = assign_result.assignment_reason

        if not referral_data.referral_no:
            source_hospital = self.db.query(Hospital).filter(
                Hospital.id == referral_data.source_hospital_id
            ).first()
            referral_data.referral_no = generate_referral_no(
                source_hospital.code if source_hospital else "H001"
            )

        referral = Referral(**referral_data.model_dump(exclude_unset=True))

        appointment = self.db.query(Appointment).filter(
            Appointment.id == referral_data.appointment_id
        ).first()
        if appointment:
            appointment.is_referral = True
            appointment.hospital_id = referral_data.target_hospital_id
            appointment.referral_source = source_hospital.name if source_hospital else ""
            appointment.referral_reason = referral_data.referral_reason

        self.db.add(referral)
        self.db.commit()
        self.db.refresh(referral)

        logger.info(f"创建转诊记录: {referral.referral_no}")

        return referral

    def accept_referral(
        self,
        referral_id: int,
        accepted_by: str,
        notes: Optional[str] = None
    ) -> Referral:
        """接受转诊"""
        referral = self._get_referral(referral_id)
        referral.status = "accepted"
        referral.accepted_by = accepted_by
        referral.accepted_at = datetime.utcnow()
        referral.status_changed_at = datetime.utcnow()

        if notes:
            referral.coordination_notes = (referral.coordination_notes or "") + f"\n接受备注: {notes}"

        appointment = self.db.query(Appointment).filter(
            Appointment.id == referral.appointment_id
        ).first()
        if appointment:
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.hospital_id = referral.target_hospital_id

        self.db.commit()
        self.db.refresh(referral)
        logger.info(f"转诊已接受: {referral.referral_no} by {accepted_by}")
        return referral

    def decline_referral(
        self,
        referral_id: int,
        declined_by: str,
        reason: str,
        suggest_alternative_hospital: Optional[int] = None
    ) -> Referral:
        """拒绝转诊"""
        referral = self._get_referral(referral_id)
        referral.status = "declined"
        referral.declined_by = declined_by
        referral.declined_reason = reason
        referral.status_changed_at = datetime.utcnow()

        appointment = self.db.query(Appointment).filter(
            Appointment.id == referral.appointment_id
        ).first()
        if appointment:
            appointment.status = AppointmentStatus.PENDING

        self.db.commit()
        self.db.refresh(referral)
        logger.warning(f"转诊已拒绝: {referral.referral_no} by {declined_by}, 原因: {reason}")
        return referral

    def complete_referral(self, referral_id: int, notes: Optional[str] = None) -> Referral:
        """完成转诊"""
        referral = self._get_referral(referral_id)
        referral.status = "completed"
        referral.is_completed = True
        referral.completed_at = datetime.utcnow()
        referral.status_changed_at = datetime.utcnow()

        if notes:
            referral.coordination_notes = (referral.coordination_notes or "") + f"\n完成备注: {notes}"

        self.db.commit()
        self.db.refresh(referral)
        logger.info(f"转诊已完成: {referral.referral_no}")
        return referral

    def list_referrals(
        self,
        params: ReferralQueryParams,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Referral], int]:
        """查询转诊列表"""
        query = self.db.query(Referral)

        if params.source_hospital_id:
            query = query.filter(Referral.source_hospital_id == params.source_hospital_id)
        if params.target_hospital_id:
            query = query.filter(Referral.target_hospital_id == params.target_hospital_id)
        if params.patient_id:
            query = query.filter(Referral.patient_id == params.patient_id)
        if params.status:
            query = query.filter(Referral.status == params.status)
        if params.referral_type:
            query = query.filter(Referral.referral_type == params.referral_type)
        if params.start_date:
            query = query.filter(func.date(Referral.created_at) >= params.start_date)
        if params.end_date:
            query = query.filter(func.date(Referral.created_at) <= params.end_date)
        if params.auto_assigned is not None:
            query = query.filter(Referral.auto_assigned == params.auto_assigned)
        if params.only_pending:
            query = query.filter(Referral.status == "proposed")

        total = query.count()
        referrals = query.order_by(desc(Referral.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return referrals, total

    def get_referral(self, referral_id: int) -> Referral:
        """获取转诊详情"""
        return self._get_referral(referral_id)

    def update_referral(
        self,
        referral_id: int,
        update_data: ReferralUpdate
    ) -> Referral:
        """更新转诊信息"""
        referral = self._get_referral(referral_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                setattr(referral, key, value)

        if update_data.status:
            referral.status_changed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(referral)
        return referral

    def get_referral_network_status(
        self,
        city: Optional[str] = None,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """获取转诊网络状态"""
        target_date = target_date or date.today()

        hospitals = self.db.query(Hospital).filter(
            Hospital.is_active == True,
            Hospital.is_referral_accepting == True
        )
        if city:
            hospitals = hospitals.filter(Hospital.city == city)
        hospitals = hospitals.all()

        network_status = {
            "total_hospitals": len(hospitals),
            "city": city,
            "date": target_date,
            "hospitals": [],
            "referral_metrics": {},
            "recommendations": []
        }

        total_proposed = 0
        total_accepted = 0
        total_completed = 0

        for hospital in hospitals:
            capacity_query = self.db.query(Hospital).filter(
                Hospital.id == hospital.id
            ).first()
            daily_capacity = capacity_query.daily_capacity if capacity_query else 20

            booked = self.db.query(Appointment).filter(
                Appointment.hospital_id == hospital.id,
                Appointment.appointment_date == target_date,
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW
                ])
            ).count()

            available = max(0, daily_capacity - booked)
            utilization = safe_divide(booked, daily_capacity)

            incoming = self.db.query(Referral).filter(
                Referral.target_hospital_id == hospital.id,
                func.date(Referral.created_at) == target_date
            ).count()

            outgoing = self.db.query(Referral).filter(
                Referral.source_hospital_id == hospital.id,
                func.date(Referral.created_at) == target_date
            ).count()

            proposed_count = self.db.query(Referral).filter(
                Referral.target_hospital_id == hospital.id,
                Referral.status == "proposed"
            ).count()

            accepted_count = self.db.query(Referral).filter(
                Referral.target_hospital_id == hospital.id,
                Referral.status == "accepted"
            ).count()

            completed_count = self.db.query(Referral).filter(
                Referral.target_hospital_id == hospital.id,
                Referral.status == "completed",
                func.date(Referral.completed_at) == target_date
            ).count()

            total_proposed += proposed_count
            total_accepted += accepted_count
            total_completed += completed_count

            hospital_status = {
                "hospital_id": hospital.id,
                "hospital_name": hospital.name,
                "code": hospital.code,
                "city": hospital.city,
                "district": hospital.district,
                "daily_capacity": daily_capacity,
                "booked": booked,
                "available": available,
                "utilization_rate": round(utilization, 4),
                "incoming_referrals_today": incoming,
                "outgoing_referrals_today": outgoing,
                "pending_acceptance": proposed_count,
                "load_level": self._determine_load_level(utilization, available),
                "can_accept_referral": available > 3 and utilization < 0.9
            }
            network_status["hospitals"].append(hospital_status)

        network_status["referral_metrics"] = {
            "total_proposed": total_proposed,
            "total_accepted": total_accepted,
            "total_completed": total_completed,
            "acceptance_rate": round(safe_divide(total_accepted, total_proposed), 4),
            "completion_rate": round(safe_divide(total_completed, total_accepted), 4)
        }

        overloaded = [h for h in network_status["hospitals"] if h["load_level"] == "overloaded"]
        underutilized = [h for h in network_status["hospitals"] if h["load_level"] == "low"]

        if overloaded:
            for oh in overloaded:
                alternatives = sorted(
                    [h for h in underutilized if h["city"] == oh["city"]],
                    key=lambda x: x["available"],
                    reverse=True
                )
                if alternatives:
                    network_status["recommendations"].append({
                        "overloaded_hospital": oh["hospital_name"],
                        "suggested_alternatives": [
                            {"name": a["hospital_name"], "available": a["available"]}
                            for a in alternatives[:3]
                        ]
                    })

        return network_status

    def _find_available_hospitals(
        self,
        source_hospital: Hospital,
        city: Optional[str],
        district: Optional[str],
        appointment: Appointment
    ) -> List[Dict[str, Any]]:
        """查找可用的目标院区"""
        query = self.db.query(Hospital).filter(
            Hospital.is_active == True,
            Hospital.is_referral_accepting == True,
            Hospital.id != source_hospital.id
        )

        if city:
            query = query.filter(Hospital.city == city)

        hospitals = query.all()

        scored_hospitals = []
        for hospital in hospitals:
            distance = calculate_distance(
                source_hospital.latitude, source_hospital.longitude,
                hospital.latitude, hospital.longitude
            )

            travel_time = estimate_travel_time(distance, "normal")

            daily_capacity = hospital.daily_capacity
            booked = self.db.query(Appointment).filter(
                Appointment.hospital_id == hospital.id,
                Appointment.appointment_date >= date.today(),
                Appointment.appointment_date <= date.today() + timedelta(days=7),
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW
                ])
            ).count()

            avg_utilization = safe_divide(booked, daily_capacity * 7)

            has_specialty = self._check_hospital_specialty(hospital, appointment)
            has_tracer = self._check_tracer_availability(hospital, appointment.tracer_type)
            has_equipment = self._check_equipment_availability(hospital, appointment.needs_anesthesia)

            score, reason = self._calculate_hospital_score(
                distance, travel_time, avg_utilization,
                has_specialty, has_tracer, has_equipment,
                district, hospital.district
            )

            if score > 0:
                scored_hospitals.append({
                    "hospital_id": hospital.id,
                    "hospital_name": hospital.name,
                    "code": hospital.code,
                    "city": hospital.city,
                    "district": hospital.district,
                    "distance_km": distance,
                    "travel_time_minutes": travel_time,
                    "avg_utilization": avg_utilization,
                    "has_specialty": has_specialty,
                    "has_tracer": has_tracer,
                    "has_equipment": has_equipment,
                    "score": score,
                    "reason": reason
                })

        scored_hospitals.sort(key=lambda x: x["score"], reverse=True)
        return scored_hospitals

    def _calculate_hospital_score(
        self,
        distance: float,
        travel_time: int,
        utilization: float,
        has_specialty: bool,
        has_tracer: bool,
        has_equipment: bool,
        patient_district: Optional[str],
        hospital_district: Optional[str]
    ) -> Tuple[int, str]:
        """计算院区综合评分"""
        score = 100
        reasons = []

        if distance > 50:
            return 0, "距离过远(>50km)"
        elif distance > 30:
            score -= 30
            reasons.append(f"距离较远({distance:.1f}km)")
        elif distance > 15:
            score -= 15
            reasons.append(f"距离适中({distance:.1f}km)")
        elif distance > 5:
            score -= 5
            reasons.append(f"距离较近({distance:.1f}km)")
        else:
            reasons.append(f"距离很近({distance:.1f}km)")

        if travel_time > 90:
            score -= 20
            reasons.append("预计行程时间过长")
        elif travel_time > 60:
            score -= 10
            reasons.append("预计行程时间较长")

        if utilization > 0.9:
            score -= 25
            reasons.append("院区负荷较高")
        elif utilization > 0.7:
            score -= 10
            reasons.append("院区负荷适中")
        elif utilization < 0.5:
            score += 10
            reasons.append("院区负荷较低，空余充足")

        if patient_district and hospital_district and patient_district == hospital_district:
            score += 15
            reasons.append("同行政区")

        if not has_tracer:
            score -= 40
            reasons.append("无匹配示踪剂")
        else:
            reasons.append("有匹配示踪剂")

        if not has_equipment:
            score -= 30
            reasons.append("设备条件不足")
        else:
            reasons.append("设备条件满足")

        if has_specialty:
            score += 20
            reasons.append("有相关专科优势")

        if score <= 0:
            return 0, "不满足基本条件"

        return max(0, score), "; ".join(reasons)

    def _check_hospital_specialty(
        self,
        hospital: Hospital,
        appointment: Appointment
    ) -> bool:
        """检查院区是否有相关专科"""
        return True

    def _check_tracer_availability(
        self,
        hospital: Hospital,
        tracer_type: str
    ) -> bool:
        """检查示踪剂供应情况"""
        tracer = self.db.query(Tracer).filter(
            Tracer.hospital_id == hospital.id,
            Tracer.tracer_type == tracer_type,
            Tracer.is_active == True
        ).first()

        if not tracer:
            return False

        available_batch = self.db.query(TracerBatch).filter(
            TracerBatch.tracer_id == tracer.id,
            TracerBatch.status == "available",
            TracerBatch.expiry_time > datetime.utcnow()
        ).first()

        return available_batch is not None

    def _check_equipment_availability(
        self,
        hospital: Hospital,
        needs_anesthesia: bool
    ) -> bool:
        """检查设备可用性"""
        from app.models import Equipment

        equipment_query = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital.id,
            Equipment.is_active == True,
            Equipment.status == "available"
        )

        return equipment_query.count() > 0

    def _get_available_dates(
        self,
        hospital_id: int,
        appointment: Appointment
    ) -> List[date]:
        """获取院区未来可用日期"""
        available_dates = []
        today = date.today()

        for i in range(1, 15):
            check_date = today + timedelta(days=i)

            hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
            daily_capacity = hospital.daily_capacity if hospital else 20

            booked = self.db.query(Appointment).filter(
                Appointment.hospital_id == hospital_id,
                Appointment.appointment_date == check_date,
                Appointment.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW
                ])
            ).count()

            if booked < daily_capacity:
                available_dates.append(check_date)
                if len(available_dates) >= 5:
                    break

        return available_dates

    def _determine_load_level(self, utilization: float, available: int) -> str:
        """判断院区负载水平"""
        if utilization >= 0.95 or available <= 2:
            return "overloaded"
        elif utilization >= 0.8:
            return "high"
        elif utilization >= 0.5:
            return "normal"
        else:
            return "low"

    def _get_referral(self, referral_id: int) -> Referral:
        """获取转诊记录"""
        referral = self.db.query(Referral).filter(Referral.id == referral_id).first()
        if not referral:
            raise ValidationError(f"转诊记录不存在: {referral_id}")
        return referral
