from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Payroll, PayrollSettings, User
from app.utils.decorators import admin_required, payroll_required, employee_or_above_required
from app.utils.calculations import calculate_monthly_salary
from datetime import datetime, date

bp = Blueprint('payroll', __name__)

@bp.route('/')
@login_required
@payroll_required
def list():
    search = request.args.get('search', '').strip()
    month_filter = request.args.get('month', '')
    year_filter = request.args.get('year', '')
    
    query = Payroll.query
    
    if search:
        query = query.join(User).filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.employee_id.ilike(f'%{search}%')
            )
        )
    
    if month_filter:
        query = query.filter_by(month=int(month_filter))
    
    if year_filter:
        query = query.filter_by(year=int(year_filter))
    
    payrolls = query.order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    
    return render_template('payroll/list.html', 
                         payrolls=payrolls, 
                         search=search,
                         month_filter=month_filter,
                         year_filter=year_filter)

@bp.route('/generate', methods=['GET', 'POST'])
@login_required
@payroll_required
def generate():
    if request.method == 'POST':
        user_id = request.form.get('user_id', '')
        month = request.form.get('month', '')
        year = request.form.get('year', '')
        
        errors = []
        
        if not user_id:
            errors.append('Employee is required')
        
        if not month or not year:
            errors.append('Month and year are required')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('payroll.generate'))
        
        user = User.query.get(int(user_id))
        if not user:
            flash('Employee not found', 'danger')
            return redirect(url_for('payroll.generate'))
        
        # Check if payroll already exists
        existing = Payroll.query.filter_by(
            user_id=user_id,
            month=int(month),
            year=int(year)
        ).first()
        
        if existing:
            flash('Payroll for this month already exists', 'warning')
            return redirect(url_for('payroll.edit', payroll_id=existing.id))
        
        # Get payroll settings
        settings = PayrollSettings.query.filter_by(user_id=user_id).first()
        if not settings or settings.basic_salary == 0:
            flash(f'Please set salary structure for {user.name} first', 'danger')
            return redirect(url_for('payroll.generate'))
        
        # Calculate salary
        salary_data = calculate_monthly_salary(user_id, int(month), int(year), settings)
        
        if not salary_data:
            flash('Error calculating salary', 'danger')
            return redirect(url_for('payroll.generate'))
        
        # Create payroll record
        payroll = Payroll(
            user_id=user_id,
            month=int(month),
            year=int(year),
            basic_salary=salary_data['basic_salary'],
            hra=salary_data['hra'],
            conveyance=salary_data['conveyance'],
            other_allowances=salary_data['other_allowances'],
            gross_salary=salary_data['gross_salary'],
            pf_contribution=salary_data['pf_contribution'],
            professional_tax=salary_data['professional_tax'],
            other_deductions=salary_data['other_deductions'],
            total_deductions=salary_data['total_deductions'],
            net_salary=salary_data['net_salary'],
            status='Unpaid'
        )
        
        db.session.add(payroll)
        db.session.commit()
        
        flash('Payroll generated successfully!', 'success')
        return redirect(url_for('payroll.view', payroll_id=payroll.id))
    
    # GET request
    employees = User.query.filter_by(role='Employee').order_by(User.name).all()
    # Get employees without salary structure and create employee settings map
    employees_without_salary = []
    employee_settings_map = {}
    for emp in employees:
        settings = PayrollSettings.query.filter_by(user_id=emp.id).first()
        employee_settings_map[emp.id] = settings
        if not settings or settings.basic_salary == 0:
            employees_without_salary.append(emp)
    
    return render_template('payroll/generate.html', 
                         employees=employees,
                         employees_without_salary=employees_without_salary,
                         employee_settings_map=employee_settings_map)

