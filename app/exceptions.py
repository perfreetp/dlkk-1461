from fastapi import HTTPException, status


class SchedulerException(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str = None):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code or "scheduler_error"


class AppointmentNotFound(SchedulerException):
    def __init__(self, appointment_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"预约记录不存在: {appointment_id}",
            code="appointment_not_found"
        )


class ResourceNotAvailable(SchedulerException):
    def __init__(self, resource_type: str, reason: str = ""):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource_type} 资源不可用: {reason}",
            code="resource_not_available"
        )


class InvalidStatusTransition(SchedulerException):
    def __init__(self, current: str, target: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的状态转换: {current} -> {target}",
            code="invalid_status_transition"
        )


class HighRiskAlert(SchedulerException):
    def __init__(self, risk_type: str, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"高风险预警 [{risk_type}]: {detail}",
            code="high_risk_alert"
        )


class AuthenticationError(SchedulerException):
    def __init__(self, detail: str = "认证失败"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            code="authentication_error"
        )


class PermissionDenied(SchedulerException):
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            code="permission_denied"
        )


class ValidationError(SchedulerException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            code="validation_error"
        )


class HospitalNotFound(SchedulerException):
    def __init__(self, hospital_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"院区不存在: {hospital_id}",
            code="hospital_not_found"
        )
