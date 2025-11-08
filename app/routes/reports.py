from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, Leave, Payroll, User
from app.utils.decorators import employee_or_above_required, payroll_required, role_required
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_, and_

bp = Blueprint('reports', __name__)

@bp.route('/')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def generate():
    # Only Admin and Payroll Officer can access reports
    # Employees and HR Officer cannot access
    return render_template('reports/generate.html')

@bp.route('/attendance')
@login_required
@role_required(['Admin', 'HR Officer', 'Payroll Officer'])
def attendance():
    # Only Admin, HR Officer, and Payroll Officer can access attendance reports
    # Employees cannot access reports
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_id = request.args.get('user_id', '')
    
    query = Attendance.query
    
    # Filter by user
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by date range
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= end)
        except ValueError:
            pass
    
    attendances = query.order_by(Attendance.date.desc()).all()
    
    # Calculate statistics
    total_days = len(attendances)
    present_days = sum(1 for a in attendances if a.status == 'Present')
    absent_days = sum(1 for a in attendances if a.status == 'Absent')
    half_days = sum(1 for a in attendances if a.status == 'Half Day')
    total_hours = sum(a.working_hours for a in attendances)
    
    # Get users for filter
    users = []
    if current_user.role in ['Admin', 'HR Officer', 'Payroll Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/attendance_report.html',
                         attendances=attendances,
                         start_date=start_date,
                         end_date=end_date,
                         user_id=user_id,
                         users=users,
                         total_days=total_days,
                         present_days=present_days,
                         absent_days=absent_days,
                         half_days=half_days,
                         total_hours=total_hours)

@bp.route('/leave')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def leave():
    # Only Admin and Payroll Officer can access leave reports
    # HR Officer and Employees cannot access
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_id = request.args.get('user_id', '')
    status_filter = request.args.get('status', '')
    
    query = Leave.query
    
    # Filter by user
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by status
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Filter by date range
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Leave.start_date >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Leave.end_date <= end)
        except ValueError:
            pass
    
    leaves = query.order_by(Leave.created_at.desc()).all()
    
    # Calculate statistics
    total_leaves = len(leaves)
    approved_leaves = sum(1 for l in leaves if l.status == 'Approved')
    rejected_leaves = sum(1 for l in leaves if l.status == 'Rejected')
    pending_leaves = sum(1 for l in leaves if l.status == 'Pending')
    total_days = sum((l.end_date - l.start_date).days + 1 for l in leaves if l.status == 'Approved')
    
    # Get users for filter
    users = []
    if current_user.role in ['Admin', 'HR Officer', 'Payroll Officer']:
        users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/leave_report.html',
                         leaves=leaves,
                         start_date=start_date,
                         end_date=end_date,
                         user_id=user_id,
                         status_filter=status_filter,
                         users=users,
                         total_leaves=total_leaves,
                         approved_leaves=approved_leaves,
                         rejected_leaves=rejected_leaves,
                         pending_leaves=pending_leaves,
                         total_days=total_days)

@bp.route('/payroll')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def payroll():
    # Only Admin and Payroll Officer can access payroll reports
    start_month = request.args.get('start_month', '')
    start_year = request.args.get('start_year', '')
    end_month = request.args.get('end_month', '')
    end_year = request.args.get('end_year', '')
    user_id = request.args.get('user_id', '')
    
    query = Payroll.query
    
    # Filter by user
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Filter by date range
    if start_year and start_month:
        query = query.filter(
            or_(
                Payroll.year > int(start_year),
                and_(Payroll.year == int(start_year), Payroll.month >= int(start_month))
            )
        )
    
    if end_year and end_month:
        query = query.filter(
            or_(
                Payroll.year < int(end_year),
                and_(Payroll.year == int(end_year), Payroll.month <= int(end_month))
            )
        )
    
    payrolls = query.order_by(Payroll.year.desc(), Payroll.month.desc()).all()
    
    # Calculate statistics
    total_payrolls = len(payrolls)
    total_gross = sum(float(p.gross_salary) for p in payrolls)
    total_deductions = sum(float(p.total_deductions) for p in payrolls)
    total_net = sum(float(p.net_salary) for p in payrolls)
    paid_count = sum(1 for p in payrolls if p.status == 'Paid')
    
    # Get users for filter
    users = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    return render_template('reports/payroll_report.html',
                         payrolls=payrolls,
                         start_month=start_month,
                         start_year=start_year,
                         end_month=end_month,
                         end_year=end_year,
                         user_id=user_id,
                         users=users,
                         total_payrolls=total_payrolls,
                         total_gross=total_gross,
                         total_deductions=total_deductions,
                         total_net=total_net,
                         paid_count=paid_count)