@bp.route('/<int:payroll_id>/view')
@login_required
@employee_or_above_required
def view(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    
    # Employees can only view their own payslips
    if current_user.role == 'Employee' and payroll.user_id != current_user.id:
        flash('You can only view your own payslips', 'danger')
        return redirect(url_for('payroll.my_payslips'))
    
    return render_template('payroll/payslip.html', payroll=payroll)

@bp.route('/<int:payroll_id>/edit', methods=['GET', 'POST'])
@login_required
@payroll_required
def edit(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    
    if request.method == 'POST':
        basic_salary = float(request.form.get('basic_salary', 0))
        hra = float(request.form.get('hra', 0))
        conveyance = float(request.form.get('conveyance', 0))
        other_allowances = float(request.form.get('other_allowances', 0))
        pf_contribution = float(request.form.get('pf_contribution', 0))
        professional_tax = float(request.form.get('professional_tax', 0))
        other_deductions = float(request.form.get('other_deductions', 0))
        status = request.form.get('status', 'Unpaid')
        
        # Recalculate
        gross_salary = basic_salary + hra + conveyance + other_allowances
        total_deductions = pf_contribution + professional_tax + other_deductions
        net_salary = gross_salary - total_deductions
        
        payroll.basic_salary = basic_salary
        payroll.hra = hra
        payroll.conveyance = conveyance
        payroll.other_allowances = other_allowances
        payroll.gross_salary = gross_salary
        payroll.pf_contribution = pf_contribution
        payroll.professional_tax = professional_tax
        payroll.other_deductions = other_deductions
        payroll.total_deductions = total_deductions
        payroll.net_salary = net_salary
        payroll.status = status
        payroll.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Payroll updated successfully!', 'success')
        return redirect(url_for('payroll.view', payroll_id=payroll.id))
    
    return render_template('payroll/edit.html', payroll=payroll)

@bp.route('/my-payslips')
@login_required
@employee_or_above_required
def my_payslips():
    if current_user.role != 'Employee':
        return redirect(url_for('payroll.list'))
    
    payrolls = Payroll.query.filter_by(user_id=current_user.id).order_by(
        Payroll.year.desc(), Payroll.month.desc()
    ).all()
    
    return render_template('payroll/my_payslips.html', payrolls=payrolls)

@bp.route('/salary-structure', methods=['GET', 'POST'])
@login_required
@payroll_required
def salary_structure_list():
    """List all employees and their salary structures"""
    employees = User.query.filter_by(role='Employee').order_by(User.name).all()
    employee_settings = {}
    for emp in employees:
        settings = PayrollSettings.query.filter_by(user_id=emp.id).first()
        employee_settings[emp.id] = settings
    
    return render_template('payroll/salary_structure_list.html', 
                         employees=employees,
                         employee_settings=employee_settings)

@bp.route('/salary-structure/<int:user_id>', methods=['GET', 'POST'])
@login_required
@payroll_required
def salary_structure(user_id):
    """Set or update salary structure for an employee"""
    user = User.query.get_or_404(user_id)
    
    if user.role != 'Employee':
        flash('Salary structure can only be set for employees', 'danger')
        return redirect(url_for('payroll.salary_structure_list'))
    
    settings = PayrollSettings.query.filter_by(user_id=user_id).first()
    
    if not settings:
        # Create new settings
        settings = PayrollSettings(
            user_id=user_id,
            basic_salary=0.0,
            hra_percentage=0.0,
            conveyance=0.0,
            other_allowances=0.0,
            pf_percentage=12.0,
            professional_tax_amount=200.0
        )
        db.session.add(settings)
        db.session.flush()
    
    if request.method == 'POST':
        basic_salary = float(request.form.get('basic_salary', 0))
        hra_percentage = float(request.form.get('hra_percentage', 0))
        conveyance = float(request.form.get('conveyance', 0))
        other_allowances = float(request.form.get('other_allowances', 0))
        pf_percentage = float(request.form.get('pf_percentage', 12.0))
        professional_tax_amount = float(request.form.get('professional_tax_amount', 200.0))
        
        errors = []
        
        if basic_salary <= 0:
            errors.append('Basic salary must be greater than 0')
        
        if hra_percentage < 0 or hra_percentage > 100:
            errors.append('HRA percentage must be between 0 and 100')
        
        if pf_percentage < 0 or pf_percentage > 100:
            errors.append('PF percentage must be between 0 and 100')
        
        if conveyance < 0:
            errors.append('Conveyance cannot be negative')
        
        if other_allowances < 0:
            errors.append('Other allowances cannot be negative')
        
        if professional_tax_amount < 0:
            errors.append('Professional tax cannot be negative')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            settings.basic_salary = basic_salary
            settings.hra_percentage = hra_percentage
            settings.conveyance = conveyance
            settings.other_allowances = other_allowances
            settings.pf_percentage = pf_percentage
            settings.professional_tax_amount = professional_tax_amount
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Salary structure for {user.name} updated successfully!', 'success')
            return redirect(url_for('payroll.salary_structure_list'))
    
    return render_template('payroll/salary_structure.html', user=user, settings=settings)

