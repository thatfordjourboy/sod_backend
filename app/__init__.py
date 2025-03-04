from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
from datetime import datetime
import logging
import os
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    # Ensure instance directory exists
    os.makedirs('instance', exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={
        r"/*": {"origins": app.config['CORS_ORIGINS']}
    })
    mail.init_app(app)
    
    # Create all database tables
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"Error creating database tables: {str(e)}")
    
    from .models.user import Admin, Permission, Role, Registration, RegistrationStatus, AuditLog, CheckIn
    
    # Initialize login manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))
    
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
        from .models.user import Permission, RegistrationStatus, AuditLog, Role, Admin, Registration, CheckIn
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
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    return app

# Create the application instance
app = create_app()

# Make the app instance available at the top level
__all__ = ['app', 'create_app']