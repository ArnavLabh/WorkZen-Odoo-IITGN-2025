from decimal import Decimal
from datetime import datetime, date, timedelta
from app import db
from app.models import Attendance, Leave, PayrollSettings

def calculate_gross_salary(basic_salary, hra_percentage, conveyance, other_allowances):
    """Calculate gross salary from components"""
    basic = Decimal(str(basic_salary))
    hra = basic * Decimal(str(hra_percentage)) / Decimal('100')
    conveyance = Decimal(str(conveyance))
    other_allowances = Decimal(str(other_allowances))
    return basic + hra + conveyance + other_allowances

def calculate_pf(basic_salary, pf_percentage=12.0):
    """Calculate PF contribution (employee contribution)"""
    basic = Decimal(str(basic_salary))
    pf = basic * Decimal(str(pf_percentage)) / Decimal('100')
    return pf

def calculate_professional_tax(professional_tax_amount=200.0):
    """Return professional tax amount"""
    return Decimal(str(professional_tax_amount))

def calculate_net_salary(gross_salary, pf_contribution, professional_tax, other_deductions=0.0):
    """Calculate net salary after all deductions"""
    gross = Decimal(str(gross_salary))
    pf = Decimal(str(pf_contribution))
    pt = Decimal(str(professional_tax))
    other = Decimal(str(other_deductions))
    total_deductions = pf + pt + other
    net = gross - total_deductions
    return net, total_deductions

def get_attendance_days(user_id, month, year):
    """Get number of present days for a user in a given month/year"""
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    present_days = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date,
        Attendance.status == 'Present'
    ).count()
    
    half_days = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date,
        Attendance.status == 'Half Day'
    ).count()
    
    return present_days, half_days

def get_approved_leaves(user_id, month, year):
    """Get number of approved leave days for a user in a given month/year"""
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    leaves = Leave.query.filter(
        Leave.user_id == user_id,
        Leave.status == 'Approved',
        Leave.start_date <= end_date,
        Leave.end_date >= start_date
    ).all()
    
    total_days = 0
    for leave in leaves:
        # Calculate overlapping days
        leave_start = max(leave.start_date, start_date)
        leave_end = min(leave.end_date, end_date)
        if leave_start <= leave_end:
            total_days += (leave_end - leave_start).days + 1
    
    return total_days

def calculate_monthly_salary(user_id, month, year, settings):
    """Calculate monthly salary based on attendance and leaves"""
    if not settings:
        return None
    
    # Get attendance and leave data
    present_days, half_days = get_attendance_days(user_id, month, year)
    leave_days = get_approved_leaves(user_id, month, year)
    
    # Calculate working days in month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    total_days = (end_date - start_date).days + 1
    working_days = total_days - leave_days
    
    # Calculate salary components
    basic_salary = Decimal(str(settings.basic_salary))
    hra_percentage = Decimal(str(settings.hra_percentage))
    conveyance = Decimal(str(settings.conveyance))
    other_allowances = Decimal(str(settings.other_allowances))
    
    # Calculate monthly gross (assuming full month)
    monthly_gross = calculate_gross_salary(basic_salary, hra_percentage, conveyance, other_allowances)
    
    # For now, we calculate full month salary
    # In a more advanced system, you might prorate based on working days
    gross_salary = monthly_gross
    
    # Calculate deductions
    pf_contribution = calculate_pf(basic_salary, settings.pf_percentage)
    professional_tax = calculate_professional_tax(settings.professional_tax_amount)
    other_deductions = Decimal('0.0')
    
    # Calculate net salary
    net_salary, total_deductions = calculate_net_salary(
        gross_salary, pf_contribution, professional_tax, other_deductions
    )
    
    return {
        'basic_salary': float(basic_salary),
        'hra': float(monthly_gross - basic_salary - conveyance - other_allowances),
        'conveyance': float(conveyance),
        'other_allowances': float(other_allowances),
        'gross_salary': float(gross_salary),
        'pf_contribution': float(pf_contribution),
        'professional_tax': float(professional_tax),
        'other_deductions': float(other_deductions),
        'total_deductions': float(total_deductions),
        'net_salary': float(net_salary),
        'present_days': present_days,
        'half_days': half_days,
        'leave_days': leave_days,
        'working_days': working_days,
        'total_days': total_days
    }

