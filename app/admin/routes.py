from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app import db
from app.admin import admin_bp
from app.models.user import Registration, Admin, CheckIn, RegistrationStatus
from app.utils.qrcode_generator import generate_qr_code
from app.utils.email import send_payment_confirmation, send_receipt_rejection
from datetime import datetime
import json
import os

# Context processor to add current year to all templates
@admin_bp.context_processor
def inject_now():
    return {'now': datetime.now()}

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard"""
    # Get stats for different statuses
    stats = {
        'total': Registration.query.filter_by(is_archived=False).count(),
        'pending_payment': Registration.query.filter_by(status=RegistrationStatus.PENDING_PAYMENT, is_archived=False).count(),
        'pending_verification': Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION, is_archived=False).count(),
        'confirmed': Registration.query.filter_by(status=RegistrationStatus.CONFIRMED, is_archived=False).count(),
        'rejected': Registration.query.filter_by(status=RegistrationStatus.REJECTED, is_archived=False).count(),
        'archived': Registration.query.filter_by(is_archived=True).count()
    }
    
    # Get recent registrations (non-archived)
    recent_registrations = Registration.query.filter_by(is_archived=False).order_by(Registration.created_at.desc()).limit(10).all()
    
    # Get pending verifications (non-archived)
    pending_verifications = Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION, is_archived=False).order_by(Registration.updated_at.desc()).limit(5).all()
    
    # Get recent check-ins
    recent_checkins = CheckIn.query.order_by(CheckIn.check_in_time.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                          stats=stats,
                          recent_registrations=recent_registrations,
                          pending_verifications=pending_verifications,
                          recent_checkins=recent_checkins)

@admin_bp.route('/registrations')
@login_required
def registrations():
    """View all registrations with pagination and filtering"""
    # Get filter parameters
    status = request.args.get('status', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'created_at_desc')
    show_archived = request.args.get('show_archived', '') == 'true'
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Base query
    query = Registration.query
    
    # Filter by archived status
    if not show_archived:
        query = query.filter_by(is_archived=False)
    
    # Apply filters
    if status:
        try:
            status_enum = RegistrationStatus[status]
            query = query.filter_by(status=status_enum)
        except KeyError:
            flash(f'Invalid status filter: {status}', 'warning')
    
    # Apply search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Registration.name.ilike(search_term),
                Registration.email.ilike(search_term),
                Registration.phone_number.ilike(search_term)
            )
        )
    
    # Apply sorting
    if sort == 'created_at_desc':
        query = query.order_by(Registration.created_at.desc())
    elif sort == 'created_at_asc':
        query = query.order_by(Registration.created_at.asc())
    elif sort == 'name_asc':
        query = query.order_by(Registration.name.asc())
    elif sort == 'name_desc':
        query = query.order_by(Registration.name.desc())
    else:
        query = query.order_by(Registration.created_at.desc())
    
    # Paginate results
    registrations = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/registrations.html', registrations=registrations, show_archived=show_archived)

@admin_bp.route('/registration/<int:registration_id>')
@login_required
def view_registration(registration_id):
    """View a specific registration"""
    registration = Registration.query.get_or_404(registration_id)
    return render_template('admin/registration_detail.html', registration=registration)

@admin_bp.route('/qr-scanner')
@login_required
def qr_scanner():
    # Get recent check-ins for the history table
    recent_check_ins = CheckIn.query.order_by(CheckIn.check_in_time.desc()).limit(10).all()
    return render_template('admin/qr_scanner.html', recent_check_ins=recent_check_ins)

@admin_bp.route('/verify-qr', methods=['POST'])
@login_required
def verify_qr():
    data = request.json
    if not data or 'qr_data' not in data:
        return jsonify({'valid': False, 'message': 'No QR data provided'}), 400
    
    qr_data = data['qr_data']
    
    try:
        # QR data should be in JSON format with registration ID
        qr_json = json.loads(qr_data)
        
        if 'id' not in qr_json:
            return jsonify({'valid': False, 'message': 'Invalid QR code format'}), 400
        
        registration_id = qr_json['id']
        registration = Registration.query.get(registration_id)
        
        if not registration:
            return jsonify({'valid': False, 'message': 'Registration not found'}), 404
        
        # Verify the registration is approved/confirmed
        if registration.status != RegistrationStatus.CONFIRMED:
            return jsonify({'valid': False, 'message': f'Registration is not confirmed (Status: {registration.status.value})'}), 400
        
        # Check if already checked in
        already_checked_in = CheckIn.query.filter_by(registration_id=registration_id).first() is not None
        
        return jsonify({
            'valid': True,
            'registration': {
                'id': registration.id,
                'name': registration.name,
                'email': registration.email,
                'phone_number': registration.phone_number,
                'status': registration.status.value,
                'view_url': url_for('admin.view_registration', registration_id=registration.id)
            },
            'already_checked_in': already_checked_in
        })
        
    except json.JSONDecodeError:
        return jsonify({'valid': False, 'message': 'Invalid QR code format'}), 400
    except Exception as e:
        return jsonify({'valid': False, 'message': str(e)}), 500

@admin_bp.route('/check-in/<int:registration_id>', methods=['POST'])
@login_required
def check_in(registration_id):
    """Check in an attendee"""
    registration = Registration.query.get_or_404(registration_id)
    
    if registration.status != RegistrationStatus.CONFIRMED:
        flash('This registration is not confirmed', 'danger')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Check if already checked in
    existing_check_in = CheckIn.query.filter_by(registration_id=registration_id).first()
    if existing_check_in:
        flash('Attendee already checked in', 'warning')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Create check-in record
    check_in = CheckIn(registration_id=registration_id)
    db.session.add(check_in)
    db.session.commit()
    
    flash('Attendee successfully checked in', 'success')
    return redirect(url_for('admin.view_registration', registration_id=registration_id))

@admin_bp.route('/registration/<int:registration_id>/approve', methods=['POST'])
@login_required
def approve_receipt(registration_id):
    """Approve a receipt and generate QR code"""
    registration = Registration.query.get_or_404(registration_id)
    
    if registration.status != RegistrationStatus.PENDING_VERIFICATION:
        flash('This registration is not pending verification.', 'warning')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Generate QR code
    try:
        # Generate QR code and get the path
        qr_code_path = generate_qr_code(registration.id, registration.email)
        
        # Update registration status and QR code
        registration.status = RegistrationStatus.CONFIRMED
        registration.qr_code = f"qrcodes/{registration.id}.png"  # Store relative path to static directory
        db.session.commit()
        
        # Send confirmation email with QR code
        try:
            send_payment_confirmation(registration)
            flash('Registration confirmed and confirmation email sent.', 'success')
        except Exception as e:
            current_app.logger.error(f"Error sending confirmation email: {e}")
            # Check if emails directory exists (indicating fallback worked)
            emails_dir = os.path.join(current_app.root_path, 'emails')
            if os.path.exists(emails_dir):
                flash('Registration confirmed. Email delivery failed, but a copy has been saved locally.', 'warning')
            else:
                flash('Registration confirmed but there was an error sending the confirmation email. Check mail server settings.', 'warning')
        
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    except Exception as e:
        current_app.logger.error(f"Error generating QR code: {e}")
        flash(f'Error generating QR code: {str(e)}', 'danger')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))

@admin_bp.route('/reject-receipt/<int:registration_id>', methods=['POST'])
@login_required
def reject_receipt(registration_id):
    """Reject a receipt"""
    registration = Registration.query.get_or_404(registration_id)
    
    if registration.status != RegistrationStatus.PENDING_VERIFICATION:
        flash('This registration is not pending verification', 'error')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Update registration
    registration.status = RegistrationStatus.REJECTED
    db.session.commit()
    
    # Send rejection email
    send_receipt_rejection(registration)
    
    flash('Receipt rejected', 'info')
    return redirect(url_for('admin.view_registration', registration_id=registration_id))

@admin_bp.route('/pending-verifications')
@login_required
def pending_verifications():
    """View all registrations pending verification"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get all registrations pending verification
    query = Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION)
    query = query.order_by(Registration.updated_at.desc())
    
    # Paginate results
    registrations = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/pending_verifications.html', registrations=registrations)

