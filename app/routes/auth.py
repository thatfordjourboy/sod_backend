from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models.user import Admin, Role, Permission, AuditLog
from app.forms import LoginForm
from app.utils.decorators import permission_required
from datetime import datetime, timedelta
import io
import csv
import logging

# Set up logger
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login route"""
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Find the admin by email
        admin = Admin.query.filter_by(email=form.email.data).first()
        
        # Check if admin exists and password is correct
        if admin and check_password_hash(admin.password_hash, form.password.data):
            # Check if admin is active
            if not admin.is_active:
                flash('Your account has been deactivated. Please contact the system administrator.', 'danger')
                return render_template('auth/login.html', form=form)
            
            # Update last login time
            admin.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(admin, remember=form.remember_me.data)
            
            # Log the login action
            ip_address = request.remote_addr
            AuditLog.log(
                admin_id=admin.id,
                action=AuditLog.ACTION_LOGIN,
                resource_type=AuditLog.RESOURCE_SYSTEM,
                details=f"Admin logged in from {ip_address}",
                ip_address=ip_address
            )
            
            logger.info(f"Admin login successful: {form.email.data} from IP {ip_address}")
            flash('Login successful. Welcome back!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            logger.warning(f"Failed login attempt for email: {form.email.data} from IP {request.remote_addr}")
            flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Admin logout route"""
    # Log the logout action
    if current_user.is_authenticated:
        ip_address = request.remote_addr
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_LOGOUT,
            resource_type=AuditLog.RESOURCE_SYSTEM,
            details=f"Admin logged out from {ip_address}",
            ip_address=ip_address
        )
    
    logger.info(f"Admin logout: {current_user.email} from IP {ip_address}")
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/create_admin', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def create_admin():
    """Create a new admin user (protected by permission)"""
    data = request.json
    
    if not data or not data.get('email') or not data.get('password') or not data.get('role_id'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Check if admin already exists
        existing_admin = Admin.query.filter_by(email=data['email']).first()
        if existing_admin:
            return jsonify({'error': 'Admin with this email already exists'}), 409
        
        # Check if role exists
        role = Role.query.get(data['role_id'])
        if not role:
            return jsonify({'error': 'Invalid role ID'}), 400
        
        # Create new admin
        new_admin = Admin(
            email=data['email'],
            role_id=data['role_id'],
            is_active=data.get('is_active', True)
        )
        new_admin.set_password(data['password'])
        
        db.session.add(new_admin)
        db.session.commit()
        
        # Log the admin creation
        ip_address = request.remote_addr
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_CREATE,
            resource_type=AuditLog.RESOURCE_ADMIN,
            resource_id=new_admin.id,
            details=f"Created admin user {new_admin.email} with role {role.name}",
            ip_address=ip_address
        )
        
        logger.info(f"Admin {current_user.email} created new admin: {new_admin.email} with role_id {data['role_id']}")
        return jsonify({
            'message': 'Admin created successfully', 
            'id': new_admin.id,
            'email': new_admin.email,
            'role': role.name
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating admin: {str(e)}")
        return jsonify({'error': f'Error creating admin: {str(e)}'}), 500

@auth_bp.route('/admins')
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def list_admins():
    """List all admin users"""
    logger.info(f"Admin {current_user.email} accessed admin management page")
    admins = Admin.query.all()
    roles = Role.query.all()
    return render_template('auth/admins.html', admins=admins, roles=roles)

@auth_bp.route('/admin/<int:admin_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def manage_admin(admin_id):
    """Manage a specific admin user"""
    admin = Admin.query.get_or_404(admin_id)
    
    if request.method == 'GET':
        return render_template('auth/admin_detail.html', admin=admin)
    
    elif request.method == 'PUT':
        data = request.json
        
        # Don't allow deactivating yourself
        if admin.id == current_user.id and data.get('is_active') is False:
            return jsonify({'error': 'You cannot deactivate your own account'}), 403
        
        # Store original values for audit log
        original_email = admin.email
        original_role = admin.role.name if admin.role else "None"
        original_status = "Active" if admin.is_active else "Inactive"
        
        # Update admin data
        if 'email' in data:
            # Check if email is already taken by another admin
            existing = Admin.query.filter(Admin.email == data['email'], Admin.id != admin_id).first()
            if existing:
                return jsonify({'error': 'Email already in use'}), 409
            admin.email = data['email']
        
        if 'role_id' in data:
            role = Role.query.get(data['role_id'])
            if not role:
                return jsonify({'error': 'Invalid role ID'}), 400
            admin.role_id = data['role_id']
        
        if 'is_active' in data:
            admin.is_active = data['is_active']
        
        if 'password' in data and data['password']:
            admin.set_password(data['password'])
        
        db.session.commit()
        
        # Log the admin update
        changes = []
        if 'email' in data and original_email != admin.email:
            changes.append(f"Email: {original_email} → {admin.email}")
        if 'role_id' in data:
            new_role = admin.role.name if admin.role else "None"
            if original_role != new_role:
                changes.append(f"Role: {original_role} → {new_role}")
        if 'is_active' in data:
            new_status = "Active" if admin.is_active else "Inactive"
            if original_status != new_status:
                changes.append(f"Status: {original_status} → {new_status}")
        if 'password' in data and data['password']:
            changes.append("Password was changed")
        
        ip_address = request.remote_addr
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_UPDATE,
            resource_type=AuditLog.RESOURCE_ADMIN,
            resource_id=admin.id,
            details=f"Updated admin user {admin.email}. Changes: {', '.join(changes)}",
            ip_address=ip_address
        )
        
        logger.info(f"Admin {current_user.email} updated admin {admin.email} role to {admin.role.name}")
        return jsonify({'message': 'Admin updated successfully'}), 200
    
    elif request.method == 'DELETE':
        # Don't allow deleting yourself
        if admin.id == current_user.id:
            return jsonify({'error': 'You cannot delete your own account'}), 403
        
        email = admin.email
        admin_id = admin.id
        
        db.session.delete(admin)
        db.session.commit()
        
        # Log the admin deletion
        ip_address = request.remote_addr
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_DELETE,
            resource_type=AuditLog.RESOURCE_ADMIN,
            resource_id=admin_id,
            details=f"Deleted admin user {email}",
            ip_address=ip_address
        )
        
        logger.info(f"Admin {current_user.email} deleted admin: {email}")
        return jsonify({'message': 'Admin deleted successfully'}), 200

@auth_bp.route('/roles')
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def list_roles():
    """List all roles"""
    roles = Role.query.all()
    return render_template('auth/roles.html', roles=roles)

@auth_bp.route('/permissions')
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def list_permissions():
    """List all permissions"""
    permissions = Permission.query.all()
    return render_template('auth/permissions.html', permissions=permissions)

@auth_bp.route('/audit-logs')
@login_required
@permission_required(Permission.VIEW_AUDIT_LOGS)
def audit_logs():
    """View audit logs"""
    # Get filter parameters
    admin_id = request.args.get('admin_id', type=int)
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    days = request.args.get('days', type=int, default=7)
    
    # Start with base query
    query = AuditLog.query
    
    # Apply filters
    if admin_id:
        query = query.filter_by(admin_id=admin_id)
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= cutoff)
    
    # Get all admins for the filter dropdown
    admins = Admin.query.all()
    
    # Get audit logs with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Get all logs for this query
    all_logs = query.order_by(AuditLog.timestamp.desc()).all()
    
    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
        
        @property
        def has_prev(self):
            return self.page > 1
        
        @property
        def has_next(self):
            return self.page < self.pages
        
        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None
        
        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    # Calculate start and end indices for the current page
    start = (page - 1) * per_page
    end = min(start + per_page, len(all_logs))
    
    # Create pagination object
    logs = SimplePagination(
        items=all_logs[start:end],
        page=page,
        per_page=per_page,
        total=len(all_logs)
    )
    
    logger.info(f"Admin {current_user.email} viewed audit logs with filters: admin_id={admin_id}, action={action}, resource_type={resource_type}, days={days}")
    
    return render_template('auth/audit_logs.html', 
                          logs=logs,
                          admins=admins,
                          actions=[
                              AuditLog.ACTION_CREATE,
                              AuditLog.ACTION_UPDATE,
                              AuditLog.ACTION_DELETE,
                              AuditLog.ACTION_LOGIN,
                              AuditLog.ACTION_LOGOUT,
                              AuditLog.ACTION_APPROVE,
                              AuditLog.ACTION_REJECT,
                              AuditLog.ACTION_CHECKIN,
                              AuditLog.ACTION_EXPORT
                          ],
                          resource_types=[
                              AuditLog.RESOURCE_ADMIN,
                              AuditLog.RESOURCE_REGISTRATION,
                              AuditLog.RESOURCE_CHECKIN,
                              AuditLog.RESOURCE_SYSTEM
                          ],
                          selected_admin_id=admin_id,
                          selected_action=action,
                          selected_resource_type=resource_type,
                          selected_days=days)

