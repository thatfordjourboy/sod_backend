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
from qrcode.image.pil import PilImage

def generate_unique_id():
    """Generate a unique ID for QR codes"""
    return str(uuid.uuid4())

def generate_qr_code(data, output_path):
    """Generate a QR code with the given data and save it to the specified path"""
    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        
        # Add data
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save image
        qr_image.save(output_path)
        
        return True
    except Exception as e:
        current_app.logger.error(f"Error generating QR code: {str(e)}")
        return False

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