#!/usr/bin/env python3
"""最终测试应用导入"""
import sys

output = []
output.append("Testing imports...")

try:
    from app.main import app
    output.append("SUCCESS: App created successfully")
    output.append(f"Routes count: {len(app.routes)}")
    output.append("\nFirst 20 routes:")
    for route in app.routes[:20]:
        methods = ",".join(sorted(route.methods)) if route.methods else "NONE"
        output.append(f"  {methods:20} {route.path}")
    output.append(f"\n... and {len(app.routes) - 20} more routes")
    output.append("\nAll imports successful!")
    result = 0
except Exception as e:
    output.append(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    output.append(traceback.format_exc())
    result = 1

with open("test_final_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("\n".join(output))
sys.exit(result)
