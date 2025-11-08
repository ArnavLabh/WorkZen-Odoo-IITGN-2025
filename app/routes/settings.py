from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import User
from app.utils.decorators import employee_or_above_required
from app.utils.validators import validate_email, validate_password, validate_phone
from datetime import datetime

bp = Blueprint('settings', __name__)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
@employee_or_above_required
def profile():
    user = current_user
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        
        errors = []
        
        if not name:
            errors.append('Name is required')
        
        if not validate_email(email):
            errors.append('Invalid email address')
        elif email != user.email and User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if contact_number and not validate_phone(contact_number):
            errors.append('Invalid contact number (10 digits required)')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            user.name = name
            user.email = email
            user.contact_number = contact_number if contact_number else None
            user.address = address if address else None
            user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('settings.profile'))
    
    return render_template('settings/profile.html', user=user)

@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@employee_or_above_required
def change_password():
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

