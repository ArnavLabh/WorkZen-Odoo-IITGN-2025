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
    
    # Profile fields
    profile_picture = db.Column(db.String(255))
    job_position = db.Column(db.String(100))
    company = db.Column(db.String(100))
    department = db.Column(db.String(100))
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    location = db.Column(db.String(100))
    
    # Private info fields
    date_of_birth = db.Column(db.Date)
    nationality = db.Column(db.String(50))
    personal_email = db.Column(db.String(120))
    gender = db.Column(db.String(20))
    marital_status = db.Column(db.String(20))
    
    # Bank details
    bank_account_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(100))
    ifsc_code = db.Column(db.String(20))
    pan_number = db.Column(db.String(20))
    uan_number = db.Column(db.String(20))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attendances = db.relationship('Attendance', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    leaves = db.relationship('Leave', foreign_keys='Leave.user_id', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    payrolls = db.relationship('Payroll', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    payroll_settings = db.relationship('PayrollSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    approved_leaves = db.relationship('Leave', foreign_keys='Leave.approved_by', backref='approver', lazy='dynamic')
    manager = db.relationship('User', remote_side=[id], backref='subordinates')
    
    @property
    def has_missing_bank_info(self):
        """Check if employee has missing bank information"""
        return not self.bank_account_number or not self.bank_name or not self.ifsc_code
    
    @property
    def has_missing_manager(self):
        """Check if employee has no manager assigned"""
        return self.manager_id is None
    
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
    extra_hours = db.Column(db.Float, default=0.0)  # Hours worked beyond standard 8 hours
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    check_logs = db.relationship('AttendanceLog', backref='attendance', lazy='dynamic', cascade='all, delete-orphan', order_by='AttendanceLog.timestamp')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)
    
    def calculate_working_hours(self):
        """Calculate total working hours from all check-in/check-out logs"""
        total_hours = 0.0
        logs = list(self.check_logs.order_by('timestamp').all())
        
        # Pair check-ins with check-outs
        i = 0
        while i < len(logs):
            if logs[i].log_type == 'check_in':
                # Find next check-out
                j = i + 1
                while j < len(logs) and logs[j].log_type != 'check_out':
                    j += 1
                
                if j < len(logs):
                    # Calculate hours between check-in and check-out
                    check_in_dt = datetime.combine(self.date, logs[i].timestamp)
                    check_out_dt = datetime.combine(self.date, logs[j].timestamp)
                    delta = check_out_dt - check_in_dt
                    total_hours += delta.total_seconds() / 3600.0
                    i = j + 1
                else:
                    # No matching check-out
                    break
            else:
                i += 1
        
        self.working_hours = total_hours
        return self.working_hours
    
    def __repr__(self):
        return f'<Attendance {self.user_id}: {self.date}>'

class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.Integer, db.ForeignKey('attendances.id'), nullable=False, index=True)
    log_type = db.Column(db.String(20), nullable=False)  # check_in, check_out
    timestamp = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AttendanceLog {self.attendance_id}: {self.log_type} at {self.timestamp}>'

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
    # Note: wage and wage_type are NOT database columns - they are calculated from salary_components
    # We use a property to access wage without storing it in the database
    pf_percentage = db.Column(db.Float, default=12.0)  # Default 12%
    professional_tax_amount = db.Column(db.Numeric(10, 2), default=200.0)  # Default 200
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    salary_components = db.relationship('SalaryComponent', backref='payroll_settings', lazy='dynamic', cascade='all, delete-orphan', order_by='SalaryComponent.display_order')
    
    # Valid column names - used to filter out invalid attributes
    _valid_columns = {
        'id', 'user_id', 'basic_salary', 'hra_percentage', 'conveyance', 
        'other_allowances', 'pf_percentage', 'professional_tax_amount',
        'created_at', 'updated_at'
    }
    
    def __init__(self, **kwargs):
        # Only allow valid model columns to be set
        # This prevents SQLAlchemy from trying to insert columns that don't exist in the database
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self._valid_columns}
        super(PayrollSettings, self).__init__(**filtered_kwargs)
        # Store wage/wage_type as non-persistent attributes (not in database)
        if 'wage' in kwargs:
            object.__setattr__(self, '_wage', kwargs['wage'])
        if 'wage_type' in kwargs:
            object.__setattr__(self, '_wage_type', kwargs.get('wage_type', 'Fixed'))
    
    @property
    def wage(self):
        """
        Get wage value. 
        Since wage is not a database column, we return:
        1. Stored _wage if explicitly set (during form processing)
        2. Otherwise, calculate from salary components if they exist
        3. Otherwise, return basic_salary as fallback
        """
        # If _wage is explicitly set (during form processing), return it
        if hasattr(self, '_wage'):
            stored_wage = getattr(self, '_wage', 0.0)
            if stored_wage is not None:
                return float(stored_wage)
        
        # Try to calculate from salary components
        # This is a simplified calculation - the actual calculation with percentages
        # happens in the payroll route when processing the form
        try:
            components = self.salary_components.filter_by(is_active=True).all()
            if components:
                # Sum all fixed components
                # For percentage components, we can't calculate without knowing the base wage
                # So we'll use a simple sum of fixed values as an approximation
                total = sum(float(comp.value) for comp in components if comp.computation_type == 'Fixed')
                # If we have a meaningful total, return it
                if total > 0:
                    return total
        except Exception:
            # Table doesn't exist or other error - fall back to basic_salary
            pass
        
        # Fallback to basic_salary
        return float(self.basic_salary) if self.basic_salary else 0.0
    
    @wage.setter
    def wage(self, value):
        """Store wage as non-persistent attribute"""
        object.__setattr__(self, '_wage', float(value) if value else 0.0)
    
    @property
    def wage_type(self):
        """Return wage type (always 'Fixed' for now)"""
        return getattr(self, '_wage_type', 'Fixed')
    
    @wage_type.setter
    def wage_type(self, value):
        """Store wage_type as non-persistent attribute"""
        object.__setattr__(self, '_wage_type', value or 'Fixed')
    
    def __repr__(self):
        return f'<PayrollSettings {self.user_id}>'
    
    def get_component_by_name(self, name):
        """Get a salary component by its name"""
        try:
            return self.salary_components.filter_by(name=name).first()
        except Exception:
            # Table doesn't exist - return None
            return None

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
    payrun_id = db.Column(db.Integer, db.ForeignKey('payruns.id'), index=True)
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

class Payrun(db.Model):
    __tablename__ = 'payruns'
    
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False, index=True)
    payslip_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payrolls = db.relationship('Payroll', backref='payrun', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])
    
    __table_args__ = (db.UniqueConstraint('month', 'year', name='unique_month_year'),)
    
    def __repr__(self):
        return f'<Payrun {self.month}/{self.year}: {self.payslip_count} payslips>'

