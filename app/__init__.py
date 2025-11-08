from flask import Flask, request, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # def get_locale():
    #     """Locale selector function for Babel"""
    #     # Check if locale is stored in session
    #     if 'locale' in session:
    #         return session['locale']
    #     # Default to browser language or app default
    #     return request.accept_languages.best_match(app.config['LANGUAGES'].keys()) or app.config['BABEL_DEFAULT_LOCALE']
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    #babel = Babel(app, locale_selector=get_locale)
    
    # For serverless environments, we don't test the connection on startup
    # Connections will be established lazily on first request
    # This prevents cold start failures in Vercel
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Babel locale selector
    # @Babel.localeselector
    # def get_locale():
    #     if 'locale' in session:
    #         return session['locale']
    #     return request.accept_languages.best_match(app.config['LANGUAGES'].keys()) or app.config['BABEL_DEFAULT_LOCALE']
    
    # babel.init_app(app)
    
    # Store locale in g for templates
    # @app.before_request
    # def before_request():
    #     g.locale = str(get_locale())
    
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
    
    # Language switching route
    @app.route('/set_language', methods=['POST'])
    def set_language():
        from flask import jsonify
        data = request.get_json()
        language = data.get('language', 'en')
        if language in app.config['LANGUAGES']:
            session['locale'] = language
            return jsonify({'success': True, 'locale': language})
        return jsonify({'success': False, 'error': 'Invalid language'}), 400
    
    # Root route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('auth.login'))
    
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

