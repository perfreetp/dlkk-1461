from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.models import Appointment, Patient, Hospital, Equipment, User, StatusRecord
from app.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    AppointmentCategorizeResponse, AppointmentQueryParams,
    AppointmentBatchCreate, PlusSignRequest, AppointmentStatus
)
from app.utils import (
    generate_appointment_no, calculate_priority_score,
    categorize_workflow, get_preparation_notes, get_logger
)
from app.exceptions import (
    AppointmentNotFound, HospitalNotFound, ValidationError,
    ResourceNotAvailable, HighRiskAlert
)
from app.config import get_settings

settings = get_settings()
logger = get_logger("appointment_service")


class AppointmentService:
    """模块1: 预约汇聚服务 - 接收各院区登记请求，按多维度条件归类"""

    def __init__(self, db: Session):
        self.db = db

    def categorize_appointment(
        self,
        appointment_data: AppointmentCreate,
        patient: Patient
    ) -> AppointmentCategorizeResponse:
        """
        对预约请求进行多维度归类
        按检查目的、病情紧急度、是否住院、是否需麻醉等条件归类
        """
        priority_score = calculate_priority_score(
            urgency_level=appointment_data.urgency_level,
            is_inpatient=appointment_data.is_inpatient,
            needs_anesthesia=appointment_data.needs_anesthesia,
            is_referral=appointment_data.is_referral,
            is_plus_sign=appointment_data.is_plus_sign,
            exam_purpose=appointment_data.exam_purpose,
            consecutive_no_show=patient.consecutive_no_show
        )

        workflow_category = categorize_workflow(
            exam_purpose=appointment_data.exam_purpose,
            clinical_diagnosis=appointment_data.clinical_diagnosis or ""
        )

        category = self._determine_category(appointment_data, patient)
        recommended_queue = self._determine_queue(appointment_data)
        resource_requirements = self._determine_resource_requirements(appointment_data)
        estimated_wait_time = self._estimate_wait_time(
            appointment_data.hospital_id,
            appointment_data.appointment_date,
            priority_score
        )
        special_handling = self._determine_special_handling(appointment_data, patient)

        if patient.consecutive_no_show >= settings.MAX_CONSECUTIVE_NO_SHOW:
            raise HighRiskAlert(
                risk_type="consecutive_no_show",
                detail=f"患者连续爽约{patient.consecutive_no_show}次，已达到风险阈值"
            )

        return AppointmentCategorizeResponse(
            category=category,
            priority_score=priority_score,
            recommended_queue=recommended_queue,
            workflow_category=workflow_category,
            resource_requirements=resource_requirements,
            estimated_wait_time_minutes=estimated_wait_time,
            special_handling=special_handling
        )

    def create_appointment(
        self,
        appointment_data: AppointmentCreate,
        creator: Optional[User] = None
    ) -> Tuple[Appointment, AppointmentCategorizeResponse]:
        """创建预约并自动归类"""
        hospital = self.db.query(Hospital).filter(
            Hospital.id == appointment_data.hospital_id
        ).first()
        if not hospital:
            raise HospitalNotFound(str(appointment_data.hospital_id))

        patient = self.db.query(Patient).filter(
            Patient.id == appointment_data.patient_id
        ).first()
        if not patient:
            raise ValidationError(f"患者不存在: {appointment_data.patient_id}")

        categorize_result = self.categorize_appointment(appointment_data, patient)

        appointment_no = generate_appointment_no(hospital.code)

        appointment = Appointment(
            **appointment_data.model_dump(exclude_unset=True),
            appointment_no=appointment_no,
            status=AppointmentStatus.PENDING,
            priority_score=categorize_result.priority_score,
            workflow_category=categorize_result.workflow_category,
            preparation_notes=get_preparation_notes(
                tracer_type=appointment_data.tracer_type,
                needs_anesthesia=appointment_data.needs_anesthesia,
                is_inpatient=appointment_data.is_inpatient,
                diabetes_type=patient.diabetes_type or "",
                fasting_hours=appointment_data.fasting_hours
            ),
            creator_id=creator.id if creator else None
        )

        if appointment_data.is_inpatient:
            patient.is_inpatient = True
            patient.inpatient_no = appointment_data.inpatient_no
            patient.ward = appointment_data.ward
            patient.bed_no = appointment_data.bed_no

        patient.total_appointments += 1

        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        logger.info(f"创建预约成功: {appointment_no}, 优先级: {categorize_result.priority_score}")

        return appointment, categorize_result

    def batch_create_appointments(
        self,
        batch_data: AppointmentBatchCreate,
        creator: Optional[User] = None
    ) -> Dict[str, Any]:
        """批量创建预约"""
        results = {
            "total": len(batch_data.appointments),
            "success": 0,
            "failed": 0,
            "failed_items": [],
            "appointments": []
        }

        for idx, appt_data in enumerate(batch_data.appointments):
            try:
                appointment, categorize_result = self.create_appointment(appt_data, creator)
                results["success"] += 1
                results["appointments"].append({
                    "appointment": appointment,
                    "categorization": categorize_result
                })
            except Exception as e:
                results["failed"] += 1
                results["failed_items"].append({
                    "index": idx,
                    "patient_id": appt_data.patient_id,
                    "error": str(e)
                })
                logger.warning(f"批量创建预约失败 #{idx}: {str(e)}")

        return results

    def get_appointment(self, appointment_id: int) -> Appointment:
        """获取预约详情"""
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        if not appointment:
            raise AppointmentNotFound(str(appointment_id))
        return appointment

    def list_appointments(
        self,
        params: AppointmentQueryParams,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Appointment], int]:
        """查询预约列表"""
        query = self.db.query(Appointment)

        if params.hospital_id:
            query = query.filter(Appointment.hospital_id == params.hospital_id)
        if params.equipment_id:
            query = query.filter(Appointment.equipment_id == params.equipment_id)
        if params.patient_id:
            query = query.filter(Appointment.patient_id == params.patient_id)
        if params.status:
            query = query.filter(Appointment.status == params.status)
        if params.urgency_level:
            query = query.filter(Appointment.urgency_level == params.urgency_level)
        if params.exam_purpose:
            query = query.filter(Appointment.exam_purpose == params.exam_purpose)
        if params.start_date:
            query = query.filter(Appointment.appointment_date >= params.start_date)
        if params.end_date:
            query = query.filter(Appointment.appointment_date <= params.end_date)
        if params.is_inpatient is not None:
            query = query.filter(Appointment.is_inpatient == params.is_inpatient)
        if params.needs_anesthesia is not None:
            query = query.filter(Appointment.needs_anesthesia == params.needs_anesthesia)
        if params.is_referral is not None:
            query = query.filter(Appointment.is_referral == params.is_referral)
        if params.is_plus_sign is not None:
            query = query.filter(Appointment.is_plus_sign == params.is_plus_sign)

        if params.search_keyword:
            keyword = f"%{params.search_keyword}%"
            query = query.join(Patient).filter(
                or_(
                    Appointment.appointment_no.like(keyword),
                    Patient.name.like(keyword),
                    Patient.medical_record_no.like(keyword)
                )
            )

        total = query.count()
        appointments = query.order_by(
            desc(Appointment.priority_score),
            Appointment.appointment_date,
            Appointment.queue_number
        ).offset((page - 1) * page_size).limit(page_size).all()

        return appointments, total

    def update_appointment(
        self,
        appointment_id: int,
        update_data: AppointmentUpdate
    ) -> Appointment:
        """更新预约信息"""
        appointment = self.get_appointment(appointment_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                setattr(appointment, key, value)

        if update_data.exam_purpose or update_data.urgency_level:
            appointment.priority_score = calculate_priority_score(
                urgency_level=update_data.urgency_level or appointment.urgency_level,
                is_inpatient=appointment.is_inpatient,
                needs_anesthesia=appointment.needs_anesthesia,
                is_referral=appointment.is_referral,
                is_plus_sign=appointment.is_plus_sign,
                exam_purpose=update_data.exam_purpose or appointment.exam_purpose
            )
            if update_data.exam_purpose:
                appointment.workflow_category = categorize_workflow(update_data.exam_purpose)

        if update_data.status:
            appointment.status_changed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(appointment)
        logger.info(f"更新预约: {appointment.appointment_no}")

        return appointment

    def create_plus_sign(
        self,
        plus_request: PlusSignRequest,
        creator: Optional[User] = None
    ) -> Tuple[Appointment, AppointmentCategorizeResponse]:
        """处理突发加号请求"""
        appointment_data = AppointmentCreate(
            patient_id=plus_request.patient_id,
            hospital_id=plus_request.hospital_id,
            exam_purpose=plus_request.exam_purpose,
            urgency_level=plus_request.urgency_level,
            appointment_date=plus_request.target_date,
            time_slot=plus_request.target_time_slot,
            is_plus_sign=True,
            plus_sign_reason=plus_request.reason,
            clinical_diagnosis=plus_request.clinical_diagnosis,
            referring_department=plus_request.referring_department,
            referring_doctor=plus_request.referring_doctor,
            needs_anesthesia=plus_request.needs_anesthesia,
            is_inpatient=plus_request.is_inpatient
        )

        appointment, categorize_result = self.create_appointment(appointment_data, creator)

        logger.info(f"加号成功: {appointment.appointment_no}, 原因: {plus_request.reason}")

        return appointment, categorize_result

    def get_daily_queue(
        self,
        hospital_id: int,
        queue_date: date,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取当日检查队列，按优先级排序"""
        query = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == queue_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.COMPLETED,
                AppointmentStatus.NO_SHOW
            ])
        )

        if category_filter:
            if category_filter == "inpatient":
                query = query.filter(Appointment.is_inpatient == True)
            elif category_filter == "anesthesia":
                query = query.filter(Appointment.needs_anesthesia == True)
            elif category_filter == "emergency":
                query = query.filter(Appointment.urgency_level.in_(["emergency", "urgent"]))
            elif category_filter == "referral":
                query = query.filter(Appointment.is_referral == True)

        appointments = query.order_by(
            desc(Appointment.priority_score),
            Appointment.queue_number
        ).all()

        queue = []
        current_queue_num = 1
        for appt in appointments:
            if appt.queue_number is None:
                appt.queue_number = current_queue_num
            current_queue_num += 1

            queue.append({
                "queue_number": appt.queue_number,
                "appointment_id": appt.id,
                "appointment_no": appt.appointment_no,
                "patient_name": appt.patient.name if appt.patient else "",
                "patient_type": "住院" if appt.is_inpatient else "门诊",
                "urgency_level": appt.urgency_level,
                "priority_score": appt.priority_score,
                "status": appt.status,
                "time_slot": appt.time_slot,
                "needs_anesthesia": appt.needs_anesthesia,
                "is_referral": appt.is_referral,
                "estimated_duration": appt.estimated_duration_minutes,
                "workflow_category": appt.workflow_category
            })

        self.db.commit()
        return queue

    def _determine_category(
        self,
        appt_data: AppointmentCreate,
        patient: Patient
    ) -> str:
        """确定预约分类"""
        if appt_data.urgency_level == "emergency":
            return "急诊绿色通道"
        elif appt_data.needs_anesthesia:
            return "麻醉预约"
        elif appt_data.is_inpatient:
            return "住院患者"
        elif appt_data.is_referral:
            return "转诊患者"
        elif appt_data.urgency_level == "urgent":
            return "加急预约"
        elif patient.consecutive_no_show >= 2:
            return "高风险患者"
        else:
            return "常规预约"

    def _determine_queue(self, appt_data: AppointmentCreate) -> str:
        """确定推荐队列"""
        if appt_data.urgency_level in ["emergency", "urgent"]:
            return "优先队列"
        elif appt_data.needs_anesthesia:
            return "麻醉专用队列"
        elif appt_data.is_inpatient:
            return "住院患者队列"
        elif appt_data.is_referral:
            return "转诊患者队列"
        else:
            return "普通队列"

    def _determine_resource_requirements(
        self,
        appt_data: AppointmentCreate
    ) -> Dict[str, Any]:
        """确定资源需求"""
        requirements = {
            "equipment_type": "petct",
            "tracer_type": appt_data.tracer_type,
            "estimated_duration_minutes": appt_data.estimated_duration_minutes,
            "needs_anesthesia_staff": appt_data.needs_anesthesia,
            "needs_escort": appt_data.needs_escort,
            "room_type": "standard"
        }

        if appt_data.needs_anesthesia:
            requirements["room_type"] = "anesthesia_ready"
            requirements["additional_staff"] = ["麻醉师", "麻醉护士"]
            requirements["preparation_time"] = 30

        if appt_data.urgency_level == "emergency":
            requirements["priority_bypass"] = True
            requirements["immediate_availability"] = True

        return requirements

    def _estimate_wait_time(
        self,
        hospital_id: int,
        appointment_date: date,
        priority_score: int
    ) -> int:
        """估算等待时间(分钟)"""
        existing_count = self.db.query(Appointment).filter(
            Appointment.hospital_id == hospital_id,
            Appointment.appointment_date == appointment_date,
            Appointment.status.notin_([
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW
            ])
        ).count()

        base_wait = existing_count * 45

        if priority_score >= 80:
            base_wait = int(base_wait * 0.3)
        elif priority_score >= 60:
            base_wait = int(base_wait * 0.6)
        elif priority_score <= 30:
            base_wait = int(base_wait * 1.2)

        return min(base_wait, 480)

    def _determine_special_handling(
        self,
        appt_data: AppointmentCreate,
        patient: Patient
    ) -> List[str]:
        """确定特殊处理要求"""
        handling = []

        if appt_data.needs_anesthesia:
            handling.append("需麻醉科会诊")
            handling.append("需术前评估")
            handling.append("需安排麻醉恢复室")

        if patient.needs_escort:
            handling.append("需家属陪同")

        if not patient.is_ambulatory:
            handling.append("需轮椅/平车接送")

        if patient.has_allergy:
            handling.append(f"注意过敏史: {patient.allergy_details}")

        if patient.diabetes_type:
            handling.append(f"糖尿病患者({patient.diabetes_type})，需监测血糖")

        if patient.egfr and patient.egfr < 60:
            handling.append("肾功能不全，需调整示踪剂剂量")

        if appt_data.urgency_level == "emergency":
            handling.append("急诊，启动绿色通道")
            handling.append("优先安排检查")

        return handling