@bp.route('/salary-statement')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def salary_statement():
    # Only Admin and Payroll Officer can access salary statement report
    employee_id = request.args.get('employee_id', '')
    year_filter = request.args.get('year', '')
    
    # Get employees for dropdown
    employees = User.query.filter_by(role='Employee').order_by(User.name).all()
    
    # Get years for dropdown (last 5 years)
    current_year = datetime.now().year
    years = list(range(current_year - 4, current_year + 1))
    
    payrolls = []
    selected_employee = None
    annual_summary = None
    
    if employee_id and year_filter:
        # Find employee
        selected_employee = User.query.get(employee_id)
        
        if selected_employee:
            # Get payrolls for the year
            payrolls = Payroll.query.filter_by(
                user_id=selected_employee.id,
                year=int(year_filter)
            ).order_by(Payroll.month).all()
            
            # Calculate annual summary
            if payrolls:
                annual_summary = {
                    'total_gross': sum(p.gross_salary for p in payrolls),
                    'total_deductions': sum(p.total_deductions for p in payrolls),
                    'total_net': sum(p.net_salary for p in payrolls),
                    'months_paid': len(payrolls)
                }
    
    return render_template('reports/salary_statement.html',
                         employees=employees,
                         years=years,
                         payrolls=payrolls,
                         selected_employee=selected_employee,
                         annual_summary=annual_summary,
                         employee_id=employee_id,
                         year_filter=year_filter)

@bp.route('/salary-statement/pdf')
@login_required
@role_required(['Admin', 'Payroll Officer'])
def salary_statement_pdf():
    employee_id = request.args.get('employee_id', '')
    year_filter = request.args.get('year', '')
    
    if not employee_id or not year_filter:
        flash('Please select employee and year', 'danger')
        return redirect(url_for('reports.salary_statement'))
    
    selected_employee = User.query.get_or_404(employee_id)
    payrolls = Payroll.query.filter_by(
        user_id=selected_employee.id,
        year=int(year_filter)
    ).order_by(Payroll.month).all()
    
    if not payrolls:
        flash('No salary data found for selected employee and year', 'warning')
        return redirect(url_for('reports.salary_statement'))
    
    from app.models import CompanySettings
    from flask import make_response
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get company name
    company_name = CompanySettings.get_setting('company_name', 'WorkZen')
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0891b2')
    )
    
    # Build PDF content
    story = []
    
    # Company Header
    story.append(Paragraph(f"<b>{company_name}</b>", title_style))
    story.append(Paragraph(f"Annual Salary Statement - {year_filter}", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Employee Info
    employee_data = [
        ['Employee Name:', selected_employee.name],
        ['Employee ID:', selected_employee.employee_id],
        ['Department:', selected_employee.department or 'N/A'],
        ['Year:', year_filter],
        ['Report Generated:', datetime.now().strftime('%d %B %Y')]
    ]
    
    employee_table = Table(employee_data, colWidths=[2*inch, 3*inch])
    employee_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(employee_table)
    story.append(Spacer(1, 20))
    
    # Monthly Breakdown
    story.append(Paragraph("<b>Monthly Breakdown</b>", styles['Heading3']))
    
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    monthly_data = [['Month', 'Gross Salary (₹)', 'Deductions (₹)', 'Net Salary (₹)']]
    
    total_gross = 0
    total_deductions = 0
    total_net = 0
    
    for payroll in payrolls:
        monthly_data.append([
            month_names[payroll.month],
            f"{payroll.gross_salary:,.2f}",
            f"{payroll.total_deductions:,.2f}",
            f"{payroll.net_salary:,.2f}"
        ])
        total_gross += payroll.gross_salary
        total_deductions += payroll.total_deductions
        total_net += payroll.net_salary
    
    # Add totals row
    monthly_data.append(['', '', '', ''])
    monthly_data.append([
        'TOTAL',
        f"{total_gross:,.2f}",
        f"{total_deductions:,.2f}",
        f"{total_net:,.2f}"
    ])
    
    monthly_table = Table(monthly_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    monthly_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#0891b2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.white),
    ]))
    
    story.append(monthly_table)
    
    # Build PDF
    doc.build(story)
    
    # Return PDF
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    buffer.close()
    
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=salary_statement_{selected_employee.employee_id}_{year_filter}.pdf'
    
    return response
