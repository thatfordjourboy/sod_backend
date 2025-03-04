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
    
    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)  # Initialize app configuration
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={
        r"/*": {"origins": app.config['CORS_ORIGINS']}
    })
    mail.init_app(app)
    
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
    
    # Create upload directories if they don't exist
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    qr_dir = os.path.join(app.root_path, 'static', 'qrcodes')
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(qr_dir, exist_ok=True)
    
    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)