# Steam-Off Daycation (SOD) 2025 - Backend

This is the backend implementation for the SOD 2025 event registration and management system. It handles user registration, receipt verification, QR code generation, and check-in functionality.

## Features

- User registration with unique email and phone number validation
- Receipt uploads and verification with re-upload option after rejection
- Automated email notifications at different stages of the process
- Admin dashboard for event coordinators to manage registrations and verifications
- QR code generation and validation for check-in at the event
- Export functionality for attendee lists

## Tech Stack

- **Framework**: Flask
- **Database**: MySQL
- **Authentication**: Flask-Login
- **Email**: Flask-Mail
- **File Uploads**: Werkzeug, Pillow
- **QR Codes**: qrcode

## Setup and Installation

### Prerequisites

- Python 3.9+
- MySQL

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Update the values in `.env` with your configuration

4. Initialize the database:
   ```bash
   flask init-db
   ```

5. Create an admin user:
   ```bash
   flask create-admin
   ```

### Running the Application

```bash
flask run
```

The application will be available at http://localhost:5000.

## API Endpoints

### Public APIs

- `POST /api/register` - Register a new attendee
- `POST /api/upload-receipt/<registration_id>` - Upload a receipt
- `GET /api/check-status/<registration_id>` - Check registration status
- `GET /api/verify-email/<email>` - Check if email is already registered
- `GET /api/verify-phone/<phone>` - Check if phone number is already registered

### Protected APIs (requires API key)

- `GET /api/registrations` - Get all registrations
- `GET /api/registrations/<registration_id>` - Get a specific registration
- `POST /api/verify-qr-code` - Verify a QR code and check in an attendee
- `GET /api/stats` - Get registration statistics

## Admin Routes

- `/admin/dashboard` - Admin dashboard
- `/admin/registrations` - View all registrations
- `/admin/registration/<registration_id>` - View a specific registration
- `/admin/approve-receipt/<registration_id>` - Approve a receipt
- `/admin/reject-receipt/<registration_id>` - Reject a receipt
- `/admin/check-in/<registration_id>` - Check in an attendee
- `/admin/export-attendees` - Export confirmed attendees as CSV
- `/admin/send-reminder` - Send reminder emails to all confirmed attendees

## Authentication

- `/auth/login` - Admin login
- `/auth/logout` - Admin logout

## Database Schema

### Registrations Table
- `id` - Unique ID for each registration
- `name` - Full name of the attendee
- `email` - Attendee's email (unique)
- `phone_number` - Attendee's phone number (unique)
- `receipt_url` - Path to the uploaded receipt
- `status` - Registration status (Pending Payment Upload, Pending Verification, Confirmed, Rejected)
- `qr_code` - Unique QR code for check-in
- `created_at` - Initial registration timestamp
- `updated_at` - Last update timestamp

### Admins Table
- `id` - Unique admin ID
- `email` - Admin email (unique)
- `password_hash` - Hashed password for authentication
- `created_at` - Account creation time

### Check-In Log Table
- `id` - Unique check-in entry
- `registration_id` - References registrations.id
- `check_in_time` - When the user checked in

## Security Features

- Password hashing for admin authentication
- QR code encryption
- API key authentication for protected endpoints
- Input validation and sanitization
- Rate limiting for sensitive operations

## License

This project is licensed under the MIT License.

## Email Templates

The system includes the following email templates:

1. **Registration Confirmation** - Sent when a user successfully registers
2. **Receipt Submission Confirmation** - Sent when a user uploads a payment receipt
3. **Receipt Rejection** - Sent when an admin rejects a payment receipt
4. **Payment Confirmation** - Sent when an admin approves a payment receipt, includes QR code
5. **Event Reminder** - Sent a few days before the event to confirmed attendees
6. **Admin Notification** - Sent to admins when a new receipt is uploaded

To test the email templates, you can run:
```bash
flask shell < test_emails.py
```

Make sure to configure your email settings in the `.env` file before testing.

## Admin Dashboard

The system includes a user-friendly admin dashboard for event coordinators to manage registrations and check-ins. The dashboard provides:

1. **Overview Statistics** - Quick view of registration counts by status
2. **Registration Management** - View, filter, and search registrations
3. **Receipt Verification** - Approve or reject payment receipts
4. **Check-in System** - Mark attendees as checked in at the event
5. **Export Functionality** - Export confirmed attendees as CSV
6. **Email Notifications** - Send reminder emails to confirmed attendees

To access the admin dashboard:
1. Create an admin user using the `flask create-admin` command
2. Navigate to `http://localhost:5000/auth/login`
3. Log in with your admin credentials

The dashboard is responsive and works well on both desktop and mobile devices.
