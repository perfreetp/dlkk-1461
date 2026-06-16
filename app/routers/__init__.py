from fastapi import APIRouter

from app.routers import auth, appointment, scheduling, status, reschedule, reports
from app.routers import alerts, notifications, schedule, referrals
from app.routers import hospitals, equipment, tracer, patients, users

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(appointment.router, prefix="/appointments", tags=["预约汇聚"])
api_router.include_router(scheduling.router, prefix="/scheduling", tags=["资源调度"])
api_router.include_router(status.router, prefix="/status", tags=["状态回传"])
api_router.include_router(reschedule.router, prefix="/reschedule", tags=["异常重排"])
api_router.include_router(reports.router, prefix="/reports", tags=["运营报表"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["风险预警"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知系统"])
api_router.include_router(schedule.router, prefix="/schedule", tags=["排班管理"])
api_router.include_router(referrals.router, prefix="/referrals", tags=["转诊管理"])
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["院区管理"])
api_router.include_router(equipment.router, prefix="/equipment", tags=["设备管理"])
api_router.include_router(tracer.router, prefix="/tracer", tags=["示踪剂管理"])
api_router.include_router(patients.router, prefix="/patients", tags=["患者管理"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
