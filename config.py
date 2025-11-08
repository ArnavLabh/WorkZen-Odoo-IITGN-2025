import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://neondb_owner:npg_AyIZVHqN23OB@ep-floral-feather-a1lmv2wi-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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

