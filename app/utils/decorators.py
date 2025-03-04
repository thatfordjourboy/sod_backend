from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def permission_required(permission):
    """
    Decorator to check if the current user has the required permission.
    Must be used after @login_required to ensure current_user is available.
    
    Usage:
        @app.route('/admin/some-route')
        @login_required
        @permission_required('some_permission')
        def some_route():
            # This will only execute if the user has 'some_permission'
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator 