"""
Vercel entrypoint for WorkZen HRMS
"""
from app import create_app

# Expose Flask app for Vercel
app = create_app()
