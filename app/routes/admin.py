from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from app import db
from app.models.user import Registration, RegistrationStatus, CheckIn, Permission, Admin, Role, AuditLog
from app.utils.email import send_payment_confirmation, send_receipt_rejection, send_event_reminder
from app.utils.qrcode_generator import generate_qr_code
from app.utils.decorators import permission_required
import csv
import io
from datetime import datetime
import json
import os
import logging
import qrcode

# Set up logger
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
def dashboard():
    """Admin dashboard route"""
    # Get registration statistics
    stats = {
        'total': Registration.query.count(),
        'pending_payment': Registration.query.filter_by(status=RegistrationStatus.PENDING_PAYMENT).count(),
        'pending_verification': Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION).count(),
        'confirmed': Registration.query.filter_by(status=RegistrationStatus.CONFIRMED).count(),
        'rejected': Registration.query.filter_by(status=RegistrationStatus.REJECTED).count(),
        'archived': Registration.query.filter_by(is_archived=True).count()
    }
    
    # Get recent registrations
    recent_registrations = Registration.query.order_by(Registration.created_at.desc()).limit(10).all()
    
    # Get recent audit logs
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()
    
    # Get recent check-ins
    recent_checkins = CheckIn.query.order_by(CheckIn.check_in_time.desc()).limit(5).all()
    
    # Get pending verifications
    pending_verifications = Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION).order_by(Registration.updated_at.desc()).limit(5).all()
    
    logger.info(f"Admin {current_user.email} accessed dashboard")
    
    return render_template('admin/dashboard.html', 
                          stats=stats,
                          total_registrations=stats['total'],
                          approved_registrations=stats['confirmed'],
                          pending_registrations=stats['pending_verification'],
                          rejected_registrations=stats['rejected'],
                          checked_in=Registration.query.filter_by(checked_in=True).count(),
                          recent_registrations=recent_registrations,
                          recent_logs=recent_logs,
                          recent_checkins=recent_checkins,
                          pending_verifications=pending_verifications)

@admin_bp.route('/registrations')
@login_required
@permission_required(Permission.VIEW_REGISTRATIONS)
def registrations():
    """List all registrations"""
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = Registration.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    registrations = query.order_by(Registration.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    logger.info(f"Admin {current_user.email} viewed registrations with status filter: {status}")
    
    return render_template('admin/registrations.html',
                           registrations=registrations,
                           status=status)

@admin_bp.route('/registration/<int:registration_id>')
@login_required
@permission_required(Permission.VIEW_REGISTRATIONS)
def view_registration(registration_id):
    """View a specific registration"""
    registration = Registration.query.get_or_404(registration_id)
    
    # Get check-in history
    check_ins = CheckIn.query.filter_by(registration_id=registration_id).order_by(CheckIn.check_in_time.desc()).all()
    
    # Get audit logs for this registration
    audit_logs = AuditLog.query.filter(
        AuditLog.details.like(f"%Registration ID: {registration_id}%")
    ).order_by(AuditLog.timestamp.desc()).all()
    
    logger.info(f"Admin {current_user.email} viewed registration details for ID: {registration_id}")
    
    return render_template('admin/registration_detail.html', 
                         registration=registration,
                         check_ins=check_ins,
                         audit_logs=audit_logs)

@admin_bp.route('/approve-receipt/<int:registration_id>', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def approve_receipt(registration_id):
    """Approve a registration receipt"""
    registration = Registration.query.get_or_404(registration_id)
    
    if registration.status != RegistrationStatus.PENDING_VERIFICATION:
        logger.error(f"Invalid status for registration {registration_id}: {registration.status}")
        return jsonify({
            'success': False,
            'message': 'Registration is not pending verification'
        }), 400
    
    try:
        # Generate QR code first
        qr_code_path = os.path.join(current_app.config['QR_CODE_FOLDER'], f'qr_{registration.id}.png')
        qr_data = f"{registration.id}:{registration.email}"
        
        logger.info(f"Generating QR code at path: {qr_code_path}")
        
        # Ensure QR code directory exists
        os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_code_path)
        
        logger.info(f"QR code generated successfully at {qr_code_path}")
        
        # Calculate relative path from static folder
        static_folder = current_app.config['STATIC_FOLDER']
        relative_qr_path = os.path.relpath(qr_code_path, static_folder)
        logger.info(f"Relative QR path: {relative_qr_path}")
        
        # Update registration status and QR code path
        registration.status = RegistrationStatus.CONFIRMED
        registration.qr_code = relative_qr_path
        db.session.commit()
        
        logger.info(f"Registration {registration_id} status updated to CONFIRMED")
        
        # Try to send confirmation email
        email_sent = send_payment_confirmation(registration)
        
        # Create audit log regardless of email status
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_APPROVE,
            resource_type=AuditLog.RESOURCE_REGISTRATION,
            resource_id=registration.id,
            details=f"Approved registration for {registration.name} ({registration.email})",
            ip_address=request.remote_addr
        )
        
        if email_sent:
            logger.info(f"Email sent successfully for registration {registration_id}")
            message = 'Registration approved and QR code sent successfully'
        else:
            logger.warning(f"Email sending failed for registration {registration_id}, but registration was approved")
            message = 'Registration approved, but there was an issue sending the confirmation email. The email will be sent later.'
        
        return jsonify({
            'success': True,
            'message': message
        })
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error approving registration {registration_id}: {str(e)}")
        logger.exception("Full traceback:")  # This will log the full stack trace
        return jsonify({
            'success': False,
            'message': 'An error occurred while approving the registration'
        }), 500

