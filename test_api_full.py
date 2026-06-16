#!/usr/bin/env python3
"""完整的API接口测试脚本 - 测试5个核心模块"""
import sys
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.main import app
from app.database import SessionLocal
from app.models import Hospital, Patient, User, Equipment, Tracer
from app.utils.auth import create_access_token

client = TestClient(app)

db = SessionLocal()

test_hospital = db.query(Hospital).first()
test_patient = db.query(Patient).first()
test_user = db.query(User).filter(User.username == "admin").first()
test_equipment = db.query(Equipment).first()
test_tracer = db.query(Tracer).first()

db.close()

if not test_hospital or not test_patient or not test_user:
    print("❌ 数据库中缺少测试数据，请先运行 python scripts/init_data.py")
    sys.exit(1)

token = create_access_token(
    data={"sub": test_user.username, "user_id": test_user.id, "role": test_user.role}
)

auth_headers = {"Authorization": f"Bearer {token}"}

test_date = date.today() + timedelta(days=1)
test_date_str = test_date.isoformat()

print("=" * 80)
print("PET-CT 检查流程协同后端服务 - API 完整测试")
print("=" * 80)
print(f"测试院区: {test_hospital.name} (ID: {test_hospital.id})")
print(f"测试患者: {test_patient.name} (ID: {test_patient.id})")
print(f"测试用户: {test_user.username} (ID: {test_user.id}, 角色: {test_user.role})")
print(f"测试日期: {test_date_str}")
print("=" * 80)

results = []

def run_test(name, func):
    """运行测试并记录结果"""
    print(f"\n📋 测试: {name}")
    try:
        result = func()
        if result:
            print(f"   ✅ {result}")
            results.append((name, "PASS", result))
            return True
        else:
            print(f"   ⚠️  返回结果为空")
            results.append((name, "WARN", "返回结果为空"))
            return False
    except AssertionError as e:
        print(f"   ❌ 断言失败: {e}")
        results.append((name, "FAIL", str(e)))
        return False
    except Exception as e:
        print(f"   ❌ 异常: {type(e).__name__}: {e}")
        results.append((name, "ERROR", str(e)))
        return False

created_appointment_id = None
created_appointment_no = None

# ============ 模块1: 预约汇聚 ============
print("\n" + "=" * 80)
print("模块1: 预约汇聚")
print("=" * 80)

