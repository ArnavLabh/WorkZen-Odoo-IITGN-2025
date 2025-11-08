from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Leave, User
from app.utils.decorators import admin_required, hr_required, payroll_required, employee_or_above_required
from app.utils.validators import validate_date_range
from datetime import datetime, date
from sqlalchemy import or_

bp = Blueprint('leave', __name__)

@bp.route('/')
@login_required
@employee_or_above_required
def list():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    if current_user.role == 'Employee':
        query = Leave.query.filter_by(user_id=current_user.id)
    else:
        query = Leave.query
        if search:
            query = query.join(User).filter(
                or_(
                    User.name.ilike(f'%{search}%'),
                    User.employee_id.ilike(f'%{search}%')
                )
            )
        if status_filter:
            query = query.filter_by(status=status_filter)
    
    leaves = query.order_by(Leave.created_at.desc()).all()
    
    return render_template('leave/list.html', leaves=leaves, search=search, status_filter=status_filter)

@bp.route('/apply', methods=['GET', 'POST'])
@login_required
@employee_or_above_required
def apply():
    if current_user.role != 'Employee':
        flash('Only employees can apply for leave', 'danger')
        return redirect(url_for('leave.list'))
    
    if request.method == 'POST':
        leave_type = request.form.get('leave_type', '').strip()
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        reason = request.form.get('reason', '').strip()
        
        errors = []
        
        if not leave_type:
            errors.append('Leave type is required')
        
        if not start_date or not end_date:
            errors.append('Start date and end date are required')
        else:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if start < date.today():
                    errors.append('Start date cannot be in the past')
                
                is_valid, message = validate_date_range(start, end)
                if not is_valid:
                    errors.append(message)
            except ValueError:
                errors.append('Invalid date format')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            leave = Leave(
                user_id=current_user.id,
                leave_type=leave_type,
                start_date=start,
                end_date=end,
                reason=reason,
                status='Pending'
            )
            db.session.add(leave)
            db.session.commit()
            flash('Leave application submitted successfully!', 'success')
            return redirect(url_for('leave.list'))
    
    return render_template('leave/apply.html')

@bp.route('/<int:leave_id>/approve', methods=['POST'])
@login_required
def approve(leave_id):
    # Payroll Officer and Admin can approve leaves (HR can allocate but Payroll approves)
    if current_user.role not in ['Admin', 'Payroll Officer']:
        flash('You do not have permission to approve leaves', 'danger')
        return redirect(url_for('leave.list'))
    leave = Leave.query.get_or_404(leave_id)
    
    if leave.status != 'Pending':
        flash('This leave request has already been processed', 'warning')
        return redirect(url_for('leave.list'))
    
    leave.status = 'Approved'
    leave.approved_by = current_user.id
    leave.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Leave request approved successfully!', 'success')
    return redirect(url_for('leave.list'))

@bp.route('/<int:leave_id>/reject', methods=['POST'])
@login_required
def reject(leave_id):
    # Payroll Officer and Admin can reject leaves
    if current_user.role not in ['Admin', 'Payroll Officer']:
        flash('You do not have permission to reject leaves', 'danger')
        return redirect(url_for('leave.list'))
    leave = Leave.query.get_or_404(leave_id)
    
    if leave.status != 'Pending':
        flash('This leave request has already been processed', 'warning')
        return redirect(url_for('leave.list'))
    
    leave.status = 'Rejected'
    leave.approved_by = current_user.id
    leave.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Leave request rejected', 'info')
    return redirect(url_for('leave.list'))

@bp.route('/<int:leave_id>/view')
@login_required
@employee_or_above_required
def view(leave_id):
    leave = Leave.query.get_or_404(leave_id)
    
    # Employees can only view their own leaves
    if current_user.role == 'Employee' and leave.user_id != current_user.id:
        flash('You can only view your own leave requests', 'danger')
        return redirect(url_for('leave.list'))
    
    return render_template('leave/view.html', leave=leave)

