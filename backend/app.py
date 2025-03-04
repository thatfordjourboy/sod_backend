from app import create_app, db
from app.models.user import Admin, Registration, CheckIn

app = create_app()

@app.cli.command("create-admin")
def create_admin():
    """Create an admin user via CLI"""
    import getpass
    
    email = input("Enter admin email: ")
    password = getpass.getpass("Enter admin password: ")
    confirm_password = getpass.getpass("Confirm password: ")
    
    if password != confirm_password:
        print("Passwords do not match!")
        return
    
    # Check if admin already exists
    existing_admin = Admin.query.filter_by(email=email).first()
    if existing_admin:
        print(f"Admin with email {email} already exists!")
        return
    
    # Create new admin
    admin = Admin(email=email)
    admin.set_password(password)
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"Admin {email} created successfully!")

@app.cli.command("init-db")
def init_db():
    """Initialize the database"""
    db.create_all()
    print("Database initialized!")

if __name__ == '__main__':
    app.run(debug=True) 