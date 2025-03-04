from app import create_app
from app.models.user import Admin, Role, Permission

app = create_app()

with app.app_context():
    print("Admin users:")
    admins = Admin.query.all()
    for admin in admins:
        print(f"ID: {admin.id}")
        print(f"Email: {admin.email}")
        print(f"Role: {admin.role.name if admin.role else 'None'}")
        print(f"Permissions: {[p.name for p in admin.permissions]}")
        print("-" * 40)
    
    print("\nRoles:")
    roles = Role.query.all()
    for role in roles:
        print(f"ID: {role.id}")
        print(f"Name: {role.name}")
        print(f"Description: {role.description}")
        print("-" * 40)
    
    print("\nPermissions:")
    permissions = Permission.query.all()
    for permission in permissions:
        print(f"ID: {permission.id}")
        print(f"Name: {permission.name}")
        print(f"Description: {permission.description}")
        print("-" * 40) 