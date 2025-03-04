from datetime import datetime
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

class RegistrationStatus(enum.Enum):
    PENDING_PAYMENT = "Pending Payment Upload"
    PENDING_VERIFICATION = "Pending Verification"
    CONFIRMED = "Confirmed"
    REJECTED = "Rejected - Reupload Required"

# Define roles for access control
class Role(db.Model):
    """Model for admin roles"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    # Define relationships
    admins = db.relationship('Admin', backref='role', lazy=True)
    
    # Define permissions as class attributes for easy reference
    VIEWER = "viewer"         # Can only view data
    REGISTRAR = "registrar"   # Can manage registrations
    CHECKER = "checker"       # Can check in attendees
    MANAGER = "manager"       # Can manage all aspects except admin users
    ADMIN = "admin"           # Full access including admin user management
    
    def __repr__(self):
        return f'<Role {self.name}>'

# Admin-Role association table for many-to-many relationship
admin_permissions = db.Table('admin_permissions',
    db.Column('admin_id', db.Integer, db.ForeignKey('admins.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class Permission(db.Model):
    """Model for granular permissions"""
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    # Define relationships
    admins = db.relationship('Admin', secondary=admin_permissions, backref=db.backref('permissions', lazy='dynamic'))
    
    # Define permission constants
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_REGISTRATIONS = "view_registrations"
    APPROVE_REGISTRATIONS = "approve_registrations"
    REJECT_REGISTRATIONS = "reject_registrations"
    MANAGE_REGISTRATIONS = "manage_registrations"
    CHECK_IN_ATTENDEES = "check_in_attendees"
    EXPORT_DATA = "export_data"
    SEND_EMAILS = "send_emails"
    MANAGE_ADMINS = "manage_admins"
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    EXPORT_AUDIT_LOGS = "export_audit_logs"
    
    def __repr__(self):
        return f'<Permission {self.name}>'

class AuditLog(db.Model):
    """Model for audit logging"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))  # IPv6 can be up to 45 chars
    
    # Define relationships
    admin = db.relationship('Admin', backref='audit_logs')
    
    # Define action types as class attributes
    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_APPROVE = "APPROVE"
    ACTION_REJECT = "REJECT"
    ACTION_CHECKIN = "CHECK_IN"
    ACTION_EXPORT = "EXPORT"
    
    # Define resource types
    RESOURCE_ADMIN = "ADMIN"
    RESOURCE_REGISTRATION = "REGISTRATION"
    RESOURCE_CHECKIN = "CHECK_IN"
    RESOURCE_SYSTEM = "SYSTEM"
    
    def __repr__(self):
        return f'<AuditLog {self.action} {self.resource_type} {self.resource_id} by {self.admin_id}>'
    
    @classmethod
    def log(cls, admin_id, action, resource_type, resource_id=None, details=None, ip_address=None):
        """Create and save an audit log entry"""
        log_entry = cls(
            admin_id=admin_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry

class Registration(db.Model):
    """Model for attendee registrations"""
    __tablename__ = 'registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    receipt_url = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(RegistrationStatus), default=RegistrationStatus.PENDING_PAYMENT, nullable=False)
    qr_code = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    checked_in = db.Column(db.Boolean, default=False)
    
    # Relationship with check-in records
    check_ins = db.relationship('CheckIn', backref='registration', lazy=True)
    
    def __repr__(self):
        return f'<Registration {self.name} ({self.email})>'
    
    def to_dict(self):
        """Convert registration to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone_number': self.phone_number,
            'receipt_url': self.receipt_url,
            'status': self.status.value,
            'qr_code': self.qr_code,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'checked_in': self.checked_in or bool(self.check_ins)
        }
    
    def generate_qr_data(self):
        """Generate QR code data in JSON format"""
        import json
        
        # Create a dictionary with the necessary data
        qr_data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Convert to JSON string
        return json.dumps(qr_data)

class Admin(UserMixin, db.Model):
    """Model for admin users"""
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Admin {self.email}>'
    
    def set_password(self, password):
        """Set the password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if the password is correct"""
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Check if admin has a specific permission"""
        # Check direct permission
        if any(p.name == permission for p in self.permissions):
            return True
        
        # Check role-based permissions
        if self.role:
            if self.role.name == Role.ADMIN:
                return True  # Admin role has all permissions
            elif self.role.name == Role.MANAGER and permission != Permission.MANAGE_ADMINS:
                return True  # Manager has all permissions except managing admins
            elif self.role.name == Role.REGISTRAR and permission in [
                Permission.VIEW_DASHBOARD, 
                Permission.VIEW_REGISTRATIONS,
                Permission.APPROVE_REGISTRATIONS,
                Permission.REJECT_REGISTRATIONS,
                Permission.MANAGE_REGISTRATIONS,
                Permission.SEND_EMAILS
            ]:
                return True
            elif self.role.name == Role.CHECKER and permission in [
                Permission.VIEW_DASHBOARD,
                Permission.VIEW_REGISTRATIONS,
                Permission.CHECK_IN_ATTENDEES
            ]:
                return True
            elif self.role.name == Role.VIEWER and permission in [
                Permission.VIEW_DASHBOARD,
                Permission.VIEW_REGISTRATIONS
            ]:
                return True
        
        return False

class CheckIn(db.Model):
    """Model for check-in records"""
    __tablename__ = 'check_ins'
    
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey('registrations.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    checked_in_by = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    
    # Relationship with admin
    admin = db.relationship('Admin', backref='check_ins', lazy=True)
    
    def __repr__(self):
        return f'<CheckIn {self.registration_id} at {self.check_in_time}>'

@login_manager.user_loader
def load_user(user_id):
    """Load a user for Flask-Login"""
    return Admin.query.get(int(user_id)) 