@admin_bp.route('/preview-attendees')
@login_required
def preview_attendees():
    """Preview attendees before export"""
    # Get filter parameters
    status = request.args.get('status', 'CONFIRMED')
    checked_in = request.args.get('checked_in', '')
    
    # Base query
    query = Registration.query
    
    # Apply filters
    if status:
        try:
            status_enum = getattr(RegistrationStatus, status)
            query = query.filter_by(status=status_enum)
        except (AttributeError, ValueError):
            pass
    
    # Filter by check-in status if specified
    if checked_in == 'yes':
        query = query.join(CheckIn).filter(CheckIn.registration_id == Registration.id)
    elif checked_in == 'no':
        query = query.outerjoin(CheckIn).filter(CheckIn.id == None)
    
    # Get all matching registrations
    registrations = query.order_by(Registration.name.asc()).all()
    
    return render_template('admin/preview_attendees.html', 
                          registrations=registrations,
                          status=status,
                          checked_in=checked_in)

@admin_bp.route('/export-attendees')
@login_required
def export_attendees():
    """Export attendees as CSV"""
    # Get filter parameters
    status = request.args.get('status', 'CONFIRMED')
    checked_in = request.args.get('checked_in', '')
    
    # Base query
    query = Registration.query
    
    # Apply filters
    if status:
        try:
            status_enum = getattr(RegistrationStatus, status)
            query = query.filter_by(status=status_enum)
        except (AttributeError, ValueError):
            pass
    
    # Filter by check-in status if specified
    if checked_in == 'yes':
        query = query.join(CheckIn).filter(CheckIn.registration_id == Registration.id)
    elif checked_in == 'no':
        query = query.outerjoin(CheckIn).filter(CheckIn.id == None)
    
    # Get all matching registrations
    registrations = query.order_by(Registration.name.asc()).all()
    
    # Create CSV in memory
    import csv
    import io
    from datetime import datetime
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Name', 'Email', 'Phone Number', 'Registration Date', 'Status', 'Checked In', 'Check-in Time'])
    
    # Write data
    for reg in registrations:
        check_in = CheckIn.query.filter_by(registration_id=reg.id).first()
        writer.writerow([
            reg.id,
            reg.name,
            reg.email,
            reg.phone_number,
            reg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            reg.status.value,
            'Yes' if check_in else 'No',
            check_in.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if check_in else ''
        ])
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'sod2025_attendees_{timestamp}.csv'
    )

