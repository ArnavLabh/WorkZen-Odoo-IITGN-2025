"""
Vercel entrypoint for WorkZen HRMS
"""
import sys
import os

try:
    from app import create_app
    app = create_app()
except Exception as e:
    print(f"Error creating app: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    raise

if __name__ == '__main__':
    app.run(debug=True)

