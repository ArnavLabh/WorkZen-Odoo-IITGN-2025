from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app import db
from app.models import Payroll, PayrollSettings, SalaryComponent, User
from app.utils.decorators import admin_required, payroll_required, employee_or_above_required, role_required
from app.utils.calculations import calculate_monthly_salary
from datetime import datetime, date
from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

bp = Blueprint('payroll', __name__)

@bp.route('/')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def list():
    """Payroll Dashboard with warnings and payrun history"""
    from app.models import Payrun
    from sqlalchemy import func, extract
    
    # Get warnings
    employees_without_bank = User.query.filter(
        User.role == 'Employee',
        db.or_(
            User.bank_account_number == None,
            User.bank_name == None,
            User.ifsc_code == None
        )
    ).count()
    
    employees_without_manager = User.query.filter(
        User.role == 'Employee',
        User.manager_id == None
    ).count()
    
    # Get payrun history
    payruns = Payrun.query.order_by(Payrun.year.desc(), Payrun.month.desc()).limit(12).all()
    
    # Get charts data - Employee count and employer cost
    current_year = datetime.now().year
    
    # Employee count by month (current year)
    employee_count_monthly = []
    for month in range(1, 13):
        count = User.query.filter(
            User.role == 'Employee',
            extract('year', User.date_of_joining) <= current_year,
            db.or_(
                extract('year', User.date_of_joining) < current_year,
                extract('month', User.date_of_joining) <= month
            )
        ).count()
        employee_count_monthly.append({'month': month, 'count': count})
    
    # Employer cost by month (current year)
    employer_cost_monthly = []
    for month in range(1, 13):
        cost = db.session.query(func.sum(Payroll.gross_salary)).filter(
            Payroll.year == current_year,
            Payroll.month == month
        ).scalar() or 0
        employer_cost_monthly.append({'month': month, 'cost': float(cost)})
    
    # Employer cost by year (last 5 years)
    employer_cost_annual = []
    for year in range(current_year - 4, current_year + 1):
        cost = db.session.query(func.sum(Payroll.gross_salary)).filter(
            Payroll.year == year
        ).scalar() or 0
        employer_cost_annual.append({'year': year, 'cost': float(cost)})
    
    return render_template('payroll/dashboard.html',
                         employees_without_bank=employees_without_bank,
                         employees_without_manager=employees_without_manager,
                         payruns=payruns,
                         employee_count_monthly=employee_count_monthly,
                         employer_cost_monthly=employer_cost_monthly,
                         employer_cost_annual=employer_cost_annual)

@bp.route('/generate', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'Payroll Officer'])
def generate():
    # Only Admin and Payroll Officer can generate payroll
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
        if not settings or (settings.wage == 0 and settings.basic_salary == 0):
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
        if not settings or (settings.wage == 0 and settings.basic_salary == 0):
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
    # HR Officer cannot view payroll
    if current_user.role == 'Employee' and payroll.user_id != current_user.id:
        abort(403)
    
    if current_user.role == 'HR Officer':
        abort(403)
    
    return render_template('payroll/payslip.html', payroll=payroll)

@bp.route('/<int:payroll_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'Payroll Officer'])
def edit(payroll_id):
    # Only Admin and Payroll Officer can edit payroll
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
@role_required(['Employee'])
def my_payslips():
    # Only employees can access their own payslips
    payrolls = Payroll.query.filter_by(user_id=current_user.id).order_by(
        Payroll.year.desc(), Payroll.month.desc()
    ).all()
    
    return render_template('payroll/my_payslips.html', payrolls=payrolls)

@bp.route('/salary-structure', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'Payroll Officer'])
def salary_structure_list():
    # Only Admin and Payroll Officer can manage salary structures
    # HR Officer cannot access
    """List all employees and their salary structures"""
    employees = User.query.filter_by(role='Employee').order_by(User.name).all()
    employee_settings = {}
    for emp in employees:
        settings = PayrollSettings.query.filter_by(user_id=emp.id).first()
        if settings:
            # Safely get component count
            try:
                settings.component_count = settings.salary_components.count()
            except Exception:
                # Table doesn't exist
                settings.component_count = 0
        employee_settings[emp.id] = settings
    
    return render_template('payroll/salary_structure_list.html', 
                         employees=employees,
                         employee_settings=employee_settings)

