import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_receipt(file):
    """Save a receipt file and return the path"""
    if file and allowed_file(file.filename):
        # Create a secure filename with a unique ID
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        
        # Get the upload folder from app config
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        # Ensure the directory exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Create the full path
        filepath = os.path.join(upload_folder, unique_filename)
        
        # Save the file
        file.save(filepath)
        
        # If it's an image, optimize it
        if filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}:
            optimize_image(filepath)
        
        # Return the path that will work with url_for('static', filename=...)
        # The path should be relative to the static directory
        static_dir = os.path.join('app', 'static')
        if upload_folder.find(static_dir) != -1:
            # Extract the part of the path after 'static/'
            relative_path = upload_folder.split('static' + os.sep)[1]
            # Use forward slashes for web compatibility regardless of OS
            return (os.path.join(relative_path, unique_filename)).replace('\\', '/')
        else:
            # Fallback to the original behavior, but ensure forward slashes
            return (os.path.join('uploads', unique_filename)).replace('\\', '/')
    
    return None

def optimize_image(filepath):
    """Optimize an image to reduce file size"""
    try:
        img = Image.open(filepath)
        
        # Resize if too large (max 1200px width)
        max_width = 1200
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        # Save with optimization
        img.save(filepath, optimize=True, quality=85)
    except Exception as e:
        current_app.logger.error(f"Error optimizing image: {e}")
        # If optimization fails, keep the original file 