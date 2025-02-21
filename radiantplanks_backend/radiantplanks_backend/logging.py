import os
import sys
from loguru import logger
from django.conf import settings

# Ensure logs directory exists
logs_dir = os.path.join(settings.BASE_DIR, 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Remove default handlers
logger.remove()

# Console logging
logger.add(
    sys.stdout, 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Audit Log
audit_logger = logger.bind(name="AUDIT")
audit_logger.add(
    os.path.join(logs_dir, 'audit.log'),
    rotation="10 MB",
    retention="30 days",
    level="SUCCESS",
    filter=lambda record: record["level"].name == "SUCCESS"
)

# Application Log
app_logger = logger.bind(name="APP")
app_logger.add(
    os.path.join(logs_dir, 'app.log'),
    rotation="50 MB",
    retention="15 days",
    level="INFO",
    filter=lambda record: record["level"].name != "SUCCESS"
)

# Trace Log
trace_logger = logger.bind(name="TRACE")
trace_logger.add(
    os.path.join(logs_dir, 'trace.log'),
    rotation="10 MB",
    retention="7 days",
    level="TRACE",
    filter=lambda record: record["level"].name == "TRACE"
)

# Export loggers for easy import
class Loggers:
    audit = audit_logger
    app = app_logger
    trace = trace_logger

# Global logger instance
log = Loggers()