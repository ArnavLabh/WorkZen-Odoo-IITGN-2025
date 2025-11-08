"""
Script to create database tables programmatically.
Run this once to initialize your database schema.
"""
from app import create_app, db
from app.models import User, Attendance, Leave, Payroll, PayrollSettings, SalaryComponent

app = create_app()

with app.app_context():
    # Create all tables
    db.create_all()
    print("✅ Database tables created successfully!")
    print("\nTables created:")
    print("- users")
    print("- attendances")
    print("- leaves")
    print("- payroll_settings")
    print("- salary_components")
    print("- payrolls")

