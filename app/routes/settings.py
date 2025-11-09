from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import User
from app.utils.decorators import employee_or_above_required
from app.utils.validators import validate_email, validate_password, validate_phone
from datetime import datetime

bp = Blueprint('settings', __name__)

@bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """View employee profile with tabs"""
    user = current_user
    
    # Get manager info if exists
    manager = User.query.get(user.manager_id) if user.manager_id else None
    
    # Get payroll settings for salary info
    from app.models import PayrollSettings
    payroll_settings = PayrollSettings.query.filter_by(user_id=user.id).first()
    
    # Get potential managers based on role hierarchy
    # Employee < HR Officer < Payroll Officer < Admin
    role_hierarchy = {
        'Employee': ['HR Officer', 'Payroll Officer', 'Admin'],
        'HR Officer': ['Payroll Officer', 'Admin'],
        'Payroll Officer': ['Admin'],
        'Admin': []  # Admins have no superiors
    }
    
    allowed_manager_roles = role_hierarchy.get(user.role, [])
    potential_managers = User.query.filter(User.role.in_(allowed_manager_roles)).order_by(User.name).all() if allowed_manager_roles else []
    
    return render_template('settings/profile.html', 
                         user=user, 
                         manager=manager,
                         payroll_settings=payroll_settings,
                         potential_managers=potential_managers)

@bp.route('/profile/update-private-info', methods=['POST'])
@login_required
def update_private_info():
    """Update private information"""
    user = current_user
    
    # Get all form fields
    company = request.form.get('company', '').strip()
    department = request.form.get('department', '').strip()
    manager_id = request.form.get('manager_id', '').strip()
    date_of_birth = request.form.get('date_of_birth', '').strip()
    nationality = request.form.get('nationality', '').strip()
    personal_email = request.form.get('personal_email', '').strip()
    gender = request.form.get('gender', '').strip()
    marital_status = request.form.get('marital_status', '').strip()
    
    errors = []
    
    if personal_email and not validate_email(personal_email):
        errors.append('Invalid personal email address')
    
    if date_of_birth:
        try:
            user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Invalid date of birth format')
    
    # Validate manager selection based on role hierarchy
    if manager_id:
        try:
            manager_id_int = int(manager_id)
            potential_manager = User.query.get(manager_id_int)
            if potential_manager:
                # Check if the selected manager is valid based on role hierarchy
                role_hierarchy = {
                    'Employee': ['HR Officer', 'Payroll Officer', 'Admin'],
                    'HR Officer': ['Payroll Officer', 'Admin'],
                    'Payroll Officer': ['Admin'],
                    'Admin': []
                }
                allowed_roles = role_hierarchy.get(user.role, [])
                if potential_manager.role not in allowed_roles:
                    errors.append('Invalid manager selection for your role')
        except (ValueError, TypeError):
            errors.append('Invalid manager selection')
    
    if errors:
        for error in errors:
            flash(error, 'danger')
    else:
        # Update all fields
        user.company = company if company else None
        user.department = department if department else None
        user.manager_id = int(manager_id) if manager_id else None
        user.nationality = nationality if nationality else None
        user.personal_email = personal_email if personal_email else None
        user.gender = gender if gender else None
        user.marital_status = marital_status if marital_status else None
        user.address = request.form.get('address', '').strip() or None
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Personal information updated successfully!', 'success')
    
    return redirect(url_for('settings.profile'))

@bp.route('/profile/update-salary-info', methods=['POST'])
@login_required
def update_salary_info():
    """Update salary/bank information"""
    user = current_user
    
    bank_account_number = request.form.get('bank_account_number', '').strip()
    bank_name = request.form.get('bank_name', '').strip()
    ifsc_code = request.form.get('ifsc_code', '').strip()
    pan_number = request.form.get('pan_number', '').strip()
    uan_number = request.form.get('uan_number', '').strip()
    
    user.bank_account_number = bank_account_number if bank_account_number else None
    user.bank_name = bank_name if bank_name else None
    user.ifsc_code = ifsc_code if ifsc_code else None
    user.pan_number = pan_number if pan_number else None
    user.uan_number = uan_number if uan_number else None
    user.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash('Bank details updated successfully!', 'success')
    
    return redirect(url_for('settings.profile'))

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    # All roles can change their own password
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        
        if not current_user.check_password(current_password):
            errors.append('Current password is incorrect')
        
        if not new_password:
            errors.append('New password is required')
        else:
            is_valid, message = validate_password(new_password)
            if not is_valid:
                errors.append(message)
        
        if new_password != confirm_password:
            errors.append('New passwords do not match')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('settings.change_password'))
    
    return render_template('settings/change_password.html')

@bp.route('/company', methods=['GET', 'POST'])
@login_required
def company_settings():
    from app.models import CompanySettings
    from app.utils.decorators import role_required
    
    # Only Admin can access company settings
    if current_user.role != 'Admin':
        from flask import abort
        abort(403)
    
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        required_hours = request.form.get('required_working_hours', '8')
        
        errors = []
        
        if not company_name:
            errors.append('Company name is required')
        
        try:
            hours = float(required_hours)
            if hours <= 0 or hours > 24:
                errors.append('Working hours must be between 0 and 24')
        except ValueError:
            errors.append('Invalid working hours value')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            CompanySettings.set_setting(
                'company_name',
                company_name,
                'Company name displayed across the application',
                current_user.id
            )
            CompanySettings.set_setting(
                'required_working_hours',
                hours,
                'Required working hours per day for full attendance',
                current_user.id
            )
            db.session.commit()
            flash('Company settings updated successfully!', 'success')
            return redirect(url_for('settings.company_settings'))
    
    # Get current settings
    company_name = CompanySettings.get_setting('company_name', 'WorkZen')
    required_hours = CompanySettings.get_setting('required_working_hours', '8')
    
    return render_template('settings/company.html', 
                         company_name=company_name,
                         required_hours=required_hours)

