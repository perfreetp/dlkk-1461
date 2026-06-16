from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta, time
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, or_, case

from app.models import Hospital, User, Equipment, ScheduleTemplate, ShiftAssignment, SupportPlan
from app.schemas import (
    ScheduleTemplateCreate, ScheduleTemplateUpdate, ScheduleTemplateResponse,
    ShiftAssignmentCreate, ShiftAssignmentUpdate, ShiftAssignmentResponse,
    SupportPlanCreate, SupportPlanUpdate, SupportPlanResponse
)
from app.utils import get_logger
from app.exceptions import ValidationError, ResourceNotAvailable
from app.config import get_settings

settings = get_settings()
logger = get_logger("schedule_management_service")


class ScheduleManagementService:
    """排班管理服务 - 节假日排班模板与临时支援方案"""

    def __init__(self, db: Session):
        self.db = db

    def create_template(
        self,
        template_data: ScheduleTemplateCreate
    ) -> ScheduleTemplateResponse:
        """创建排班模板"""
        hospital = self.db.query(Hospital).filter(
            Hospital.id == template_data.hospital_id
        ).first()

        if not hospital:
            raise ValidationError(f"院区不存在: {template_data.hospital_id}")

        if template_data.morning_capacity + template_data.afternoon_capacity != template_data.daily_capacity:
            raise ValidationError("上午容量 + 下午容量 必须等于 日检查容量")

        if (template_data.anesthesia_slots + template_data.inpatient_slots + template_data.emergency_slots) > template_data.daily_capacity:
            raise ValidationError("各类型时段之和不能超过日检查容量")

        template = ScheduleTemplate(**template_data.model_dump())
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)

        logger.info(
            f"创建排班模板: {template.template_name}, 类型={template.template_type}, "
            f"院区={hospital.name}, 日容量={template.daily_capacity}"
        )

        return ScheduleTemplateResponse.model_validate(template)

    def update_template(
        self,
        template_id: int,
        update_data: ScheduleTemplateUpdate
    ) -> ScheduleTemplateResponse:
        """更新排班模板"""
        template = self.db.query(ScheduleTemplate).filter(
            ScheduleTemplate.id == template_id
        ).first()

        if not template:
            raise ValidationError(f"排班模板不存在: {template_id}")

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(template, field, value)

        template.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(template)

        logger.info(f"更新排班模板: {template_id}, 名称={template.template_name}")

        return ScheduleTemplateResponse.model_validate(template)

    def get_template(
        self,
        template_id: int
    ) -> ScheduleTemplateResponse:
        """获取排班模板详情"""
        template = self.db.query(ScheduleTemplate).filter(
            ScheduleTemplate.id == template_id
        ).first()

        if not template:
            raise ValidationError(f"排班模板不存在: {template_id}")

        return ScheduleTemplateResponse.model_validate(template)

    def list_templates(
        self,
        hospital_id: Optional[int] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        include_expired: bool = False
    ) -> List[ScheduleTemplateResponse]:
        """查询排班模板列表"""
        query = self.db.query(ScheduleTemplate)

        if hospital_id:
            query = query.filter(ScheduleTemplate.hospital_id == hospital_id)
        if template_type:
            query = query.filter(ScheduleTemplate.template_type == template_type)
        if is_active is not None:
            query = query.filter(ScheduleTemplate.is_active == is_active)
        if not include_expired:
            today = date.today()
            query = query.filter(
                or_(
                    ScheduleTemplate.expiry_date.is_(None),
                    ScheduleTemplate.expiry_date >= today
                )
            )

        templates = query.order_by(desc(ScheduleTemplate.created_at)).all()

        return [ScheduleTemplateResponse.model_validate(t) for t in templates]

    def get_applicable_template(
        self,
        hospital_id: int,
        target_date: date
    ) -> Optional[ScheduleTemplate]:
        """获取指定日期适用的排班模板"""
        weekday = target_date.weekday()
        is_weekend = weekday >= 5
        is_holiday = self._check_is_holiday(hospital_id, target_date)

        query = self.db.query(ScheduleTemplate).filter(
            and_(
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
            )
        ).order_by(
            case(
                (ScheduleTemplate.template_type == "holiday" and is_holiday, 1),
                (ScheduleTemplate.template_type == "special", 2),
                (ScheduleTemplate.template_type == "weekend" if is_weekend else "weekday", 3),
                (ScheduleTemplate.template_type == "normal", 4),
                else_=5
            )
        )

        template = query.first()

        if not template:
            template = self.db.query(ScheduleTemplate).filter(
                and_(
                    ScheduleTemplate.hospital_id == hospital_id,
                    ScheduleTemplate.is_active == True,
                    ScheduleTemplate.template_type == "normal"
                )
            ).first()

        return template

    def generate_holiday_template(
        self,
        hospital_id: int,
        holiday_name: str,
        start_date: date,
        end_date: date,
        capacity_factor: float = 0.5
    ) -> ScheduleTemplateResponse:
        """生成节假日排班模板"""
        normal_template = self.get_applicable_template(
            hospital_id=hospital_id,
            target_date=start_date - timedelta(days=1)
        )

        if not normal_template:
            raise ValidationError("未找到正常工作日模板，无法生成节假日模板")

        daily_capacity = max(1, int(normal_template.daily_capacity * capacity_factor))
        morning_capacity = max(1, int(normal_template.morning_capacity * capacity_factor))
        afternoon_capacity = max(1, int(normal_template.afternoon_capacity * capacity_factor))

        template_data = ScheduleTemplateCreate(
            hospital_id=hospital_id,
            template_name=f"节假日模板-{holiday_name}",
            template_type="holiday",
            effective_date=start_date,
            expiry_date=end_date,
            work_start_time=normal_template.work_start_time,
            work_end_time=normal_template.work_end_time,
            lunch_start_time=normal_template.lunch_start_time,
            lunch_end_time=normal_template.lunch_end_time,
            daily_capacity=daily_capacity,
            morning_capacity=morning_capacity,
            afternoon_capacity=afternoon_capacity,
            anesthesia_slots=max(0, int(normal_template.anesthesia_slots * capacity_factor)),
            inpatient_slots=max(0, int(normal_template.inpatient_slots * capacity_factor)),
            emergency_slots=normal_template.emergency_slots,
            is_active=True,
            notes=f"自动生成的{holiday_name}节假日模板，容量为正常日的{int(capacity_factor * 100)}%"
        )

        return self.create_template(template_data)

    def create_shift_assignment(
        self,
        shift_data: ShiftAssignmentCreate
    ) -> ShiftAssignmentResponse:
        """创建班次分配"""
        hospital = self.db.query(Hospital).filter(
            Hospital.id == shift_data.hospital_id
        ).first()

        if not hospital:
            raise ValidationError(f"院区不存在: {shift_data.hospital_id}")

        user = self.db.query(User).filter(
            User.id == shift_data.user_id
        ).first()

        if not user:
            raise ValidationError(f"用户不存在: {shift_data.user_id}")

        if shift_data.equipment_id:
            equipment = self.db.query(Equipment).filter(
                Equipment.id == shift_data.equipment_id
            ).first()
            if not equipment:
                raise ValidationError(f"设备不存在: {shift_data.equipment_id}")

        if shift_data.template_id:
            template = self.db.query(ScheduleTemplate).filter(
                ScheduleTemplate.id == shift_data.template_id
            ).first()
            if not template:
                raise ValidationError(f"排班模板不存在: {shift_data.template_id}")

        if self._check_shift_conflict(
            user_id=shift_data.user_id,
            shift_date=shift_data.shift_date,
            shift_type=shift_data.shift_type
        ):
            raise ResourceNotAvailable(
                f"用户 {user.name} 在 {shift_data.shift_date} {shift_data.shift_type} 已有排班"
            )

        shift = ShiftAssignment(**shift_data.model_dump())
        self.db.add(shift)
        self.db.commit()
        self.db.refresh(shift)

        logger.info(
            f"创建班次分配: 日期={shift.shift_date}, 班次={shift.shift_type}, "
            f"人员={user.name}, 院区={hospital.name}"
        )

        return ShiftAssignmentResponse.model_validate(shift)

    def update_shift_assignment(
        self,
        shift_id: int,
        update_data: ShiftAssignmentUpdate
    ) -> ShiftAssignmentResponse:
        """更新班次分配"""
        shift = self.db.query(ShiftAssignment).filter(
            ShiftAssignment.id == shift_id
        ).first()

        if not shift:
            raise ValidationError(f"班次不存在: {shift_id}")

        if update_data.user_id and update_data.user_id != shift.user_id:
            if self._check_shift_conflict(
                user_id=update_data.user_id,
                shift_date=shift.shift_date,
                shift_type=update_data.shift_type or shift.shift_type,
                exclude_shift_id=shift_id
            ):
                raise ResourceNotAvailable(
                    f"用户 {update_data.user_id} 在该时段已有排班"
                )

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(shift, field, value)

        shift.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(shift)

        logger.info(f"更新班次分配: {shift_id}, 日期={shift.shift_date}")

        return ShiftAssignmentResponse.model_validate(shift)

    def request_shift_swap(
        self,
        shift_id: int,
        swap_user_id: int,
        requested_by: str
    ) -> Dict[str, Any]:
        """申请换班"""
        shift = self.db.query(ShiftAssignment).filter(
            ShiftAssignment.id == shift_id
        ).first()

        if not shift:
            raise ValidationError(f"班次不存在: {shift_id}")

        if shift.user_id == swap_user_id:
            raise ValidationError("不能与自己换班")

        swap_user = self.db.query(User).filter(
            User.id == swap_user_id
        ).first()

        if not swap_user:
            raise ValidationError(f"换班对象不存在: {swap_user_id}")

        if self._check_shift_conflict(
            user_id=swap_user_id,
            shift_date=shift.shift_date,
            shift_type=shift.shift_type
        ):
            raise ResourceNotAvailable(
                f"用户 {swap_user.name} 在该时段已有排班，无法换班"
            )

        shift.swap_requested = True
        shift.swap_user_id = swap_user_id
        shift.notes = f"{shift.notes or ''}\n换班申请: {requested_by} 申请与 {swap_user.name} 换班"
        self.db.commit()

        logger.info(
            f"换班申请: 班次={shift_id}, 原人员={shift.user_id}, "
            f"换班人员={swap_user_id}, 申请人={requested_by}"
        )

        return {
            "success": True,
            "shift_id": shift_id,
            "swap_user_id": swap_user_id,
            "swap_user_name": swap_user.name,
            "status": "pending_approval"
        }

    def approve_shift_swap(
        self,
        shift_id: int,
        approved_by: str
    ) -> Dict[str, Any]:
        """批准换班"""
        shift = self.db.query(ShiftAssignment).filter(
            ShiftAssignment.id == shift_id
        ).first()

        if not shift:
            raise ValidationError(f"班次不存在: {shift_id}")

        if not shift.swap_requested or not shift.swap_user_id:
            raise ValidationError("该班次没有待批准的换班申请")

        old_user_id = shift.user_id
        old_user = self.db.query(User).filter(User.id == old_user_id).first()
        new_user = self.db.query(User).filter(User.id == shift.swap_user_id).first()

        shift.user_id = shift.swap_user_id
        shift.swap_requested = False
        shift.swap_user_id = None
        shift.notes = f"{shift.notes or ''}\n换班已批准: {approved_by}，由 {old_user.name if old_user else old_user_id} 换为 {new_user.name if new_user else shift.user_id}"
        self.db.commit()

        logger.info(
            f"换班已批准: 班次={shift_id}, 原人员={old_user_id}, "
            f"新人员={shift.user_id}, 批准人={approved_by}"
        )

        return {
            "success": True,
            "shift_id": shift_id,
            "old_user_id": old_user_id,
            "new_user_id": shift.user_id,
            "approved_by": approved_by
        }

    def list_shift_assignments(
        self,
        hospital_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        shift_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[ShiftAssignmentResponse]:
        """查询班次列表"""
        query = self.db.query(ShiftAssignment)

        if hospital_id:
            query = query.filter(ShiftAssignment.hospital_id == hospital_id)
        if user_id:
            query = query.filter(ShiftAssignment.user_id == user_id)
        if start_date:
            query = query.filter(ShiftAssignment.shift_date >= start_date)
        if end_date:
            query = query.filter(ShiftAssignment.shift_date <= end_date)
        if shift_type:
            query = query.filter(ShiftAssignment.shift_type == shift_type)
        if is_active is not None:
            query = query.filter(ShiftAssignment.is_active == is_active)

        shifts = query.order_by(ShiftAssignment.shift_date, ShiftAssignment.start_time).all()

        return [ShiftAssignmentResponse.model_validate(s) for s in shifts]

    def create_support_plan(
        self,
        plan_data: SupportPlanCreate
    ) -> SupportPlanResponse:
        """创建临时支援方案"""
        hospital = self.db.query(Hospital).filter(
            Hospital.id == plan_data.hospital_id
        ).first()

        if not hospital:
            raise ValidationError(f"目标院区不存在: {plan_data.hospital_id}")

        if plan_data.source_hospital_id:
            source_hospital = self.db.query(Hospital).filter(
                Hospital.id == plan_data.source_hospital_id
            ).first()
            if not source_hospital:
                raise ValidationError(f"来源院区不存在: {plan_data.source_hospital_id}")

        if plan_data.start_date > plan_data.end_date:
            raise ValidationError("开始日期不能晚于结束日期")

        plan = SupportPlan(**plan_data.model_dump())
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        logger.info(
            f"创建支援方案: {plan.plan_name}, 类型={plan.plan_type}, "
            f"目标院区={hospital.name}, 日期={plan.start_date} ~ {plan.end_date}, "
            f"额外容量={plan.additional_capacity}, 支援人数={plan.staff_count}"
        )

        return SupportPlanResponse.model_validate(plan)

    def update_support_plan(
        self,
        plan_id: int,
        update_data: SupportPlanUpdate
    ) -> SupportPlanResponse:
        """更新支援方案"""
        plan = self.db.query(SupportPlan).filter(
            SupportPlan.id == plan_id
        ).first()

        if not plan:
            raise ValidationError(f"支援方案不存在: {plan_id}")

        update_dict = update_data.model_dump(exclude_unset=True)

        if "status" in update_dict and update_dict["status"] == "active":
            if not plan.approved_by and not update_dict.get("approved_by"):
                raise ValidationError("激活支援方案需要审批人信息")

            if "approved_by" in update_dict:
                plan.approved_at = datetime.utcnow()

        for field, value in update_dict.items():
            setattr(plan, field, value)

        plan.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(plan)

        logger.info(
            f"更新支援方案: {plan_id}, 名称={plan.plan_name}, 状态={plan.status}"
        )

        return SupportPlanResponse.model_validate(plan)

    def approve_support_plan(
        self,
        plan_id: int,
        approved_by: str
    ) -> SupportPlanResponse:
        """审批支援方案"""
        plan = self.db.query(SupportPlan).filter(
            SupportPlan.id == plan_id
        ).first()

        if not plan:
            raise ValidationError(f"支援方案不存在: {plan_id}")

        plan.status = "active"
        plan.approved_by = approved_by
        plan.approved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(plan)

        logger.info(
            f"支援方案已审批: {plan_id}, 名称={plan.plan_name}, 审批人={approved_by}"
        )

        return SupportPlanResponse.model_validate(plan)

    def get_support_plan(
        self,
        plan_id: int
    ) -> SupportPlanResponse:
        """获取支援方案详情"""
        plan = self.db.query(SupportPlan).filter(
            SupportPlan.id == plan_id
        ).first()

        if not plan:
            raise ValidationError(f"支援方案不存在: {plan_id}")

        return SupportPlanResponse.model_validate(plan)

    def list_support_plans(
        self,
        hospital_id: Optional[int] = None,
        source_hospital_id: Optional[int] = None,
        plan_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[SupportPlanResponse]:
        """查询支援方案列表"""
        query = self.db.query(SupportPlan)

        if hospital_id:
            query = query.filter(
                or_(
                    SupportPlan.hospital_id == hospital_id,
                    SupportPlan.source_hospital_id == hospital_id
                )
            )
        if source_hospital_id:
            query = query.filter(SupportPlan.source_hospital_id == source_hospital_id)
        if plan_type:
            query = query.filter(SupportPlan.plan_type == plan_type)
        if status:
            query = query.filter(SupportPlan.status == status)
        if start_date:
            query = query.filter(SupportPlan.end_date >= start_date)
        if end_date:
            query = query.filter(SupportPlan.start_date <= end_date)

        plans = query.order_by(desc(SupportPlan.created_at)).all()

        return [SupportPlanResponse.model_validate(p) for p in plans]

    def get_active_support_plans(
        self,
        hospital_id: int,
        target_date: date
    ) -> List[SupportPlanResponse]:
        """获取指定日期有效的支援方案"""
        plans = self.db.query(SupportPlan).filter(
            and_(
                SupportPlan.hospital_id == hospital_id,
                SupportPlan.status == "active",
                SupportPlan.start_date <= target_date,
                SupportPlan.end_date >= target_date
            )
        ).all()

        return [SupportPlanResponse.model_validate(p) for p in plans]

    def get_schedule_summary(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """获取排班摘要"""
        shifts = self.list_shift_assignments(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date
        )

        support_plans = self.list_support_plans(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date
        )

        template = self.get_applicable_template(hospital_id, start_date)

        total_shifts = len(shifts)
        shifts_by_type = {}
        shifts_by_user = {}

        for shift in shifts:
            shifts_by_type[shift.shift_type] = shifts_by_type.get(shift.shift_type, 0) + 1
            user_name = shift.user_id
            shifts_by_user[user_name] = shifts_by_user.get(user_name, 0) + 1

        swap_requests = sum(1 for s in shifts if s.swap_requested)
        active_supports = [p for p in support_plans if p.status == "active"]

        additional_capacity = sum(
            p.additional_capacity for p in active_supports
        )

        return {
            "hospital_id": hospital_id,
            "start_date": start_date,
            "end_date": end_date,
            "template": {
                "id": template.id if template else None,
                "name": template.template_name if template else "默认模板",
                "daily_capacity": template.daily_capacity if template else 20
            },
            "total_shifts": total_shifts,
            "shifts_by_type": shifts_by_type,
            "shifts_by_user": shifts_by_user,
            "swap_requests": swap_requests,
            "active_support_plans": len(active_supports),
            "additional_capacity": additional_capacity,
            "total_capacity": (template.daily_capacity if template else 20) + additional_capacity
        }

    def _check_shift_conflict(
        self,
        user_id: int,
        shift_date: date,
        shift_type: str,
        exclude_shift_id: Optional[int] = None
    ) -> bool:
        """检查班次冲突"""
        query = self.db.query(ShiftAssignment).filter(
            and_(
                ShiftAssignment.user_id == user_id,
                ShiftAssignment.shift_date == shift_date,
                ShiftAssignment.shift_type == shift_type,
                ShiftAssignment.is_active == True
            )
        )

        if exclude_shift_id:
            query = query.filter(ShiftAssignment.id != exclude_shift_id)

        return query.first() is not None

    def _check_is_holiday(
        self,
        hospital_id: int,
        target_date: date
    ) -> bool:
        """检查是否为节假日"""
        date_str = target_date.strftime("%Y-%m-%d")

        holiday_templates = self.db.query(ScheduleTemplate).filter(
            and_(
                ScheduleTemplate.hospital_id == hospital_id,
                ScheduleTemplate.template_type == "holiday",
                ScheduleTemplate.is_active == True
            )
        ).all()

        for template in holiday_templates:
            if hasattr(template, 'special_dates') and template.special_dates:
                special_dates = template.special_dates.split(',')
                if date_str in special_dates:
                    return True

            if template.effective_date and template.expiry_date:
                if template.effective_date <= target_date <= template.expiry_date:
                    return True

        return False

    def generate_weekly_schedule(
        self,
        hospital_id: int,
        week_start_date: date,
        template_id: Optional[int] = None
    ) -> List[ShiftAssignment]:
        """自动生成周排班"""
        if week_start_date.weekday() != 0:
            raise ValidationError("周开始日期必须是周一")

        template = None
        if template_id:
            template = self.db.query(ScheduleTemplate).filter(
                ScheduleTemplate.id == template_id
            ).first()
            if not template:
                raise ValidationError(f"排班模板不存在: {template_id}")

        users = self.db.query(User).filter(
            and_(
                User.hospital_id == hospital_id if hasattr(User, 'hospital_id') else True,
                User.is_active == True if hasattr(User, 'is_active') else True
            )
        ).all()

        if not users:
            raise ValidationError("未找到可用人员")

        shifts = []
        shift_types = ["morning", "afternoon"]

        for day_offset in range(7):
            shift_date = week_start_date + timedelta(days=day_offset)

            if not template:
                day_template = self.get_applicable_template(hospital_id, shift_date)
            else:
                day_template = template

            if not day_template:
                continue

            for shift_type in shift_types:
                user_index = (len(shifts) // len(shift_types)) % len(users)
                assigned_user = users[user_index]

                shift_data = ShiftAssignmentCreate(
                    hospital_id=hospital_id,
                    user_id=assigned_user.id,
                    shift_date=shift_date,
                    shift_type=shift_type,
                    template_id=day_template.id,
                    start_time=day_template.work_start_time if shift_type == "morning" else day_template.lunch_end_time,
                    end_time=day_template.lunch_start_time if shift_type == "morning" else day_template.work_end_time
                )

                try:
                    shift = ShiftAssignment(**shift_data.model_dump())
                    shifts.append(shift)
                except Exception as e:
                    logger.warning(f"生成班次失败: {e}")

        for shift in shifts:
            self.db.add(shift)
        self.db.commit()

        logger.info(
            f"自动生成周排班: 院区={hospital_id}, "
            f"开始日期={week_start_date}, 生成班次={len(shifts)}个"
        )

        return shifts