@auth_bp.route('/export-audit-logs')
@login_required
@permission_required(Permission.EXPORT_AUDIT_LOGS)
def export_audit_logs():
    """Export audit logs to CSV"""
    # Get filter parameters
    admin_id = request.args.get('admin_id', type=int)
    action = request.args.get('action')
    resource_type = request.args.get('resource_type')
    days = request.args.get('days', type=int, default=7)
    
    # Start with base query
    query = AuditLog.query
    
    # Apply filters
    if admin_id:
        query = query.filter_by(admin_id=admin_id)
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= cutoff)
    
    # Get all matching logs
    logs = query.order_by(AuditLog.timestamp.desc()).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['ID', 'Timestamp', 'Admin', 'Action', 'Resource Type', 
                    'Resource ID', 'Details', 'IP Address'])
    
    # Write data rows
    for log in logs:
        admin_email = log.admin.email if log.admin else 'Unknown'
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            admin_email,
            log.action,
            log.resource_type,
            log.resource_id,
            log.details,
            log.ip_address
        ])
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Log the export action
    filter_details = {
        'admin_id': admin_id,
        'action': action,
        'resource_type': resource_type,
        'days': days
    }
    AuditLog.log(
        admin_id=current_user.id,
        action=AuditLog.ACTION_EXPORT,
        resource_type=AuditLog.RESOURCE_SYSTEM,
        resource_id=0,
        details=f"Exported audit logs with filters: {filter_details}",
        ip_address=request.remote_addr
    )
    
    logger.info(f"Admin {current_user.email} exported audit logs with filters: admin_id={admin_id}, action={action}, resource_type={resource_type}, days={days}")
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'audit_logs_{timestamp}.csv'
    ) 