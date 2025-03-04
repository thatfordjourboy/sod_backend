from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from app import db
from app.models.user import Registration, RegistrationStatus
from app.utils.email import send_registration_confirmation, send_receipt_submission_confirmation, notify_admin_new_receipt
from app.utils.file_upload import save_receipt
from app.models.user import Admin
import uuid

main_bp = Blueprint('main', __name__)

@main_bp.route('/register', methods=['POST'])
def register():
    """Register a new attendee"""
    data = request.json
    
    # Validate required fields
    if not data or not data.get('name') or not data.get('email') or not data.get('phone_number'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if email or phone number already exists
    existing_email = Registration.query.filter_by(email=data['email']).first()
    if existing_email:
        return jsonify({'error': 'Email already registered'}), 409
    
    existing_phone = Registration.query.filter_by(phone_number=data['phone_number']).first()
    if existing_phone:
        return jsonify({'error': 'Phone number already registered'}), 409
    
    # Create new registration
    new_registration = Registration(
        name=data['name'],
        email=data['email'],
        phone_number=data['phone_number'],
        status=RegistrationStatus.PENDING_VERIFICATION
    )
    
    db.session.add(new_registration)
    db.session.commit()
    
    # Send confirmation email
    send_registration_confirmation(new_registration)
    
    return jsonify({
        'message': 'Registration successful',
        'registration_id': new_registration.id
    }), 201

@main_bp.route('/upload-receipt/<int:registration_id>', methods=['POST'])
def upload_receipt(registration_id):
    """Upload a receipt for a registration"""
    # Find the registration
    registration = Registration.query.get_or_404(registration_id)
    
    # Check if registration is in a valid state for receipt upload
    if registration.status not in [RegistrationStatus.REJECTED]:
        return jsonify({'error': 'Registration is not in a valid state for receipt upload'}), 400
    
    # Check if file was included in the request
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['receipt']
    
    # Check if file is empty
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save the file and get the path
    receipt_path = save_receipt(file)
    
    if not receipt_path:
        return jsonify({'error': 'Invalid file type. Please upload a PNG, JPG, JPEG, or PDF file.'}), 400
    
    # Update registration with receipt path and change status
    registration.receipt_url = receipt_path
    registration.status = RegistrationStatus.PENDING_VERIFICATION
    db.session.commit()
    
    # Send confirmation email to user
    send_receipt_submission_confirmation(registration)
    
    # Notify admins about the new receipt
    admin_emails = [admin.email for admin in Admin.query.all()]
    if admin_emails:
        notify_admin_new_receipt(admin_emails, registration)
    
    return jsonify({
        'message': 'Receipt uploaded successfully',
        'status': registration.status.value
    }), 200

@main_bp.route('/check-status/<int:registration_id>', methods=['GET'])
def check_status(registration_id):
    """Check the status of a registration"""
    registration = Registration.query.get_or_404(registration_id)
    
    return jsonify({
        'status': registration.status.value,
        'name': registration.name,
        'email': registration.email,
        'has_receipt': bool(registration.receipt_url),
        'qr_code': bool(registration.qr_code)
    }), 200

@main_bp.route('/verify-email/<email>', methods=['GET'])
def verify_email(email):
    """Check if an email is already registered"""
    existing = Registration.query.filter_by(email=email).first()
    return jsonify({'exists': bool(existing)}), 200

@main_bp.route('/verify-phone/<phone>', methods=['GET'])
def verify_phone(phone):
    """Check if a phone number is already registered"""
    existing = Registration.query.filter_by(phone_number=phone).first()
    return jsonify({'exists': bool(existing)}), 200

@main_bp.route('/')
def root():
    """Redirect to login page"""
    return redirect(url_for('auth.login')) 