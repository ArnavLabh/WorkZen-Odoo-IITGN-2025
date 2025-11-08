"""
Utility functions for employee management
"""
import secrets
import string
from datetime import datetime
from app import db
from app.models import User


def generate_login_id(first_name, last_name, date_of_joining):
    """
    Generate login ID in format: OI[First2FirstName][First2LastName][Year][SerialNumber]
    Example: OIJODO20220001
    
    Args:
        first_name: Employee's first name
        last_name: Employee's last name
        date_of_joining: Date of joining (date object)
    
    Returns:
        Generated login ID string
    """
    import re
    
    # Extract only alphabetic characters and take first 2 letters
    first_alpha = re.sub(r'[^A-Za-z]', '', first_name)
    last_alpha = re.sub(r'[^A-Za-z]', '', last_name)
    
    # Extract first 2 letters of first name (uppercase)
    if len(first_alpha) >= 2:
        first_initials = first_alpha[:2].upper()
    elif len(first_alpha) == 1:
        first_initials = first_alpha.upper() + 'X'
    else:
        first_initials = 'XX'  # Fallback if no alphabetic characters
    
    # Extract first 2 letters of last name (uppercase)
    if len(last_alpha) >= 2:
        last_initials = last_alpha[:2].upper()
    elif len(last_alpha) == 1:
        last_initials = last_alpha.upper() + 'X'
    else:
        last_initials = 'XX'  # Fallback if no alphabetic characters
    
    # Get year of joining
    year = str(date_of_joining.year)
    
    # Find the serial number for this year
    # Get all users who joined in the same year
    year_start = datetime(date_of_joining.year, 1, 1).date()
    year_end = datetime(date_of_joining.year, 12, 31).date()
    
    existing_users = User.query.filter(
        User.date_of_joining >= year_start,
        User.date_of_joining <= year_end
    ).count()
    
    # Serial number is 1-based, so add 1 to count
    serial_number = existing_users + 1
    
    # Format serial number as 4-digit string (e.g., 0001)
    serial_str = f"{serial_number:04d}"
    
    # Combine: OI + First2 + Last2 + Year + Serial
    login_id = f"OI{first_initials}{last_initials}{year}{serial_str}"
    
    # Ensure uniqueness (in case of collision)
    counter = 0
    while User.query.filter_by(employee_id=login_id).first():
        counter += 1
        serial_number = existing_users + 1 + counter
        serial_str = f"{serial_number:04d}"
        login_id = f"OI{first_initials}{last_initials}{year}{serial_str}"
    
    return login_id


def generate_random_password(length=12):
    """
    Generate a random secure password
    
    Args:
        length: Length of the password (default: 12)
    
    Returns:
        Generated password string
    """
    # Define character sets
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    
    # Ensure at least one of each required type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*")
    ]
    
    # Fill the rest randomly
    for _ in range(length - 4):
        password.append(secrets.choice(alphabet))
    
    # Shuffle to randomize position
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

