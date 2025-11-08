import os
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Handle DATABASE_URL for Vercel (fix SSL mode)
    database_url = os.environ.get('DATABASE_URL') or 'postgresql://neondb_owner:npg_AyIZVHqN23OB@ep-floral-feather-a1lmv2wi-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
    
    # Ensure SSL mode is set correctly for serverless environments
    if database_url.startswith('postgres://'):
        # Convert postgres:// to postgresql://
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Parse and ensure SSL parameters
    parsed = urlparse(database_url)
    query_params = {}
    if parsed.query:
        query_params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
    
    # Set SSL mode for serverless (Vercel, etc.)
    # Remove channel_binding as it can cause issues in serverless environments
    query_params.pop('channel_binding', None)
    if 'sslmode' not in query_params:
        query_params['sslmode'] = 'require'
    
    # Rebuild URL
    query_string = '&'.join(f'{k}={v}' for k, v in query_params.items())
    database_url = urlunparse(parsed._replace(query=query_string))
    
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # For serverless environments (Vercel), configure connection pooling
    # Note: Flask-SQLAlchemy 3.x uses SQLALCHEMY_ENGINE_OPTIONS
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'connect_timeout': 10,
            'sslmode': 'require'
        }
    }
    
    # Flask-Babel configuration
    LANGUAGES = {
        'en': 'English',
        'hi': 'Hindi',
        'gu': 'Gujarati'
    }
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or '526764377709-eumd84rde6job3qrr73otr1outhpfbol.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or ''
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

