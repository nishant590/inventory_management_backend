import os
import shutil
import datetime
import sqlite3
import gzip
from django.conf import settings


def manage_backups(database_type="sqlite", backup_dir=None, retention_period_days=90, compress=False, human_readable=False):
    """
    Handles database backups with optional compression and human-readable SQL dumps.

    Args:
        database_type (str): The type of the database ('sqlite' supported).
        backup_dir (str): Directory to store backups. Defaults to 'backups/' in BASE_DIR.
        retention_period_days (int): Number of days to retain backups. Defaults to 90 days.
        compress (bool): Whether to compress the backup file.
        human_readable (bool): Whether to export a human-readable SQL dump.

    Returns:
        dict: Status and message of the backup process.
    """
    if backup_dir is None:
        backup_dir = os.path.join(settings.BASE_DIR, "backups")

    # Ensure backup directory exists
    os.makedirs(backup_dir, exist_ok=True)

    # Get database file path
    if database_type == "sqlite":
        db_path = settings.DATABASES["default"]["NAME"]
        if not os.path.exists(db_path):
            return {"status": "error", "message": "Database file not found"}
    else:
        return {"status": "error", "message": f"Unsupported database type: {database_type}"}

    # Generate timestamped backup filename
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if human_readable:
        backup_file = os.path.join(backup_dir, f"{database_type}_backup_{timestamp}.sql")
    else:
        backup_file = os.path.join(backup_dir, f"{database_type}_backup_{timestamp}.db")

    try:
        # Create a backup
        if database_type == "sqlite":
            if human_readable:
                # Export a human-readable SQL dump
                conn = sqlite3.connect(db_path)
                with open(backup_file, "w") as f:
                    for line in conn.iterdump():
                        f.write(f"{line}\n")
                conn.close()
            else:
                # Copy the database file
                shutil.copy2(db_path, backup_file)

            # Compress the backup file if requested
            if compress:
                compressed_file = backup_file + ".gz"
                with open(backup_file, "rb") as f_in, gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(backup_file)  # Remove the uncompressed file
                backup_file = compressed_file

            backup_status = {"status": "success", "file": backup_file}
        else:
            return {"status": "error", "message": "Backup logic not implemented for this database type"}

    except Exception as e:
        return {"status": "error", "message": f"Backup failed: {str(e)}"}

    # Cleanup old backups
    try:
        cleanup_old_backups(backup_dir, retention_period_days)
    except Exception as e:
        return {"status": "error", "message": f"Backup created, but cleanup failed: {str(e)}"}

    return backup_status


def cleanup_old_backups(backup_dir, days):
    """
    Deletes old backups older than the specified retention period.

    Args:
        backup_dir (str): Directory containing backup files.
        days (int): Retention period in days.

    Raises:
        Exception: If there are issues deleting files.
    """
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    for file in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file)
        if os.path.isfile(file_path):
            file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_time < cutoff_date:
                os.remove(file_path)
                print(f"Deleted old backup: {file_path}")
