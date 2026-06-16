#!/usr/bin/env python3
"""数据库初始化脚本 - 创建基础数据"""
import sys
import os
from datetime import datetime, date, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import (
    User, Hospital, Equipment, Tracer, TracerBatch,
    Patient, ScheduleTemplate
)
from app.utils.auth import get_password_hash
from app.utils.logger import get_logger

logger = get_logger("init_data")


def init_sample_data():
    """初始化示例数据"""
    init_db()
    db = SessionLocal()

    try:
        logger.info("开始初始化示例数据...")

        if db.query(Hospital).count() == 0:
            hospitals = [
                Hospital(
                    code="H001",
                    name="中心医院",
                    address="北京市朝阳区中心路1号",
                    phone="010-12345678",
                    latitude=39.9042,
                    longitude=116.4074,
                    daily_capacity=20,
                    morning_capacity=10,
                    afternoon_capacity=10,
                    operating_hours_start="08:00",
                    operating_hours_end="17:00",
                    slot_duration_minutes=30,
                    is_active=True
                ),
                Hospital(
                    code="H002",
                    name="东院区",
                    address="北京市海淀区东部路2号",
                    phone="010-23456789",
                    latitude=39.9542,
                    longitude=116.3374,
                    daily_capacity=15,
                    morning_capacity=8,
                    afternoon_capacity=7,
                    operating_hours_start="08:30",
                    operating_hours_end="17:30",
                    slot_duration_minutes=30,
                    is_active=True
                ),
                Hospital(
                    code="H003",
                    name="西院区",
                    address="北京市西城区西部路3号",
                    phone="010-34567890",
                    latitude=39.9142,
                    longitude=116.3674,
                    daily_capacity=18,
                    morning_capacity=9,
                    afternoon_capacity=9,
                    operating_hours_start="08:00",
                    operating_hours_end="17:00",
                    slot_duration_minutes=30,
                    is_active=True
                )
            ]
            db.add_all(hospitals)
            db.flush()
            logger.info(f"创建了 {len(hospitals)} 个院区")

        if db.query(User).count() == 0:
            users = [
                User(
                    username="admin",
                    real_name="系统管理员",
                    password_hash=get_password_hash("admin123"),
                    phone="13800138000",
                    email="admin@example.com",
                    role="admin",
                    hospital_id=1,
                    is_active=True,
                    is_admin=True
                ),
                User(
                    username="supervisor",
                    real_name="张主管",
                    password_hash=get_password_hash("123456"),
                    phone="13800138001",
                    email="supervisor@example.com",
                    role="supervisor",
                    hospital_id=1,
                    is_active=True,
                    is_admin=False
                ),
                User(
                    username="scheduler",
                    real_name="李调度员",
                    password_hash=get_password_hash("123456"),
                    phone="13800138002",
                    email="scheduler@example.com",
                    role="scheduler",
                    hospital_id=1,
                    is_active=True,
                    is_admin=False
                ),
                User(
                    username="technician",
                    real_name="王技师",
                    password_hash=get_password_hash("123456"),
                    phone="13800138003",
                    email="technician@example.com",
                    role="technician",
                    hospital_id=1,
                    is_active=True,
                    is_admin=False
                ),
                User(
                    username="pharmacist",
                    real_name="赵药师",
                    password_hash=get_password_hash("123456"),
                    phone="13800138004",
                    email="pharmacist@example.com",
                    role="pharmacist",
                    hospital_id=1,
                    is_active=True,
                    is_admin=False
                )
            ]
            db.add_all(users)
            db.flush()
            logger.info(f"创建了 {len(users)} 个用户")

        if db.query(Equipment).count() == 0:
            equipment_list = [
                Equipment(
                    code="PET001",
                    name="PET-CT 设备1号",
                    equipment_type="petct",
                    manufacturer="SIEMENS",
                    model="Biograph Vision",
                    hospital_id=1,
                    location="核医学科1室",
                    status="available",
                    is_active=True
                ),
                Equipment(
                    code="PET002",
                    name="PET-CT 设备2号",
                    equipment_type="petct",
                    manufacturer="GE",
                    model="Discovery MI",
                    hospital_id=1,
                    location="核医学科2室",
                    status="available",
                    is_active=True
                ),
                Equipment(
                    code="PET003",
                    name="PET-CT 设备1号",
                    equipment_type="petct",
                    manufacturer="SIEMENS",
                    model="Biograph Horizon",
                    hospital_id=2,
                    location="核医学科1室",
                    status="available",
                    is_active=True
                ),
                Equipment(
                    code="PET004",
                    name="PET-CT 设备1号",
                    equipment_type="petct",
                    manufacturer="Philips",
                    model="Vereos",
                    hospital_id=3,
                    location="核医学科1室",
                    status="available",
                    is_active=True
                )
            ]
            db.add_all(equipment_list)
            db.flush()
            logger.info(f"创建了 {len(equipment_list)} 个设备")

        if db.query(Tracer).count() == 0:
            tracers = [
                Tracer(
                    code="FDG",
                    name="氟代脱氧葡萄糖",
                    name_en="Fluorodeoxyglucose",
                    half_life_minutes=109.7,
                    default_dose_mbq=370.0,
                    min_dose_mbq=185.0,
                    max_dose_mbq=740.0,
                    dose_per_kg_mbq=5.18,
                    unit="MBq",
                    cost_per_mbq=0.5,
                    is_active=True,
                    description="最常用的PET示踪剂，用于肿瘤评估"
                ),
                Tracer(
                    code="FDOPA",
                    name="氟多巴",
                    name_en="Fluorodopa",
                    half_life_minutes=109.7,
                    default_dose_mbq=185.0,
                    min_dose_mbq=111.0,
                    max_dose_mbq=370.0,
                    dose_per_kg_mbq=2.59,
                    unit="MBq",
                    cost_per_mbq=1.2,
                    is_active=True,
                    description="用于帕金森病和神经内分泌肿瘤"
                ),
                Tracer(
                    code="PSMA",
                    name="前列腺特异性膜抗原",
                    name_en="Prostate Specific Membrane Antigen",
                    half_life_minutes=109.7,
                    default_dose_mbq=259.0,
                    min_dose_mbq=148.0,
                    max_dose_mbq=444.0,
                    dose_per_kg_mbq=3.7,
                    unit="MBq",
                    cost_per_mbq=1.5,
                    is_active=True,
                    description="用于前列腺癌显像"
                )
            ]
            db.add_all(tracers)
            db.flush()
            logger.info(f"创建了 {len(tracers)} 个示踪剂")

        if db.query(TracerBatch).count() == 0:
            from datetime import timedelta
            now = datetime.now()
            tracer_batches = [
                TracerBatch(
                    batch_no="FDG2026061701",
                    tracer_id=1,
                    total_activity_mbq=3700.0,
                    calibration_activity=3700.0,
                    calibration_time=now,
                    production_time=now - timedelta(hours=2),
                    arrival_time=now - timedelta(hours=1),
                    expiry_time=now + timedelta(hours=12),
                    status="available",
                    used_activity_mbq=0.0,
                    wasted_activity_mbq=0.0
                ),
                TracerBatch(
                    batch_no="FDG2026061702",
                    tracer_id=1,
                    total_activity_mbq=2960.0,
                    calibration_activity=2960.0,
                    calibration_time=now,
                    production_time=now - timedelta(hours=2),
                    arrival_time=now - timedelta(hours=1),
                    expiry_time=now + timedelta(hours=12),
                    status="available",
                    used_activity_mbq=0.0,
                    wasted_activity_mbq=0.0
                ),
                TracerBatch(
                    batch_no="FDOPA2026061701",
                    tracer_id=2,
                    total_activity_mbq=1850.0,
                    calibration_activity=1850.0,
                    calibration_time=now,
                    production_time=now - timedelta(hours=2),
                    arrival_time=now - timedelta(hours=1),
                    expiry_time=now + timedelta(hours=12),
                    status="available",
                    used_activity_mbq=0.0,
                    wasted_activity_mbq=0.0
                )
            ]
            db.add_all(tracer_batches)
            db.flush()
            logger.info(f"创建了 {len(tracer_batches)} 个示踪剂批次")

        if db.query(Patient).count() == 0:
            patients = [
                Patient(
                    medical_record_no="MR000001",
                    id_card="110101198001010001",
                    name="张三",
                    gender="male",
                    birth_date=date(1980, 1, 1),
                    phone="13900139001",
                    address="北京市朝阳区",
                    has_diabetes=False,
                    has_allergies=False,
                    consecutive_no_show=0,
                    total_appointments=0,
                    is_active=True
                ),
                Patient(
                    medical_record_no="MR000002",
                    id_card="110101197505150002",
                    name="李四",
                    gender="female",
                    birth_date=date(1975, 5, 15),
                    phone="13900139002",
                    address="北京市海淀区",
                    has_diabetes=True,
                    diabetes_type="type2",
                    has_allergies=False,
                    consecutive_no_show=0,
                    total_appointments=0,
                    is_active=True
                ),
                Patient(
                    medical_record_no="MR000003",
                    id_card="110101196812200003",
                    name="王五",
                    gender="male",
                    birth_date=date(1968, 12, 20),
                    phone="13900139003",
                    address="北京市西城区",
                    has_diabetes=False,
                    has_allergies=True,
                    allergy_details="青霉素过敏",
                    consecutive_no_show=2,
                    total_appointments=5,
                    is_active=True
                )
            ]
            db.add_all(patients)
            db.flush()
            logger.info(f"创建了 {len(patients)} 个患者")

        if db.query(ScheduleTemplate).count() == 0:
            templates = [
                ScheduleTemplate(
                    name="工作日模板",
                    template_type="weekday",
                    hospital_id=1,
                    morning_start="08:00",
                    morning_end="12:00",
                    afternoon_start="13:30",
                    afternoon_end="17:00",
                    slots_per_hour=2,
                    daily_capacity=16,
                    is_active=True
                ),
                ScheduleTemplate(
                    name="周末模板",
                    template_type="weekend",
                    hospital_id=1,
                    morning_start="08:30",
                    morning_end="12:00",
                    afternoon_start="13:30",
                    afternoon_end="16:30",
                    slots_per_hour=2,
                    daily_capacity=12,
                    is_active=True
                ),
                ScheduleTemplate(
                    name="节假日模板",
                    template_type="holiday",
                    hospital_id=1,
                    morning_start="09:00",
                    morning_end="12:00",
                    afternoon_start="13:30",
                    afternoon_end="16:00",
                    slots_per_hour=2,
                    daily_capacity=8,
                    is_active=True
                )
            ]
            for t in templates:
                if not t.template_name:
                    t.template_name = t.name
            db.add_all(templates)
            db.flush()
            logger.info(f"创建了 {len(templates)} 个排班模板")

        db.commit()
        logger.info("示例数据初始化完成！")
        logger.info("默认登录账号: admin / admin123")
        logger.info("其他账号: supervisor/123456, scheduler/123456, technician/123456, pharmacist/123456")

    except Exception as e:
        db.rollback()
        logger.error(f"初始化数据失败: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_sample_data()