@admin_bp.route('/reject-receipt/<int:registration_id>', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def reject_receipt(registration_id):
    """Reject a registration receipt"""
    registration = Registration.query.get_or_404(registration_id)
    
    if registration.status != RegistrationStatus.PENDING_VERIFICATION:
        return jsonify({
            'success': False,
            'message': 'Registration is not pending verification'
        }), 400
    
    data = request.get_json()
    if not data or 'reason' not in data:
        return jsonify({
            'success': False,
            'message': 'Rejection reason is required'
        }), 400
    
    try:
        registration.status = RegistrationStatus.REJECTED
        db.session.commit()
        
        # Send rejection email
        if send_receipt_rejection(registration, data['reason']):
            # Create audit log
            AuditLog.log(
                admin_id=current_user.id,
                action=AuditLog.ACTION_REJECT,
                resource_type=AuditLog.RESOURCE_REGISTRATION,
                resource_id=registration.id,
                details=f"Rejected registration for {registration.name} ({registration.email})",
                ip_address=request.remote_addr
            )
            
            return jsonify({
                'success': True,
                'message': 'Registration rejected successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error sending rejection email'
            }), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error rejecting registration {registration_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while rejecting the registration'
        }), 500

@admin_bp.route('/check-in/<int:registration_id>', methods=['POST'])
@login_required
@permission_required(Permission.CHECK_IN_ATTENDEES)
def check_in(registration_id):
    """Check in an attendee"""
    registration = Registration.query.get_or_404(registration_id)
    
    # Only allow check-in for confirmed registrations
    if registration.status != RegistrationStatus.CONFIRMED:
        flash('Only confirmed registrations can be checked in', 'warning')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Check if already checked in
    existing_checkin = CheckIn.query.filter_by(registration_id=registration_id).first()
    if existing_checkin:
        flash('This attendee has already been checked in', 'info')
        return redirect(url_for('admin.view_registration', registration_id=registration_id))
    
    # Create check-in record
    checkin = CheckIn(
        registration_id=registration_id,
        checked_in_by=current_user.id
    )
    
    # Update the registration's checked_in status
    registration.checked_in = True
    
    db.session.add(checkin)
    db.session.commit()
    
    flash('Attendee checked in successfully', 'success')
    return redirect(url_for('admin.view_registration', registration_id=registration_id))

