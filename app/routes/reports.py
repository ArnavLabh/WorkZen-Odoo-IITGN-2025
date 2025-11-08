from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, Leave, Payroll, User
from app.utils.decorators import employee_or_above_required, payroll_required
from datetime import datetime, date, timedelta
from sqlalchemy import func

bp = Blueprint('reports', __name__)

@bp.route('/')
@login_required
def generate():
    # Employees cannot access reports
    if current_user.role == 'Employee':
        flash('You do not have permission to access reports', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    return render_template('reports/generate.html')

@bp.route('/attendance')
@login_required
def attendance():
    # Employees cannot access reports - they can only view their own data via attendance list
    if current_user.role == 'Employee':
        flash('You do not have permission to access reports', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_id = request.args.get('user_id', '')
    
    query = Attendance.query
    
    # Filter by user
    if current_user.role == 'Employee':
        query = query.filter_by(user_id=current_user.id)
    elif user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by date range
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= end)
        except ValueError:
            pass
    
    attendances = query.order_by(Attendance.date.desc()).all()
    
    # Calculate statistics
    total_days = len(attendances)
    present_days = sum(1 for a in attendances if a.status == 'Present')
    absent_days = sum(1 for a in attendances if a.status == 'Absent')
    half_days = sum(1 for a in attendances if a.status == 'Half Day')
    total_hours = sum(a.working_hours for a in attendances)
    
    # Get users for filter
    users = []
    if current_user.role in ['Admin', 'HR Officer', 'Payroll Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/attendance_report.html',
                         attendances=attendances,
                         start_date=start_date,
                         end_date=end_date,
                         user_id=user_id,
                         users=users,
                         total_days=total_days,
                         present_days=present_days,
                         absent_days=absent_days,
                         half_days=half_days,
                         total_hours=total_hours)

@bp.route('/leave')
@login_required
def leave():
    # Employees cannot access reports - they can only view their own leaves via leave list
    if current_user.role == 'Employee':
        flash('You do not have permission to access reports', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_id = request.args.get('user_id', '')
    status_filter = request.args.get('status', '')
    
    query = Leave.query
    
    # Filter by user
    if current_user.role == 'Employee':
        query = query.filter_by(user_id=current_user.id)
    elif user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by status
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Filter by date range
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Leave.start_date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Leave.end_date <= end)
        except ValueError:
            pass
    
    leaves = query.order_by(Leave.created_at.desc()).all()
    
    # Calculate statistics
    total_leaves = len(leaves)
    approved_leaves = sum(1 for l in leaves if l.status == 'Approved')
    rejected_leaves = sum(1 for l in leaves if l.status == 'Rejected')
    pending_leaves = sum(1 for l in leaves if l.status == 'Pending')
    total_days = sum((l.end_date - l.start_date).days + 1 for l in leaves if l.status == 'Approved')
    
    # Get users for filter
    users = []
    if current_user.role in ['Admin', 'HR Officer', 'Payroll Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/leave_report.html',
                         leaves=leaves,
                         start_date=start_date,
                         end_date=end_date,
                         user_id=user_id,
                         status_filter=status_filter,
                         users=users,
                         total_leaves=total_leaves,
                         approved_leaves=approved_leaves,
                         rejected_leaves=rejected_leaves,
                         pending_leaves=pending_leaves,
                         total_days=total_days)

@bp.route('/payroll')
@login_required
@payroll_required
def payroll():
    start_month = request.args.get('start_month', '')
    start_year = request.args.get('start_year', '')
    end_month = request.args.get('end_month', '')
    end_year = request.args.get('end_year', '')
    user_id = request.args.get('user_id', '')
    
    query = Payroll.query
    
    # Filter by user
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by date range
    if start_year and start_month:
        query = query.filter(
            db.or_(
                Payroll.year > int(start_year),
                db.and_(Payroll.year == int(start_year), Payroll.month >= int(start_month))
            )
        )
    
    if end_year and end_month:
        query = query.filter(
            db.or_(
                Payroll.year < int(end_year),
                db.and_(Payroll.year == int(end_year), Payroll.month <= int(end_month))
            )
        )
    
    payrolls = query.order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    
    # Calculate statistics
    total_payrolls = len(payrolls)
    total_gross = sum(float(p.gross_salary) for p in payrolls)
    total_deductions = sum(float(p.total_deductions) for p in payrolls)
    total_net = sum(float(p.net_salary) for p in payrolls)
    paid_count = sum(1 for p in payrolls if p.status == 'Paid')
    
    # Get users for filter
    users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/payroll_report.html',
                         payrolls=payrolls,
                         start_month=start_month,
                         start_year=start_year,
                         end_month=end_month,
                         end_year=end_year,
                         user_id=user_id,
                         users=users,
                         total_payrolls=total_payrolls,
                         total_gross=total_gross,
                         total_deductions=total_deductions,
                         total_net=total_net,
                         paid_count=paid_count)

