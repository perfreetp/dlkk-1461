#!/usr/bin/env python3
"""测试应用导入"""
import sys

print("Testing imports...")

try:
    from app.main import app
    print("SUCCESS: App created successfully")
    print(f"Routes count: {len(app.routes)}")
    print("\nRoutes:")
    for route in app.routes[:10]:
        print(f"  {route.path} - {route.methods}")
    if len(app.routes) > 10:
        print(f"  ... and {len(app.routes) - 10} more routes")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll imports successful!")
