from loguru import logger
import os

# Define the log file directory and ensure it exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Loguru configuration
logger.remove()  # Remove the default handler
logger.add(
    os.path.join(log_dir, "app.log"),
    format="{time} - {name} - {level} - {message}",
    rotation="10 MB",  # Rotation after log file reaches 10MB
    compression="zip",
    retention="30 days",  # Keep logs for 30 days
)

# For trace-level logs (for errors)
logger.add(
    os.path.join(log_dir, "error_trace.log"),
    format="{time} - {name} - {level} - {message}",
    level="TRACE",  # Only log trace level or above
    rotation="10 MB",
    compression="zip",
    retention="30 days",
)
