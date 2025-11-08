from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, PayrollSettings
from app.utils.decorators import admin_required, hr_required, employee_or_above_required
from app.utils.validators import validate_email, validate_phone, validate_password, validate_employee_id
from datetime import datetime

bp = Blueprint('employees', __name__)

@bp.route('/')
@login_required
def list():
    # Only Admin and HR Officer can see full list with actions
    # Payroll Officer cannot access employee management
    if current_user.role not in ['Admin', 'HR Officer']:
        if current_user.role == 'Employee':
            return redirect(url_for('employees.directory'))
        flash('You do not have permission to access employee management', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    if current_user.role in ['Admin', 'HR Officer']:
        search = request.args.get('search', '').strip()
        query = User.query.filter(User.role == 'Employee')
        
        if search:
            query = query.filter(
                db.or_(
                    User.name.ilike(f'%{search}%'),
                    User.employee_id.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
        
        employees = query.order_by(User.created_at.desc()).all()
        return render_template('employees/list.html', employees=employees, search=search)
    
    # Employees can only see directory
    return redirect(url_for('employees.directory'))

@bp.route('/directory')
@login_required
@employee_or_above_required
def directory():
    search = request.args.get('search', '').strip()
    query = User.query.filter(User.role == 'Employee')
    
    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.employee_id.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    employees = query.order_by(User.name).all()
    return render_template('employees/directory.html', employees=employees, search=search)

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@hr_required
def register():
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'Employee')
        date_of_joining = request.form.get('date_of_joining', '')
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        
        # Validation
        errors = []
        
        if not validate_employee_id(employee_id)[0]:
            errors.append('Employee ID is required')
        elif User.query.filter_by(employee_id=employee_id).first():
            errors.append('Employee ID already exists')
        
        if not name:
            errors.append('Name is required')
        
        if not validate_email(email):
            errors.append('Invalid email address')
        elif User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if not password:
            errors.append('Password is required')
        else:
            is_valid, message = validate_password(password)
            if not is_valid:
                errors.append(message)
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if role not in ['Employee', 'HR Officer', 'Payroll Officer']:
            errors.append('Invalid role')
        
        if not date_of_joining:
            errors.append('Date of joining is required')
        
        if contact_number and not validate_phone(contact_number):
            errors.append('Invalid contact number (10 digits required)')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            user = User(
                employee_id=employee_id,
                name=name,
                email=email,
                role=role,
                date_of_joining=datetime.strptime(date_of_joining, '%Y-%m-%d').date(),
                contact_number=contact_number if contact_number else None,
                address=address if address else None
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Create payroll settings with default values
            payroll_settings = PayrollSettings(
                user_id=user.id,
                basic_salary=0.0,
                hra_percentage=0.0,
                conveyance=0.0,
                other_allowances=0.0,
                pf_percentage=12.0,
                professional_tax_amount=200.0
            )
            db.session.add(payroll_settings)
            db.session.commit()
            
            flash(f'Employee {name} registered successfully!', 'success')
            return redirect(url_for('employees.list'))
    
    return render_template('employees/register.html')

@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit(user_id):
    user = User.query.get_or_404(user_id)
    
    # HR Officers can only edit employees
    if current_user.role == 'HR Officer' and user.role != 'Employee':
        flash('You can only edit employee profiles', 'danger')
        return redirect(url_for('employees.list'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'Employee')
        date_of_joining = request.form.get('date_of_joining', '')
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        
        # Validation
        errors = []
        
        if not name:
            errors.append('Name is required')
        
        if not validate_email(email):
            errors.append('Invalid email address')
        elif email != user.email and User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if role not in ['Employee', 'HR Officer', 'Payroll Officer', 'Admin']:
            errors.append('Invalid role')
        
        if not date_of_joining:
            errors.append('Date of joining is required')
        
        if contact_number and not validate_phone(contact_number):
            errors.append('Invalid contact number (10 digits required)')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            user.name = name
            user.email = email
            user.role = role
            user.date_of_joining = datetime.strptime(date_of_joining, '%Y-%m-%d').date()
            user.contact_number = contact_number if contact_number else None
            user.address = address if address else None
            user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Employee {name} updated successfully!', 'success')
            return redirect(url_for('employees.list'))
    
    return render_template('employees/edit.html', user=user)

@bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('employees.list'))
    
    name = user.name
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Employee {name} deleted successfully!', 'success')
    return redirect(url_for('employees.list'))

@bp.route('/<int:user_id>/view')
@login_required
@employee_or_above_required
def view(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('employees/view.html', user=user)

