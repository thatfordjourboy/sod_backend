from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.user import Registration, RegistrationStatus, CheckIn
from app.utils.email import send_registration_confirmation, send_receipt_submission_confirmation
from app.utils.file_upload import save_receipt
from app.utils.qrcode_generator import decrypt_qr_data
from functools import wraps
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Simple API key authentication for frontend
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != current_app.config.get('API_KEY', 'your-api-key-here'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/registrations', methods=['GET'])
@require_api_key
def get_registrations():
    """Get all registrations (for admin dashboard)"""
    registrations = Registration.query.all()
    return jsonify({
        'registrations': [reg.to_dict() for reg in registrations]
    }), 200

@api_bp.route('/registrations/<int:registration_id>', methods=['GET'])
@require_api_key
def get_registration(registration_id):
    """Get a specific registration"""
    registration = Registration.query.get_or_404(registration_id)
    return jsonify(registration.to_dict()), 200

@api_bp.route('/register', methods=['POST'])
def register():
    """Register a new attendee (public API)"""
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
        status=RegistrationStatus.PENDING_PAYMENT
    )
    
    db.session.add(new_registration)
    db.session.commit()
    
    # Send confirmation email
    send_registration_confirmation(new_registration)
    
    return jsonify({
        'message': 'Registration successful',
        'registration_id': new_registration.id
    }), 201

@api_bp.route('/upload-receipt/<int:registration_id>', methods=['POST'])
def upload_receipt(registration_id):
    """Upload a receipt for a registration (public API)"""
    # Find the registration
    registration = Registration.query.get_or_404(registration_id)
    
    # Check if registration is in a valid state for receipt upload
    if registration.status not in [RegistrationStatus.PENDING_PAYMENT, RegistrationStatus.REJECTED]:
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
    
    return jsonify({
        'message': 'Receipt uploaded successfully',
        'status': registration.status.value
    }), 200

@api_bp.route('/check-status/<int:registration_id>', methods=['GET'])
def check_status(registration_id):
    """Check the status of a registration (public API)"""
    registration = Registration.query.get_or_404(registration_id)
    
    return jsonify({
        'status': registration.status.value,
        'name': registration.name,
        'email': registration.email,
        'has_receipt': bool(registration.receipt_url),
        'qr_code': bool(registration.qr_code)
    }), 200

@api_bp.route('/verify-qr-code', methods=['POST'])
@require_api_key
def verify_qr_code():
    """Verify a QR code and check in an attendee"""
    data = request.json
    
    if not data or not data.get('qr_data'):
        return jsonify({'error': 'Missing QR code data'}), 400
    
    # Decrypt QR code data
    qr_info = decrypt_qr_data(data['qr_data'])
    
    if not qr_info or 'id' not in qr_info:
        return jsonify({'error': 'Invalid QR code'}), 400
    
    # Get registration
    registration_id = qr_info['id']
    registration = Registration.query.get(registration_id)
    
    if not registration:
        return jsonify({'error': 'Registration not found'}), 404
    
    if registration.status != RegistrationStatus.CONFIRMED:
        return jsonify({'error': 'Registration is not confirmed'}), 400
    
    # Check if already checked in
    existing_check_in = CheckIn.query.filter_by(registration_id=registration_id).first()
    if existing_check_in:
        return jsonify({
            'error': 'Already checked in',
            'check_in_time': existing_check_in.check_in_time.isoformat()
        }), 400
    
    # Create check-in record
    check_in = CheckIn(registration_id=registration_id)
    db.session.add(check_in)
    db.session.commit()
    
    return jsonify({
        'message': 'Check-in successful',
        'name': registration.name,
        'email': registration.email,
        'check_in_time': check_in.check_in_time.isoformat()
    }), 200

@api_bp.route('/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get registration statistics"""
    total_registrations = Registration.query.count()
    pending_verification = Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION).count()
    confirmed = Registration.query.filter_by(status=RegistrationStatus.CONFIRMED).count()
    rejected = Registration.query.filter_by(status=RegistrationStatus.REJECTED).count()
    checked_in = CheckIn.query.count()
    
    return jsonify({
        'total_registrations': total_registrations,
        'pending_verification': pending_verification,
        'confirmed': confirmed,
        'rejected': rejected,
        'checked_in': checked_in
    }), 200 