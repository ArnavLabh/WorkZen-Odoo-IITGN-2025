import re
from datetime import datetime, date

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    pattern = r'^[0-9]{10}$'
    return re.match(pattern, phone) is not None

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def validate_date_range(start_date, end_date):
    if start_date > end_date:
        return False, "Start date must be before or equal to end date"
    return True, "Date range is valid"

def validate_employee_id(employee_id):
    if not employee_id or len(employee_id.strip()) == 0:
        return False, "Employee ID cannot be empty"
    return True, "Employee ID is valid"

