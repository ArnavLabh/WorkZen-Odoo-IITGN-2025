from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import User, Attendance, Leave, Payroll
from app.utils.decorators import employee_or_above_required
from datetime import datetime, date, timedelta
from sqlalchemy import func

bp = Blueprint('dashboard', __name__)

@bp.route('/')
@login_required
@employee_or_above_required
def dashboard():
    user = current_user
    role = user.role
    
    # Role-based redirect
    if role == 'Employee':
        # Employees land on My Profile
        return redirect(url_for('settings.profile'))
    elif role == 'Admin':
        # Admin lands on Employee Directory
        return redirect(url_for('employees.directory'))
    elif role == 'HR Officer':
        # HR Officer lands on Employee Directory
        return redirect(url_for('employees.directory'))
    elif role == 'Payroll Officer':
        # Payroll Officer lands on Employee Directory
        return redirect(url_for('employees.directory'))
    else:
        return redirect(url_for('employees.directory'))

def admin_dashboard():
    # Statistics
    total_employees = User.query.filter(User.role == 'Employee').count()
    total_admins = User.query.filter(User.role == 'Admin').count()
    total_hr = User.query.filter(User.role == 'HR Officer').count()
    total_payroll = User.query.filter(User.role == 'Payroll Officer').count()
    
    # Today's attendance
    today = date.today()
    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status == 'Present'
    ).count()
    
    # Pending leave requests
    pending_leaves = Leave.query.filter(Leave.status == 'Pending').count()
    
    # Recent employees
    recent_employees = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Recent attendance
    recent_attendance = Attendance.query.order_by(Attendance.date.desc()).limit(10).all()
    
    return render_template('dashboard/admin_dashboard.html',
                         total_employees=total_employees,
                         total_admins=total_admins,
                         total_hr=total_hr,
                         total_payroll=total_payroll,
                         present_today=present_today,
                         pending_leaves=pending_leaves,
                         recent_employees=recent_employees,
                         recent_attendance=recent_attendance)

def employee_dashboard():
    user = current_user
    today = date.today()
    
    # Today's attendance
    today_attendance = Attendance.query.filter_by(
        user_id=user.id,
        date=today
    ).first()
    
    # My attendance summary (this month)
    month_start = date.today().replace(day=1)
    month_attendance = Attendance.query.filter(
        Attendance.user_id == user.id,
        Attendance.date >= month_start,
        Attendance.date <= today
    ).all()
    
    present_count = sum(1 for a in month_attendance if a.status == 'Present')
    absent_count = sum(1 for a in month_attendance if a.status == 'Absent')
    half_day_count = sum(1 for a in month_attendance if a.status == 'Half Day')
    
    # My leaves
    my_leaves = Leave.query.filter_by(user_id=user.id).order_by(Leave.created_at.desc()).limit(5).all()
    
    # My recent payslips
    my_payslips = Payroll.query.filter_by(user_id=user.id).order_by(Payroll.year.desc(), Payroll.month.desc()).limit(3).all()
    
    return render_template('dashboard/employee_dashboard.html',
                         today_attendance=today_attendance,
                         present_count=present_count,
                         absent_count=absent_count,
                         half_day_count=half_day_count,
                         my_leaves=my_leaves,
                         my_payslips=my_payslips)

def hr_dashboard():
    # Statistics
    total_employees = User.query.filter(User.role == 'Employee').count()
    
    # Today's attendance
    today = date.today()
    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status == 'Present'
    ).count()
    
    # Pending leave requests
    pending_leaves = Leave.query.filter(Leave.status == 'Pending').count()
    
    # Recent employees
    recent_employees = User.query.filter(User.role == 'Employee').order_by(User.created_at.desc()).limit(5).all()
    
    # Recent leave requests
    recent_leaves = Leave.query.order_by(Leave.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/hr_dashboard.html',
                         total_employees=total_employees,
                         present_today=present_today,
                         pending_leaves=pending_leaves,
                         recent_employees=recent_employees,
                         recent_leaves=recent_leaves)

def payroll_dashboard():
    # Statistics
    total_employees = User.query.filter(User.role == 'Employee').count()
    
    # This month's payroll
    current_month = date.today().month
    current_year = date.today().year
    payroll_this_month = Payroll.query.filter(
        Payroll.month == current_month,
        Payroll.year == current_year
    ).count()
    
    # Pending leave requests
    pending_leaves = Leave.query.filter(Leave.status == 'Pending').count()
    
    # Recent payrolls
    recent_payrolls = Payroll.query.order_by(Payroll.year.desc(), Payroll.month.desc()).limit(10).all()
    
    # Recent leave requests
    recent_leaves = Leave.query.order_by(Leave.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/payroll_dashboard.html',
                         total_employees=total_employees,
                         payroll_this_month=payroll_this_month,
                         pending_leaves=pending_leaves,
                         recent_payrolls=recent_payrolls,
                         recent_leaves=recent_leaves)

