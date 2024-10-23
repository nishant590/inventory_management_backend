# common/logging.py

from functools import wraps
from loguru import logger
from django.conf import settings
import sys

# Configure loguru
logger.remove()  # Remove default handler
logger.add(sys.stdout, colorize=True, format="{time} - {level} - {message}")
logger.add(**settings.LOGURU_CONFIG["handlers"][0])  # Add file handler from settings

def log_api_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        view_instance = args[0]
        request = args[1]
        
        # Log request
        logger.info(f"API Call: {request.method} {request.path}")
        logger.info(f"User: {request.user}")
        logger.info(f"Data: {request.data if hasattr(request, 'data') else 'No data'}")
        
        try:
            response = func(*args, **kwargs)
            # Log success
            logger.success(f"API Response: {response.status_code}")
            return response
        except Exception as e:
            # Log error
            logger.error(f"API Error: {str(e)}")
            raise
    
    return wrapper