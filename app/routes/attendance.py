from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, User
from app.utils.decorators import admin_required, hr_required, employee_or_above_required
from datetime import datetime, date, time
from sqlalchemy import or_

bp = Blueprint('attendance', __name__)

@bp.route('/')
@login_required
@employee_or_above_required
def list():
    # Get filter parameters
    search = request.args.get('search', '').strip()
    filter_date = request.args.get('date', '')
    user_filter = request.args.get('user_id', '')
    
    # Build query based on role
    if current_user.role == 'Employee':
        query = Attendance.query.filter_by(user_id=current_user.id)
    else:
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
    
    if filter_date:
        try:
            date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
            query = query.filter_by(date=date_obj)
        except ValueError:
            pass
    
    attendances = query.order_by(Attendance.date.desc(), Attendance.user_id).limit(100).all()
    
    # Get all users for filter (Admin/HR/Payroll can view all)
    users = []
    if current_user.role in ['Admin', 'HR Officer', 'Payroll Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('attendance/list.html', 
                         attendances=attendances, 
                         search=search,
                         filter_date=filter_date,
                         user_filter=user_filter,
                         users=users)

# Manual attendance marking has been removed - attendance is controlled exclusively by employees through Check-In/Check-Out

@bp.route('/checkin', methods=['POST'])
@login_required
def checkin():
    """Check in for today - Employee only"""
    # Only employees can check in
    if current_user.role != 'Employee':
        flash('Only employees can check in', 'danger')
        return redirect(request.referrer or url_for('employees.directory'))
    
    today = date.today()
    user_id = current_user.id
    
    # Check if already checked in today
    existing = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    if existing and existing.check_in:
        flash('You have already checked in today', 'warning')
        return redirect(request.referrer or url_for('settings.profile'))
    
    # Check if already checked out today (prevent checking in again after checkout)
    if existing and existing.check_out:
        flash('You have already checked out today', 'warning')
        return redirect(request.referrer or url_for('settings.profile'))
    
    check_in_time = datetime.now().time()
    
    # Create new attendance entry on check-in
    if existing:
        # If record exists but no check-in, update it
        existing.check_in = check_in_time
        existing.status = 'Present'  # Always set to Present when checking in
        existing.calculate_working_hours()
    else:
        # Create new attendance record
        attendance = Attendance(
            user_id=user_id,
            date=today,
            check_in=check_in_time,
            status='Present'
        )
        attendance.calculate_working_hours()
        db.session.add(attendance)
    
    db.session.commit()
    flash('Checked in successfully!', 'success')
    return redirect(request.referrer or url_for('settings.profile'))

@bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    """Check out for today - Employee only"""
    # Only employees can check out
    if current_user.role != 'Employee':
        flash('Only employees can check out', 'danger')
        return redirect(request.referrer or url_for('employees.directory'))
    
    today = date.today()
    user_id = current_user.id
    
    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    if not attendance:
        flash('Please check in first', 'danger')
        return redirect(request.referrer or url_for('settings.profile'))
    
    if not attendance.check_in:
        flash('Please check in first', 'danger')
        return redirect(request.referrer or url_for('settings.profile'))
    
    if attendance.check_out:
        flash('You have already checked out today', 'warning')
        return redirect(request.referrer or url_for('settings.profile'))
    
    # Close attendance entry on check-out
    attendance.check_out = datetime.now().time()
    attendance.calculate_working_hours()
    db.session.commit()
    
    flash('Checked out successfully!', 'success')
    return redirect(request.referrer or url_for('settings.profile'))

# Manual attendance editing and deletion have been removed - attendance is controlled exclusively by employees through Check-In/Check-Out

