from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
from datetime import datetime
import logging
import os
import sys
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    
    try:
        # Load configuration
        app.config.from_object(config_class)
        
        # Ensure all required directories exist
        os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, app.config['UPLOAD_FOLDER']), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, app.config['QR_CODE_FOLDER']), exist_ok=True)
        os.makedirs(os.path.join(app.root_path, app.config['LOG_DIR']), exist_ok=True)
        
        # Initialize extensions
        db.init_app(app)
        migrate.init_app(app, db)
        CORS(app, resources={
            r"/*": {"origins": app.config['CORS_ORIGINS']}
        })
        mail.init_app(app)
        
        # Create all database tables
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
        
        from .models.user import Admin, Permission, Role, Registration, RegistrationStatus, AuditLog, CheckIn
        
        # Initialize login manager
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        
        @login_manager.user_loader
        def load_user(user_id):
            try:
                return Admin.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user: {str(e)}")
                return None
        
        # Register blueprints
        from .routes.auth import auth_bp
        from .routes.admin import admin_bp
        from .routes.main import main_bp
        from .routes.api import api_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(api_bp)
        
        # Context processors
        @app.context_processor
        def inject_models():
            return {
                'Permission': Permission,
                'RegistrationStatus': RegistrationStatus,
                'datetime': datetime,
                'AuditLog': AuditLog,
                'Role': Role,
                'Admin': Admin,
                'Registration': Registration,
                'CheckIn': CheckIn
            }
        
        # Error handlers
        @app.errorhandler(500)
        def internal_error(error):
            db.session.rollback()  # Roll back db session in case of error
            logger.error(f'Server Error: {str(error)}')
            return render_template('errors/500.html'), 500

        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('errors/404.html'), 404
            
        logger.info("Application initialized successfully")
        return app
        
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise

# Create the application instance
try:
    app = create_app()
    logger.info("Application instance created successfully")
except Exception as e:
    logger.error(f"Failed to create application instance: {str(e)}")
    raise

# Make the app instance available at the top level
__all__ = ['app', 'create_app']