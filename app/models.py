from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # Admin, Employee, HR Officer, Payroll Officer
    date_of_joining = db.Column(db.Date, nullable=False)
    contact_number = db.Column(db.String(20))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attendances = db.relationship('Attendance', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    leaves = db.relationship('Leave', foreign_keys='Leave.user_id', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    payrolls = db.relationship('Payroll', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    payroll_settings = db.relationship('PayrollSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    approved_leaves = db.relationship('Leave', foreign_keys='Leave.approved_by', backref='approver', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.employee_id}: {self.name}>'

class Attendance(db.Model):
    __tablename__ = 'attendances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.Time)
    check_out = db.Column(db.Time)
    status = db.Column(db.String(20), nullable=False, default='Absent')  # Present, Absent, Half Day
    working_hours = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)
    
    def calculate_working_hours(self):
        if self.check_in and self.check_out:
            from datetime import datetime, date
            check_in_dt = datetime.combine(date.today(), self.check_in)
            check_out_dt = datetime.combine(date.today(), self.check_out)
            delta = check_out_dt - check_in_dt
            self.working_hours = delta.total_seconds() / 3600.0
        return self.working_hours
    
    def __repr__(self):
        return f'<Attendance {self.user_id}: {self.date}>'

class Leave(db.Model):
    __tablename__ = 'leaves'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    leave_type = db.Column(db.String(50), nullable=False)  # Sick Leave, Casual Leave, Annual Leave, etc.
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending, Approved, Rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Leave {self.user_id}: {self.leave_type} - {self.status}>'

class PayrollSettings(db.Model):
    __tablename__ = 'payroll_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    # Legacy fields (kept for backward compatibility)
    basic_salary = db.Column(db.Numeric(10, 2), default=0.0, nullable=True)
    hra_percentage = db.Column(db.Float, default=0.0)
    conveyance = db.Column(db.Numeric(10, 2), default=0.0)
    other_allowances = db.Column(db.Numeric(10, 2), default=0.0)
    # New fields
    wage = db.Column(db.Numeric(10, 2), default=0.0)  # Fixed wage amount
    wage_type = db.Column(db.String(20), default='Fixed')  # Currently only 'Fixed' is supported
    pf_percentage = db.Column(db.Float, default=12.0)  # Default 12%
    professional_tax_amount = db.Column(db.Numeric(10, 2), default=200.0)  # Default 200
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    salary_components = db.relationship('SalaryComponent', backref='payroll_settings', lazy='dynamic', cascade='all, delete-orphan', order_by='SalaryComponent.display_order')
    
    def __repr__(self):
        return f'<PayrollSettings {self.user_id}>'
    
    def get_component_by_name(self, name):
        """Get a salary component by its name"""
        return self.salary_components.filter_by(name=name).first()

class SalaryComponent(db.Model):
    __tablename__ = 'salary_components'
    
    id = db.Column(db.Integer, primary_key=True)
    payroll_settings_id = db.Column(db.Integer, db.ForeignKey('payroll_settings.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)  # Basic, HRA, Standard Allowance, etc.
    computation_type = db.Column(db.String(20), nullable=False)  # 'Fixed' or 'Percentage'
    value = db.Column(db.Numeric(10, 4), nullable=False)  # Fixed amount or percentage value
    base_for_percentage = db.Column(db.String(50), default='Wage')  # 'Wage' or 'Basic' - what the percentage is calculated from
    display_order = db.Column(db.Integer, default=0)  # Order in which components are displayed
    is_active = db.Column(db.Boolean, default=True)  # Whether this component is active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('payroll_settings_id', 'name', name='unique_settings_component'),)
    
    def __repr__(self):
        return f'<SalaryComponent {self.name} - {self.computation_type}>'
    
    def calculate_amount(self, wage, basic_amount=None):
        """Calculate the component amount based on wage and computation type"""
        from decimal import Decimal
        wage_decimal = Decimal(str(wage))
        value_decimal = Decimal(str(self.value))
        
        if self.computation_type == 'Fixed':
            return float(value_decimal)
        elif self.computation_type == 'Percentage':
            if self.base_for_percentage == 'Basic' and basic_amount:
                base = Decimal(str(basic_amount))
            else:
                base = wage_decimal
            return float(base * value_decimal / Decimal('100'))
        return 0.0

class Payroll(db.Model):
    __tablename__ = 'payrolls'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False, index=True)
    basic_salary = db.Column(db.Numeric(10, 2), nullable=False)
    hra = db.Column(db.Numeric(10, 2), default=0.0)
    conveyance = db.Column(db.Numeric(10, 2), default=0.0)
    other_allowances = db.Column(db.Numeric(10, 2), default=0.0)
    gross_salary = db.Column(db.Numeric(10, 2), nullable=False)
    pf_contribution = db.Column(db.Numeric(10, 2), default=0.0)
    professional_tax = db.Column(db.Numeric(10, 2), default=0.0)
    other_deductions = db.Column(db.Numeric(10, 2), default=0.0)
    total_deductions = db.Column(db.Numeric(10, 2), default=0.0)
    net_salary = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Unpaid')  # Paid, Unpaid
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'month', 'year', name='unique_user_month_year'),)
    
    def __repr__(self):
        return f'<Payroll {self.user_id}: {self.month}/{self.year}>'

