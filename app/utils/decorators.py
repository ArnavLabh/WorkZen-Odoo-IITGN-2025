"""
Role-Based Access Control (RBAC) Decorators

This module provides decorators for enforcing role-based access control
across all routes in the application.

Role Definitions:
- Admin: Full access to all modules and operations
- Employee: Limited access to own data, time off, attendance, and read-only directory
- HR Officer: Employee management, attendance monitoring, leave allocation
- Payroll Officer: Payroll management, leave approval, reports
"""
from functools import wraps
from flask import abort, jsonify, request
from flask_login import current_user


def role_required(allowed_roles):
    """
    Decorator to restrict access to specific roles.
    
    Args:
        allowed_roles: List of role names that are allowed to access the route.
                      If a single string is provided, it will be converted to a list.
                      Admin always has access regardless of the allowed_roles.
    
    Usage:
        @role_required(['Admin', 'HR Officer'])
        def some_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is authenticated
            if not current_user.is_authenticated:
                if request.is_json or request.content_type == 'application/json':
                    return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
                abort(401)
            
            # Convert single role to list
            if isinstance(allowed_roles, str):
                roles = [allowed_roles]
            else:
                roles = allowed_roles
            
            # Admin always has access
            if current_user.role == 'Admin':
                return f(*args, **kwargs)
            
            # Check if user's role is in allowed roles
            if current_user.role not in roles:
                if request.is_json or request.content_type == 'application/json':
                    return jsonify({'error': 'Forbidden', 'message': 'You do not have permission to access this resource'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to restrict access to Admin only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
            abort(401)
        
        if current_user.role != 'Admin':
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Forbidden', 'message': 'Admin access required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def hr_required(f):
    """Decorator to restrict access to Admin and HR Officer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
            abort(401)
        
        if current_user.role not in ['Admin', 'HR Officer']:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Forbidden', 'message': 'HR Officer or Admin access required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def payroll_required(f):
    """Decorator to restrict access to Admin and Payroll Officer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
            abort(401)
        
        if current_user.role not in ['Admin', 'Payroll Officer']:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Forbidden', 'message': 'Payroll Officer or Admin access required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def employee_or_above_required(f):
    """
    Decorator to ensure user is authenticated.
    All authenticated users (Employee, HR Officer, Payroll Officer, Admin) can access.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
            from flask import redirect, url_for
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def employee_only(f):
    """Decorator to restrict access to Employee role only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Unauthorized', 'message': 'Please log in to access this resource'}), 401
            abort(401)
        
        if current_user.role != 'Employee':
            if request.is_json or request.content_type == 'application/json':
                return jsonify({'error': 'Forbidden', 'message': 'Employee access only'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function
