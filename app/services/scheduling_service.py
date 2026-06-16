from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta, time
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models import (
    Appointment, Hospital, Equipment, Tracer, TracerBatch,
    ScheduleTemplate, SupportPlan, Patient
)
from app.schemas import (
    AppointmentStatus, AppointmentCategorizeResponse, AppointmentCreate
)
from app.utils import (
    get_logger, safe_divide, calculate_distance, estimate_travel_time
)
from app.exceptions import ResourceNotAvailable, ValidationError
from app.config import get_settings

settings = get_settings()
logger = get_logger("scheduling_service")


class SchedulingService:
    """模块2: 资源调度服务 - 统一分配号源与示踪剂使用窗口"""

    def __init__(self, db: Session):
        self.db = db

    def allocate_resources(
        self,
        appointment_or_id,
        categorization: Optional[AppointmentCategorizeResponse] = None
    ) -> Dict[str, Any]:
        """
        为预约分配资源：号源、设备时段、示踪剂窗口
        支持传入appointment对象或appointment_id
        """
        if isinstance(appointment_or_id, int):
            from app.services import AppointmentService
            apt_service = AppointmentService(self.db)
            appointment = apt_service.get_appointment(appointment_or_id)
            patient = apt_service._get_patient(appointment.patient_id)
            if categorization is None:
                categorization = apt_service.categorize_appointment(
                    appointment_data=AppointmentCreate(**{
                        'patient_id': appointment.patient_id,
                        'hospital_id': appointment.hospital_id,
                        'exam_purpose': appointment.exam_purpose,
                        'urgency_level': appointment.urgency_level,
                        'is_inpatient': appointment.is_inpatient,
                        'needs_anesthesia': appointment.needs_anesthesia,
                        'appointment_date': appointment.appointment_date,
                        'tracer_type': appointment.tracer_type
                    }),
                    patient=patient
                )
        else:
            appointment = appointment_or_id

        result = {
            "appointment_id": appointment.id,
            "appointment_no": appointment.appointment_no,
            "allocated": False,
            "equipment_id": None,
            "time_slot": None,
            "tracer_batch_id": None,
            "injection_window": None,
            "tracer_window": None,
            "queue_number": None,
            "warnings": []
        }

        if appointment.equipment_id and appointment.time_slot and appointment.queue_number:
            result["allocated"] = True
            result["equipment_id"] = appointment.equipment_id
            result["time_slot"] = appointment.time_slot
            result["queue_number"] = appointment.queue_number
            result["tracer_batch_id"] = appointment.tracer_batch_id
            result["tracer_window"] = "待分配"
            result["appointment_date"] = appointment.appointment_date
            result["hospital_id"] = appointment.hospital_id
            result["warnings"].append("预约已有资源分配")
            return result

        daily_capacity = self._get_daily_capacity(
            appointment.hospital_id,
            appointment.appointment_date
        )

        current_count = self._get_daily_appointment_count(
            appointment.hospital_id,
            appointment.appointment_date
        )

        if current_count >= daily_capacity and not appointment.is_plus_sign:
            result["warnings"].append(f"当日号源已满，当前{current_count}/{daily_capacity}")
            result["alternative_dates"] = self._find_alternative_dates(
                appointment.hospital_id,
                appointment.appointment_date,
                days_ahead=7
            )
            return result

        available_equipment = self._find_available_equipment(
            appointment.hospital_id,
            appointment.appointment_date,
            appointment.needs_anesthesia,
            categorization
        )

        if not available_equipment:
            result["warnings"].append("无可用设备")
            return result

        equipment = available_equipment[0]
        result["equipment_id"] = equipment.id

        time_slot, queue_num = self._allocate_time_slot(
            appointment,
            equipment,
            categorization
        )

        if not time_slot:
            result["warnings"].append("无可用时段")
            return result

        result["time_slot"] = time_slot
        result["queue_number"] = queue_num

        tracer_allocation = self._allocate_tracer_window(
            appointment,
            time_slot,
            categorization
        )

        if tracer_allocation:
            result.update(tracer_allocation)

        if "tracer_window" not in result or result.get("tracer_window") is None:
            result["tracer_window"] = result.get("injection_window")
        if result.get("tracer_window") is None:
            result["tracer_window"] = "待分配"

        appointment.equipment_id = equipment.id
        appointment.time_slot = time_slot
        appointment.queue_number = queue_num
        appointment.status = AppointmentStatus.CONFIRMED

        if tracer_allocation and tracer_allocation.get("tracer_batch_id"):
            appointment.tracer_batch_id = tracer_allocation["tracer_batch_id"]
            appointment.tracer_dose_mbq = tracer_allocation.get("allocated_dose")

        result["allocated"] = True
        result["tracer_window"] = result.get("injection_window")
        result["appointment_date"] = appointment.appointment_date
        result["hospital_id"] = appointment.hospital_id
        self.db.commit()

        logger.info(f"资源分配成功: 预约{appointment.appointment_no} -> 设备{equipment.id}, 时段{time_slot}")

        return result

    def _get_daily_capacity(self, hospital_id: int, target_date: date) -> int:
        """获取院区当日容量，考虑节假日模板和临时支援方案"""
        template = self._get_applicable_template(hospital_id, target_date)
        base_capacity = template.daily_capacity if template else 20

        additional_capacity = self.db.query(SupportPlan).filter(
            SupportPlan.hospital_id == hospital_id,
            SupportPlan.status == "active",
            SupportPlan.start_date <= target_date,
            SupportPlan.end_date >= target_date
        ).with_entities(func.sum(SupportPlan.additional_capacity)).scalar() or 0

        total = base_capacity + additional_capacity
        logger.debug(f"院区{hospital_id} {target_date} 容量: 基础{base_capacity} + 支援{additional_capacity} = {total}")

        return total

    def _get_applicable_template(
        self,
        hospital_id: int,
        target_date: date
    ) -> Optional[ScheduleTemplate]:
        """获取适用的排班模板"""
        day_of_week = target_date.weekday()
        is_weekday = day_of_week < 5

        templates = self.db.query(ScheduleTemplate).filter(
            ScheduleTemplate.hospital_id == hospital_id,
            ScheduleTemplate.is_active == True,
            or_(
                ScheduleTemplate.effective_date.is_(None),
                ScheduleTemplate.effective_date <= target_date
            ),
            or_(
                ScheduleTemplate.expiry_date.is_(None),
                ScheduleTemplate.expiry_date >= target_date
            )
        ).all()

        holiday_templates = [t for t in templates if t.template_type == "holiday"]
        if holiday_templates:
            for t in holiday_templates:
                if (t.day_of_week is None or t.day_of_week == day_of_week):
                    return t

        weekday_templates = [t for t in templates if t.template_type == "normal"
                            and (t.is_weekday is None or t.is_weekday == is_weekday)
                            and (t.day_of_week is None or t.day_of_week == day_of_week)]

        return weekday_templates[0] if weekday_templates else (templates[0] if templates else None)

    def _get_daily_appointment_count(self, hospital_id: int, target_date: date) -> int:
        """获取当日已预约数"""
        return self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW
            ])
        ).count()

    def _find_alternative_dates(
        self,
        hospital_id: int,
        start_date: date,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """查找未来可用日期"""
        alternatives = []
        for i in range(1, days_ahead + 1):
            check_date = start_date + timedelta(days=i)
            capacity = self._get_daily_capacity(hospital_id, check_date)
            booked = self._get_daily_appointment_count(hospital_id, check_date)
            available = max(0, capacity - booked)

            if available > 0:
                alternatives.append({
                    "date": check_date,
                    "capacity": capacity,
                    "booked": booked,
                    "available": available,
                    "utilization_rate": safe_divide(booked, capacity)
                })

        return alternatives[:5]

    def _find_available_equipment(
        self,
        hospital_id: int,
        target_date: date,
        needs_anesthesia: bool,
        categorization: AppointmentCategorizeResponse
    ) -> List[Equipment]:
        """查找可用设备"""
        query = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True,
            Equipment.status == "available"
        )

        equipment_list = query.all()

        available = []
        for eq in equipment_list:
            daily_schedule = self._get_equipment_daily_schedule(eq.id, target_date)
            used_slots = len(daily_schedule)
            if used_slots < eq.daily_capacity:
                available.append(eq)

        available.sort(key=lambda eq: self._get_equipment_priority_score(
            eq, needs_anesthesia, categorization
        ), reverse=True)

        return available

    def _get_equipment_daily_schedule(
        self,
        equipment_id: int,
        target_date: date
    ) -> List[Appointment]:
        """获取设备当日排班"""
        return self.db.query(Appointment).filter(
            Appointment.equipment_id == equipment_id,
            Appointment.appointment_date == target_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW
            ])
        ).order_by(Appointment.queue_number).all()

    def _get_equipment_priority_score(
        self,
        equipment: Equipment,
        needs_anesthesia: bool,
        categorization: AppointmentCategorizeResponse
    ) -> int:
        """计算设备适配度评分"""
        score = 100

        if needs_anesthesia:
            if "麻醉" not in (equipment.name or ""):
                score -= 30

        workflow = categorization.workflow_category
        if workflow == "神经" and "脑" in (equipment.name or ""):
            score += 20
        elif workflow == "心血管" and "心" in (equipment.name or ""):
            score += 20

        return score

    def _allocate_time_slot(
        self,
        appointment: Appointment,
        equipment: Equipment,
        categorization: AppointmentCategorizeResponse
    ) -> Tuple[Optional[str], Optional[int]]:
        """分配时段和队列号"""
        schedule = self._get_equipment_daily_schedule(equipment.id, appointment.appointment_date)
        existing_queues = [a.queue_number for a in schedule if a.queue_number]

        next_queue = max(existing_queues) + 1 if existing_queues else 1

        priority = appointment.priority_score
        if priority >= 80:
            insert_position = self._find_priority_insert_position(schedule, priority)
            next_queue = insert_position
            self._shift_queues(schedule, insert_position)

        time_slot = self._calculate_time_slot(next_queue, equipment, categorization)

        return time_slot, next_queue

    def _find_priority_insert_position(
        self,
        schedule: List[Appointment],
        priority: int
    ) -> int:
        """为高优先级预约找插入位置"""
        for idx, appt in enumerate(schedule):
            if appt.priority_score < priority:
                return idx + 1
        return len(schedule) + 1

    def _shift_queues(self, schedule: List[Appointment], insert_position: int):
        """向后移位队列号"""
        for appt in schedule:
            if appt.queue_number and appt.queue_number >= insert_position:
                appt.queue_number += 1

    def _parse_time_str(self, time_str: Optional[str], default: time) -> time:
        """将时间字符串转换为time对象"""
        if not time_str:
            return default
        try:
            if isinstance(time_str, time):
                return time_str
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return default

    def _calculate_time_slot(
        self,
        queue_number: int,
        equipment: Equipment,
        categorization: Optional[AppointmentCategorizeResponse] = None
    ) -> str:
        """计算具体时段"""
        template = self._get_applicable_template(equipment.hospital_id, date.today())
        work_start = self._parse_time_str(template.work_start_time if template else None, time(8, 0))
        work_end = self._parse_time_str(template.work_end_time if template else None, time(17, 0))
        lunch_start = self._parse_time_str(template.lunch_start_time if template else None, time(12, 0))
        lunch_end = self._parse_time_str(template.lunch_end_time if template else None, time(13, 30))

        slot_duration = equipment.scan_duration_minutes + equipment.setup_duration_minutes
        morning_capacity = template.morning_capacity if template else 12

        if queue_number <= morning_capacity:
            minutes_from_start = (queue_number - 1) * slot_duration
            slot_start = datetime.combine(date.today(), work_start) + timedelta(minutes=minutes_from_start)

            lunch_start_dt = datetime.combine(date.today(), lunch_start)
            if slot_start >= lunch_start_dt:
                slot_start = datetime.combine(date.today(), lunch_end) + timedelta(
                    minutes=(queue_number - morning_capacity - 1) * slot_duration
                )
        else:
            afternoon_pos = queue_number - morning_capacity
            slot_start = datetime.combine(date.today(), lunch_end) + timedelta(
                minutes=(afternoon_pos - 1) * slot_duration
            )

        priority_score = categorization.priority_score if categorization else 50
        if priority_score >= 80:
            period = "优先"
        elif priority_score >= 60:
            period = "上午" if queue_number <= morning_capacity else "下午"
        else:
            period = "上午" if queue_number <= morning_capacity else "下午"

        return f"{period} {slot_start.strftime('%H:%M')}"

    def _allocate_tracer_window(
        self,
        appointment: Appointment,
        time_slot: str,
        categorization: AppointmentCategorizeResponse
    ) -> Optional[Dict[str, Any]]:
        """分配示踪剂使用窗口"""
        tracer_type = appointment.tracer_type

        tracer = self.db.query(Tracer).filter(
            Tracer.hospital_id == appointment.hospital_id,
            Tracer.tracer_type == tracer_type,
            Tracer.is_active == True
        ).first()

        if not tracer:
            logger.warning(f"未找到示踪剂类型: {tracer_type}")
            return None

        available_batch = self._find_available_tracer_batch(
            tracer.id,
            appointment.appointment_date,
            time_slot
        )

        if not available_batch:
            return {
                "tracer_batch_id": None,
                "injection_window": None,
                "allocated_dose": None,
                "warning": "暂无可用示踪剂批次，请确认供应"
            }

        patient = self.db.query(Patient).filter(Patient.id == appointment.patient_id).first()
        weight = patient.weight_kg if patient and patient.weight_kg else 70
        dose = tracer.default_dose_mbq
        if weight > 90:
            dose *= 1.2
        elif weight < 50:
            dose *= 0.8

        scan_time = self._parse_time_slot(time_slot)
        injection_time = scan_time - timedelta(minutes=60)
        injection_window = f"{injection_time.strftime('%H:%M')} - {(injection_time + timedelta(minutes=10)).strftime('%H:%M')}"

        return {
            "tracer_batch_id": available_batch.id,
            "injection_window": injection_window,
            "allocated_dose": round(dose, 1),
            "tracer_name": tracer.name,
            "half_life": tracer.half_life_minutes,
            "batch_no": available_batch.batch_no,
            "expiry_time": available_batch.expiry_time
        }

    def _find_available_tracer_batch(
        self,
        tracer_id: int,
        target_date: date,
        time_slot: str
    ) -> Optional[TracerBatch]:
        """查找可用的示踪剂批次"""
        batches = self.db.query(TracerBatch).filter(
            TracerBatch.tracer_id == tracer_id,
            TracerBatch.status == "available",
            func.date(TracerBatch.arrival_time) <= target_date,
            TracerBatch.expiry_time >= datetime.combine(target_date, time(23, 59))
        ).all()

        if not batches:
            return None

        batches.sort(key=lambda b: b.expiry_time)
        return batches[0]

    def _parse_time_slot(self, time_slot: str) -> datetime:
        """解析时段字符串为时间"""
        try:
            time_str = time_slot.split(" ")[-1]
            hour, minute = map(int, time_str.split(":"))
            return datetime.combine(date.today(), time(hour, minute))
        except:
            return datetime.combine(date.today(), time(10, 0))

    def get_hospital_capacity_status(
        self,
        hospital_id: int,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """获取院区容量状态"""
        target_date = target_date or date.today()

        capacity = self._get_daily_capacity(hospital_id, target_date)
        booked = self._get_daily_appointment_count(hospital_id, target_date)
        available = max(0, capacity - booked)

        morning_cap = 12
        afternoon_cap = 8
        template = self._get_applicable_template(hospital_id, target_date)
        if template:
            morning_cap = template.morning_capacity
            afternoon_cap = template.afternoon_capacity

        morning_booked = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.time_slot.like("上午%"),
            Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
        ).count()

        afternoon_booked = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.time_slot.like("下午%"),
            Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
        ).count()

        equipment_status = []
        for eq in self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True
        ).all():
            eq_schedule = self._get_equipment_daily_schedule(eq.id, target_date)
            equipment_status.append({
                "equipment_id": eq.id,
                "equipment_name": eq.name,
                "status": eq.status,
                "daily_capacity": eq.daily_capacity,
                "booked": len(eq_schedule),
                "available": max(0, eq.daily_capacity - len(eq_schedule))
            })

        tracer_status = []
        for tracer in self.db.query(Tracer).filter(
            Tracer.hospital_id == hospital_id,
            Tracer.is_active == True
        ).all():
            available_batches = self.db.query(TracerBatch).filter(
                TracerBatch.tracer_id == tracer.id,
                TracerBatch.status == "available"
            ).count()
            total_activity = self.db.query(TracerBatch).filter(
                TracerBatch.tracer_id == tracer.id,
                TracerBatch.status == "available"
            ).with_entities(func.sum(TracerBatch.total_activity_mbq - TracerBatch.used_activity_mbq)).scalar() or 0

            tracer_status.append({
                "tracer_id": tracer.id,
                "tracer_name": tracer.name,
                "tracer_type": tracer.tracer_type,
                "available_batches": available_batches,
                "available_activity_mbq": round(total_activity, 1)
            })

        return {
            "hospital_id": hospital_id,
            "date": target_date,
            "total_capacity": capacity,
            "total_booked": booked,
            "total_available": available,
            "used_capacity": booked,
            "available_capacity": available,
            "utilization_rate": round(safe_divide(booked, capacity), 4),
            "morning": {
                "capacity": morning_cap,
                "booked": morning_booked,
                "available": max(0, morning_cap - morning_booked)
            },
            "afternoon": {
                "capacity": afternoon_cap,
                "booked": afternoon_booked,
                "available": max(0, afternoon_cap - afternoon_booked)
            },
            "equipment": equipment_status,
            "tracers": tracer_status
        }

    def batch_allocate(self, appointments: List[Appointment]) -> Dict[str, Any]:
        """批量资源分配"""
        results = {
            "total": len(appointments),
            "success": 0,
            "failed": 0,
            "details": []
        }

        appointments.sort(key=lambda a: a.priority_score, reverse=True)

        for appt in appointments:
            try:
                categorization = AppointmentCategorizeResponse(
                    category="批量分配",
                    priority_score=appt.priority_score,
                    recommended_queue="普通队列",
                    workflow_category=appt.workflow_category or "其他",
                    resource_requirements={},
                    estimated_wait_time_minutes=0,
                    special_handling=[]
                )
                result = self.allocate_resources(appt, categorization)
                if result["allocated"]:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append(result)
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "appointment_id": appt.id,
                    "error": str(e)
                })
                logger.error(f"批量分配失败: {appt.id}, {str(e)}")

        return results

    def batch_allocate_resources(self, hospital_id: int, target_date: date) -> Dict[str, Any]:
        """批量分配某日某院所有待分配预约的资源（路由调用）"""
        from app.models import Appointment
        appointments = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(["pending"]),
            Appointment.equipment_id.is_(None)
        ).all()

        result = self.batch_allocate(appointments)
        result["total"] = len(appointments)
        return result

    def get_available_time_slots(
        self,
        hospital_id: int,
        target_date: date,
        tracer_type: Optional[str] = None,
        needs_anesthesia: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """获取可用时段列表"""
        from app.models import Equipment, Appointment

        try:
            equipment_list = self.db.query(Equipment).filter(
                Equipment.hospital_id == hospital_id,
                Equipment.is_active == True,
                Equipment.status == "available"
            ).all()
        except Exception:
            return []

        if not equipment_list:
            return []

        slots = []
        for eq in equipment_list:
            try:
                daily_schedule = self._get_equipment_daily_schedule(eq.id, target_date)
                used_queues = [a.queue_number for a in daily_schedule if a.queue_number]

                template = self._get_applicable_template(hospital_id, target_date)
                morning_cap = template.morning_capacity if template else 12
                total_cap = eq.daily_capacity

                for queue_num in range(1, total_cap + 1):
                    if queue_num not in used_queues:
                        time_slot = self._calculate_time_slot(queue_num, eq, None)
                        period = "上午" if queue_num <= morning_cap else "下午"

                        slots.append({
                            "equipment_id": eq.id,
                            "equipment_name": eq.name,
                            "queue_number": queue_num,
                            "time_slot": time_slot,
                            "period": period,
                            "duration_minutes": eq.scan_duration_minutes + eq.setup_duration_minutes,
                            "needs_anesthesia": needs_anesthesia,
                            "tracer_type": tracer_type or "fdg"
                        })
            except Exception:
                continue

        return slots[:30]

    def get_tracer_usage_windows(
        self,
        hospital_id: int,
        target_date: date,
        tracer_type: str = "fdg"
    ) -> List[Dict[str, Any]]:
        """获取示踪剂使用窗口"""
        from app.models import Tracer, TracerBatch

        tracer = self.db.query(Tracer).filter(
            Tracer.hospital_id == hospital_id,
            Tracer.tracer_type == tracer_type,
            Tracer.is_active == True
        ).first()

        if not tracer:
            return []

        batches = self.db.query(TracerBatch).filter(
            TracerBatch.tracer_id == tracer.id,
            TracerBatch.status == "available",
            func.date(TracerBatch.arrival_time) <= target_date,
            TracerBatch.expiry_time >= datetime.combine(target_date, time(23, 59))
        ).all()

        windows = []
        start_hour = 8
        for batch in batches:
            for i in range(6):
                hour = start_hour + i
                if hour < 12 or hour > 13:
                    windows.append({
                        "tracer_id": tracer.id,
                        "tracer_name": tracer.name,
                        "batch_id": batch.id,
                        "batch_no": batch.batch_no,
                        "window_start": f"{hour:02d}:00",
                        "window_end": f"{hour:02d}:30",
                        "available_activity_mbq": batch.remaining_activity if hasattr(batch, 'remaining_activity') else batch.total_activity_mbq,
                        "max_patients": 5
                    })

        return windows

    def generate_daily_scheduling_plan(
        self,
        hospital_id: int,
        target_date: date,
        auto_confirm: bool = False
    ) -> Dict[str, Any]:
        """生成每日排班计划"""
        from app.models import Appointment

        appointments = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(["pending", "confirmed"])
        ).order_by(Appointment.priority_score.desc()).all()

        unallocated = [a for a in appointments if a.equipment_id is None]
        if unallocated and auto_confirm:
            self.batch_allocate(unallocated)

        allocated = [a for a in appointments if a.equipment_id is not None]

        return {
            "date": target_date,
            "hospital_id": hospital_id,
            "total_appointments": len(appointments),
            "allocated": len(allocated),
            "unallocated": len(unallocated),
            "appointments": [
                {
                    "appointment_id": a.id,
                    "appointment_no": a.appointment_no,
                    "patient_name": a.patient.name if a.patient else "",
                    "priority_score": a.priority_score,
                    "queue_number": a.queue_number,
                    "time_slot": a.time_slot,
                    "equipment_id": a.equipment_id,
                    "status": a.status
                }
                for a in allocated
            ]
        }

    def get_equipment_load_status(
        self,
        hospital_id: int,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """获取设备负载情况"""
        from app.models import Equipment, Appointment

        target_date = target_date or date.today()

        equipment_list = self.db.query(Equipment).filter(
            Equipment.hospital_id == hospital_id,
            Equipment.is_active == True
        ).all()

        load_status = []
        for eq in equipment_list:
            daily_schedule = self._get_equipment_daily_schedule(eq.id, target_date)
            load = len(daily_schedule) / eq.daily_capacity if eq.daily_capacity > 0 else 0

            load_status.append({
                "equipment_id": eq.id,
                "equipment_name": eq.name,
                "equipment_code": eq.code,
                "daily_capacity": eq.daily_capacity,
                "booked_count": len(daily_schedule),
                "load_rate": round(load, 4),
                "status": eq.status
            })

        return {
            "hospital_id": hospital_id,
            "date": target_date,
            "equipment_load": load_status,
            "average_load_rate": round(sum(s["load_rate"] for s in load_status) / len(load_status), 4) if load_status else 0
        }

    def optimize_queue_order(
        self,
        hospital_id: int,
        target_date: date,
        strategy: str = "priority_first"
    ) -> Dict[str, Any]:
        """优化排队队列顺序"""
        from app.models import Appointment

        appointments = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == target_date,
            Appointment.status.notin_(["completed", "cancelled", "no_show"])
        ).all()

        if strategy == "priority_first":
            appointments.sort(key=lambda a: (-a.priority_score, a.queue_number or 999))
        elif strategy == "earliest_first":
            appointments.sort(key=lambda a: (a.time_slot or "", a.queue_number or 999))
        elif strategy == "inpatient_first":
            appointments.sort(key=lambda a: (-1 if a.is_inpatient else 0, -a.priority_score))

        adjusted_count = 0
        for idx, appt in enumerate(appointments):
            new_queue = idx + 1
            if appt.queue_number != new_queue:
                appt.queue_number = new_queue
                adjusted_count += 1

        self.db.commit()

        return {
            "hospital_id": hospital_id,
            "date": target_date,
            "strategy": strategy,
            "total_optimized": len(appointments),
            "adjusted_count": adjusted_count
        }

    def get_network_capacity_status(
        self,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """获取整个医联体网络容量状态"""
        from app.models import Hospital

        target_date = target_date or date.today()

        hospitals = self.db.query(Hospital).filter(Hospital.is_active == True).all()

        network_status = []
        for hospital in hospitals:
            status = self.get_hospital_capacity_status(hospital.id, target_date)
            network_status.append(status)

        total_capacity = sum(s["total_capacity"] for s in network_status)
        total_booked = sum(s["total_booked"] for s in network_status)
        total_available = sum(s["total_available"] for s in network_status)

        return {
            "date": target_date,
            "total_hospitals": len(hospitals),
            "total_capacity": total_capacity,
            "total_booked": total_booked,
            "total_available": total_available,
            "used_capacity": total_booked,
            "available_capacity": total_available,
            "overall_utilization_rate": round(safe_divide(total_booked, total_capacity), 4),
            "hospitals": network_status
        }

    def allocate_resources_for_reschedule(
        self,
        appointment: Appointment,
        target_hospital_id: int,
        target_date: date,
        preferred_equipment_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """为重排预约分配资源"""
        original_hospital_id = appointment.hospital_id
        original_date = appointment.appointment_date

        try:
            original_equipment_id = appointment.equipment_id
            original_time_slot = appointment.time_slot
            original_queue_number = appointment.queue_number
            original_tracer_batch_id = appointment.tracer_batch_id

            appointment.equipment_id = preferred_equipment_id
            appointment.time_slot = None
            appointment.queue_number = None
            appointment.tracer_batch_id = None

            from app.services import AppointmentService
            apt_service = AppointmentService(self.db)
            patient = apt_service._get_patient(appointment.patient_id)
            categorization = apt_service.categorize_appointment(
                appointment_data=AppointmentCreate(**{
                    'patient_id': appointment.patient_id,
                    'hospital_id': target_hospital_id,
                    'exam_purpose': appointment.exam_purpose,
                    'urgency_level': appointment.urgency_level,
                    'is_inpatient': appointment.is_inpatient,
                    'needs_anesthesia': appointment.needs_anesthesia,
                    'appointment_date': target_date,
                    'tracer_type': appointment.tracer_type
                }),
                patient=patient
            )

            result = self.allocate_resources(appointment, categorization)

            if not result["allocated"]:
                appointment.hospital_id = original_hospital_id
                appointment.appointment_date = original_date
                appointment.equipment_id = original_equipment_id
                appointment.time_slot = original_time_slot
                appointment.queue_number = original_queue_number
                appointment.tracer_batch_id = original_tracer_batch_id
            else:
                result["appointment_date"] = appointment.appointment_date
                result["hospital_id"] = appointment.hospital_id

            return result

        except Exception as e:
            logger.error(f"重排资源分配失败: {str(e)}")
            appointment.hospital_id = original_hospital_id
            appointment.appointment_date = original_date
            appointment.equipment_id = None
            return {
                "appointment_id": appointment.id,
                "allocated": False,
                "warnings": [str(e)]
            }
