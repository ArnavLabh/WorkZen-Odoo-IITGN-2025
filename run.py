from app import create_app, db
from app.models import User, Attendance, Leave, Payroll, PayrollSettings

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Attendance': Attendance,
        'Leave': Leave,
        'Payroll': Payroll,
        'PayrollSettings': PayrollSettings
    }

if __name__ == '__main__':
    app.run(debug=True)
