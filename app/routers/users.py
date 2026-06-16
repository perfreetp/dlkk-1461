from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.utils.auth import get_current_active_user, require_roles, get_password_hash
from app.utils.logger import get_logger
from app.exceptions import ResourceNotFound, ValidationError

router = APIRouter()
logger = get_logger("router_users")


@router.get("", response_model=ApiResponse[PaginatedResponse[UserResponse]])
def list_users(
    hospital_id: Optional[int] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户列表"""
    query = db.query(User)
    if hospital_id:
        query = query.filter(User.hospital_id == hospital_id)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(
        data=PaginatedResponse(
            items=[UserResponse.model_validate(u) for u in users],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
    )


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ResourceNotFound(f"用户不存在: {user_id}")
    return ApiResponse(data=UserResponse.model_validate(user))


@router.post("", response_model=ApiResponse[UserResponse])
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """创建用户"""
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise ValidationError(f"用户名已存在: {user_data.username}")

    hashed_password = get_password_hash(user_data.password)
    user = User(
        **user_data.model_dump(exclude={"password"}),
        password_hash=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"创建用户: {user.username} (ID: {user.id}) by {current_user.username}")
    return ApiResponse(data=UserResponse.model_validate(user), message="用户创建成功")


@router.put("/{user_id}", response_model=ApiResponse[UserResponse])
def update_user(
    user_id: int,
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ResourceNotFound(f"用户不存在: {user_id}")

    update_dict = update_data.model_dump(exclude_unset=True)
    if "password" in update_dict and update_dict["password"]:
        update_dict["password_hash"] = get_password_hash(update_dict.pop("password"))

    for field, value in update_dict.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return ApiResponse(data=UserResponse.model_validate(user), message="用户信息更新成功")


@router.delete("/{user_id}", response_model=ApiResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """删除用户（软删除）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ResourceNotFound(f"用户不存在: {user_id}")

    if user.id == current_user.id:
        raise ValidationError("不能删除当前登录用户")

    user.is_active = False
    db.commit()
    return ApiResponse(message="用户已停用")


@router.put("/{user_id}/password", response_model=ApiResponse)
def reset_password(
    user_id: int,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"]))
):
    """重置用户密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ResourceNotFound(f"用户不存在: {user_id}")

    user.password_hash = get_password_hash(new_password)
    db.commit()

    logger.info(f"重置密码: 用户 {user.username} by {current_user.username}")
    return ApiResponse(message="密码重置成功")


@router.put("/me/password", response_model=ApiResponse)
def change_password(
    old_password: str,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """修改当前用户密码"""
    from app.utils.auth import verify_password

    if not verify_password(old_password, current_user.password_hash):
        raise ValidationError("原密码错误")

    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    return ApiResponse(message="密码修改成功")


@router.get("/roles/list", response_model=ApiResponse)
def get_roles_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取角色列表"""
    roles = [
        {"code": "admin", "name": "管理员", "description": "系统管理员，拥有所有权限"},
        {"code": "supervisor", "name": "主管", "description": "调度主管，负责排班和异常处理"},
        {"code": "scheduler", "name": "调度员", "description": "日常预约调度操作人员"},
        {"code": "technician", "name": "技师", "description": "设备操作和检查执行人员"},
        {"code": "pharmacist", "name": "药师", "description": "负责示踪剂管理"},
        {"code": "doctor", "name": "医生", "description": "申请检查和查看结果"},
        {"code": "nurse", "name": "护士", "description": "患者护理和准备工作"},
        {"code": "receptionist", "name": "前台", "description": "患者登记和签到"}
    ]
    return ApiResponse(data={"roles": roles})


@router.get("/hospital/{hospital_id}", response_model=ApiResponse)
def get_users_by_hospital(
    hospital_id: int,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取某院区的用户"""
    query = db.query(User).filter(
        User.hospital_id == hospital_id,
        User.is_active == True
    )
    if role:
        query = query.filter(User.role == role)

    users = query.all()
    return ApiResponse(data={
        "users": [UserResponse.model_validate(u) for u in users],
        "total": len(users)
    })
