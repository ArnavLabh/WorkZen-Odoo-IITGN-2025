from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, PayrollSettings
from app.utils.validators import validate_email, validate_password
from config import Config
import requests
from datetime import datetime
from sqlalchemy import or_

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'Admin')
        
        # Validation
        errors = []
        
        if not name:
            errors.append('Name is required')
        
        if not validate_email(email):
            errors.append('Invalid email address')
        
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if not password:
            errors.append('Password is required')
        else:
            is_valid, message = validate_password(password)
            if not is_valid:
                errors.append(message)
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if role not in ['Admin', 'HR Officer']:
            errors.append('Invalid role for registration')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            # Generate employee ID
            employee_id = f"EMP{User.query.count() + 1:04d}"
            while User.query.filter_by(employee_id=employee_id).first():
                employee_id = f"EMP{User.query.count() + 1:04d}"
            
            user = User(
                employee_id=employee_id,
                name=name,
                email=email,
                role=role,
                date_of_joining=db.func.current_date()
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        login_id = request.form.get('email', '').strip()  # Can be email or employee_id
        password = request.form.get('password', '')
        
        if not login_id or not password:
            flash('Please enter both login ID/email and password', 'danger')
            return render_template('auth/login.html')
        
        # Try to find user by email or employee_id
        user = User.query.filter(
            or_(
                User.email == login_id,
                User.employee_id == login_id
            )
        ).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard.dashboard')
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page)
        else:
            flash('Invalid login ID/email or password', 'danger')
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/google')
def google_login():
    """Initiate Google OAuth login"""
    from flask import current_app
    
    # Get Google OAuth configuration
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    redirect_uri = request.url_root.rstrip('/') + url_for('auth.google_callback')
    
    # Build Google OAuth URL
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=openid email profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    return redirect(google_auth_url)

@bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    from flask import current_app
    import requests
    
    code = request.args.get('code')
    if not code:
        flash('Google authentication failed', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        client_id = current_app.config.get('GOOGLE_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')
        redirect_uri = request.url_root.rstrip('/') + url_for('auth.google_callback')
        
        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if 'error' in token_json:
            flash('Google authentication failed', 'danger')
            return redirect(url_for('auth.login'))
        
        access_token = token_json.get('access_token')
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info = user_info_response.json()
        
        if 'error' in user_info:
            flash('Failed to get user information from Google', 'danger')
            return redirect(url_for('auth.login'))
        
        email = user_info.get('email')
        name = user_info.get('name', '')
        google_id = user_info.get('id')
        
        if not email:
            flash('Unable to get email from Google account', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Create new user with Google sign-in
            # Default role is Employee for Google sign-ups
            employee_id = f"EMP{User.query.count() + 1:04d}"
            while User.query.filter_by(employee_id=employee_id).first():
                employee_id = f"EMP{User.query.count() + 1:04d}"
            
            user = User(
                employee_id=employee_id,
                name=name or email.split('@')[0],
                email=email,
                role='Employee',
                date_of_joining=datetime.utcnow().date(),
                password_hash='google_oauth'  # Special marker for OAuth users
            )
            db.session.add(user)
            db.session.flush()
            
            # Create payroll settings
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
            
            flash('Account created successfully with Google!', 'success')
        
        # Log in the user
        login_user(user)
        flash(f'Welcome, {user.name}!', 'success')
        return redirect(url_for('dashboard.dashboard'))
        
    except Exception as e:
        flash(f'Google authentication error: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

