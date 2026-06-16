#!/usr/bin/env python3
"""检查所有路由文件中的导入问题"""
import ast
import os
from pathlib import Path
import importlib
import sys

sys.path.insert(0, ".")

routers_dir = Path("app/routers")
router_files = list(routers_dir.glob("*.py"))

# 已知正确的类名映射（错误名 -> 正确名）
class_mapping = {
    # status_record
    "ScanningStartRequest": "ScanStartRequest",
    "CompleteRequest": "CompletionRequest",
    "CancelRequest": "CancellationRequest",
    # alert
    "RiskType": "AlertType",
    "SeverityLevel": "AlertSeverity",
    # schedule
    "ShiftCreate": "ShiftAssignmentCreate",
    "ShiftUpdate": "ShiftAssignmentUpdate",
    "ShiftResponse": "ShiftAssignmentResponse",
    "ShiftSwapRequest": None,  # 不存在
    "WeeklyScheduleRequest": None,  # 不存在
    "SupportPlanResponse": "SupportPlanResponse",
    # notification
    "PreparationReminderRequest": None,  # 不存在
    # referral
    "ReferralAcceptRequest": None,
    "ReferralRejectRequest": None,
    "ReferralCompleteRequest": None,
    # user
    "ChangePasswordRequest": None,
    "UserListResponse": None,
    "UserLoginResponse": None,
    # hospital
    "HospitalListResponse": None,
    "HospitalCapacityUpdate": None,
    "HospitalStatusResponse": None,
    # equipment
    "EquipmentListResponse": None,
    "MaintenanceRecordCreate": None,
    # tracer
    "TracerListResponse": None,
    "TracerWasteRecord": None,
    "TracerUsageRecord": None,
    # patient
    "PatientListResponse": None,
    "PatientRiskAssessment": None,
    "HighRiskPatient": None,
    # reports
    "KPIDashboardResponse": None,
}

print("=" * 80)
print("检查路由文件中的导入问题")
print("=" * 80)

all_issues = []

for file in sorted(router_files):
    if file.name == "__init__.py":
        continue
    
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    
    issues = []
    
    for wrong_name, correct_name in class_mapping.items():
        if wrong_name in content:
            if correct_name is None:
                issues.append(f"❌ {wrong_name}: 类不存在，需要删除或替换")
            else:
                issues.append(f"⚠️  {wrong_name} -> {correct_name}")
    
    if issues:
        print(f"\n📄 {file.name}:")
        for issue in issues:
            print(f"   {issue}")
        all_issues.extend(issues)

print("\n" + "=" * 80)
print("检查完成")
if not all_issues:
    print("✅ 没有发现问题")
print("=" * 80)
