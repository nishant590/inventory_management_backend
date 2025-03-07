import os
import django
import re

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radiantplanks_backend.settings')  # Replace 'your_project' with your Django project name
django.setup()

from accounts.models import TransactionLine  # Replace 'your_app' with your actual app name

def update_transaction_lines():
    transaction_lines = TransactionLine.objects.all()

    for line in transaction_lines:
        bill_match = re.search(r'Payment for bill (\d+)', line.description or "")
        invoice_match = re.search(r'Payment for invoice (\d+)', line.description or "")

        updated = False

        if bill_match:
            line.bill_id = int(bill_match.group(1))
            updated = True

        if invoice_match:
            line.invoice_id = int(invoice_match.group(1))
            updated = True

        if updated:
            line.save()

    print("Transaction lines updated successfully.")

if __name__ == "__main__":
    update_transaction_lines()
