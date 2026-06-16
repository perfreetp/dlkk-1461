#!/usr/bin/env python3
"""测试应用导入"""
import sys
import traceback

with open("test_output.txt", "w", encoding="utf-8") as f:
    f.write("Testing imports...\n")
    
    try:
        from app.main import app
        f.write("SUCCESS: App created successfully\n")
        f.write(f"Routes count: {len(app.routes)}\n")
        f.write("\nRoutes:\n")
        for route in app.routes[:20]:
            f.write(f"  {route.path} - {route.methods}\n")
        if len(app.routes) > 20:
            f.write(f"  ... and {len(app.routes) - 20} more routes\n")
        f.write("\nAll imports successful!\n")
    except Exception as e:
        f.write(f"ERROR: {e}\n")
        f.write(traceback.format_exc())
        sys.exit(1)

print("Test completed. Check test_output.txt for details.")
