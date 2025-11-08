# WorkZen - Smart Human Resource Management System

A comprehensive HRMS built with Flask, PostgreSQL, and modern web technologies.

## Features

- **User & Role Management**: Registration, login, and role-based access control (Admin, Employee, HR Officer, Payroll Officer)
- **Attendance Management**: Mark attendance, track check-in/check-out, view attendance records
- **Leave Management**: Apply for leaves, approve/reject leave requests
- **Payroll Management**: Generate payroll, calculate salaries with deductions (PF, Professional Tax), generate payslips
- **Reports**: Generate attendance, leave, and payroll reports
- **Dashboard & Analytics**: Role-specific dashboards with statistics
- **Multi-language Support**: English, Hindi, Gujarati (Flask-Babel)
- **Dark/Light Theme**: Professional theme with toggle functionality

## Technology Stack

- **Backend**: Flask 3.0.0
- **Database**: PostgreSQL (NeonDB)
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Icons**: Font Awesome
- **Font**: Poppins (Google Fonts)
- **Authentication**: Flask-Login (session-based)
- **Internationalization**: Flask-Babel

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL database (NeonDB connection string provided)
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd WorkZen-Odoo-IITGN-2025
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://neondb_owner:npg_AyIZVHqN23OB@ep-floral-feather-a1lmv2wi-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

5. Initialize the database:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. Run the application:
```bash
python run.py
```

The application will be available at `http://localhost:5000`

## Database Models

- **User**: Employees, Admins, HR Officers, Payroll Officers
- **Attendance**: Daily attendance records with check-in/check-out times
- **Leave**: Leave applications and approvals
- **Payroll**: Monthly payroll records with salary breakdown
- **PayrollSettings**: Salary structure for each employee

## Role-Based Access Control

### Admin
- Full access to all modules
- Can create, read, update, and delete all data
- Can manage user roles

### Employee
- View and mark own attendance
- Apply for leaves
- View own payslips
- View employee directory (read-only)
- Cannot access payroll or system settings

### HR Officer
- Create and update employee profiles
- Monitor attendance records
- Manage and allocate leaves
- Generate attendance and leave reports
- Cannot access payroll data

### Payroll Officer
- Approve/reject leave requests
- Generate payroll and payslips
- Generate all reports
- View attendance (read-only)
- Cannot create/modify employee data

## Payroll Calculations

- **Gross Salary** = Basic + HRA + Conveyance + Other Allowances
- **PF Contribution** = Basic Salary × 12% (employee contribution)
- **Professional Tax** = Fixed amount per month (default: ₹200)
- **Net Salary** = Gross Salary - Total Deductions

## Project Structure

```
WorkZen-Odoo-IITGN-2025/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # Database models
│   ├── routes/              # Route blueprints
│   ├── templates/           # Jinja2 templates
│   ├── static/              # CSS, JS, images
│   └── utils/               # Utility functions
├── migrations/              # Database migrations
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
└── run.py                  # Application entry point
```

## License

MIT License