@admin_bp.route('/send-reminder', methods=['POST'])
@login_required
def send_reminder():
    """Send reminder emails to selected registrations"""
    from app.utils.email import send_event_reminder
    
    reminder_type = request.form.get('reminder_type', 'all')
    custom_message = request.form.get('custom_message', '')
    
    # Determine which registrations to send reminders to
    if reminder_type == 'all':
        registrations = Registration.query.filter_by(status=RegistrationStatus.CONFIRMED).all()
    elif reminder_type == 'not_checked_in':
        registrations = Registration.query.filter_by(status=RegistrationStatus.CONFIRMED)\
            .outerjoin(CheckIn).filter(CheckIn.id == None).all()
    else:
        flash('Invalid reminder type', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Send reminders
    sent_count = 0
    for registration in registrations:
        try:
            send_event_reminder(registration, custom_message)
            sent_count += 1
        except Exception as e:
            current_app.logger.error(f"Failed to send reminder to {registration.email}: {str(e)}")
    
    flash(f'Sent {sent_count} reminder emails', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/registration/<int:registration_id>/delete', methods=['POST'])
@login_required
def delete_registration(registration_id):
    """Delete a registration"""
    registration = Registration.query.get_or_404(registration_id)
    
    # Delete associated check-ins first to avoid foreign key constraint errors
    CheckIn.query.filter_by(registration_id=registration_id).delete()
    
    # Store email for flash message
    email = registration.email
    
    # Delete the registration
    db.session.delete(registration)
    db.session.commit()
    
    flash(f'Registration for {email} has been permanently deleted.', 'success')
    return redirect(url_for('admin.registrations'))

@admin_bp.route('/registration/<int:registration_id>/archive', methods=['POST'])
@login_required
def archive_registration(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    registration.is_archived = True
    db.session.commit()
    flash('Registration archived successfully', 'success')
    return redirect(url_for('admin.registrations'))

@admin_bp.route('/registration/<int:registration_id>/unarchive', methods=['POST'])
@login_required
def unarchive_registration(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    registration.is_archived = False
    db.session.commit()
    flash('Registration unarchived successfully', 'success')
    return redirect(url_for('admin.view_registration', registration_id=registration_id)) 