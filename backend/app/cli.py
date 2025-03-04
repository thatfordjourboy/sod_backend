import click
from flask.cli import with_appcontext
from app import db
from app.models.user import Admin, Role, Permission

def register_commands(app):
    """Register CLI commands"""
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(init_roles_command)

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database."""
    db.create_all()
    click.echo('Initialized the database.')

@click.command('create-admin')
@click.option('--email', prompt=True, help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@with_appcontext
def create_admin_command(email, password):
    """Create an admin user."""
    # Check if admin already exists
    existing_admin = Admin.query.filter_by(email=email).first()
    if existing_admin:
        click.echo(f'Admin with email {email} already exists.')
        return
    
    # Get admin role
    admin_role = Role.query.filter_by(name=Role.ADMIN).first()
    if not admin_role:
        click.echo('Admin role not found. Please run init-roles first.')
        return
    
    # Create admin
    admin = Admin(email=email, role_id=admin_role.id)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'Created admin with email {email}.')

@click.command('init-roles')
@with_appcontext
def init_roles_command():
    """Initialize roles and permissions."""
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
            click.echo(f"Created role: {role_data['name']}")
    
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
            click.echo(f"Created permission: {perm_data['name']}")
    
    db.session.commit()
    click.echo('Initialized roles and permissions.')

def init_app(app):
    """Register CLI commands."""
    register_commands(app) 