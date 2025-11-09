from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    jsonify,
    abort,
)
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, User, Leave
from app.utils.decorators import (
    admin_required,
    hr_required,
    employee_or_above_required,
    role_required,
)
from datetime import datetime, date, time, timedelta
from calendar import monthrange
from sqlalchemy import or_, and_, inspect
from sqlalchemy.exc import OperationalError, InternalError, ProgrammingError

bp = Blueprint("attendance", __name__)


@bp.route("/")
@login_required
@role_required(["Employee"])
def list():
    """
    Employee attendance view - shows current month by default
    Displays: Date, Check In, Check Out, Work Hours, Extra Hours
    Includes month navigation and summary counters
    """
    # Get month and year from query parameters, default to current month
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year

    # Ensure valid month/year
    if month < 1 or month > 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year

    # Calculate start and end dates for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    # Get attendance records for the month
    attendances = (
        Attendance.query.filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .order_by(Attendance.date.desc())
        .all()
    )

    # Calculate summary statistics
    days_present = sum(1 for a in attendances if a.status == "Present")

    # Get leave count for the month
    leaves = Leave.query.filter(
        Leave.user_id == current_user.id,
        Leave.status == "Approved",
        Leave.start_date <= end_date,
        Leave.end_date >= start_date,
    ).all()

    leave_count = 0
    for leave in leaves:
        # Calculate overlapping days
        leave_start = max(leave.start_date, start_date)
        leave_end = min(leave.end_date, end_date)
        if leave_start <= leave_end:
            leave_count += (leave_end - leave_start).days + 1

    # Calculate total working days (excluding weekends - Saturday=5, Sunday=6)
    total_working_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday to Friday
            total_working_days += 1
        current += timedelta(days=1)

    # Calculate previous and next month/year
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    return render_template(
        "attendance/employee_list.html",
        attendances=attendances,
        month=month,
        year=year,
        month_name=month_names[month - 1],
        days_present=days_present,
        leave_count=leave_count,
        total_working_days=total_working_days,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        start_date=start_date,
        end_date=end_date,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(["Admin"])
def create():
    """
    Create attendance record - Admin only
    Allows manual creation of attendance data
    """
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        date_str = request.form.get("date", "")
        check_in_str = request.form.get("check_in", "").strip()
        check_out_str = request.form.get("check_out", "").strip()
        status = request.form.get("status", "Absent")

        errors = []

        # Validate user
        user = User.query.get(user_id)
        if not user:
            errors.append("Invalid employee selected")

        # Validate date
        try:
            attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invalid date format")
            attendance_date = date.today()

        # Check if attendance already exists
        existing = Attendance.query.filter_by(
            user_id=user_id, date=attendance_date
        ).first()
        if existing:
            errors.append(
                f'Attendance record already exists for {user.name} on {attendance_date.strftime("%Y-%m-%d")}'
            )

        # Validate times
        check_in_time = None
        check_out_time = None

        if check_in_str:
            try:
                check_in_time = datetime.strptime(check_in_str, "%H:%M").time()
            except ValueError:
                errors.append("Invalid check-in time format")

        if check_out_str:
            try:
                check_out_time = datetime.strptime(check_out_str, "%H:%M").time()
            except ValueError:
                errors.append("Invalid check-out time format")

        # Validate status
        if status not in ["Present", "Half Day", "Absent"]:
            errors.append("Invalid status")
            status = "Absent"

        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            # Create attendance record
            attendance = Attendance(
                user_id=user_id,
                date=attendance_date,
                check_in=check_in_time,
                check_out=check_out_time,
                status=status,
            )

            # Calculate working hours if both times are provided
            if check_in_time and check_out_time:
                check_in_dt = datetime.combine(attendance_date, check_in_time)
                check_out_dt = datetime.combine(attendance_date, check_out_time)
                duration = (check_out_dt - check_in_dt).total_seconds()
                attendance.working_hours = round(duration / 3600, 2)
            else:
                attendance.working_hours = 0.0

            try:
                db.session.add(attendance)
                db.session.commit()
                flash(
                    f"Attendance record created successfully for {user.name}!",
                    "success",
                )
                return redirect(
                    url_for(
                        "admin_attendance_route",
                        date=attendance_date.strftime("%Y-%m-%d"),
                    )
                )
            except Exception as e:
                db.session.rollback()
                flash("Error creating attendance record. Please try again.", "danger")
                print(f"Error creating attendance: {str(e)}")

    # GET request - show form
    employees = User.query.filter_by(role="Employee").order_by(User.name).all()
    attendance_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))

    return render_template(
        "attendance/mark.html",
        users=employees,
        attendance_date=attendance_date,
        existing=None,
    )


