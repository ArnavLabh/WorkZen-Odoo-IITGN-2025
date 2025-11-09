from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app import db
from app.models import Leave, User
from app.utils.decorators import admin_required, hr_required, payroll_required, employee_or_above_required, role_required
from app.utils.validators import validate_date_range
from datetime import datetime, date
from sqlalchemy import or_

bp = Blueprint('leave', __name__)

@bp.route('/')
@login_required
@employee_or_above_required
def list():
    # All roles can access leave list
    # Employees see only their own leaves
    # HR Officer, Payroll Officer, Admin can see all leaves
    
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    if current_user.role == 'Employee':
        # Employees can only view their own leaves
        query = Leave.query.filter_by(user_id=current_user.id)
    else:
        # HR Officer, Payroll Officer, Admin can view all leaves
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
@role_required(['Employee'])
def apply():
    # Only employees can apply for leave
    
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
                
                if end < start:
                    errors.append('End date must be on or after start date')
                
                is_valid, message = validate_date_range(start, end)
                if not is_valid:
                    errors.append(message)
                
                # Check for overlapping leaves
                overlapping_leaves = Leave.query.filter(
                    Leave.user_id == current_user.id,
                    Leave.status.in_(['Pending', 'Approved']),
                    or_(
                        and_(Leave.start_date <= start, Leave.end_date >= start),
                        and_(Leave.start_date <= end, Leave.end_date >= end),
                        and_(Leave.start_date >= start, Leave.end_date <= end)
                    )
                ).all()
                
                if overlapping_leaves:
                    overlap_details = ', '.join([
                        f"{leave.leave_type} ({leave.start_date.strftime('%Y-%m-%d')} to {leave.end_date.strftime('%Y-%m-%d')}) - {leave.status}"
                        for leave in overlapping_leaves
                    ])
                    errors.append(f'You already have leave(s) for overlapping dates: {overlap_details}')
                    
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
@role_required(['Admin', 'Payroll Officer'])
def approve(leave_id):
    # Payroll Officer and Admin can approve/reject leaves
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
@role_required(['Admin', 'Payroll Officer'])
def reject(leave_id):
    # Payroll Officer and Admin can approve/reject leaves
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

@bp.route('/<int:leave_id>/delete', methods=['POST'])
@login_required
@role_required(['Employee'])
def delete(leave_id):
    # Employees can only delete their own pending leave requests
    leave = Leave.query.get_or_404(leave_id)
    
    # Check if leave belongs to current user
    if leave.user_id != current_user.id:
        abort(403)
    
    # Only allow deletion of pending leaves
    if leave.status != 'Pending':
        flash('You can only delete pending leave requests', 'danger')
        return redirect(url_for('leave.list'))
    
    leave_type = leave.leave_type
    start_date = leave.start_date.strftime('%Y-%m-%d')
    
    db.session.delete(leave)
    db.session.commit()
    
    flash(f'{leave_type} request for {start_date} deleted successfully!', 'success')
    return redirect(url_for('leave.list'))

@bp.route('/<int:leave_id>/view')
@login_required
@employee_or_above_required
def view(leave_id):
    leave = Leave.query.get_or_404(leave_id)
    
    # Employees can only view their own leaves
    if current_user.role == 'Employee' and leave.user_id != current_user.id:
        abort(403)
    
    return render_template('leave/view.html', leave=leave)

