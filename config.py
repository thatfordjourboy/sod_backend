import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Basic Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///instance/app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    QR_CODE_FOLDER = os.environ.get('QR_CODE_FOLDER', 'app/static/qrcodes')
    STATIC_FOLDER = os.environ.get('STATIC_FOLDER', 'app/static')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))  # 5MB default
    
    # CORS configuration
    CORS_ORIGINS = [
        'http://localhost:3000',  # Next.js development server
        'http://127.0.0.1:3000',
        'https://sod2025.com',    # Production domain
    ]
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_REPLY_TO = os.environ.get('MAIL_REPLY_TO')
    MAIL_DEBUG = os.environ.get('MAIL_DEBUG', 'False').lower() == 'true'
    MAIL_MAX_EMAILS = int(os.environ.get('MAIL_MAX_EMAILS', 100))
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'False').lower() == 'true'
    MAIL_ASCII_ATTACHMENTS = os.environ.get('MAIL_ASCII_ATTACHMENTS', 'False').lower() == 'true'

    @staticmethod
    def init_app(app):
        """Initialize application configuration"""
        # Ensure all required directories exist
        os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, app.config['UPLOAD_FOLDER']), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, app.config['QR_CODE_FOLDER']), exist_ok=True)
        
        # Set up production logging
        if not app.debug and not app.testing:
            import logging
            from logging.handlers import RotatingFileHandler
            
            # Ensure log directory exists
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            # Set up file handler
            file_handler = RotatingFileHandler(
                'logs/sod_backend.log',
                maxBytes=10240,
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('SOD Backend startup') 