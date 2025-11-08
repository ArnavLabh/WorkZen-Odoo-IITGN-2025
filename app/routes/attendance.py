from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, User
from app.utils.decorators import admin_required, hr_required, employee_or_above_required
from datetime import datetime, date, time

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
                db.or_(
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

@bp.route('/mark', methods=['GET', 'POST'])
@login_required
@employee_or_above_required
def mark():
    if request.method == 'POST':
        user_id = request.form.get('user_id', current_user.id)
        attendance_date = request.form.get('date', '')
        check_in_time = request.form.get('check_in', '')
        check_out_time = request.form.get('check_out', '')
        status = request.form.get('status', 'Present')
        
        # Validation
        errors = []
        
        if not attendance_date:
            errors.append('Date is required')
        
        # Only Admin/HR can mark for other users
        if int(user_id) != current_user.id and current_user.role not in ['Admin', 'HR Officer']:
            errors.append('You can only mark your own attendance')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('attendance.mark'))
        
        try:
            date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            check_in = datetime.strptime(check_in_time, '%H:%M').time() if check_in_time else None
            check_out = datetime.strptime(check_out_time, '%H:%M').time() if check_out_time else None
        except ValueError:
            flash('Invalid date or time format', 'danger')
            return redirect(url_for('attendance.mark'))
        
        # Check if attendance already exists
        existing = Attendance.query.filter_by(user_id=user_id, date=date_obj).first()
        
        if existing:
            # Update existing
            existing.check_in = check_in
            existing.check_out = check_out
            existing.status = status
            existing.calculate_working_hours()
            existing.updated_at = datetime.utcnow()
            flash('Attendance updated successfully!', 'success')
        else:
            # Create new
            attendance = Attendance(
                user_id=user_id,
                date=date_obj,
                check_in=check_in,
                check_out=check_out,
                status=status
            )
            attendance.calculate_working_hours()
            db.session.add(attendance)
            flash('Attendance marked successfully!', 'success')
        
        db.session.commit()
        return redirect(url_for('attendance.list'))
    
    # GET request - show form
    user_id = request.args.get('user_id', current_user.id)
    attendance_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    
    # Get existing attendance if any
    try:
        date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
        existing = Attendance.query.filter_by(user_id=user_id, date=date_obj).first()
    except ValueError:
        existing = None
    
    # Get users for dropdown (Admin/HR can mark, Payroll can view)
    users = []
    if current_user.role in ['Admin', 'HR Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('attendance/mark.html', 
                         user_id=user_id,
                         attendance_date=attendance_date,
                         existing=existing,
                         users=users)

@bp.route('/checkin', methods=['POST'])
@login_required
@employee_or_above_required
def checkin():
    """Check in for today"""
    today = date.today()
    user_id = current_user.id
    
    # Check if already checked in today
    existing = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    if existing and existing.check_in:
        flash('You have already checked in today', 'warning')
        return redirect(url_for('attendance.list'))
    
    check_in_time = datetime.now().time()
    
    if existing:
        existing.check_in = check_in_time
        if existing.status == 'Absent':
            existing.status = 'Present'
        existing.calculate_working_hours()
    else:
        attendance = Attendance(
            user_id=user_id,
            date=today,
            check_in=check_in_time,
            status='Present'
        )
        db.session.add(attendance)
    
    db.session.commit()
    flash('Checked in successfully!', 'success')
    return redirect(url_for('dashboard.dashboard'))

@bp.route('/checkout', methods=['POST'])
@login_required
@employee_or_above_required
def checkout():
    """Check out for today"""
    today = date.today()
    user_id = current_user.id
    
    attendance = Attendance.query.filter_by(user_id=user_id, date=today).first()
    
    if not attendance:
        flash('Please check in first', 'danger')
        return redirect(url_for('attendance.list'))
    
    if attendance.check_out:
        flash('You have already checked out today', 'warning')
        return redirect(url_for('attendance.list'))
    
    attendance.check_out = datetime.now().time()
    attendance.calculate_working_hours()
    db.session.commit()
    
    flash('Checked out successfully!', 'success')
    return redirect(url_for('dashboard.dashboard'))

@bp.route('/<int:attendance_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    
    if request.method == 'POST':
        attendance_date = request.form.get('date', '')
        check_in_time = request.form.get('check_in', '')
        check_out_time = request.form.get('check_out', '')
        status = request.form.get('status', 'Present')
        
        try:
            date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            check_in = datetime.strptime(check_in_time, '%H:%M').time() if check_in_time else None
            check_out = datetime.strptime(check_out_time, '%H:%M').time() if check_out_time else None
        except ValueError:
            flash('Invalid date or time format', 'danger')
            return redirect(url_for('attendance.edit', attendance_id=attendance_id))
        
        attendance.date = date_obj
        attendance.check_in = check_in
        attendance.check_out = check_out
        attendance.status = status
        attendance.calculate_working_hours()
        attendance.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Attendance updated successfully!', 'success')
        return redirect(url_for('attendance.list'))
    
    return render_template('attendance/edit.html', attendance=attendance)

@bp.route('/<int:attendance_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete(attendance_id):
    attendance = Attendance.query.get_or_404(attendance_id)
    db.session.delete(attendance)
    db.session.commit()
    flash('Attendance deleted successfully!', 'success')
    return redirect(url_for('attendance.list'))

