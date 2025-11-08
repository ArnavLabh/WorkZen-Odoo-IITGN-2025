from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, User, Leave
from app.utils.decorators import admin_required, hr_required, employee_or_above_required, role_required
from datetime import datetime, date, time, timedelta
from calendar import monthrange
from sqlalchemy import or_, and_, inspect
from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

bp = Blueprint('attendance', __name__)

@bp.route('/')
@login_required
@role_required(['Employee'])
def list():
    """
    Employee attendance view - shows current month by default
    Displays: Date, Check In, Check Out, Work Hours, Extra Hours
    Includes month navigation and summary counters
    """
    # Get month and year from query parameters, default to current month
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year
    
    # Ensure valid month/year
    if month < 1 or month > 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year
    
    # Calculate start and end dates for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    # Get attendance records for the month
    attendances = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date.desc()).all()
    
    # Calculate summary statistics
    days_present = sum(1 for a in attendances if a.status == 'Present')
    
    # Get leave count for the month
    leaves = Leave.query.filter(
        Leave.user_id == current_user.id,
        Leave.status == 'Approved',
        Leave.start_date <= end_date,
        Leave.end_date >= start_date
    ).all()
    
    leave_count = 0
    for leave in leaves:
        # Calculate overlapping days
        leave_start = max(leave.start_date, start_date)
        leave_end = min(leave.end_date, end_date)
        if leave_start <= leave_end:
            leave_count += (leave_end - leave_start).days + 1
    
    # Calculate total working days (excluding weekends - Saturday=5, Sunday=6)
    total_working_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday to Friday
            total_working_days += 1
        current += timedelta(days=1)
    
    # Calculate previous and next month/year
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    return render_template('attendance/employee_list.html',
                         attendances=attendances,
                         month=month,
                         year=year,
                         month_name=month_names[month - 1],
                         days_present=days_present,
                         leave_count=leave_count,
                         total_working_days=total_working_days,
                         prev_month=prev_month,
                         prev_year=prev_year,
                         next_month=next_month,
                         next_year=next_year,
                         start_date=start_date,
                         end_date=end_date)

# Manual attendance marking has been removed - attendance is controlled exclusively by employees through Check-In/Check-Out

@bp.route('/checkin', methods=['POST'])
@login_required
@role_required(['Employee'])
def checkin():
    """Check in for today - Employee only - supports multiple check-ins"""
    from app.models import AttendanceLog
    
    today = date.today()
    user_id = current_user.id
    
    try:
        # Get or create attendance record for today
        attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
        
        if not attendance:
            # Create new attendance record
            attendance = Attendance(
                user_id=user_id,
                date=today,
                status='Present'
            )
            db.session.add(attendance)
            db.session.flush()
        
        # Check if already checked in (not checked out yet)
        last_log = attendance.check_logs.order_by(AttendanceLog.id.desc()).first()
        if last_log and last_log.log_type == 'check_in':
            flash('You are already checked in. Please check out first.', 'warning')
            return redirect(request.referrer or url_for('settings.profile'))
        
        # Create check-in log
        check_in_time = datetime.now().time()
        log = AttendanceLog(
            attendance_id=attendance.id,
            log_type='check_in',
            timestamp=check_in_time
        )
        db.session.add(log)
        
        # Update first check-in time if not set
        if not attendance.check_in:
            attendance.check_in = check_in_time
        
        attendance.status = 'Present'
        db.session.commit()
        
        flash('Checked in successfully!', 'success')
    except (OperationalError, InternalError, ProgrammingError) as e:
        db.session.rollback()
        flash('Error checking in. Please try again.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash('Error checking in. Please try again.', 'danger')
    
    return redirect(request.referrer or url_for('settings.profile'))

@bp.route('/checkout', methods=['POST'])
@login_required
@role_required(['Employee'])
def checkout():
    """Check out for today - Employee only - supports multiple check-outs"""
    from app.models import AttendanceLog
    
    today = date.today()
    user_id = current_user.id
    
    try:
        attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
        
        if not attendance:
            flash('Please check in first', 'danger')
            return redirect(request.referrer or url_for('settings.profile'))
        
        # Check if already checked out (or never checked in)
        last_log = attendance.check_logs.order_by(AttendanceLog.id.desc()).first()
        if not last_log or last_log.log_type == 'check_out':
            flash('You need to check in first', 'danger')
            return redirect(request.referrer or url_for('settings.profile'))
        
        # Create check-out log
        check_out_time = datetime.now().time()
        log = AttendanceLog(
            attendance_id=attendance.id,
            log_type='check_out',
            timestamp=check_out_time
        )
        db.session.add(log)
        
        # Update last check-out time
        attendance.check_out = check_out_time
        
        # Recalculate working hours
        attendance.calculate_working_hours()
        
        db.session.commit()
        flash('Checked out successfully!', 'success')
    except (OperationalError, InternalError, ProgrammingError) as e:
        db.session.rollback()
        flash('Error checking out. Please try again.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash('Error checking out. Please try again.', 'danger')
    
    return redirect(request.referrer or url_for('settings.profile'))

# Manual attendance editing and deletion have been removed - attendance is controlled exclusively by employees through Check-In/Check-Out

