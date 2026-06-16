from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, time as dt_time

from app.database import SessionLocal
from app.services import AlertService
from app.utils.logger import get_logger

logger = get_logger("scheduler")

_scheduler: BackgroundScheduler = None


def run_monitoring_cycle():
    """执行定时监控任务"""
    logger.info("Starting scheduled monitoring cycle...")
    try:
        db = SessionLocal()
        try:
            alert_service = AlertService(db)
            results = alert_service.run_monitoring_cycle()
            logger.info(f"Monitoring cycle completed: {results}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in monitoring cycle: {e}", exc_info=True)


def run_daily_nightly_tasks():
    """执行每日夜间任务"""
    logger.info("Starting daily nightly tasks...")
    try:
        db = SessionLocal()
        try:
            from app.services import ReportService, NotificationService
            report_service = ReportService(db)
            notification_service = NotificationService(db)

            logger.info("Daily nightly tasks completed")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in nightly tasks: {e}", exc_info=True)


def run_hourly_status_check():
    """每小时状态检查"""
    logger.info("Starting hourly status check...")
    try:
        db = SessionLocal()
        try:
            alert_service = AlertService(db)
            results = alert_service.check_checkin_timeout()
            results.update(alert_service.check_queue_overload())
            logger.info(f"Hourly status check completed: {results}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in hourly status check: {e}", exc_info=True)


def run_drug_expiry_check():
    """检查药物过期"""
    logger.info("Starting drug expiry check...")
    try:
        db = SessionLocal()
        try:
            alert_service = AlertService(db)
            results = alert_service.check_drug_waste_high()
            logger.info(f"Drug expiry check completed: {results}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in drug expiry check: {e}", exc_info=True)


def start_scheduler():
    """启动定时任务调度器"""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.warning("Scheduler already running")
        return _scheduler

    executors = {
        "default": ThreadPoolExecutor(10),
        "processpool": ProcessPoolExecutor(3)
    }

    job_defaults = {
        "coalesce": True,
        "max_instances": 3,
        "misfire_grace_time": 60
    }

    _scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone="Asia/Shanghai"
    )

    _scheduler.add_job(
        run_monitoring_cycle,
        trigger=IntervalTrigger(hours=1, start_date=datetime.now()),
        id="monitoring_cycle",
        name="风险监控周期",
        replace_existing=True
    )

    _scheduler.add_job(
        run_hourly_status_check,
        trigger=IntervalTrigger(hours=1, start_date=datetime.now()),
        id="hourly_status_check",
        name="每小时状态检查",
        replace_existing=True
    )

    _scheduler.add_job(
        run_daily_nightly_tasks,
        trigger=CronTrigger(hour=2, minute=0, timezone="Asia/Shanghai"),
        id="daily_nightly_tasks",
        name="每日夜间任务",
        replace_existing=True
    )

    _scheduler.add_job(
        run_drug_expiry_check,
        trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Shanghai"),
        id="drug_expiry_check",
        name="药物过期检查",
        replace_existing=True
    )

    _scheduler.start()
    logger.info("Scheduler started successfully")

    jobs = _scheduler.get_jobs()
    for job in jobs:
        logger.info(f"Registered job: {job.id} - {job.name} - next run: {job.next_run_time}")

    return _scheduler


def shutdown_scheduler():
    """关闭定时任务调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown successfully")
        _scheduler = None


def get_scheduler() -> BackgroundScheduler:
    """获取调度器实例"""
    return _scheduler


def add_manual_job(job_func, job_id: str, job_name: str, trigger=None, **kwargs):
    """手动添加任务"""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        raise RuntimeError("Scheduler not running")

    job = _scheduler.add_job(
        job_func,
        trigger=trigger,
        id=job_id,
        name=job_name,
        replace_existing=True,
        **kwargs
    )
    logger.info(f"Manual job added: {job_id} - {job_name}")
    return job
