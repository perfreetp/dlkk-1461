from app.models.base import Base
from app.models.user import User
from app.models.hospital import Hospital
from app.models.equipment import Equipment
from app.models.tracer import Tracer, TracerBatch, TracerUsage
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.status_record import StatusRecord
from app.models.schedule import ScheduleTemplate, ShiftAssignment, SupportPlan
from app.models.notification import Notification
from app.models.alert import Alert
from app.models.referral import Referral
from app.models.drug_waste import DrugWasteRecord

all_models = [
    User, Hospital, Equipment, Tracer, TracerBatch, TracerUsage,
    Patient, Appointment, StatusRecord, ScheduleTemplate,
    ShiftAssignment, SupportPlan, Notification, Alert,
    Referral, DrugWasteRecord
]

__all__ = [
    "Base", "User", "Hospital", "Equipment", "Tracer", "TracerBatch",
    "TracerUsage", "Patient", "Appointment", "StatusRecord",
    "ScheduleTemplate", "ShiftAssignment", "SupportPlan",
    "Notification", "Alert", "Referral", "DrugWasteRecord", "all_models"
]
