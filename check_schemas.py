#!/usr/bin/env python3
"""检查所有schemas文件中实际定义的类"""
import ast
import os
from pathlib import Path

schemas_dir = Path("app/schemas")
schema_files = list(schemas_dir.glob("*.py"))

print("=" * 80)
print("检查schemas文件中定义的类")
print("=" * 80)

all_classes = {}

for file in sorted(schema_files):
    if file.name == "__init__.py":
        continue
    
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        all_classes[file.name] = classes
        
        print(f"\n📄 {file.name}:")
        print(f"   类: {', '.join(classes)}")
    except SyntaxError as e:
        print(f"\n❌ {file.name}: 语法错误 - {e}")

print("\n" + "=" * 80)
print("检查当前 __init__.py 中的导入")
print("=" * 80)

init_file = schemas_dir / "__init__.py"
with open(init_file, "r", encoding="utf-8") as f:
    init_content = f.read()

# 提取所有导入
imports = []
for line in init_content.split("\n"):
    line = line.strip()
    if line.startswith("from app.schemas.") and "import" in line:
        module = line.split("from app.schemas.")[1].split(" import")[0]
        imports_str = line.split("import")[1].strip()
        imports_str = imports_str.rstrip(")").strip().lstrip("(").strip()
        imported_classes = [c.strip() for c in imports_str.split(",") if c.strip()]
        imports.append((module, imported_classes))
        
        print(f"\n📦 {module}.py:")
        print(f"   导入: {', '.join(imported_classes)}")
        
        # 检查哪些类不存在
        actual_classes = all_classes.get(f"{module}.py", [])
        missing = [c for c in imported_classes if c not in actual_classes]
        extra = [c for c in actual_classes if c not in imported_classes and not c.startswith("_")]
        if missing:
            print(f"   ❌ 不存在的类: {', '.join(missing)}")
        if extra:
            print(f"   ⚠️  未导入的类: {', '.join(extra)}")

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
