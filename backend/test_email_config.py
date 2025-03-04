import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_config():
    """Test email configuration by sending a test email"""
    # Get email configuration from environment variables
    mail_server = os.environ.get('MAIL_SERVER')
    mail_port = int(os.environ.get('MAIL_PORT', 587))
    mail_use_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    mail_use_ssl = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')
    mail_default_sender = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Print configuration (without password)
    print("Email Configuration:")
    print(f"MAIL_SERVER: {mail_server}")
    print(f"MAIL_PORT: {mail_port}")
    print(f"MAIL_USE_TLS: {mail_use_tls}")
    print(f"MAIL_USE_SSL: {mail_use_ssl}")
    print(f"MAIL_USERNAME: {mail_username}")
    print(f"MAIL_PASSWORD: {'*' * 8 if mail_password else 'Not set'}")
    print(f"MAIL_DEFAULT_SENDER: {mail_default_sender}")
    
    # Check if required configuration is set
    if not all([mail_server, mail_port, mail_username, mail_password]):
        print("\nERROR: Missing required email configuration.")
        return False
    
    # Create a test email
    msg = MIMEMultipart()
    msg['From'] = mail_default_sender or mail_username
    msg['To'] = mail_username  # Send to self for testing
    msg['Subject'] = "Test Email from SOD 2025 App"
    
    body = """
    This is a test email from the SOD 2025 application.
    If you're receiving this, the email configuration is working correctly.
    """
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to the mail server
        print("\nConnecting to mail server...")
        
        # Create SSL context for secure connection
        context = ssl.create_default_context()
        
        if mail_use_ssl:
            print(f"Using SSL connection to {mail_server}:{mail_port}")
            server = smtplib.SMTP_SSL(mail_server, mail_port, context=context)
        else:
            print(f"Using standard connection to {mail_server}:{mail_port}")
            server = smtplib.SMTP(mail_server, mail_port)
            if mail_use_tls:
                print("Starting TLS encryption")
                server.starttls(context=context)
        
        # Set debug level
        server.set_debuglevel(1)
        
        # Login to the mail server
        print(f"Logging in as {mail_username}...")
        server.login(mail_username, mail_password)
        
        # Send the email
        print("Sending test email...")
        server.send_message(msg)
        
        # Close the connection
        server.quit()
        
        print("\nSUCCESS: Test email sent successfully!")
        return True
    except Exception as e:
        print(f"\nERROR: Failed to send test email: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_email_config()
    sys.exit(0 if success else 1) 