import os
import uuid
import qrcode
from flask import current_app
from datetime import datetime
import json
import base64
from cryptography.fernet import Fernet
from app.models.user import Registration
import logging

def generate_unique_id():
    """Generate a unique ID for QR codes"""
    return str(uuid.uuid4())

def generate_qr_code(registration_id, registration_email):
    """
    Generate a QR code for a registration
    
    Args:
        registration_id: The ID of the registration
        registration_email: The email of the registrant
        
    Returns:
        The path to the generated QR code file
    """
    try:
        # Create QR code data (JSON with registration ID and email)
        qr_data = json.dumps({
            'id': registration_id,
            'email': registration_email
        })
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create an image from the QR Code
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Get the QR code folder from app config
        qr_folder = current_app.config.get('QR_CODE_FOLDER', 'app/static/qrcodes')
        
        # Ensure the directory exists
        os.makedirs(qr_folder, exist_ok=True)
        
        # Save the QR code image
        filename = f"{registration_id}.png"
        filepath = os.path.join(qr_folder, filename)
        img.save(filepath)
        
        current_app.logger.info(f"QR code generated and saved to {filepath}")
        
        # Return the path relative to the static folder
        return f"qrcodes/{filename}"
    except Exception as e:
        current_app.logger.error(f"Error generating QR code: {e}")
        raise

def get_encryption_key():
    """Get or generate an encryption key for QR codes"""
    key = current_app.config.get('QR_ENCRYPTION_KEY')
    if not key:
        # Generate a key and store it in the app config
        key = Fernet.generate_key()
        current_app.config['QR_ENCRYPTION_KEY'] = key
    return key

def encrypt_qr_data(data):
    """Encrypt QR code data"""
    key = get_encryption_key()
    f = Fernet(key)
    json_data = json.dumps(data)
    encrypted_data = f.encrypt(json_data.encode())
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_qr_data(encrypted_data):
    """Decrypt QR code data"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decoded_data = base64.urlsafe_b64decode(encrypted_data)
        decrypted_data = f.decrypt(decoded_data)
        return json.loads(decrypted_data.decode())
    except Exception as e:
        current_app.logger.error(f"Error decrypting QR code: {e}")
        return None 