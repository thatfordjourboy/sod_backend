import os
import sys
import logging

# Add the application directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app import create_app

try:
    application = create_app()
    logging.info("Application created successfully")
except Exception as e:
    logging.error(f"Failed to create application: {str(e)}")
    raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    application.run(host="0.0.0.0", port=port) 