@bp.route('/salary-structure/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required(['Admin', 'Payroll Officer'])
def salary_structure(user_id):
    # Only Admin and Payroll Officer can set salary structures
    # HR Officer cannot access
    """Set or update salary structure for an employee"""
    from decimal import Decimal
    
    user = User.query.get_or_404(user_id)
    
    # Salary structure can only be set for employees
    if user.role != 'Employee':
        abort(403)
    
    settings = PayrollSettings.query.filter_by(user_id=user_id).first()
    
    # Default component definitions
    DEFAULT_COMPONENTS = [
        {'name': 'Basic', 'computation_type': 'Percentage', 'value': 50.0, 'base_for_percentage': 'Wage', 'display_order': 1},
        {'name': 'House Rent Allowance', 'computation_type': 'Percentage', 'value': 50.0, 'base_for_percentage': 'Basic', 'display_order': 2},
        {'name': 'Standard Allowance', 'computation_type': 'Fixed', 'value': 4167.0, 'base_for_percentage': 'Wage', 'display_order': 3},
        {'name': 'Performance Bonus', 'computation_type': 'Percentage', 'value': 8.33, 'base_for_percentage': 'Wage', 'display_order': 4},
        {'name': 'Leave Travel Allowance', 'computation_type': 'Percentage', 'value': 8.333, 'base_for_percentage': 'Wage', 'display_order': 5},
        {'name': 'Fixed Allowance', 'computation_type': 'Fixed', 'value': 0.0, 'base_for_percentage': 'Wage', 'display_order': 6},  # Will be calculated as remaining
    ]
    
    if not settings:
        # Create new settings with default wage
        settings = PayrollSettings(
            user_id=user_id,
            wage=0.0,
            wage_type='Fixed',
            pf_percentage=12.0,
            professional_tax_amount=200.0
        )
        db.session.add(settings)
        db.session.flush()
        
        # Create default components if they don't exist
        for comp_def in DEFAULT_COMPONENTS:
            component = SalaryComponent(
                payroll_settings_id=settings.id,
                name=comp_def['name'],
                computation_type=comp_def['computation_type'],
                value=comp_def['value'],
                base_for_percentage=comp_def['base_for_percentage'],
                display_order=comp_def['display_order']
            )
            db.session.add(component)
        db.session.commit()
    
    if request.method == 'POST':
        wage = float(request.form.get('wage', 0))
        pf_percentage = float(request.form.get('pf_percentage', 12.0))
        professional_tax_amount = float(request.form.get('professional_tax_amount', 200.0))
        
        errors = []
        
        if wage <= 0:
            errors.append('Wage must be greater than 0')
        
        if pf_percentage < 0 or pf_percentage > 100:
            errors.append('PF percentage must be between 0 and 100')
        
        if professional_tax_amount < 0:
            errors.append('Professional tax cannot be negative')
        
        # Get component data from form
        component_names = request.form.getlist('component_name[]')
        component_types = request.form.getlist('component_type[]')
        component_values = request.form.getlist('component_value[]')
        component_bases = request.form.getlist('component_base[]')
        component_orders = request.form.getlist('component_order[]')
        
        # Validate and process components
        components_data = []
        
        # First pass: Store all component data
        for i, name in enumerate(component_names):
            if i < len(component_types) and i < len(component_values) and i < len(component_bases):
                comp_type = component_types[i]
                try:
                    comp_value = float(component_values[i])
                except (ValueError, TypeError):
                    comp_value = 0.0
                comp_base = component_bases[i] if i < len(component_bases) else 'Wage'
                comp_order = int(component_orders[i]) if i < len(component_orders) and component_orders[i] else i + 1
                
                components_data.append({
                    'name': name,
                    'type': comp_type,
                    'value': comp_value,
                    'base': comp_base,
                    'order': comp_order,
                    'amount': 0.0  # Will be calculated
                })
        
        # Second pass: Calculate Basic first
        basic_amount = 0.0
        for comp in components_data:
            if comp['name'] == 'Basic':
                if comp['type'] == 'Percentage':
                    basic_amount = wage * comp['value'] / 100.0
                else:
                    basic_amount = comp['value']
                comp['amount'] = basic_amount
                break
        
        # Third pass: Calculate all other components
        total_components = 0.0
        for comp in components_data:
            if comp['name'] == 'Fixed Allowance':
                # Skip Fixed Allowance for now
                continue
            
            if comp['amount'] > 0:
                # Already calculated (Basic)
                total_components += comp['amount']
            elif comp['type'] == 'Fixed':
                comp['amount'] = comp['value']
                total_components += comp['amount']
            elif comp['type'] == 'Percentage':
                if comp['base'] == 'Basic' and basic_amount > 0:
                    comp['amount'] = basic_amount * comp['value'] / 100.0
                else:
                    comp['amount'] = wage * comp['value'] / 100.0
                total_components += comp['amount']
        
        # Fourth pass: Calculate Fixed Allowance (remaining amount)
        remaining = wage - total_components
        for comp in components_data:
            if comp['name'] == 'Fixed Allowance':
                comp['amount'] = max(0, remaining)  # Ensure non-negative
                comp['value'] = comp['amount']  # Update the value to the calculated amount
                total_components += comp['amount']
                break
        
        # Validate total doesn't exceed wage
        if total_components > wage + 0.01:  # Allow small floating point differences
            errors.append(f'Total of all components (₹{total_components:,.2f}) exceeds wage (₹{wage:,.2f})')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            # Update settings
            settings.wage = wage
            settings.wage_type = 'Fixed'
            settings.pf_percentage = pf_percentage
            settings.professional_tax_amount = professional_tax_amount
            settings.updated_at = datetime.utcnow()
            
            # Delete existing components and recreate
            try:
                SalaryComponent.query.filter_by(payroll_settings_id=settings.id).delete()
            except Exception as e:
                # Table doesn't exist - rollback and show error
                db.session.rollback()
                flash(f'Salary components table not found. Please run: python create_tables.py to create the table.', 'danger')
                # Get default components for display
                components = []
                for comp_def in DEFAULT_COMPONENTS:
                    components.append(type('Component', (), {
                        'name': comp_def['name'],
                        'computation_type': comp_def['computation_type'],
                        'value': comp_def['value'],
                        'base_for_percentage': comp_def['base_for_percentage'],
                        'display_order': comp_def['display_order']
                    })())
                components = sorted(components, key=lambda x: x.display_order)
                return render_template('payroll/salary_structure.html', user=user, settings=settings, components=components)
            
            for comp_data in components_data:
                component = SalaryComponent(
                    payroll_settings_id=settings.id,
                    name=comp_data['name'],
                    computation_type=comp_data['type'],
                    value=comp_data['value'],
                    base_for_percentage=comp_data['base'],
                    display_order=comp_data['order']
                )
                db.session.add(component)
            
            db.session.commit()
            flash(f'Salary structure for {user.name} updated successfully!', 'success')
            return redirect(url_for('payroll.salary_structure_list'))
    
    # GET request - get components or use defaults
    components = []
    if settings:
        try:
            components = list(settings.salary_components.all())
        except Exception as e:
            # Handle case where salary_components table doesn't exist
            # Rollback the failed transaction first
            try:
                db.session.rollback()
            except:
                pass
            # Don't try to create table here - it causes transaction issues
            # Just show error message
            flash(f'Salary components table not found. Please run: python create_tables.py to create the table.', 'danger')
            components = []
    if not components:
        # Create default components for display
        components = []
        for comp_def in DEFAULT_COMPONENTS:
            components.append(type('Component', (), {
                'name': comp_def['name'],
                'computation_type': comp_def['computation_type'],
                'value': comp_def['value'],
                'base_for_percentage': comp_def['base_for_percentage'],
                'display_order': comp_def['display_order']
            })())
    
    # Sort components by display order
    components = sorted(components, key=lambda x: x.display_order)
    
    return render_template('payroll/salary_structure.html', user=user, settings=settings, components=components)

