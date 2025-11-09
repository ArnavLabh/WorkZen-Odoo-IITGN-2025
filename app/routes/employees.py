from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, PayrollSettings
from app.utils.decorators import admin_required, hr_required, employee_or_above_required, role_required
from app.utils.validators import validate_email, validate_phone, validate_password, validate_employee_id
from app.utils.employee_utils import generate_login_id, generate_random_password
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

bp = Blueprint('employees', __name__)

@bp.route('/')
@login_required
@role_required(['Admin', 'HR Officer'])
def list():
    # Only Admin and HR Officer can see full list with actions
    # This is for employee management (create, edit, delete operations)
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

@bp.route('/directory')
@login_required
@role_required(['Admin', 'HR Officer', 'Payroll Officer', 'Employee'])
def directory():
    # All roles can access Employee Directory
    # Employees have read-only access (cannot edit or delete)
    # Admin, HR Officer, Payroll Officer have full access
    
    from app.models import Attendance, Leave
    from datetime import date, datetime
    
    search = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', '').strip()
    
    # Admin can see all users (Employee, HR Officer, Payroll Officer)
    # Others can only see Employees
    if current_user.role == 'Admin':
        query = User.query.filter(User.role.in_(['Employee', 'HR Officer', 'Payroll Officer']))
    else:
        query = User.query.filter(User.role == 'Employee')
    
    # Apply filters
    if filter_type == 'no_bank':
        query = query.filter(
            or_(
                User.bank_account_number == None,
                User.bank_name == None,
                User.ifsc_code == None
            )
        )
    elif filter_type == 'no_manager':
        query = query.filter(User.manager_id == None)
    
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search}%'),
                User.employee_id.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    employees = query.order_by(User.name).all()
    
    # Get today's date
    today = date.today()
    
    # Get employee statuses based on live attendance data
    employee_statuses = {}
    for employee in employees:
        try:
            # Check if on leave today (leave takes priority)
            today_leave = Leave.query.filter(
                Leave.user_id == employee.id,
                Leave.start_date <= today,
                Leave.end_date >= today,
                Leave.status == 'Approved'
            ).first()
            
            if today_leave:
                employee_statuses[employee.id] = 'on_leave'  # Airplane icon
            else:
                # Check today's attendance - use live check-in/checkout status based on logs
                try:
                    from app.models import AttendanceLog
                    
                    today_attendance = Attendance.query.filter_by(
                        user_id=employee.id,
                        date=today
                    ).first()
                    
                    if today_attendance:
                        # Check the last log to determine current status
                        last_log = AttendanceLog.query.filter_by(
                            attendance_id=today_attendance.id
                        ).order_by(AttendanceLog.id.desc()).first()
                        
                        # If last log is check_in, employee is currently checked in (green)
                        # If last log is check_out or no logs, employee is not checked in (red)
                        if last_log and last_log.log_type == 'check_in':
                            employee_statuses[employee.id] = 'present'  # Green dot - checked in
                        else:
                            employee_statuses[employee.id] = 'absent'  # Red dot - checked out or not checked in
                    else:
                        employee_statuses[employee.id] = 'absent'  # Red dot - no attendance record
                except (OperationalError, InternalError, ProgrammingError) as e:
                    # Transaction error - rollback and set default status
                    try:
                        db.session.rollback()
                    except:
                        pass
                    employee_statuses[employee.id] = 'absent'  # Default to absent on error
                except Exception:
                    # Any other error - set default status
                    employee_statuses[employee.id] = 'absent'
        except (OperationalError, InternalError, ProgrammingError) as e:
            # Transaction error - rollback and set default status
            try:
                db.session.rollback()
            except:
                pass
            employee_statuses[employee.id] = 'absent'  # Default to absent on error
        except Exception:
            # Any other error - set default status
            employee_statuses[employee.id] = 'absent'
    
    return render_template('employees/directory.html', 
                         employees=employees, 
                         search=search,
                         employee_statuses=employee_statuses)

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'HR Officer'])
def register():
    # Admin and HR Officer can register new employees
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
            
            flash(f'Employee {name} registered successfully! Login ID: {employee_id}, Password: {password}. Please share these credentials with the employee.', 'credentials')
            return redirect(url_for('employees.directory'))
    
    return render_template('employees/register.html')

@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'HR Officer'])
def edit(user_id):
    user = User.query.get_or_404(user_id)
    
    # HR Officers can only edit employees (not other HR Officers, Payroll Officers, or Admins)
    if current_user.role == 'HR Officer' and user.role != 'Employee':
        abort(403)
    
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
        
        # Role validation
        if current_user.role == 'Admin':
            # Admin can change role to anything except Admin (to prevent accidental admin removal)
            if user.role == 'Admin' and role != 'Admin':
                errors.append('Cannot change role of Admin user. This is a security measure.')
            elif role not in ['Employee', 'HR Officer', 'Payroll Officer', 'Admin']:
                errors.append('Invalid role')
        else:
            # HR Officer can only keep role as Employee
            if role != 'Employee':
                errors.append('HR Officers can only manage Employee roles')
        
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
            # Only update role if user is not Admin or if keeping Admin role
            if user.role != 'Admin':
                user.role = role
            user.date_of_joining = datetime.strptime(date_of_joining, '%Y-%m-%d').date()
            user.contact_number = contact_number if contact_number else None
            user.address = address if address else None
            user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'User {name} updated successfully!', 'success')
            return redirect(url_for('employees.directory'))
    
    return render_template('employees/edit.html', user=user)

@bp.route('/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('employees.directory'))
    
    name = user.name
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Employee {name} deleted successfully!', 'success')
    return redirect(url_for('employees.directory'))

@bp.route('/<int:user_id>/view')
@login_required
@employee_or_above_required
def view(user_id):
    user = User.query.get_or_404(user_id)
    
    # Permission checks:
    # - Employees can only view their own profile
    # - Admin, HR Officer, Payroll Officer can view any employee
    if current_user.role == 'Employee' and current_user.id != user_id:
        abort(403)
    
    # Determine if profile should be editable
    can_edit = False
    can_edit_salary = False
    
    if current_user.role == 'Admin':
        can_edit = True
        can_edit_salary = True
    elif current_user.role == 'HR Officer':
        # HR can edit employee profiles only
        can_edit = (user.role == 'Employee')
        can_edit_salary = False  # HR cannot edit salary
    elif current_user.role == 'Payroll Officer':
        can_edit = False  # Payroll cannot edit profiles
        can_edit_salary = (user.role == 'Employee')  # But can edit salary components for employees only
    
    return render_template('employees/view.html', 
                         user=user, 
                         can_edit=can_edit,
                         can_edit_salary=can_edit_salary,
                         is_own_profile=(current_user.id == user_id))