def test_1_create_appointment():
    """测试创建预约"""
    global created_appointment_id, created_appointment_no
    payload = {
        "hospital_id": test_hospital.id,
        "patient_id": test_patient.id,
        "appointment_date": test_date_str,
        "time_slot": "上午 09:00",
        "exam_purpose": "initial_staging",
        "urgency_level": "normal",
        "is_inpatient": False,
        "needs_anesthesia": False,
        "clinical_diagnosis": "肺癌术后复查",
        "referring_department": "胸外科",
        "referring_doctor": "张医生",
        "tracer_type": "fdg"
    }
    response = client.post(
        "/api/v1/appointments",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200, f"状态码错误: {response.status_code}"
    data = response.json()
    assert data["code"] == 200, f"返回码错误: {data.get('code')}"
    assert "data" in data, "缺少data字段"
    assert "id" in data["data"], "缺少id字段"
    assert "appointment_no" in data["data"], "缺少appointment_no字段"
    created_appointment_id = data["data"]["id"]
    created_appointment_no = data["data"]["appointment_no"]
    return f"创建成功: {created_appointment_no}"

def test_2_get_appointment_detail():
    """测试获取预约详情"""
    assert created_appointment_id, "没有创建的预约ID"
    response = client.get(
        f"/api/v1/appointments/{created_appointment_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["id"] == created_appointment_id
    assert data["data"]["appointment_no"] == created_appointment_no
    return f"查询成功: {data['data']['appointment_no']}"

def test_3_list_appointments():
    """测试获取预约列表"""
    response = client.get(
        "/api/v1/appointments",
        params={"hospital_id": test_hospital.id, "page": 1, "page_size": 10},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    assert "items" in data["data"]
    assert isinstance(data["data"]["items"], list)
    return f"列表查询成功: {len(data['data']['items'])} 条记录"

def test_4_categorize_appointment():
    """测试预约归类"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {"appointment_ids": [created_appointment_id]}
    response = client.post(
        "/api/v1/appointments/categorize",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    assert isinstance(data["data"], list)
    if data["data"]:
        item = data["data"][0]
        assert "workflow_category" in item, "缺少workflow_category字段"
        assert "priority_score" in item, "缺少priority_score字段"
        return f"归类成功: 类别={item['workflow_category']}, 优先级={item['priority_score']}"
    return "归类完成"

def test_5_update_appointment():
    """测试更新预约"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {
        "clinical_diagnosis": "肺癌术后复查 - 已更新",
        "exam_notes": "患者有轻微咳嗽"
    }
    response = client.put(
        f"/api/v1/appointments/{created_appointment_id}",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["clinical_diagnosis"] == "肺癌术后复查 - 已更新"
    return "更新成功"

def test_6_daily_queue():
    """测试每日队列查询"""
    response = client.get(
        f"/api/v1/appointments/queue/{test_hospital.id}/{test_date_str}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    if isinstance(data["data"], dict):
        assert "queue" in data["data"], "缺少queue字段"
        assert isinstance(data["data"]["queue"], list)
        return f"队列查询成功: {len(data['data'].get('queue', []))} 条记录"
    return f"队列查询成功: {len(data['data'])} 条记录"

run_test("1.1 创建预约", test_1_create_appointment)
run_test("1.2 获取预约详情", test_2_get_appointment_detail)
run_test("1.3 获取预约列表", test_3_list_appointments)
run_test("1.4 预约归类", test_4_categorize_appointment)
run_test("1.5 更新预约", test_5_update_appointment)
run_test("1.6 每日队列查询", test_6_daily_queue)

# ============ 模块2: 资源调度 ============
print("\n" + "=" * 80)
print("模块2: 资源调度")
print("=" * 80)

def test_7_capacity_query():
    """测试容量查询"""
    response = client.get(
        f"/api/v1/scheduling/capacity/{test_hospital.id}",
        params={"date": test_date_str},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["total_capacity", "used_capacity", "available_capacity"]:
            assert key in d, f"缺少{key}字段"
        return f"容量查询成功: 总{d.get('total_capacity')}/已用{d.get('used_capacity')}/可用{d.get('available_capacity')}"
    return "容量查询成功"

def test_8_available_slots():
    """测试可用时段查询"""
    response = client.get(
        f"/api/v1/scheduling/slots/{test_hospital.id}/{test_date_str}",
        params={
            "tracer_type": "fdg",
            "needs_anesthesia": False
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    assert isinstance(data["data"], list)
    return f"可用时段查询成功: {len(data['data'])} 个时段"

def test_9_allocate_resource():
    """测试号源分配"""
    assert created_appointment_id, "没有创建的预约ID"
    response = client.post(
        f"/api/v1/scheduling/allocate/{created_appointment_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["equipment_id", "time_slot", "queue_number", "tracer_window"]:
            assert key in d, f"缺少{key}字段"
        return (f"分配成功: 设备={d.get('equipment_id')}, "
                f"时段={d.get('time_slot')}, 队列号={d.get('queue_number')}, "
                f"示踪剂窗口={d.get('tracer_window')}")
    return "分配成功"

def test_10_batch_allocate():
    """测试批量分配"""
    response = client.post(
        f"/api/v1/scheduling/allocate/batch?hospital_id={test_hospital.id}&target_date={test_date_str}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["total", "success", "failed"]:
            assert key in d, f"缺少{key}字段"
        return f"批量分配完成: 总{d.get('total')}/成功{d.get('success')}/失败{d.get('failed')}"
    return "批量分配完成"

def test_11_optimize_queue():
    """测试队列优化"""
    response = client.post(
        f"/api/v1/scheduling/queue/optimize/{test_hospital.id}/{test_date_str}",
        params={"strategy": "priority_first"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        return f"队列优化完成: 调整{d.get('adjusted_count', 0)} 条记录"
    return "队列优化完成"

run_test("2.1 容量查询", test_7_capacity_query)
run_test("2.2 可用时段查询", test_8_available_slots)
run_test("2.3 号源分配", test_9_allocate_resource)
run_test("2.4 批量分配", test_10_batch_allocate)
run_test("2.5 队列优化", test_11_optimize_queue)

# ============ 模块3: 状态回传 ============
print("\n" + "=" * 80)
print("模块3: 状态回传")
print("=" * 80)

def test_12_checkin():
    """测试签到"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {
        "appointment_id": created_appointment_id,
        "checkin_time": datetime.now().isoformat(),
        "weight_kg": 70,
        "blood_glucose": 5.6
    }
    response = client.post(
        "/api/v1/status/checkin",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "status" in d, "缺少status字段"
        assert "record_id" in d, "缺少record_id字段"
        assert "checkin_time" in d, "缺少checkin_time字段"
        return f"签到成功: 状态={d['status']}, 记录ID={d['record_id']}"
    return "签到成功"

def test_13_injection():
    """测试注射"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {
        "appointment_id": created_appointment_id,
        "tracer_id": test_tracer.id if test_tracer else 1,
        "tracer_name": "FDG",
        "dose_mbq": 370.0,
        "injection_time": datetime.now().isoformat(),
        "injection_site": "左肘静脉",
        "operator": "李技师"
    }
    response = client.post(
        "/api/v1/status/injection",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "status" in d, "缺少status字段"
        assert "record_id" in d, "缺少record_id字段"
        assert "injection_time" in d, "缺少injection_time字段"
        return f"注射成功: 状态={d['status']}, 记录ID={d['record_id']}"
    return "注射成功"

def test_14_scanning_start():
    """测试入机（开始扫描）"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {
        "appointment_id": created_appointment_id,
        "equipment_code": test_equipment.code if test_equipment else "PET-CT-01",
        "scan_start_time": datetime.now().isoformat(),
        "scan_protocol": "全身常规",
        "recorded_by": "王技师"
    }
    response = client.post(
        "/api/v1/status/scan-start",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "status" in d, "缺少status字段"
        assert "record_id" in d, "缺少record_id字段"
        assert "scan_start_time" in d, "缺少scan_start_time字段"
        return f"入机成功: 状态={d['status']}, 记录ID={d['record_id']}"
    return "入机成功"

def test_15_complete():
    """测试完成"""
    assert created_appointment_id, "没有创建的预约ID"
    payload = {
        "appointment_id": created_appointment_id,
        "scan_end_time": datetime.now().isoformat(),
        "scan_duration_seconds": 1500,
        "images_acquired": 1200,
        "image_quality": "good",
        "notes": "图像质量良好",
        "recorded_by": "李技师"
    }
    response = client.post(
        "/api/v1/status/completion",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "status" in d, "缺少status字段"
        assert "record_id" in d, "缺少record_id字段"
        assert "complete_time" in d, "缺少complete_time字段"
        return f"完成成功: 状态={d['status']}, 记录ID={d['record_id']}"
    return "完成成功"

def test_16_cancel():
    """测试取消（创建一个新预约然后取消）"""
    payload = {
        "hospital_id": test_hospital.id,
        "patient_id": test_patient.id,
        "appointment_date": test_date_str,
        "time_slot": "上午 10:00",
        "exam_purpose": "initial_staging",
        "urgency_level": "normal",
        "is_inpatient": False,
        "needs_anesthesia": False,
        "clinical_diagnosis": "测试取消",
        "tracer_type": "fdg"
    }
    create_resp = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
    cancel_id = create_resp.json()["data"]["id"]

    payload = {
        "appointment_id": cancel_id,
        "cancellation_reason": "患者放弃检查",
        "cancelled_by": test_user.username,
        "reschedule_requested": False
    }
    response = client.post(
        "/api/v1/status/cancellation",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "status" in d, "缺少status字段"
        assert "record_id" in d, "缺少record_id字段"
        assert "cancel_time" in d, "缺少cancel_time字段"
        return f"取消成功: 状态={d['status']}, 记录ID={d['record_id']}"
    return "取消成功"

run_test("3.1 签到", test_12_checkin)
run_test("3.2 注射", test_13_injection)
run_test("3.3 入机（开始扫描）", test_14_scanning_start)
run_test("3.4 完成", test_15_complete)
run_test("3.5 取消", test_16_cancel)

# ============ 模块4: 异常重排 ============
print("\n" + "=" * 80)
print("模块4: 异常重排")
print("=" * 80)

# 先创建几个待重排的预约
test_appointments_for_reschedule = []
for i in range(3):
    payload = {
        "hospital_id": test_hospital.id,
        "patient_id": test_patient.id,
        "appointment_date": test_date_str,
        "time_slot": f"下午 {14 + i}:00",
        "exam_purpose": "initial_staging",
        "urgency_level": "normal",
        "is_inpatient": False,
        "needs_anesthesia": False,
        "clinical_diagnosis": f"重排测试{i+1}",
        "tracer_type": "fdg"
    }
    resp = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
    if resp.status_code == 200:
        test_appointments_for_reschedule.append(resp.json()["data"]["id"])

new_date = test_date + timedelta(days=1)
new_date_str = new_date.isoformat()

def test_17_equipment_downtime():
    """测试设备停机重排"""
    if not test_appointments_for_reschedule:
        return "无测试预约，跳过"
    payload = {
        "equipment_id": test_equipment.id if test_equipment else 1,
        "start_time": datetime.now().isoformat(),
        "end_time": (datetime.now() + timedelta(hours=4)).isoformat(),
        "reason": "设备例行维护",
        "affected_appointment_ids": test_appointments_for_reschedule,
        "reschedule_strategy": "priority_first",
        "new_date": new_date_str
    }
    response = client.post(
        "/api/v1/reschedule/equipment-downtime",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["total", "success", "failed", "skipped"]:
            assert key in d, f"缺少{key}字段"
        if "success_details" in d and d["success_details"]:
            detail = d["success_details"][0]
            assert "new_date" in detail, "成功明细缺少new_date"
            assert "new_time_slot" in detail, "成功明细缺少new_time_slot"
            assert "notification_sent" in detail, "成功明细缺少notification_sent"
        return (f"设备停机重排: 总{d.get('total')}/成功{d.get('success')}/"
                f"失败{d.get('failed')}/跳过{d.get('skipped')}")
    return "设备停机重排完成"

def test_18_drug_delay():
    """测试药物延迟重排"""
    new_appointments = []
    for i in range(2):
        payload = {
            "hospital_id": test_hospital.id,
            "patient_id": test_patient.id,
            "appointment_date": test_date_str,
            "time_slot": f"上午 {11 + i}:00",
            "exam_purpose": "initial_staging",
            "urgency_level": "normal",
            "is_inpatient": False,
            "needs_anesthesia": False,
            "clinical_diagnosis": f"药物延迟测试{i+1}",
            "tracer_type": "fdg"
        }
        resp = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
        if resp.status_code == 200:
            new_appointments.append(resp.json()["data"]["id"])
    
    if not new_appointments:
        return "无测试预约，跳过"
    
    payload = {
        "tracer_id": test_tracer.id if test_tracer else 1,
        "new_arrival_time": (datetime.now() + timedelta(hours=3)).isoformat(),
        "affected_hospital_ids": [test_hospital.id],
        "affected_appointment_ids": new_appointments,
        "affected_date": test_date_str,
        "reschedule_strategy": "earliest_first",
        "notify_patients": True
    }
    response = client.post(
        "/api/v1/reschedule/drug-delay",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["total", "success", "failed", "skipped"]:
            assert key in d, f"缺少{key}字段"
        return (f"药物延迟重排: 总{d.get('total')}/成功{d.get('success')}/"
                f"失败{d.get('failed')}/跳过{d.get('skipped')}")
    return "药物延迟重排完成"

def test_19_emergency_plus():
    """测试突发加号"""
    payload = {
        "hospital_id": test_hospital.id,
        "patient_id": test_patient.id,
        "target_date": test_date_str,
        "exam_purpose": "initial_staging",
        "urgency_level": "urgent",
        "is_inpatient": False,
        "needs_anesthesia": False,
        "clinical_diagnosis": "突发急诊测试",
        "plus_sign_reason": "疑似急性肺栓塞"
    }
    response = client.post(
        "/api/v1/reschedule/emergency-plus",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "appointment_id" in d, "缺少appointment_id字段"
        assert "queue_position" in d, "缺少queue_position字段"
        assert "affected_count" in d, "缺少affected_count字段"
        return f"突发加号成功: 位置={d.get('queue_position')}, 影响{d.get('affected_count')}人"
    return "突发加号成功"

def test_20_batch_reschedule():
    """测试批量重排"""
    new_appointments = []
    for i in range(2):
        payload = {
            "hospital_id": test_hospital.id,
            "patient_id": test_patient.id,
            "appointment_date": test_date_str,
            "time_slot": f"下午 {16 + i}:00",
            "exam_purpose": "initial_staging",
            "urgency_level": "normal",
            "is_inpatient": False,
            "needs_anesthesia": False,
            "clinical_diagnosis": f"批量重排测试{i+1}",
            "tracer_type": "fdg"
        }
        resp = client.post("/api/v1/appointments", json=payload, headers=auth_headers)
        if resp.status_code == 200:
            new_appointments.append(resp.json()["data"]["id"])
    
    if not new_appointments:
        return "无测试预约，跳过"
    
    payload = {
        "appointment_ids": new_appointments,
        "target_date": new_date_str,
        "strategy": "maintain_order",
        "reason": "other",
        "reason_detail": "批量调整",
        "notify_patient": False
    }
    response = client.post(
        "/api/v1/reschedule/batch",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["total", "success", "failed", "skipped"]:
            assert key in d, f"缺少{key}字段"
        if "success_details" in d and d["success_details"]:
            detail = d["success_details"][0]
            assert "new_date" in detail, "成功明细缺少new_date"
            assert "new_time_slot" in detail, "成功明细缺少new_time_slot"
            assert "notification_sent" in detail, "成功明细缺少notification_sent"
        return (f"批量重排: 总{d.get('total')}/成功{d.get('success')}/"
                f"失败{d.get('failed')}/跳过{d.get('skipped')}")
    return "批量重排完成"

run_test("4.1 设备停机重排", test_17_equipment_downtime)
run_test("4.2 药物延迟重排", test_18_drug_delay)
run_test("4.3 突发加号", test_19_emergency_plus)
run_test("4.4 批量重排", test_20_batch_reschedule)

# ============ 模块5: 运营报表 ============
print("\n" + "=" * 80)
print("模块5: 运营报表")
print("=" * 80)

report_start_date = (date.today() - timedelta(days=7)).isoformat()
report_end_date = date.today().isoformat()

def test_21_turnover_efficiency():
    """测试周转效率报表"""
    response = client.get(
        "/api/v1/reports/turnover-efficiency",
        params={
            "hospital_id": test_hospital.id,
            "start_date": report_start_date,
            "end_date": report_end_date,
            "include_details": True
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "summary" in d, "缺少summary字段"
        assert "items" in d, "缺少items字段"
        assert isinstance(d["items"], list)
        summary = d["summary"]
        for key in ["total_appointments", "completion_rate", "avg_turnover_minutes"]:
            assert key in summary, f"汇总缺少{key}字段"
        return (f"周转效率报表: {len(d['items'])} 条明细, "
                f"完成率={summary.get('completion_rate', 0):.1%}")
    return "周转效率报表生成成功"

def test_22_drug_utilization():
    """测试药物利用率报表"""
    response = client.get(
        "/api/v1/reports/drug-utilization",
        params={
            "hospital_id": test_hospital.id,
            "start_date": report_start_date,
            "end_date": report_end_date,
            "include_details": True
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "summary" in d, "缺少summary字段"
        assert "items" in d, "缺少items字段"
        assert isinstance(d["items"], list)
        summary = d["summary"]
        for key in ["total_used_mbq", "utilization_rate", "waste_rate"]:
            assert key in summary, f"汇总缺少{key}字段"
        return (f"药物利用率报表: {len(d['items'])} 条明细, "
                f"利用率={summary.get('utilization_rate', 0):.1%}")
    return "药物利用率报表生成成功"

def test_23_referral_completion():
    """测试转诊完成率报表"""
    response = client.get(
        "/api/v1/reports/referral-completion",
        params={
            "hospital_id": test_hospital.id,
            "start_date": report_start_date,
            "end_date": report_end_date,
            "include_details": True
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "summary" in d, "缺少summary字段"
        assert "items" in d, "缺少items字段"
        assert isinstance(d["items"], list)
        summary = d["summary"]
        for key in ["total_referrals", "completion_rate", "acceptance_rate"]:
            assert key in summary, f"汇总缺少{key}字段"
        return (f"转诊完成率报表: {len(d['items'])} 条明细, "
                f"完成率={summary.get('completion_rate', 0):.1%}")
    return "转诊完成率报表生成成功"

def test_24_daily_operation():
    """测试每日运营报表"""
    response = client.get(
        "/api/v1/reports/daily-operation",
        params={
            "hospital_id": test_hospital.id,
            "start_date": report_start_date,
            "end_date": report_end_date,
            "include_details": True
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        assert "summary" in d, "缺少summary字段"
        assert "items" in d, "缺少items字段"
        assert isinstance(d["items"], list)
        return f"每日运营报表: {len(d['items'])} 条明细"
    return "每日运营报表生成成功"

def test_25_kpi_dashboard():
    """测试KPI仪表盘"""
    response = client.get(
        "/api/v1/reports/kpi-dashboard",
        params={
            "period": "week",
            "hospital_id": test_hospital.id
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    d = data["data"]
    if isinstance(d, dict):
        for key in ["completion_rate", "no_show_rate", "avg_turnover_minutes"]:
            assert key in d, f"缺少{key}字段"
        return (f"KPI仪表盘: 完成率={d.get('completion_rate', 0):.1%}, "
                f"爽约率={d.get('no_show_rate', 0):.1%}")
    return "KPI仪表盘查询成功"

run_test("5.1 周转效率报表", test_21_turnover_efficiency)
run_test("5.2 药物利用率报表", test_22_drug_utilization)
run_test("5.3 转诊完成率报表", test_23_referral_completion)
run_test("5.4 每日运营报表", test_24_daily_operation)
run_test("5.5 KPI仪表盘", test_25_kpi_dashboard)

# ============ 测试结果汇总 ============
print("\n" + "=" * 80)
print("测试结果汇总")
print("=" * 80)

pass_count = sum(1 for _, status, _ in results if status == "PASS")
warn_count = sum(1 for _, status, _ in results if status == "WARN")
fail_count = sum(1 for _, status, _ in results if status == "FAIL")
error_count = sum(1 for _, status, _ in results if status == "ERROR")

print(f"\n总测试数: {len(results)}")
print(f"✅ 通过: {pass_count}")
print(f"⚠️  警告: {warn_count}")
print(f"❌ 失败: {fail_count}")
print(f"💥 异常: {error_count}")

if fail_count + error_count > 0:
    print("\n❌ 失败/异常的测试:")
    for name, status, detail in results:
        if status in ["FAIL", "ERROR"]:
            print(f"   - {name}: {detail}")

print("\n" + "=" * 80)
if pass_count == len(results):
    print("🎉 所有测试通过！")
else:
    print(f"⚠️  部分测试未通过，请检查")
print("=" * 80)
