from app import create_app, db
from app.models.user import Permission, Role, Admin, admin_permissions

app = create_app()

with app.app_context():
    # Add new permissions if they don't exist
    permissions_to_add = [
        {
            'name': Permission.MANAGE_REGISTRATIONS,
            'description': 'Manage registrations (approve, reject, update)'
        },
        {
            'name': Permission.MANAGE_SYSTEM,
            'description': 'Manage system settings and view system information'
        },
        {
            'name': 'export_audit_logs',
            'description': 'Export audit logs'
        },
        {
            'name': 'view_audit_logs',
            'description': 'View audit logs'
        }
    ]
    
    for perm_data in permissions_to_add:
        existing_perm = Permission.query.filter_by(name=perm_data['name']).first()
        if not existing_perm:
            new_perm = Permission(name=perm_data['name'], description=perm_data['description'])
            db.session.add(new_perm)
            print(f"Added permission: {perm_data['name']}")
        else:
            print(f"Permission already exists: {perm_data['name']}")
    
    # Commit to get IDs for new permissions
    db.session.commit()
    
    # Get admin users
    admin_users = Admin.query.all()
    
    # Get all permissions
    all_permissions = Permission.query.all()
    
    # Add all permissions to admin users with admin role
    for admin in admin_users:
        if admin.role and admin.role.name == Role.ADMIN:
            for perm in all_permissions:
                # Check if admin already has this permission
                if perm not in admin.permissions:
                    admin.permissions.append(perm)
                    print(f"Added permission {perm.name} to admin {admin.email}")
    
    # Commit changes
    db.session.commit()
    print("Permissions initialized successfully") 