from app import create_app, db
from app.models.user import Admin, Role, Permission

def create_admin_user():
    app = create_app()
    with app.app_context():
        # Create admin role if it doesn't exist
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            admin_role = Role(name='Admin', description='Administrator with full access')
            admin_role.permissions = [
                Permission.VIEW_REGISTRATIONS,
                Permission.MANAGE_REGISTRATIONS,
                Permission.CHECK_IN_ATTENDEES,
                Permission.EXPORT_DATA,
                Permission.SEND_EMAILS,
                Permission.MANAGE_ADMINS,
                Permission.MANAGE_SYSTEM
            ]
            db.session.add(admin_role)
            db.session.commit()

        # Create default admin user if it doesn't exist
        admin = Admin.query.filter_by(email='quaysoneleazer@gmail.com').first()
        if not admin:
            admin = Admin(
                email='quaysoneleazer@gmail.com',
                role=admin_role
            )
            admin.set_password('admin123')  # Set a default password
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Email: quaysoneleazer@gmail.com")
            print("Password: admin123")
        else:
            print("Admin user already exists!")

if __name__ == '__main__':
    create_admin_user() 