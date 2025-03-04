from app import create_app, db
from app.models.user import Admin
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Get the admin user
    admin = Admin.query.filter_by(email='admin@example.com').first()
    
    if admin:
        # Reset password to 'Admin@123'
        admin.password_hash = generate_password_hash('Admin@123')
        db.session.commit()
        print(f"Password reset for admin user: {admin.email}")
        print("New password: Admin@123")
    else:
        print("Admin user not found!") 