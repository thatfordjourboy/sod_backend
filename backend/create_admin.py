from app import create_app, db
from app.models.user import Role, Permission, Admin

def init_roles_and_admin():
    app = create_app()
    with app.app_context():
        # Create roles
        roles = [
            {'name': Role.ADMIN, 'description': 'Full access to all features'},
            {'name': Role.MANAGER, 'description': 'Can manage all aspects except admin users'},
            {'name': Role.REGISTRAR, 'description': 'Can manage registrations and approvals'},
            {'name': Role.CHECKER, 'description': 'Can check in attendees'},
            {'name': Role.VIEWER, 'description': 'Can only view data'}
        ]
        
        for role_data in roles:
            role = Role.query.filter_by(name=role_data['name']).first()
            if not role:
                role = Role(**role_data)
                db.session.add(role)
                print(f"Created role: {role_data['name']}")
        
        # Create permissions
        permissions = [
            {'name': Permission.VIEW_DASHBOARD, 'description': 'Can view the admin dashboard'},
            {'name': Permission.VIEW_REGISTRATIONS, 'description': 'Can view registrations'},
            {'name': Permission.APPROVE_REGISTRATIONS, 'description': 'Can approve registrations'},
            {'name': Permission.REJECT_REGISTRATIONS, 'description': 'Can reject registrations'},
            {'name': Permission.CHECK_IN_ATTENDEES, 'description': 'Can check in attendees'},
            {'name': Permission.EXPORT_DATA, 'description': 'Can export data'},
            {'name': Permission.SEND_EMAILS, 'description': 'Can send emails'},
            {'name': Permission.MANAGE_ADMINS, 'description': 'Can manage admin users'}
        ]
        
        for perm_data in permissions:
            perm = Permission.query.filter_by(name=perm_data['name']).first()
            if not perm:
                perm = Permission(**perm_data)
                db.session.add(perm)
                print(f"Created permission: {perm_data['name']}")
        
        # Create admin role
        admin_role = Role.query.filter_by(name=Role.ADMIN).first()
        
        # Create first admin
        email = input("Enter admin email: ")
        password = input("Enter admin password: ")
        
        existing_admin = Admin.query.filter_by(email=email).first()
        if existing_admin:
            print(f"Admin with email {email} already exists.")
            return
        
        admin = Admin(email=email, role_id=admin_role.id)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        
        print(f"Created admin with email {email}")

if __name__ == '__main__':
    init_roles_and_admin() 