@admin_bp.route('/export-attendees')
@login_required
@permission_required(Permission.EXPORT_DATA)
def export_attendees():
    """Export attendees to CSV"""
    # Get filter parameters
    status = request.args.get('status', '')
    
    # Start with base query
    query = Registration.query
    
    # Apply status filter if provided
    if status and status in [s.name for s in RegistrationStatus]:
        query = query.filter_by(status=RegistrationStatus[status])
    else:
        # Default to confirmed registrations
        query = query.filter_by(status=RegistrationStatus.CONFIRMED)
    
    # Get all matching registrations
    registrations = query.all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Status', 'Registration Date', 'Checked In'])
    
    # Write data
    for reg in registrations:
        checked_in = bool(reg.check_ins)
        writer.writerow([
            reg.id,
            reg.name,
            reg.email,
            reg.phone_number,
            reg.status.value,
            reg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if checked_in else 'No'
        ])
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'attendees_{timestamp}.csv'
    )

@admin_bp.route('/send-reminder', methods=['POST'])
@login_required
@permission_required(Permission.SEND_EMAILS)
def send_reminder():
    """Send reminder emails to confirmed attendees"""
    # Get all confirmed registrations
    registrations = Registration.query.filter_by(status=RegistrationStatus.CONFIRMED).all()
    
    # Send reminder emails
    count = 0
    for registration in registrations:
        send_event_reminder(registration)
        count += 1
    
    flash(f'Reminder emails sent to {count} confirmed attendees', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/pending-verifications')
@login_required
@permission_required(Permission.VIEW_REGISTRATIONS)
def pending_verifications():
    """View all pending verifications"""
    page = request.args.get('page', 1, type=int)
    
    # Get paginated pending verifications
    pending = Registration.query.filter_by(status=RegistrationStatus.PENDING_VERIFICATION)\
        .order_by(Registration.updated_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/pending_verifications.html', registrations=pending)

@admin_bp.route('/qr-scanner')
@login_required
@permission_required(Permission.CHECK_IN_ATTENDEES)
def qr_scanner():
    """QR code scanner for check-in"""
    logger.info(f"Admin {current_user.email} accessed QR scanner page")
    return render_template('admin/qr_scanner.html')

@admin_bp.route('/process-qr', methods=['POST'])
@login_required
@permission_required(Permission.CHECK_IN_ATTENDEES)
def process_qr():
    """Process QR code data and check in attendee"""
    data = request.json
    qr_data = data.get('qr_data')
    
    if not qr_data:
        logger.warning(f"Admin {current_user.email} submitted empty QR data")
        return jsonify({'success': False, 'message': 'QR data is required'}), 400
    
    try:
        # QR data should be in format "REG_ID:EMAIL"
        parts = qr_data.split(':')
        if len(parts) != 2:
            return jsonify({'success': False, 'message': 'Invalid QR code format'}), 400
        
        reg_id, email = parts
        
        # Find registration
        registration = Registration.query.filter_by(id=reg_id, email=email).first()
        
        if not registration:
            logger.warning(f"Admin {current_user.email} scanned invalid QR code with data: {qr_data}")
            return jsonify({'success': False, 'message': 'Invalid QR code. Registration not found.'}), 404
        
        if registration.status != 'APPROVED':
            logger.warning(f"Admin {current_user.email} attempted to check in non-approved registration via QR code, ID: {reg_id}")
            return jsonify({
                'success': False, 
                'message': f'Registration is not approved (Status: {registration.status})',
                'registration': {
                    'id': registration.id,
                    'name': f"{registration.first_name} {registration.last_name}",
                    'email': registration.email,
                    'status': registration.status
                }
            }), 400
        
        # Check if already checked in
        if registration.checked_in:
            logger.info(f"Admin {current_user.email} scanned QR for already checked-in attendee ID: {reg_id}")
            return jsonify({
                'success': True,
                'already_checked_in': True,
                'attendee': {
                    'id': registration.id,
                    'name': f"{registration.first_name} {registration.last_name}",
                    'email': registration.email,
                    'check_in_time': registration.check_in_time.isoformat() if registration.check_in_time else None
                },
                'message': f'{registration.first_name} {registration.last_name} is already checked in.'
            })
        
        # Perform check-in
        registration.checked_in = True
        registration.check_in_time = datetime.utcnow()
        db.session.commit()
        
        # Log the check-in
        ip_address = request.remote_addr
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_CHECKIN,
            resource_type=AuditLog.RESOURCE_CHECKIN,
            resource_id=registration.id,
            details=f"Checked in attendee {registration.first_name} {registration.last_name} ({registration.email}) via QR scan",
            ip_address=ip_address
        )
        
        logger.info(f"Admin {current_user.email} checked in attendee via QR code, ID: {reg_id} - {registration.first_name} {registration.last_name}")
        
        return jsonify({
            'success': True,
            'already_checked_in': False,
            'attendee': {
                'id': registration.id,
                'name': f"{registration.first_name} {registration.last_name}",
                'email': registration.email,
                'check_in_time': registration.check_in_time.isoformat()
            },
            'message': f'{registration.first_name} {registration.last_name} has been checked in successfully.'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing QR code: {str(e)}")
        return jsonify({'success': False, 'message': f'Error processing QR code: {str(e)}'}), 500

@admin_bp.route('/settings')
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def settings():
    """Admin settings page"""
    admins = Admin.query.all()
    roles = Role.query.all()
    
    logger.info(f"Admin {current_user.email} accessed settings page")
    
    return render_template('admin/settings.html', admins=admins, roles=roles)

@admin_bp.route('/preview-attendees')
@login_required
@permission_required(Permission.EXPORT_DATA)
def preview_attendees():
    """Preview attendees before export"""
    return render_template('admin/preview_attendees.html')

@admin_bp.route('/api/registrations')
@login_required
@permission_required(Permission.VIEW_REGISTRATIONS)
def get_registrations():
    """API endpoint to get registrations data for DataTables"""
    # Get query parameters from DataTables
    draw = request.args.get('draw', type=int, default=1)
    start = request.args.get('start', type=int, default=0)
    length = request.args.get('length', type=int, default=10)
    search_value = request.args.get('search[value]', default='')
    
    # Filter by status if provided
    status_filter = request.args.get('status', default=None)
    
    # Start with base query
    query = Registration.query
    
    # Apply status filter if provided
    if status_filter and status_filter != 'ALL':
        query = query.filter_by(status=status_filter)
    
    # Apply search if provided
    if search_value:
        search_term = f"%{search_value}%"
        query = query.filter(
            (Registration.first_name.like(search_term)) |
            (Registration.last_name.like(search_term)) |
            (Registration.email.like(search_term)) |
            (Registration.phone.like(search_term))
        )
    
    # Get total count before pagination
    total_records = query.count()
    filtered_records = total_records  # If no search, filtered = total
    
    # Apply sorting
    order_column_idx = request.args.get('order[0][column]', type=int, default=0)
    order_direction = request.args.get('order[0][dir]', default='asc')
    
    # Map DataTables column index to model field
    columns = ['id', 'first_name', 'last_name', 'email', 'phone', 'status', 'created_at', 'checked_in']
    
    if order_column_idx < len(columns):
        order_column = columns[order_column_idx]
        column_obj = getattr(Registration, order_column)
        
        if order_direction == 'desc':
            query = query.order_by(column_obj.desc())
        else:
            query = query.order_by(column_obj.asc())
    
    # Apply pagination
    registrations = query.offset(start).limit(length).all()
    
    # Format data for DataTables
    data = []
    for reg in registrations:
        data.append({
            'id': reg.id,
            'first_name': reg.first_name,
            'last_name': reg.last_name,
            'email': reg.email,
            'phone': reg.phone,
            'status': reg.status,
            'created_at': reg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'checked_in': reg.checked_in,
            'actions': ''  # Placeholder for action buttons
        })
    
    # Return JSON response
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })

@admin_bp.route('/registration/<int:registration_id>', methods=['GET', 'PUT'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def registration_detail(registration_id):
    """Get or update a specific registration"""
    registration = Registration.query.get_or_404(registration_id)
    
    if request.method == 'GET':
        # Get check-in history
        check_ins = CheckIn.query.filter_by(registration_id=registration_id).order_by(CheckIn.check_in_time.desc()).all()
        
        # Get audit logs for this registration
        audit_logs = AuditLog.query.filter(
            AuditLog.details.like(f"%Registration ID: {registration_id}%")
        ).order_by(AuditLog.timestamp.desc()).all()
        
        return render_template('admin/registration_detail.html', 
                             registration=registration,
                             check_ins=check_ins,
                             audit_logs=audit_logs)
    
    elif request.method == 'PUT':
        data = request.json
        
        # Store original values for audit log
        original_status = registration.status
        original_checked_in = registration.checked_in
        
        # Update registration data
        if 'status' in data:
            registration.status = data['status']
        
        if 'checked_in' in data:
            registration.checked_in = data['checked_in']
            if data['checked_in']:
                # Create check-in record if not exists
                if not registration.check_ins:
                    checkin = CheckIn(
                        registration_id=registration.id,
                        checked_in_by=current_user.id
                    )
                    db.session.add(checkin)
        
        db.session.commit()
        
        # Log the registration update
        changes = []
        if 'status' in data and original_status != registration.status:
            changes.append(f"Status: {original_status} → {registration.status}")
            
            # Log specific approval/rejection actions
            if registration.status == RegistrationStatus.CONFIRMED:
                AuditLog.log(
                    admin_id=current_user.id,
                    action=AuditLog.ACTION_APPROVE,
                    resource_type=AuditLog.RESOURCE_REGISTRATION,
                    resource_id=registration.id,
                    details=f"Approved registration for {registration.name} ({registration.email})",
                    ip_address=request.remote_addr
                )
            elif registration.status == RegistrationStatus.REJECTED:
                AuditLog.log(
                    admin_id=current_user.id,
                    action=AuditLog.ACTION_REJECT,
                    resource_type=AuditLog.RESOURCE_REGISTRATION,
                    resource_id=registration.id,
                    details=f"Rejected registration for {registration.name} ({registration.email})",
                    ip_address=request.remote_addr
                )
        
        if 'checked_in' in data and original_checked_in != registration.checked_in:
            changes.append(f"Checked In: {original_checked_in} → {registration.checked_in}")
            
            if registration.checked_in:
                AuditLog.log(
                    admin_id=current_user.id,
                    action=AuditLog.ACTION_CHECKIN,
                    resource_type=AuditLog.RESOURCE_CHECKIN,
                    resource_id=registration.id,
                    details=f"Checked in attendee {registration.name} ({registration.email})",
                    ip_address=request.remote_addr
                )
        
        # General update log if there were changes
        if changes:
            AuditLog.log(
                admin_id=current_user.id,
                action=AuditLog.ACTION_UPDATE,
                resource_type=AuditLog.RESOURCE_REGISTRATION,
                resource_id=registration.id,
                details=f"Updated registration for {registration.name}. Changes: {', '.join(changes)}",
                ip_address=request.remote_addr
            )
        
        return jsonify({'message': 'Registration updated successfully'})

@admin_bp.route('/export-registrations')
@login_required
@permission_required(Permission.EXPORT_DATA)
def export_registrations():
    """Export registrations to CSV"""
    # Get filter parameters
    status = request.args.get('status', default=None)
    
    # Start with base query
    query = Registration.query
    
    # Apply status filter if provided
    if status and status != 'ALL':
        query = query.filter_by(status=status)
    
    # Get all registrations
    registrations = query.all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Status', 
                    'Created At', 'Checked In', 'Checked In At'])
    
    # Write data rows
    for reg in registrations:
        writer.writerow([
            reg.id,
            reg.first_name,
            reg.last_name,
            reg.email,
            reg.phone,
            reg.status,
            reg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if reg.checked_in else 'No',
            reg.checked_in_at.strftime('%Y-%m-%d %H:%M:%S') if reg.checked_in_at else ''
        ])
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Log the export action
    ip_address = request.remote_addr
    AuditLog.log(
        admin_id=current_user.id,
        action=AuditLog.ACTION_EXPORT,
        resource_type=AuditLog.RESOURCE_REGISTRATION,
        resource_id=0,  # 0 indicates bulk operation
        details=f"Exported registrations data with filter: status={status or 'ALL'}",
        ip_address=ip_address
    )
    
    logger.info(f"Admin {current_user.email} exported registrations with status filter: {status}")
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'registrations_{timestamp}.csv'
    )

