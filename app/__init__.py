from flask import Flask, request, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from sqlalchemy import event

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

    # Note: wage and wage_type are now properties in PayrollSettings model, not database columns
    # They are stored as non-persistent attributes (_wage, _wage_type) which SQLAlchemy ignores

    # For serverless environments, we don't test the connection on startup
    # Connections will be established lazily on first request
    # This prevents cold start failures in Vercel

    # Configure login manager
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # User loader for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"Error loading user: {e}")
            return None

    # Register blueprints
    from app.routes.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.routes.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    from app.routes.employees import bp as employees_bp

    app.register_blueprint(employees_bp, url_prefix="/employees")

    from app.routes.attendance import bp as attendance_bp

    app.register_blueprint(attendance_bp, url_prefix="/attendance")

    # Register admin attendance route at /admin/attendance
    from flask_login import login_required

    @app.route("/admin/attendance")
    @login_required
    def admin_attendance_route():
        from flask import render_template, request
        from flask_login import current_user
        from app.models import Attendance, User
        from datetime import datetime, date, timedelta
        from sqlalchemy import or_
        from app.utils.decorators import role_required

        # Check role
        if current_user.role not in ["Admin", "HR Officer", "Payroll Officer"]:
            from flask import abort

            abort(403)

        # Get date from query parameters, default to today
        filter_date_str = request.args.get("date", "")
        search = request.args.get("search", "").strip()

        if filter_date_str:
            try:
                filter_date = datetime.strptime(filter_date_str, "%Y-%m-%d").date()
            except ValueError:
                filter_date = date.today()
        else:
            filter_date = date.today()

        # Build query - join with User to enable filtering and ordering
        query = Attendance.query.join(User).filter(Attendance.date == filter_date)

        # Apply search filter
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.employee_id.ilike(f"%{search}%"),
                )
            )

        # Get all employees for the date, ordered by user name
        attendances = query.order_by(User.name).all()

        # Calculate previous and next dates
        prev_date = filter_date - timedelta(days=1)
        next_date = filter_date + timedelta(days=1)

        # Get all employees to show in dropdown
        all_employees = User.query.filter_by(role="Employee").order_by(User.name).all()

        return render_template(
            "attendance/admin_list.html",
            attendances=attendances,
            filter_date=filter_date,
            search=search,
            prev_date=prev_date,
            next_date=next_date,
            all_employees=all_employees,
        )

    from app.routes.leave import bp as leave_bp

    app.register_blueprint(leave_bp, url_prefix="/leave")

    from app.routes.payroll import bp as payroll_bp

    app.register_blueprint(payroll_bp, url_prefix="/payroll")

    from app.routes.reports import bp as reports_bp

    app.register_blueprint(reports_bp, url_prefix="/reports")

    from app.routes.settings import bp as settings_bp

    app.register_blueprint(settings_bp, url_prefix="/settings")

    # Context processor for attendance status
    @app.context_processor
    def inject_attendance_status():
        from flask_login import current_user
        from datetime import date
        from app.models import Attendance, AttendanceLog
        from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

        if current_user.is_authenticated:
            try:
                today = date.today()
                today_attendance = Attendance.query.filter_by(
                    user_id=current_user.id, date=today
                ).first()

                # Check last log to determine current status
                is_checked_in = False
                is_checked_out = False

                if today_attendance:
                    last_log = today_attendance.check_logs.order_by(
                        AttendanceLog.id.desc()
                    ).first()
                    if last_log:
                        # If last log is check_in, user is currently checked in
                        # If last log is check_out, user is currently checked out
                        is_checked_in = last_log.log_type == "check_in"
                        is_checked_out = last_log.log_type == "check_out"

                check_in_time = (
                    today_attendance.check_in
                    if today_attendance and today_attendance.check_in
                    else None
                )

                return {
                    "is_checked_in": is_checked_in,
                    "is_checked_out": is_checked_out,
                    "check_in_time": check_in_time,
                    "today_attendance": today_attendance,
                }
            except (OperationalError, InternalError, ProgrammingError) as e:
                # Transaction error - rollback and return defaults
                try:
                    db.session.rollback()
                except:
                    pass
                return {
                    "is_checked_in": False,
                    "is_checked_out": False,
                    "check_in_time": None,
                    "today_attendance": None,
                }
            except Exception:
                # Any other error - return defaults
                return {
                    "is_checked_in": False,
                    "is_checked_out": False,
                    "check_in_time": None,
                    "today_attendance": None,
                }
        return {
            "is_checked_in": False,
            "is_checked_out": False,
            "check_in_time": None,
            "today_attendance": None,
        }

    # Root route
    @app.route("/")
    def index():
        from flask import render_template
        from flask_login import current_user

        if current_user.is_authenticated:
            from flask import redirect, url_for

            return redirect(url_for("dashboard.dashboard"))
        return render_template("index.html")

    # Error handlers for better error reporting
    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

        # Rollback transaction on database errors
        try:
            if isinstance(error, (OperationalError, InternalError, ProgrammingError)):
                db.session.rollback()
        except:
            pass

        app.logger.error(f"Server Error: {error}", exc_info=True)
        # Return JSON for API compatibility, or simple HTML
        return jsonify({"error": "Internal Server Error", "message": str(error)}), 500

    # After request handler to rollback on transaction errors
    @app.after_request
    def after_request_handler(response):
        from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError
        import traceback

        # Check if there was a database error
        if response.status_code == 500:
            try:
                # Try to rollback any failed transaction
                db.session.rollback()
            except:
                pass
        return response

    # Teardown handler to ensure transactions are cleaned up
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

        if exception:
            # Rollback on any exception
            try:
                db.session.rollback()
            except:
                pass
        # Flask-SQLAlchemy handles commits automatically, we just need to clean up on errors

    @app.errorhandler(404)
    def not_found_error(error):
        from flask import jsonify

        return jsonify({"error": "Not Found", "message": "Page not found"}), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import jsonify, render_template
        from flask_login import current_user

        # Return JSON for API requests
        if request.is_json or request.content_type == "application/json":
            return (
                jsonify(
                    {
                        "error": "Forbidden",
                        "message": "You do not have permission to access this resource",
                    }
                ),
                403,
            )

        # Return HTML for web requests
        return render_template("errors/403.html"), 403

    @app.errorhandler(401)
    def unauthorized_error(error):
        from flask import jsonify, redirect, url_for
        from flask_login import current_user

        # Return JSON for API requests
        if request.is_json or request.content_type == "application/json":
            return (
                jsonify(
                    {
                        "error": "Unauthorized",
                        "message": "Please log in to access this resource",
                    }
                ),
                401,
            )

        # Redirect to login for web requests
        return redirect(url_for("auth.login"))

    return app
