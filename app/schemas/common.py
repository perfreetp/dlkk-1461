from typing import Generic, TypeVar, Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=200, description="响应码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="时间戳")

    class Config:
        from_attributes = True


class ResponseModel(BaseModel, Generic[T]):
    success: bool = True
    message: str = ""
    data: Optional[T] = None
    errors: Optional[List[str]] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        from_attributes = True


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class DateRangeParams(BaseModel):
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")

    @field_validator("end_date")
    def check_date_order(cls, v, values):
        if v and values.data.get("start_date") and v < values.data["start_date"]:
            raise ValueError("结束日期不能早于开始日期")
        return v


class StatusChangeRequest(BaseModel):
    status: str = Field(..., description="新状态")
    reason: Optional[str] = Field(default=None, description="变更原因")
    operator: Optional[str] = Field(default=None, description="操作人")


class BulkOperationResponse(BaseModel):
    total: int = Field(description="总记录数")
    success: int = Field(description="成功数")
    failed: int = Field(description="失败数")
    failed_items: List[dict] = Field(default_factory=list, description="失败详情")
    message: str = Field(default="", description="操作消息")
