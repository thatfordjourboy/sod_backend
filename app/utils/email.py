from flask import current_app, render_template
from flask_mail import Message
from threading import Thread
from app import mail
import os
import logging
import json
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import requests
import base64
from app.utils.qrcode_generator import generate_qr_code

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            app.logger.info(f"Attempting to send email to {msg.recipients} via {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
            app.logger.info(f"Using username: {app.config['MAIL_USERNAME']}")
            app.logger.info(f"TLS enabled: {app.config['MAIL_USE_TLS']}, SSL enabled: {app.config['MAIL_USE_SSL']}")
            
            mail.send(msg)
            app.logger.info(f"Email sent successfully to {msg.recipients}")
            return True
        except Exception as e:
            app.logger.error(f"Failed to send email: {str(e)}")
            app.logger.error(f"Error type: {type(e).__name__}")
            # Fallback to saving email to file
            save_email_to_file(msg)
            return False

def send_via_mailgun_api(recipients, subject, text_body, html_body=None, attachments=None, sender=None, reply_to=None):
    """Send email using Mailgun API directly."""
    app = current_app._get_current_object()
    
    try:
        # Get Mailgun configuration
        mail_username = app.config.get('MAIL_USERNAME', '')
        # Extract domain from MAIL_USERNAME (postmaster@YOUR_DOMAIN)
        domain = mail_username.split('@')[1] if '@' in mail_username else None
        
        if not domain:
            logger.error("Could not extract domain from MAIL_USERNAME. Format should be 'postmaster@YOUR_DOMAIN'")
            return False
        
        api_key = app.config.get('MAIL_PASSWORD')
        if not api_key:
            logger.error("MAIL_PASSWORD (API key) is not set")
            return False
        
        if not sender:
            sender = app.config.get('MAIL_DEFAULT_SENDER')
        
        if not reply_to:
            reply_to = app.config.get('MAIL_REPLY_TO')
        
        # Prepare data for API request
        data = {
            "from": sender,
            "to": recipients if isinstance(recipients, str) else ", ".join(recipients),
            "subject": subject,
            "text": text_body
        }
        
        if html_body:
            data["html"] = html_body
            
        if reply_to:
            data["h:Reply-To"] = reply_to
        
        files = []
        # Add attachments if any
        if attachments:
            for attachment in attachments:
                if isinstance(attachment, dict) and 'filename' in attachment and 'data' in attachment:
                    files.append(
                        ("attachment", (
                            attachment['filename'],
                            attachment['data'],
                            attachment.get('content_type', 'application/octet-stream')
                        ))
                    )
        
        # Send the request
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data=data,
            files=files
        )
        
        if response.status_code == 200:
            logger.info(f"Email sent successfully via Mailgun API to {recipients}")
            return True
        else:
            logger.error(f"Failed to send email via Mailgun API. Status code: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending email via Mailgun API: {str(e)}")
        return False

def send_email(subject, recipients, text_body, html_body=None, attachments=None, sender=None, reply_to=None):
    """Send an email using Mailgun API with fallback to SMTP and file if sending fails."""
    app = current_app._get_current_object()
    
    if not sender:
        sender = app.config.get('MAIL_DEFAULT_SENDER')
    
    if not reply_to:
        reply_to = app.config.get('MAIL_REPLY_TO')
    
    # Create a message object for both sending and saving
    msg = Message(subject, sender=sender, recipients=recipients if isinstance(recipients, list) else [recipients], reply_to=reply_to)
    msg.body = text_body
    
    if html_body:
        msg.html = html_body
    
    if attachments:
        for attachment in attachments:
            if isinstance(attachment, dict) and 'filename' in attachment and 'data' in attachment:
                msg.attach(
                    filename=attachment['filename'],
                    content_type=attachment.get('content_type', 'application/octet-stream'),
                    data=attachment['data']
                )
    
    # Check if we're in development mode
    if app.config.get('MAIL_SUPPRESS_SEND', False) or app.debug:
        # In development, just save to file
        logger.info(f"Development mode: Saving email to file instead of sending")
        return save_email_to_file(msg)
    
    # In production, try to send
    # First try Mailgun API if we're using Mailgun
    if app.config.get('MAIL_SERVER') == 'smtp.mailgun.org':
        try:
            api_success = send_via_mailgun_api(
                recipients=recipients,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                attachments=attachments,
                sender=sender,
                reply_to=reply_to
            )
            if api_success:
                return True
            # If API fails, continue to SMTP method
            logger.info("Mailgun API failed, falling back to SMTP...")
        except Exception as e:
            logger.error(f"Error with Mailgun API, falling back to SMTP: {str(e)}")
    
    # Try SMTP method
    try:
        success = send_async_email(app, msg)
        if success:
            return True
        # If sending fails, save to file
        logger.info(f"Email sending failed, saving to file as fallback")
    except Exception as e:
        logger.error(f"Error initiating email thread: {str(e)}")
    
    # Always save to file as a fallback
    return save_email_to_file(msg)

