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
    
    return render_template('settings/profile.html', 
                         user=user, 
                         manager=manager,
                         payroll_settings=payroll_settings)

@bp.route('/profile/update-private-info', methods=['POST'])
@login_required
def update_private_info():
    """Update private information"""
    user = current_user
    
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
    
    if errors:
        for error in errors:
            flash(error, 'danger')
    else:
        user.nationality = nationality if nationality else None
        user.personal_email = personal_email if personal_email else None
        user.gender = gender if gender else None
        user.marital_status = marital_status if marital_status else None
        user.address = request.form.get('address', '').strip() or None
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Private information updated successfully!', 'success')
    
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
        required_hours = request.form.get('required_working_hours', '8')
        
        try:
            hours = float(required_hours)
            if hours <= 0 or hours > 24:
                flash('Working hours must be between 0 and 24', 'danger')
            else:
                CompanySettings.set_setting(
                    'required_working_hours',
                    hours,
                    'Required working hours per day for full attendance',
                    current_user.id
                )
                db.session.commit()
                flash('Company settings updated successfully!', 'success')
                return redirect(url_for('settings.company_settings'))
        except ValueError:
            flash('Invalid working hours value', 'danger')
    
    # Get current settings
    required_hours = CompanySettings.get_setting('required_working_hours', '8')
    
    return render_template('settings/company.html', required_hours=required_hours)

