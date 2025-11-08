"""
Vercel entrypoint for WorkZen HRMS
"""
from app import create_app
import os

# Create the Flask app instance
# Vercel's @vercel/python will automatically detect this as the WSGI app
app = create_app()

# For local development
if __name__ == '__main__':
    app.run(debug=True)

