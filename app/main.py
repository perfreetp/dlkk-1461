from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import init_db
from app.routers import api_router
from app.exceptions import SchedulerException
from app.utils.logger import get_logger

logger = get_logger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"Starting {settings.PROJECT_NAME}...")

    init_db()
    logger.info("Database initialized")

    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
        logger.info("Scheduler shutdown")
    except Exception as e:
        logger.warning(f"Scheduler shutdown error: {e}")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="面向医联体核医学中心调度员的 PET-CT 检查流程协同后端服务",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(SchedulerException)
    async def scheduler_exception_handler(request: Request, exc: SchedulerException):
        """自定义业务异常处理器"""
        logger.error(f"Business error: {exc.code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "error_code": exc.code,
                "data": None,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": "->".join([str(loc) for loc in error["loc"]]),
                "message": error["msg"],
                "type": error["type"]
            })
        logger.warning(f"Validation error: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "请求参数验证失败",
                "error_code": "validation_error",
                "data": {"errors": errors},
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        """数据库异常处理器"""
        logger.error(f"Database error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "数据库操作异常",
                "error_code": "database_error",
                "data": None,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """全局异常处理器"""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "服务器内部错误",
                "error_code": "internal_server_error",
                "data": None,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查端点"""
        return {
            "code": 200,
            "message": "success",
            "data": {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": settings.PROJECT_NAME,
                "version": "1.0.0"
            }
        }

    @app.get("/", tags=["系统"])
    async def root():
        """根路径"""
        return {
            "code": 200,
            "message": "success",
            "data": {
                "service": settings.PROJECT_NAME,
                "version": "1.0.0",
                "docs": "/docs",
                "health": "/health"
            }
        }

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
