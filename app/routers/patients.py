from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.patient import (
    PatientCreate, PatientUpdate, PatientResponse, PatientQueryParams
)
from app.utils.auth import get_current_active_user, require_roles
from app.utils.logger import get_logger
from app.models.patient import Patient
from app.exceptions import ResourceNotFound, ValidationError

router = APIRouter()
logger = get_logger("router_patients")


@router.get("", response_model=ApiResponse[PaginatedResponse[PatientResponse]])
def list_patients(
    query_params: PatientQueryParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者列表"""
    query = db.query(Patient)

    if query_params.search_keyword:
        keyword = f"%{query_params.search_keyword}%"
        query = query.filter(
            Patient.name.like(keyword) |
            Patient.id_card.like(keyword) |
            Patient.phone.like(keyword) |
            Patient.medical_record_no.like(keyword)
        )
    if query_params.gender:
        query = query.filter(Patient.gender == query_params.gender)
    if query_params.has_diabetes is not None:
        query = query.filter(Patient.has_diabetes == query_params.has_diabetes)
    if query_params.has_allergies is not None:
        query = query.filter(Patient.has_allergies == query_params.has_allergies)
    if query_params.consecutive_no_show_min is not None:
        query = query.filter(Patient.consecutive_no_show >= query_params.consecutive_no_show_min)
    if query_params.is_active is not None:
        query = query.filter(Patient.is_active == query_params.is_active)

    total = query.count()
    patients = query.order_by(Patient.updated_at.desc()).offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(
        data=PaginatedResponse(
            items=[PatientResponse.model_validate(p) for p in patients],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{patient_id}", response_model=ApiResponse[PatientResponse])
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者详情"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ResourceNotFound(f"患者不存在: {patient_id}")
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.post("", response_model=ApiResponse[PatientResponse])
def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建患者"""
    existing = db.query(Patient).filter(
        (Patient.id_card == patient_data.id_card) |
        (Patient.medical_record_no == patient_data.medical_record_no)
    ).first()
    if existing:
        raise ValidationError(f"患者身份证号或病历号已存在: {patient_data.id_card}")

    patient = Patient(**patient_data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)

    logger.info(f"创建患者: {patient.name} (ID: {patient.id})")
    return ApiResponse(data=PatientResponse.model_validate(patient), message="患者创建成功")


@router.put("/{patient_id}", response_model=ApiResponse[PatientResponse])
def update_patient(
    patient_id: int,
    update_data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """更新患者信息"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ResourceNotFound(f"患者不存在: {patient_id}")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return ApiResponse(data=PatientResponse.model_validate(patient), message="患者信息更新成功")


@router.delete("/{patient_id}", response_model=ApiResponse)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """删除患者（软删除）"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ResourceNotFound(f"患者不存在: {patient_id}")

    patient.is_active = False
    db.commit()
    return ApiResponse(message="患者已停用")


@router.get("/id-card/{id_card}", response_model=ApiResponse[PatientResponse])
def get_patient_by_id_card(
    id_card: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """根据身份证号查找患者"""
    patient = db.query(Patient).filter(Patient.id_card == id_card).first()
    if not patient:
        raise ResourceNotFound(f"患者不存在: {id_card}")
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.get("/medical-record/{medical_record_no}", response_model=ApiResponse[PatientResponse])
def get_patient_by_medical_record(
    medical_record_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """根据病历号查找患者"""
    patient = db.query(Patient).filter(Patient.medical_record_no == medical_record_no).first()
    if not patient:
        raise ResourceNotFound(f"患者不存在: {medical_record_no}")
    return ApiResponse(data=PatientResponse.model_validate(patient))


@router.get("/{patient_id}/appointments", response_model=ApiResponse)
def get_patient_appointments(
    patient_id: int,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者预约历史"""
    from app.models.appointment import Appointment

    query = db.query(Appointment).filter(Appointment.patient_id == patient_id)
    if status:
        query = query.filter(Appointment.status == status)
    if start_date:
        query = query.filter(Appointment.appointment_date >= start_date)
    if end_date:
        query = query.filter(Appointment.appointment_date <= end_date)

    appointments = query.order_by(Appointment.appointment_date.desc()).limit(limit).all()
    return ApiResponse(data={
        "appointments": appointments,
        "total": len(appointments)
    })


@router.get("/{patient_id}/risk-assessment", response_model=ApiResponse)
def get_patient_risk_assessment(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取患者风险评估"""
    from app.services import AlertService
    service = AlertService(db)
    assessment = service.get_patient_risk_assessment(patient_id)
    return ApiResponse(data=assessment)


@router.get("/high-risk/list", response_model=ApiResponse)
def get_high_risk_patients(
    hospital_id: Optional[int] = None,
    risk_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "supervisor", "scheduler"]))
):
    """获取高风险患者列表"""
    from app.config import get_settings
    settings = get_settings()

    query = db.query(Patient).filter(Patient.is_active == True)
    if risk_type == "consecutive_no_show" or risk_type is None:
        query = query.filter(Patient.consecutive_no_show >= settings.MAX_CONSECUTIVE_NO_SHOW)

    patients = query.all()
    return ApiResponse(data={
        "patients": [PatientResponse.model_validate(p) for p in patients],
        "total": len(patients),
        "threshold": settings.MAX_CONSECUTIVE_NO_SHOW
    })