@admin_bp.route('/bulk-approve', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def bulk_approve():
    """Bulk approve registrations"""
    data = request.json
    registration_ids = data.get('registration_ids', [])
    
    if not registration_ids:
        return jsonify({'success': False, 'message': 'No registrations selected'}), 400
    
    # Get registrations
    registrations = Registration.query.filter(Registration.id.in_(registration_ids)).all()
    
    # Count how many were actually updated
    updated_count = 0
    
    for reg in registrations:
        if reg.status != 'APPROVED':
            reg.status = 'APPROVED'
            updated_count += 1
    
    db.session.commit()
    
    # Log the bulk approval
    if updated_count > 0:
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_APPROVE,
            resource_type=AuditLog.RESOURCE_REGISTRATION,
            resource_id=0,  # 0 indicates bulk operation
            details=f"Bulk approved {updated_count} registrations",
            ip_address=request.remote_addr
        )
    
    return jsonify({
        'success': True, 
        'message': f'Successfully approved {updated_count} registrations',
        'updated_count': updated_count
    })

@admin_bp.route('/bulk-reject', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def bulk_reject():
    """Bulk reject registrations"""
    data = request.json
    registration_ids = data.get('registration_ids', [])
    
    if not registration_ids:
        return jsonify({'success': False, 'message': 'No registrations selected'}), 400
    
    # Get registrations
    registrations = Registration.query.filter(Registration.id.in_(registration_ids)).all()
    
    # Count how many were actually updated
    updated_count = 0
    
    for reg in registrations:
        if reg.status != 'REJECTED':
            reg.status = 'REJECTED'
            updated_count += 1
    
    db.session.commit()
    
    # Log the bulk rejection
    if updated_count > 0:
        AuditLog.log(
            admin_id=current_user.id,
            action=AuditLog.ACTION_REJECT,
            resource_type=AuditLog.RESOURCE_REGISTRATION,
            resource_id=0,  # 0 indicates bulk operation
            details=f"Bulk rejected {updated_count} registrations",
            ip_address=request.remote_addr
        )
    
    return jsonify({
        'success': True, 
        'message': f'Successfully rejected {updated_count} registrations',
        'updated_count': updated_count
    })

@admin_bp.route('/system-info')
@login_required
@permission_required(Permission.MANAGE_SYSTEM)
def system_info():
    """System information page"""
    # Get system stats
    stats = {
        'total_admins': Admin.query.count(),
        'total_roles': Role.query.all(),
        'total_registrations': Registration.query.count(),
        'database_size': get_database_size(),
        'python_version': os.sys.version,
        'flask_version': current_app.config.get('FLASK_VERSION', 'Unknown'),
        'server_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    
    return render_template('admin/system_info.html', stats=stats)

def get_database_size():
    """Get the size of the SQLite database file"""
    try:
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            if size_bytes < 1024:
                return f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.2f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.2f} MB"
        return "Unknown"
    except Exception as e:
        current_app.logger.error(f"Error getting database size: {str(e)}")
        return "Error"

@admin_bp.route('/create-account', methods=['GET', 'POST'])
@login_required
@permission_required(Permission.MANAGE_ADMINS)
def create_account():
    """Create a new admin account"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not all([email, password, role]):
            flash('All fields are required', 'error')
            return redirect(url_for('admin.create_account'))

        # Check if admin already exists
        if Admin.query.filter_by(email=email).first():
            flash('An admin with this email already exists', 'error')
            return redirect(url_for('admin.create_account'))

        # Create new admin
        admin = Admin(email=email)
        admin.set_password(password)
        
        # Assign role
        role_obj = Role.query.filter_by(name=role).first()
        if role_obj:
            admin.role = role_obj
        
        db.session.add(admin)
        db.session.commit()

        flash('Admin account created successfully', 'success')
        return redirect(url_for('admin.dashboard'))

    # GET request - render form
    roles = Role.query.all()
    return render_template('admin/create_account.html', roles=roles)

@admin_bp.route('/registration/<int:registration_id>/archive', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def archive_registration(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    registration.is_archived = True
    
    # Log the action
    logger.info(f"Admin {current_user.email} archived registration for {registration.name}")
    
    # Create audit log
    AuditLog.log(
        admin_id=current_user.id,
        action=AuditLog.ACTION_UPDATE,
        resource_type=AuditLog.RESOURCE_REGISTRATION,
        resource_id=registration.id,
        details=f"Archived registration for {registration.name}",
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    flash('Registration archived successfully.', 'success')
    return redirect(url_for('admin.registrations'))

@admin_bp.route('/registration/<int:registration_id>/delete', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def delete_registration(registration_id):
    """Delete a registration"""
    registration = Registration.query.get_or_404(registration_id)
    
    # Log the action
    logger.info(f"Admin {current_user.email} deleted registration for {registration.name}")
    
    # Create audit log
    AuditLog.log(
        admin_id=current_user.id,
        action=AuditLog.ACTION_DELETE,
        resource_type=AuditLog.RESOURCE_REGISTRATION,
        resource_id=registration.id,
        details=f"Deleted registration for {registration.name}",
        ip_address=request.remote_addr
    )
    
    # Delete associated files
    if registration.receipt_url:
        try:
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], registration.receipt_url))
        except OSError as e:
            logger.error(f"Error deleting receipt file: {e}")
    
    if registration.qr_code:
        try:
            os.remove(os.path.join(current_app.config['QR_CODE_FOLDER'], registration.qr_code))
        except OSError as e:
            logger.error(f"Error deleting QR code file: {e}")
    
    # Delete the registration
    db.session.delete(registration)
    db.session.commit()
    
    flash('Registration deleted successfully.', 'success')
    return redirect(url_for('admin.registrations'))

@admin_bp.route('/registration/<int:registration_id>/unarchive', methods=['POST'])
@login_required
@permission_required(Permission.MANAGE_REGISTRATIONS)
def unarchive_registration(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    registration.is_archived = False
    
    # Log the action
    logger.info(f"Admin {current_user.email} unarchived registration for {registration.name}")
    
    # Create audit log
    AuditLog.log(
        admin_id=current_user.id,
        action=AuditLog.ACTION_UPDATE,
        resource_type=AuditLog.RESOURCE_REGISTRATION,
        resource_id=registration.id,
        details=f"Unarchived registration for {registration.name}",
        ip_address=request.remote_addr
    )
    
    db.session.commit()
    flash('Registration unarchived successfully.', 'success')
    return redirect(url_for('admin.registrations'))