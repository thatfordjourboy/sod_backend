import os
import sys
import requests
from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail, Message
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_test_app():
    """Create a test Flask application with mail configuration."""
    app = Flask(__name__)
    
    # Configure mail settings from environment variables
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
    app.config['MAIL_MAX_EMAILS'] = int(os.environ.get('MAIL_MAX_EMAILS', 100))
    app.config['MAIL_DEBUG'] = os.environ.get('MAIL_DEBUG', 'False').lower() == 'true'
    
    return app

def test_send_email_smtp(recipient_email):
    """Test sending an email using Flask-Mail (SMTP)."""
    app = create_test_app()
    mail = Mail(app)
    
    print("\nMail configuration (SMTP):")
    print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
    print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    
    with app.app_context():
        try:
            msg = Message(
                subject="Test Email from SOD 2025 (Mailgun SMTP)",
                recipients=[recipient_email],
                body="This is a test email sent using Mailgun SMTP.",
                html="<p>This is a test email sent using <b>Mailgun SMTP</b>.</p>"
            )
            
            # Set reply-to if configured
            reply_to = os.environ.get('MAIL_REPLY_TO')
            if reply_to:
                msg.reply_to = reply_to
            
            print(f"\nSending test email to {recipient_email} via SMTP...")
            mail.send(msg)
            print("Email sent successfully via SMTP!")
            return True
        except Exception as e:
            print(f"Failed to send email via SMTP: {str(e)}")
            return False

def test_send_email_api(recipient_email):
    """Test sending an email using Mailgun API directly."""
    try:
        # Extract domain from MAIL_USERNAME (postmaster@YOUR_DOMAIN)
        mail_username = os.environ.get('MAIL_USERNAME', '')
        domain = mail_username.split('@')[1] if '@' in mail_username else None
        
        if not domain:
            print("Could not extract domain from MAIL_USERNAME. Format should be 'postmaster@YOUR_DOMAIN'")
            return False
        
        api_key = os.environ.get('MAIL_PASSWORD')
        if not api_key:
            print("MAIL_PASSWORD (API key) is not set")
            return False
        
        print("\nMailgun API configuration:")
        print(f"Domain: {domain}")
        print(f"API Key: {api_key[:5]}...{api_key[-5:]}")
        
        sender = os.environ.get('MAIL_DEFAULT_SENDER')
        if not sender:
            sender = f"SOD 2025 <steamoffdaycation@gmail.com>"
        
        print(f"Sender: {sender}")
        print(f"Sending test email to {recipient_email} via API...")
        
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": sender,
                "to": recipient_email,
                "subject": "Test Email from SOD 2025 (Mailgun API)",
                "text": "This is a test email sent using Mailgun API.",
                "html": "<p>This is a test email sent using <b>Mailgun API</b>.</p>"
            }
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print(f"Email sent successfully via API!")
            return True
        else:
            print(f"Failed to send email via API. Status code: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error sending email via API: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_mailgun.py <recipient_email> [smtp|api]")
        sys.exit(1)
    
    recipient_email = sys.argv[1]
    method = sys.argv[2].lower() if len(sys.argv) > 2 else "both"
    
    success = False
    
    if method == "smtp" or method == "both":
        print("\n=== Testing SMTP Method ===")
        smtp_success = test_send_email_smtp(recipient_email)
        if smtp_success:
            print(f"✅ Test email sent successfully to {recipient_email} via SMTP")
            success = True
        else:
            print(f"❌ Failed to send test email to {recipient_email} via SMTP")
    
    if method == "api" or method == "both":
        print("\n=== Testing API Method ===")
        api_success = test_send_email_api(recipient_email)
        if api_success:
            print(f"✅ Test email sent successfully to {recipient_email} via API")
            success = True
        else:
            print(f"❌ Failed to send test email to {recipient_email} via API")
    
    if success:
        print("\n✅ At least one method succeeded!")
        sys.exit(0)
    else:
        print("\n❌ All methods failed!")
        sys.exit(1) 