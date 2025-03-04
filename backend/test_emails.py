"""
Test script to verify email templates.
Run this script with: flask shell < test_emails.py
"""

import os
import sys
from datetime import datetime
from app.models.user import Registration, RegistrationStatus
from app.utils.email import (
    send_registration_confirmation,
    send_receipt_submission_confirmation,
    send_receipt_rejection,
    send_payment_confirmation,
    send_event_reminder,
    notify_admin_new_receipt
)

# Create a mock registration object
mock_registration = Registration(
    id=12345,
    name="Test User",
    email="test@example.com",
    phone_number="+1234567890",
    status=RegistrationStatus.PENDING_VERIFICATION,
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)

# Create QR code directory if it doesn't exist
from flask import current_app
qr_dir = current_app.config['QR_CODE_FOLDER']
os.makedirs(qr_dir, exist_ok=True)

# Create a dummy QR code file for testing
import qrcode
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)
qr.add_data(f"SOD2025:{mock_registration.id}:{mock_registration.email}")
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.save(os.path.join(qr_dir, f"{mock_registration.id}.png"))

# Test all email templates
print("Testing registration confirmation email...")
send_registration_confirmation(mock_registration)

print("Testing receipt submission confirmation email...")
send_receipt_submission_confirmation(mock_registration)

print("Testing receipt rejection email...")
mock_registration.status = RegistrationStatus.REJECTED
send_receipt_rejection(mock_registration)

print("Testing payment confirmation email with QR code...")
mock_registration.status = RegistrationStatus.CONFIRMED
send_payment_confirmation(mock_registration)

print("Testing event reminder email...")
send_event_reminder(mock_registration)

print("Testing admin notification email...")
notify_admin_new_receipt(["admin@example.com"], mock_registration)

print("All email tests completed. Check your email server or logs.")

# Exit the flask shell
sys.exit() 