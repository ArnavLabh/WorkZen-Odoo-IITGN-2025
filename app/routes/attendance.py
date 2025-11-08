from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, User
from app.utils.decorators import admin_required, hr_required, employee_or_above_required, role_required
from datetime import datetime, date, time
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

bp = Blueprint('attendance', __name__)

@bp.route('/')
@login_required
@employee_or_above_required
def list():
    # All roles can access attendance
    # Employees see only their own attendance
    # HR Officer, Payroll Officer, Admin can see all employees' attendance
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    filter_date = request.args.get('date', '')
    user_filter = request.args.get('user_id', '')
    
    # Build query based on role
    if current_user.role == 'Employee':
        # Employees can only view their own attendance
        query = Attendance.query.filter_by(user_id=current_user.id)
        users = []  # No user filter for employees
    else:
        # HR Officer, Payroll Officer, Admin can view all attendance
        query = Attendance.query
        
        if user_filter:
            query = query.filter_by(user_id=user_filter)
        
        if search:
            query = query.join(User).filter(
                or_(
                    User.name.ilike(f'%{search}%'),
                    User.employee_id.ilike(f'%{search}%')
                )
            )
        
        # Get all users for filter
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    if filter_date:
        try:
            date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
            query = query.filter_by(date=date_obj)
        except ValueError:
            pass
    
    attendances = query.order_by(Attendance.date.desc(), Attendance.user_id).limit(100).all()
    
    return render_template('attendance/list.html', 
                         attendances=attendances, 
                         search=search,
                         filter_date=filter_date,
                         user_filter=user_filter,
                         users=users)

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

