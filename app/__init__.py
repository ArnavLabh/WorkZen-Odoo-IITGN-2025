from flask import Flask, request, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # For serverless environments, we don't test the connection on startup
    # Connections will be established lazily on first request
    # This prevents cold start failures in Vercel
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # User loader for Flask-Login
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f'Error loading user: {e}')
            return None
    
    # Register blueprints
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    
    from app.routes.employees import bp as employees_bp
    app.register_blueprint(employees_bp, url_prefix='/employees')
    
    from app.routes.attendance import bp as attendance_bp
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    
    from app.routes.leave import bp as leave_bp
    app.register_blueprint(leave_bp, url_prefix='/leave')
    
    from app.routes.payroll import bp as payroll_bp
    app.register_blueprint(payroll_bp, url_prefix='/payroll')
    
    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    from app.routes.settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Context processor for attendance status
    @app.context_processor
    def inject_attendance_status():
        from flask_login import current_user
        from datetime import date
        from app.models import Attendance
        
        if current_user.is_authenticated:
            today = date.today()
            today_attendance = Attendance.query.filter_by(
                user_id=current_user.id,
                date=today
            ).first()
            
            is_checked_in = today_attendance and today_attendance.check_in is not None
            is_checked_out = today_attendance and today_attendance.check_out is not None
            check_in_time = today_attendance.check_in if today_attendance and today_attendance.check_in else None
            
            return {
                'is_checked_in': is_checked_in,
                'is_checked_out': is_checked_out,
                'check_in_time': check_in_time,
                'today_attendance': today_attendance
            }
        return {
            'is_checked_in': False,
            'is_checked_out': False,
            'check_in_time': None,
            'today_attendance': None
        }
    
    # Root route
    @app.route('/')
    def index():
        from flask import render_template
        from flask_login import current_user
        if current_user.is_authenticated:
            from flask import redirect, url_for
            return redirect(url_for('dashboard.dashboard'))
        return render_template('index.html')
    
    # Error handlers for better error reporting
    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        app.logger.error(f'Server Error: {error}', exc_info=True)
        # Return JSON for API compatibility, or simple HTML
        return jsonify({'error': 'Internal Server Error', 'message': str(error)}), 500
    
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import jsonify
        return jsonify({'error': 'Not Found', 'message': 'Page not found'}), 404
    
    return app

