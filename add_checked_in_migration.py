from app import create_app, db
from app.models.user import Registration
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Add the checked_in column to the registrations table
    db.session.execute(text("ALTER TABLE registrations ADD COLUMN checked_in BOOLEAN DEFAULT FALSE"))
    db.session.commit()
    
    # Update the checked_in status based on existing check-ins
    db.session.execute(text("""
        UPDATE registrations 
        SET checked_in = TRUE 
        WHERE id IN (SELECT DISTINCT registration_id FROM check_ins)
    """))
    db.session.commit()
    
    print("Successfully added checked_in column to registrations table")
    print("Updated checked_in status based on existing check-ins")