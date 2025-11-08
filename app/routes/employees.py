from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, PayrollSettings
from app.utils.decorators import admin_required, hr_required, employee_or_above_required
from app.utils.validators import validate_email, validate_phone, validate_password, validate_employee_id
from app.utils.employee_utils import generate_login_id, generate_random_password
from datetime import datetime
from sqlalchemy import or_

bp = Blueprint('employees', __name__)

@bp.route('/')
@login_required
def list():
    # Only Admin and HR Officer can see full list with actions
    # Payroll Officer and Employees cannot access employee management
    if current_user.role not in ['Admin', 'HR Officer']:
        if current_user.role == 'Employee':
            flash('You do not have permission to access employee management', 'danger')
            return redirect(url_for('settings.profile'))
        flash('You do not have permission to access employee management', 'danger')
        return redirect(url_for('employees.directory'))
    
    if current_user.role in ['Admin', 'HR Officer']:
        search = request.args.get('search', '').strip()
        query = User.query.filter(User.role == 'Employee')
        
        if search:
            query = query.filter(
                or_(
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
def directory():
    # Only Admin, HR Officer, and Payroll Officer can access Employee Directory
    # Employees cannot see the directory
    if current_user.role == 'Employee':
        flash('You do not have permission to access the employee directory', 'danger')
        return redirect(url_for('settings.profile'))
    
    if current_user.role not in ['Admin', 'HR Officer', 'Payroll Officer']:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    from app.models import Attendance, Leave
    from datetime import date, datetime
    
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
    
    # Get today's date
    today = date.today()
    
    # Get employee statuses
    employee_statuses = {}
    for employee in employees:
        # Check today's attendance
        today_attendance = Attendance.query.filter_by(
            user_id=employee.id,
            date=today
        ).first()
        
        # Check if on leave today
        today_leave = Leave.query.filter(
            Leave.user_id == employee.id,
            Leave.start_date <= today,
            Leave.end_date >= today,
            Leave.status == 'Approved'
        ).first()
        
        # Determine status
        if today_leave:
            employee_statuses[employee.id] = 'on_leave'  # Airplane icon
        elif today_attendance and today_attendance.status == 'Present':
            employee_statuses[employee.id] = 'present'  # Green dot
        else:
            employee_statuses[employee.id] = 'absent'  # Yellow dot
    
    return render_template('employees/directory.html', 
                         employees=employees, 
                         search=search,
                         employee_statuses=employee_statuses)

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@hr_required
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'Employee')
        date_of_joining = request.form.get('date_of_joining', '')
        contact_number = request.form.get('contact_number', '').strip()
        address = request.form.get('address', '').strip()
        
        # Validation
        errors = []
        first_name = None
        last_name = None
        
        if not name:
            errors.append('Name is required')
        else:
            # Split name into first and last name
            name_parts = name.split()
            if len(name_parts) < 2:
                errors.append('Please provide both first name and last name')
            else:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])  # In case of multiple last names
        
        if not validate_email(email):
            errors.append('Invalid email address')
        elif User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
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
            # Parse date of joining
            try:
                joining_date = datetime.strptime(date_of_joining, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'danger')
                return render_template('employees/register.html')
            
            # Auto-generate login ID
            employee_id = generate_login_id(first_name, last_name, joining_date)
            
            # Auto-generate password
            password = generate_random_password(12)
            
            user = User(
                employee_id=employee_id,
                name=name,
                email=email,
                role=role,
                date_of_joining=joining_date,
                contact_number=contact_number if contact_number else None,
                address=address if address else None
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.flush()  # Flush to get user.id
            
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
            
            flash(f'Employee {name} registered successfully! Login ID: {employee_id}, Password: {password}. Please share these credentials with the employee.', 'success')
            return redirect(url_for('employees.list'))
    
    return render_template('employees/register.html')

@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(user_id):
    user = User.query.get_or_404(user_id)
    
    # Permission checks: Only Admin and HR Officer can edit employee profiles
    if current_user.role not in ['Admin', 'HR Officer']:
        flash('You do not have permission to edit employee profiles', 'danger')
        if current_user.role == 'Employee':
            return redirect(url_for('settings.profile'))
        return redirect(url_for('employees.directory'))
    
    # HR Officers can only edit employees
    if current_user.role == 'HR Officer' and user.role != 'Employee':
        flash('You can only edit employee profiles', 'danger')
        return redirect(url_for('employees.directory'))
    
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
def view(user_id):
    user = User.query.get_or_404(user_id)
    
    # Permission checks:
    # - Employees can only view their own profile
    # - Admin, HR Officer, Payroll Officer can view any employee
    if current_user.role == 'Employee' and current_user.id != user_id:
        flash('You can only view your own profile', 'danger')
        return redirect(url_for('settings.profile'))
    
    # Determine if profile should be editable
    can_edit = False
    can_edit_salary = False
    
    if current_user.role == 'Admin':
        can_edit = True
        can_edit_salary = True
    elif current_user.role == 'HR Officer':
        can_edit = True  # HR can edit employee profiles
        can_edit_salary = False
    elif current_user.role == 'Payroll Officer':
        can_edit = False  # Payroll cannot edit profiles
        can_edit_salary = True  # But can edit salary components
    
    return render_template('employees/view.html', 
                         user=user, 
                         can_edit=can_edit,
                         can_edit_salary=can_edit_salary,
                         is_own_profile=(current_user.id == user_id))

