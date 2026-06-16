from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class ReportType(str, Enum):
    TURNOVER_EFFICIENCY = "turnover_efficiency"
    DRUG_UTILIZATION = "drug_utilization"
    REFERRAL_COMPLETION = "referral_completion"
    DAILY_OPERATION = "daily_operation"
    RISK_ANALYSIS = "risk_analysis"


class ReportFormat(str, Enum):
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"


class ReportQueryParams(BaseModel):
    hospital_id: Optional[int] = Field(default=None, description="院区ID")
    report_type: ReportType = Field(..., description="报表类型")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    granularity: str = Field(default="daily", max_length=20, description="时间粒度: daily/weekly/monthly")
    include_details: bool = Field(default=False, description="是否包含明细")
    compare_with_previous_period: bool = Field(default=False, description="是否同比环比")


class ReportExportRequest(BaseModel):
    hospital_ids: Optional[List[int]] = Field(default=None, description="院区ID列表")
    report_type: ReportType = Field(..., description="报表类型")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    format: ReportFormat = Field(default=ReportFormat.EXCEL, description="导出格式")
    include_charts: bool = Field(default=True, description="是否包含图表")
    language: str = Field(default="zh-CN", max_length=10, description="语言")


class TurnoverEfficiencyItem(BaseModel):
    hospital_id: int
    hospital_name: str
    stat_date: date
    total_appointments: int = Field(description="总预约数")
    completed_count: int = Field(description="完成数")
    cancelled_count: int = Field(description="取消数")
    no_show_count: int = Field(description="爽约数")
    completion_rate: float = Field(description="完成率")
    no_show_rate: float = Field(description="爽约率")
    avg_wait_time_minutes: float = Field(description="平均等待时间(分钟)")
    avg_scan_time_minutes: float = Field(description="平均扫描时间(分钟)")
    avg_turnover_minutes: float = Field(description="平均周转时间(分钟)")
    equipment_utilization_rate: float = Field(description="设备利用率")
    daily_capacity_utilization: float = Field(description="日容量利用率")
    peak_hour: Optional[str] = Field(default=None, description="高峰时段")
    peak_count: int = Field(default=0, description="高峰时段检查数")


class TurnoverEfficiencyReport(BaseModel):
    report_type: str = "turnover_efficiency"
    start_date: date
    end_date: date
    generated_at: datetime
    summary: Dict[str, Any] = Field(description="汇总数据")
    items: List[TurnoverEfficiencyItem] = Field(description="明细数据")
    trends: Optional[Dict[str, Any]] = Field(default=None, description="趋势数据")
    hospital_comparison: Optional[Dict[str, Any]] = Field(default=None, description="院区间对比")


class DrugUtilizationItem(BaseModel):
    hospital_id: int
    hospital_name: str
    stat_date: date
    tracer_id: int
    tracer_name: str
    total_received_mbq: float = Field(description="总到货活度(MBq)")
    total_used_mbq: float = Field(description="总使用活度(MBq)")
    total_wasted_mbq: float = Field(description="总浪费活度(MBq)")
    utilization_rate: float = Field(description="利用率")
    waste_rate: float = Field(description="浪费率")
    waste_rate_noshow: float = Field(description="爽约导致浪费率")
    waste_rate_expired: float = Field(description="过期浪费率")
    average_dose_mbq: float = Field(description="平均剂量(MBq)")
    patient_count: int = Field(description="使用患者数")
    batch_count: int = Field(description="使用批次")
    cost_estimate: float = Field(description="估算成本")
    waste_cost: float = Field(description="浪费成本")


class DrugUtilizationReport(BaseModel):
    report_type: str = "drug_utilization"
    start_date: date
    end_date: date
    generated_at: datetime
    summary: Dict[str, Any] = Field(description="汇总数据")
    items: List[DrugUtilizationItem] = Field(description="明细数据")
    trends: Optional[Dict[str, Any]] = Field(default=None, description="趋势数据")
    tracer_breakdown: Optional[Dict[str, Any]] = Field(default=None, description="药物分类统计")
    waste_analysis: Optional[Dict[str, Any]] = Field(default=None, description="浪费原因分析")


class ReferralCompletionItem(BaseModel):
    hospital_id: int
    hospital_name: str
    stat_date: date
    total_referrals_out: int = Field(description="转出总数")
    total_referrals_in: int = Field(description="转入总数")
    completed_referrals: int = Field(description="已完成数")
    accepted_referrals: int = Field(description="已接受数")
    declined_referrals: int = Field(description="已拒绝数")
    pending_referrals: int = Field(description="待处理数")
    completion_rate: float = Field(description="完成率")
    acceptance_rate: float = Field(description="接受率")
    avg_response_time_minutes: float = Field(description="平均响应时间(分钟)")
    avg_travel_time_minutes: float = Field(description="平均行程时间(分钟)")
    auto_assign_count: int = Field(description="系统自动分配数")
    auto_assign_acceptance_rate: float = Field(description="自动分配接受率")
    top_reasons: List[Dict[str, Any]] = Field(default_factory=list, description="主要转诊原因")


class ReferralCompletionReport(BaseModel):
    report_type: str = "referral_completion"
    start_date: date
    end_date: date
    generated_at: datetime
    summary: Dict[str, Any] = Field(description="汇总数据")
    items: List[ReferralCompletionItem] = Field(description="明细数据")
    trends: Optional[Dict[str, Any]] = Field(default=None, description="趋势数据")
    hospital_network: Optional[Dict[str, Any]] = Field(default=None, description="转诊网络分析")
    reason_analysis: Optional[Dict[str, Any]] = Field(default=None, description="原因分析")


class DailyOperationItem(BaseModel):
    hospital_id: int
    hospital_name: str
    stat_date: date
    morning_capacity: int
    afternoon_capacity: int
    total_capacity: int
    morning_booked: int
    afternoon_booked: int
    total_booked: int
    morning_utilization: float
    afternoon_utilization: float
    total_utilization: float
    emergency_count: int
    urgent_count: int
    inpatient_count: int
    anesthesia_count: int
    plus_sign_count: int
    avg_queue_time: float
    equipment_available_hours: float
    equipment_downtime_minutes: int
    alerts_count: int
    alerts_resolved_count: int


class DailyOperationReport(BaseModel):
    report_type: str = "daily_operation"
    start_date: date
    end_date: date
    generated_at: datetime
    summary: Dict[str, Any] = Field(description="汇总数据")
    items: List[DailyOperationItem] = Field(description="明细数据")
    kpi_summary: Dict[str, Any] = Field(description="KPI摘要")
    alerts_summary: Optional[Dict[str, Any]] = Field(default=None, description="预警摘要")
