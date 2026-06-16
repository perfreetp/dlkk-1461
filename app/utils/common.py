import math
import uuid
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional, Dict, Any
from math import radians, sin, cos, sqrt, atan2


def generate_appointment_no(hospital_code: str = "H001") -> str:
    """生成预约编号: 前缀 + 日期 + 6位序号"""
    today = datetime.now().strftime("%Y%m%d")
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"APT{hospital_code}{today}{random_suffix}"


def generate_referral_no(hospital_code: str = "H001") -> str:
    """生成转诊编号"""
    today = datetime.now().strftime("%Y%m%d")
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"REF{hospital_code}{today}{random_suffix}"


def calculate_distance(
    lat1: Optional[float], lon1: Optional[float],
    lat2: Optional[float], lon2: Optional[float]
) -> float:
    """使用Haversine公式计算两点之间的距离(公里)"""
    if None in (lat1, lon1, lat2, lon2):
        return 999.0

    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return round(R * c, 2)


def calculate_priority_score(
    urgency_level: str = "normal",
    is_inpatient: bool = False,
    needs_anesthesia: bool = False,
    is_referral: bool = False,
    is_plus_sign: bool = False,
    exam_purpose: str = "other",
    consecutive_no_show: int = 0
) -> int:
    """计算优先级评分 0-100，分数越高优先级越高"""
    score = 50

    urgency_weights = {
        "emergency": 40,
        "urgent": 25,
        "normal": 0,
        "elective": -10
    }
    score += urgency_weights.get(urgency_level, 0)

    if is_inpatient:
        score += 10
    if needs_anesthesia:
        score += 5
    if is_referral:
        score += 5
    if is_plus_sign:
        score += 15

    purpose_weights = {
        "initial_staging": 10,
        "restaging": 8,
        "therapy_response": 5,
        "surveillance": 0,
        "other": 0
    }
    score += purpose_weights.get(exam_purpose, 0)

    if consecutive_no_show >= 3:
        score -= 20
    elif consecutive_no_show >= 2:
        score -= 10

    return max(0, min(100, score))


def categorize_workflow(exam_purpose: str, clinical_diagnosis: str = "") -> str:
    """分类工作流"""
    purpose_category = {
        "initial_staging": "肿瘤评估",
        "restaging": "肿瘤评估",
        "therapy_response": "肿瘤评估",
        "surveillance": "肿瘤评估"
    }

    diagnosis = clinical_diagnosis.lower() if clinical_diagnosis else ""
    if any(keyword in diagnosis for keyword in ["脑", "神经", "痴呆", "癫痫", "parkinson"]):
        return "神经"
    if any(keyword in diagnosis for keyword in ["心", "心肌", "冠脉", "myocardial"]):
        return "心血管"
    if any(keyword in diagnosis for keyword in ["骨", "转移"]):
        return "骨转移评估"

    return purpose_category.get(exam_purpose, "其他")


def get_preparation_notes(
    tracer_type: str = "fdg",
    needs_anesthesia: bool = False,
    is_inpatient: bool = False,
    diabetes_type: str = "",
    fasting_hours: int = 6
) -> str:
    """生成检查准备事项"""
    notes = []

    notes.append(f"1. 检查前需禁食 {fasting_hours} 小时，可饮用白开水")
    notes.append("2. 检查前24小时避免剧烈运动")
    notes.append("3. 检查前请停用含糖药物及饮品")

    if tracer_type == "fdg":
        notes.append("4. 检查前4-6小时控制血糖在正常范围")
        if diabetes_type:
            notes.append(f"5. 糖尿病患者({diabetes_type})请携带降糖药物，检查当日请咨询医生是否停药")

    if needs_anesthesia:
        notes.append("6. 麻醉患者需额外禁食8小时，禁饮4小时")
        notes.append("7. 请携带麻醉评估相关资料")
        notes.append("8. 必须有家属陪同")

    if not is_inpatient:
        notes.append("9. 请携带既往检查资料（CT、MRI、病理报告等）")
        notes.append("10. 建议有家属陪同")

    notes.append("11. 检查后需多饮水，促进示踪剂排泄")
    notes.append("12. 检查后24小时内避免接触孕妇及儿童")

    return "\n".join(notes)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法，避免除零错误"""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator


def format_datetime(dt: Optional[datetime]) -> str:
    """格式化日期时间"""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_date_range(
    start_date: Optional[date],
    end_date: Optional[date]
) -> Tuple[date, date]:
    """解析日期范围，提供默认值"""
    today = date.today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    return start_date, end_date


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def estimate_travel_time(distance_km: float, traffic_condition: str = "normal") -> int:
    """估算行程时间(分钟)"""
    speed_map = {
        "smooth": 60,
        "normal": 40,
        "congested": 25,
        "heavy": 15
    }
    speed = speed_map.get(traffic_condition, 40)
    return max(10, int(math.ceil(distance_km / speed * 60)))
