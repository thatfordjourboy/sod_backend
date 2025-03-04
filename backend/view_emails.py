import os
import json
import sys
import webbrowser
from datetime import datetime
from flask import Flask

def create_app():
    """Create a Flask application."""
    app = Flask(__name__)
    return app

def list_saved_emails(app):
    """List all saved emails."""
    email_dir = os.path.join(app.instance_path, 'emails')
    
    if not os.path.exists(email_dir):
        print(f"Email directory not found: {email_dir}")
        return []
    
    # Get all HTML files
    html_files = [f for f in os.listdir(email_dir) if f.endswith('.html')]
    html_files.sort(reverse=True)  # Most recent first
    
    emails = []
    for i, html_file in enumerate(html_files):
        # Get corresponding JSON file
        json_file = html_file.replace('.html', '.json')
        json_path = os.path.join(email_dir, json_file)
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    
                # Extract email info
                subject = data.get('subject', 'No Subject')
                recipients = ', '.join(data.get('recipients', []))
                date_str = data.get('date', '')
                
                # Parse date
                try:
                    date = datetime.fromisoformat(date_str)
                    date_formatted = date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_formatted = date_str
                
                emails.append({
                    'id': i + 1,
                    'file': html_file,
                    'subject': subject,
                    'recipients': recipients,
                    'date': date_formatted
                })
            except Exception as e:
                print(f"Error reading {json_file}: {str(e)}")
    
    return emails

def display_emails(emails):
    """Display a list of emails."""
    if not emails:
        print("No emails found.")
        return
    
    print("\n=== Saved Emails ===")
    print(f"{'ID':<4} {'Date':<20} {'Subject':<40} {'Recipients':<30}")
    print("-" * 94)
    
    for email in emails:
        print(f"{email['id']:<4} {email['date']:<20} {email['subject'][:38]:<40} {email['recipients'][:28]:<30}")

def view_email(app, email_id, emails):
    """View a specific email."""
    if not emails or email_id <= 0 or email_id > len(emails):
        print(f"Invalid email ID: {email_id}")
        return
    
    email = emails[email_id - 1]
    email_path = os.path.join(app.instance_path, 'emails', email['file'])
    
    if os.path.exists(email_path):
        # Open in browser
        webbrowser.open('file://' + os.path.abspath(email_path))
        print(f"Opening email: {email['subject']}")
    else:
        print(f"Email file not found: {email_path}")

if __name__ == "__main__":
    app = create_app()
    
    # Create instance directory if it doesn't exist
    os.makedirs(app.instance_path, exist_ok=True)
    
    # List all emails
    emails = list_saved_emails(app)
    display_emails(emails)
    
    if emails:
        try:
            if len(sys.argv) > 1:
                email_id = int(sys.argv[1])
                view_email(app, email_id, emails)
            else:
                while True:
                    try:
                        choice = input("\nEnter email ID to view (or 'q' to quit): ")
                        if choice.lower() == 'q':
                            break
                        email_id = int(choice)
                        view_email(app, email_id, emails)
                    except ValueError:
                        print("Please enter a valid number or 'q' to quit.")
                    except KeyboardInterrupt:
                        break
        except KeyboardInterrupt:
            print("\nExiting...")
    
    print("\nDone.") 