#!/usr/bin/env python3
"""测试应用导入"""
import sys

print("Testing imports...")
sys.stdout.flush()

try:
    from app.main import app
    print("SUCCESS: App created successfully")
    print(f"Routes count: {len(app.routes)}")
    print("\nFirst 10 routes:")
    for route in app.routes[:10]:
        methods = ",".join(sorted(route.methods)) if route.methods else "NONE"
        print(f"  {methods:20} {route.path}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll imports successful!")