def save_email_to_file(msg):
    """Save email to a file as fallback when sending fails or as primary method in development."""
    try:
        # Create emails directory if it doesn't exist
        app = current_app._get_current_object()
        email_dir = os.path.join(app.instance_path, 'emails')
        os.makedirs(email_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"email_{timestamp}.json"
        filepath = os.path.join(email_dir, filename)
        
        # Convert email to JSON serializable format
        email_data = {
            'subject': msg.subject,
            'sender': msg.sender,
            'recipients': msg.recipients,
            'body': msg.body,
            'html': msg.html,
            'date': datetime.now().isoformat(),
            'attachments': []
        }
        
        # Handle attachments if any
        if hasattr(msg, 'attachments') and msg.attachments:
            for attachment in msg.attachments:
                if len(attachment) >= 3:
                    email_data['attachments'].append({
                        'filename': attachment[0],
                        'content_type': attachment[1],
                        'data_length': len(attachment[2]) if attachment[2] else 0
                    })
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(email_data, f, indent=4)
        
        # Also save HTML version for easy viewing
        html_filepath = os.path.join(email_dir, f"email_{timestamp}.html")
        with open(html_filepath, 'w') as f:
            f.write(f"<h2>Email: {msg.subject}</h2>")
            f.write(f"<p><strong>To:</strong> {', '.join(msg.recipients)}</p>")
            f.write(f"<p><strong>From:</strong> {msg.sender}</p>")
            f.write(f"<p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
            f.write("<hr>")
            f.write(msg.html or f"<pre>{msg.body}</pre>" or "<p>No content</p>")
        
        logger.info(f"Email saved to file: {filepath} and {html_filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save email to file: {str(e)}")
        return False

def send_registration_confirmation(registration):
    """Send registration confirmation email."""
    subject = "Registration Confirmation - SOD 2025"
    recipients = [registration.email]
    
    # Get the template data
    text_body = render_template('emails/registration_confirmation.txt', 
                               registration=registration)
    html_body = render_template('emails/registration_confirmation.html', 
                               registration=registration)
    
    return send_email(subject, recipients, text_body, html_body)

def send_payment_instructions(registration):
    """Send payment instructions email."""
    subject = "Payment Instructions - SOD 2025"
    recipients = [registration.email]
    
    # Get the template data
    text_body = render_template('emails/payment_instructions.txt', 
                               registration=registration)
    html_body = render_template('emails/payment_instructions.html', 
                               registration=registration)
    
    return send_email(subject, recipients, text_body, html_body)

def send_payment_confirmation(registration):
    """Send confirmation email with QR code to attendee"""
    try:
        # Create message
        msg = Message(
            'SOD 2025 Registration Confirmed!',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[registration.email]
        )
        
        # Render both HTML and text versions
        msg.html = render_template('emails/payment_confirmation.html', registration=registration)
        msg.body = render_template('emails/payment_confirmation.txt', registration=registration)
        
        # Attach QR code if it exists
        if registration.qr_code:
            qr_code_path = os.path.join(current_app.config['STATIC_FOLDER'], registration.qr_code)
            if os.path.exists(qr_code_path):
                with open(qr_code_path, 'rb') as qr:
                    msg.attach('qr_code.png', 'image/png', qr.read(), 'inline', 
                             headers=[['Content-ID', '<qr_code>']])
            else:
                current_app.logger.error(f"QR code file not found at {qr_code_path}")
                return False
        else:
            current_app.logger.error(f"No QR code path set for registration {registration.id}")
            return False
        
        # Send email
        mail.send(msg)
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error sending confirmation email: {str(e)}")
        return False

def send_qr_code(registration):
    """Send QR code email."""
    subject = "Your QR Code for SOD 2025"
    recipients = [registration.email]
    
    # Get the template data
    text_body = render_template('emails/qr_code.txt', 
                               registration=registration)
    html_body = render_template('emails/qr_code.html', 
                               registration=registration)
    
    # Generate QR code
    from app.utils.qr_code import generate_qr_code
    qr_code_data = generate_qr_code(registration.id)
    
    attachments = [{
        'filename': f'qr_code_{registration.id}.png',
        'content_type': 'image/png',
        'data': qr_code_data
    }]
    
    return send_email(subject, recipients, text_body, html_body, attachments)

def send_test_email(recipient):
    """Send a test email."""
    subject = "Test Email from SOD 2025"
    text_body = "This is a test email from the SOD 2025 application."
    html_body = "<p>This is a test email from the SOD 2025 application.</p>"
    
    return send_email(subject, [recipient], text_body, html_body)

def send_receipt_submission_confirmation(registration):
    """Send receipt submission confirmation email"""
    return send_email(
        subject="SOD 2025 - Receipt Submission Confirmation",
        recipients=[registration.email],
        text_body="",
        html_body=render_template('emails/receipt_submission.html', registration=registration)
    )

def send_receipt_rejection(registration, reason):
    """Send rejection email to attendee"""
    try:
        msg = Message(
            'SOD 2025 Registration Update',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[registration.email]
        )
        
        msg.html = render_template('emails/receipt_rejection.html', 
                                 registration=registration,
                                 reason=reason)
        msg.body = render_template('emails/receipt_rejection.txt', 
                                 registration=registration,
                                 reason=reason)
        
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending rejection email: {str(e)}")
        return False

def send_event_reminder(registration):
    """Send event reminder email to attendee"""
    try:
        msg = Message(
            'SOD 2025 Event Reminder',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[registration.email]
        )
        
        msg.html = render_template('emails/event_reminder.html', registration=registration)
        msg.body = render_template('emails/event_reminder.txt', registration=registration)
        
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending reminder email: {str(e)}")
        return False

def notify_admin_new_receipt(registration, admin_emails):
    """Notify admins about a new receipt upload"""
    return send_email(
        subject="SOD 2025 - New Receipt Uploaded",
        recipients=admin_emails,
        text_body="",
        html_body=render_template('emails/admin_new_receipt.html', registration=registration)
    ) 