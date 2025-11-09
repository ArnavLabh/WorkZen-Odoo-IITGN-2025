# WorkZen

Enterprise Human Resource Management System for streamlined workforce operations.

## Overview

WorkZen is a comprehensive HRMS platform that centralizes employee management, attendance tracking, leave administration, and payroll processing. Built with modern web technologies, it provides role-based access control and real-time analytics for efficient HR operations.

## Demo Video - [Click here to watch](https://drive.google.com/file/d/1oXpIk190UBB12YKyUY-gY2cTifx5gl5K/view)

## Key Features

- **Role-Based Access Control** - Secure multi-role system (Admin, HR Officer, Payroll Officer, Employee)
- **Attendance Management** - Real-time check-in/check-out tracking with detailed records
- **Leave Management** - Automated leave application and approval workflows
- **Payroll Processing** - Automated salary calculation with PF, professional tax, and custom deductions
- **Analytics & Reporting** - Comprehensive dashboards and exportable reports for attendance, leaves, and payroll
- **Multi-language Support** - English, Hindi, and Gujarati
- **Responsive Design** - Dark/light theme with modern, intuitive interface

## Technology Stack

- **Backend**: Flask 3.0.0, Python 3.8+
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, JavaScript
- **Authentication**: Flask-Login (session-based)
- **Deployment**: Vercel (serverless-ready)

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL database
- pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd WorkZen-Odoo-IITGN-2025
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
Create a `.env` file:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=your-postgresql-connection-string
```

5. Initialize database:
```bash
flask db upgrade
```

6. Run the application:
```bash
python run.py
```

The application will be available at `http://localhost:5000`

## Deployment

The application is configured for serverless deployment on Vercel. Configure environment variables in your deployment platform and deploy using the provided `vercel.json` configuration.

## License

MIT License