@bp.route("/<int:attendance_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["Admin"])
def edit(attendance_id):
    """
    Edit attendance record - Admin only
    Allows manual correction of attendance data
    """
    attendance = Attendance.query.get_or_404(attendance_id)

    if request.method == "POST":
        date_str = request.form.get("date", "")
        check_in_str = request.form.get("check_in", "").strip()
        check_out_str = request.form.get("check_out", "").strip()
        status = request.form.get("status", "Absent")

        errors = []

        # Validate date
        try:
            new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Invalid date format")
            new_date = attendance.date

        # Validate times
        check_in_time = None
        check_out_time = None

        if check_in_str:
            try:
                check_in_time = datetime.strptime(check_in_str, "%H:%M").time()
            except ValueError:
                errors.append("Invalid check-in time format")

        if check_out_str:
            try:
                check_out_time = datetime.strptime(check_out_str, "%H:%M").time()
            except ValueError:
                errors.append("Invalid check-out time format")

        # Validate status
        if status not in ["Present", "Half Day", "Absent"]:
            errors.append("Invalid status")
            status = "Absent"

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("attendance/edit.html", attendance=attendance)
        
        # Update attendance record
        attendance.date = new_date
        attendance.check_in = check_in_time
        attendance.check_out = check_out_time
        attendance.status = status

        # Calculate working hours if both times are provided
        if check_in_time and check_out_time:
            check_in_dt = datetime.combine(new_date, check_in_time)
            check_out_dt = datetime.combine(new_date, check_out_time)
            duration = (check_out_dt - check_in_dt).total_seconds()
            attendance.working_hours = round(duration / 3600, 2)
        else:
            attendance.working_hours = 0.0

        attendance.updated_at = datetime.utcnow()

        try:
            db.session.commit()
            flash("Attendance record updated successfully!", "success")
            return redirect(
                url_for(
                    "admin_attendance_route", date=new_date.strftime("%Y-%m-%d")
                )
            )
        except Exception as e:
            db.session.rollback()
            flash("Error updating attendance record. Please try again.", "danger")
            print(f"Error updating attendance: {str(e)}")
            return render_template("attendance/edit.html", attendance=attendance)

    return render_template("attendance/edit.html", attendance=attendance)


@bp.route("/<int:attendance_id>/delete", methods=["POST"])
@login_required
@role_required(["Admin"])
def delete(attendance_id):
    """
    Delete attendance record - Admin only
    """
    attendance = Attendance.query.get_or_404(attendance_id)
    user_name = attendance.user.name
    attendance_date = attendance.date

    try:
        db.session.delete(attendance)
        db.session.commit()
        flash(
            f'Attendance record for {user_name} on {attendance_date.strftime("%Y-%m-%d")} deleted successfully!',
            "success",
        )
    except Exception as e:
        db.session.rollback()
        flash("Error deleting attendance record. Please try again.", "danger")
        print(f"Error deleting attendance: {str(e)}")

    return redirect(
        url_for("admin_attendance_route", date=attendance_date.strftime("%Y-%m-%d"))
    )


@bp.route("/checkin", methods=["POST"])
@login_required
@role_required(["Employee"])
def checkin():
    """
    Check in for today - Employee only
    Creates attendance record and logs check-in time
    """
    from app.models import AttendanceLog

    today = date.today()
    current_time = datetime.now()

    try:
        # Check if attendance record exists for today
        attendance = Attendance.query.filter_by(
            user_id=current_user.id, date=today
        ).first()

        # If no attendance record, create one
        if not attendance:
            attendance = Attendance(
                user_id=current_user.id,
                date=today,
                check_in=current_time.time(),
                status="Present",
            )
            db.session.add(attendance)
            db.session.flush()  # Get the attendance ID

            # Create check-in log
            log = AttendanceLog(
                attendance_id=attendance.id,
                log_type="check_in",
                timestamp=current_time.time(),
            )
            db.session.add(log)
            db.session.commit()

            flash(
                f'Checked in successfully at {current_time.strftime("%I:%M %p")}',
                "success",
            )
            return redirect(request.referrer or url_for("dashboard.dashboard"))

        # If attendance exists, check the last log
        last_log = (
            AttendanceLog.query.filter_by(attendance_id=attendance.id)
            .order_by(AttendanceLog.id.desc())
            .first()
        )

        # If last action was check-in, prevent duplicate check-in
        if last_log and last_log.log_type == "check_in":
            flash("You are already checked in. Please check out first.", "warning")
            return redirect(request.referrer or url_for("dashboard.dashboard"))

        # Allow check-in after check-out (multiple sessions per day)
        log = AttendanceLog(
            attendance_id=attendance.id,
            log_type="check_in",
            timestamp=current_time.time(),
        )
        db.session.add(log)
        db.session.commit()

        flash(
            f'Checked in successfully at {current_time.strftime("%I:%M %p")}', "success"
        )

    except Exception as e:
        db.session.rollback()
        flash("Error during check-in. Please try again.", "danger")
        print(f"Check-in error: {str(e)}")

    return redirect(request.referrer or url_for("dashboard.dashboard"))


@bp.route("/checkout", methods=["POST"])
@login_required
@role_required(["Employee"])
def checkout():
    """
    Check out for today - Employee only
    Updates attendance record and calculates working hours
    """
    from app.models import AttendanceLog

    today = date.today()
    current_time = datetime.now()

    try:
        # Get today's attendance record
        attendance = Attendance.query.filter_by(
            user_id=current_user.id, date=today
        ).first()

        # If no attendance record, user hasn't checked in
        if not attendance:
            flash("Please check in first before checking out.", "warning")
            return redirect(request.referrer or url_for("dashboard.dashboard"))

        # Get the last log entry
        last_log = (
            AttendanceLog.query.filter_by(attendance_id=attendance.id)
            .order_by(AttendanceLog.id.desc())
            .first()
        )

        # If no logs or last action was check-out, prevent duplicate check-out
        if not last_log or last_log.log_type == "check_out":
            flash("You need to check in first before checking out.", "warning")
            return redirect(request.referrer or url_for("dashboard.dashboard"))

        # Create check-out log
        log = AttendanceLog(
            attendance_id=attendance.id,
            log_type="check_out",
            timestamp=current_time.time(),
        )
        db.session.add(log)

        # Update check-out time in attendance record
        attendance.check_out = current_time.time()

        # Calculate total working hours from all check-in/check-out pairs
        all_logs = (
            AttendanceLog.query.filter_by(attendance_id=attendance.id)
            .order_by(AttendanceLog.id)
            .all()
        )

        total_seconds = 0
        check_in_time = None

        for log in all_logs:
            if log.log_type == "check_in":
                check_in_time = log.timestamp
            elif log.log_type == "check_out" and check_in_time:
                # Calculate duration between check-in and check-out
                check_in_dt = datetime.combine(today, check_in_time)
                check_out_dt = datetime.combine(today, log.timestamp)
                duration = (check_out_dt - check_in_dt).total_seconds()
                total_seconds += duration
                check_in_time = None

        # Convert total seconds to hours
        attendance.working_hours = round(total_seconds / 3600, 2)

        db.session.commit()

        hours = int(attendance.working_hours)
        minutes = int((attendance.working_hours - hours) * 60)
        flash(
            f'Checked out successfully at {current_time.strftime("%I:%M %p")}. Total hours: {hours}h {minutes}m',
            "success",
        )

    except Exception as e:
        db.session.rollback()
        flash("Error during check-out. Please try again.", "danger")
        print(f"Check-out error: {str(e)}")

    return redirect(request.referrer or url_for("dashboard.dashboard"))


# Manual attendance editing and deletion have been removed - attendance is controlled exclusively by employees through Check-In/Check-Out


@bp.route("/logs/<int:attendance_id>")
@login_required
@role_required(["Employee"])
def get_logs(attendance_id):
    """
    Get all check-in/check-out logs for a specific attendance record
    Returns JSON with logs and calculated durations
    """
    from app.models import AttendanceLog

    # Get attendance record and verify it belongs to current user
    attendance = Attendance.query.get_or_404(attendance_id)

    if attendance.user_id != current_user.id:
        abort(403)

    # Get all logs for this attendance
    logs = (
        AttendanceLog.query.filter_by(attendance_id=attendance_id)
        .order_by(AttendanceLog.id)
        .all()
    )

    # Format logs with duration calculation
    logs_data = []
    check_in_time = None

    for log in logs:
        log_dict = {
            "log_type": log.log_type,
            "timestamp": log.timestamp.strftime("%I:%M %p"),
        }

        if log.log_type == "check_in":
            check_in_time = log.timestamp
            log_dict["duration"] = None
        elif log.log_type == "check_out" and check_in_time:
            # Calculate duration
            check_in_dt = datetime.combine(attendance.date, check_in_time)
            check_out_dt = datetime.combine(attendance.date, log.timestamp)
            duration_seconds = (check_out_dt - check_in_dt).total_seconds()
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            log_dict["duration"] = f"{hours}h {minutes}m"
            check_in_time = None

        logs_data.append(log_dict)

    return jsonify(
        {"logs": logs_data, "total_hours": f"{attendance.working_hours:.1f}"}
    )


@bp.route("/status")
@login_required
@role_required(["Employee"])
def get_status():
    """
    Get current check-in/check-out status for today
    Returns JSON indicating whether user should see check-in or check-out button
    """
    from app.models import AttendanceLog

    today = date.today()

    # Get today's attendance
    attendance = Attendance.query.filter_by(user_id=current_user.id, date=today).first()

    if not attendance:
        # No attendance record - show check-in button
        return jsonify(
            {
                "status": "not_checked_in",
                "show_button": "checkin",
                "message": "Start your day",
                "check_in_time": None,
            }
        )

    # Get last log
    last_log = (
        AttendanceLog.query.filter_by(attendance_id=attendance.id)
        .order_by(AttendanceLog.id.desc())
        .first()
    )

    if not last_log or last_log.log_type == "check_out":
        # Last action was check-out or no logs - show check-in button
        return jsonify(
            {
                "status": "checked_out",
                "show_button": "checkin",
                "message": "Check in again",
                "working_hours": f"{attendance.working_hours:.1f}",
                "check_in_time": None,
            }
        )
    else:
        # Last action was check-in - show check-out button
        check_in_time = last_log.timestamp.strftime("%I:%M %p")
        return jsonify(
            {
                "status": "checked_in",
                "show_button": "checkout",
                "message": f"Checked in at {check_in_time}",
                "check_in_time": check_in_time,
            }
        )
