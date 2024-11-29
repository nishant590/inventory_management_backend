from rest_framework import generics, exceptions
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import (Expense, ExpenseItems)
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from authentication.models import NewUser
from accounts.models import Account
import posixpath
from django.core.files.storage import FileSystemStorage
import traceback
from django.conf import settings
import os
import json
import jwt
from xhtml2pdf import pisa
from io import BytesIO
from customers.models import Customer, Vendor
from django.utils import timezone
from django.core.mail import EmailMessage
from accounts.models import Account, Transaction, TransactionLine, ReceivableTracking
from django.template.loader import render_to_string
import math
import uuid
import time
from decimal import Decimal
from django.db import transaction as db_transaction
from datetime import date, datetime
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import base64
from django.db.models import Max
import logging

# Get the default logger
logger = logging.getLogger('custom_logger')

def generate_short_unique_filename(extension):
    # Shortened UUID (6 characters) + Unix timestamp for uniqueness
    unique_id = uuid.uuid4().hex[:6]  # Get the first 6 characters of UUID
    timestamp = str(int(time.time()))  # Unix timestamp as a string
    return f"{unique_id}_{timestamp}{extension}"

# Create your views here.
class CreateExpenseView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def post(self, request):
        user = self.get_user_from_token(request)
        data = request.data
        vendor_id = data.get("vendor_id")
        items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }

        if isinstance(items, str):  # Convert to dictionary if received as a JSON string
            items = json.loads(items)
        if not vendor_id or not items:
            return Response({"detail": "vendor ID and items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with db_transaction.atomic():
                vendor = Vendor.objects.get(vendor_id=vendor_id)
                data = request.data
                expense_number = data.get("expense_number")
                expense_account = data.get("expense_account")
                tags = data.get("tags")
                memo = data.get("memo")
                payment_date = data.get("payment_date")
                total_amount = Decimal(data.get("total_amount"))
                is_paid = data.get("is_paid")
                if isinstance(is_paid, str):
                    is_paid = is_paid.lower() in ['true', '1', 'yes', 'y']
                attachments = request.FILES.get("attachments")

                if attachments:
                    extension = os.path.splitext(attachments.name)[1]  # Get the file extension
                    short_unique_filename = generate_short_unique_filename(extension)
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'expense_attachments'))
                    logo_path = fs.save(short_unique_filename, attachments)
                    attachments_url = posixpath.join('media/expense_attachments', logo_path)
                else:
                    attachments_url = ""
                
                expense_account=Account.objects.get(id=expense_account)
                
                # Create temporary invoice
                expense = Expense.objects.create(
                    vendor=vendor,
                    tags = tags,
                    expense_number = expense_number,
                    payment_date = payment_date, 
                    memo=memo,
                    expense_account=expense_account,  
                    is_paid = is_paid,
                    total_amount=total_amount,
                    attachments=attachments_url,
                    created_date=timezone.now(),
                    created_by=request.user,
                    is_active=True
                )


                transaction = Transaction.objects.create(
                    reference_number=expense_number,
                    transaction_type="expense",
                    date=payment_date,
                    description=f"Expense for vendor {vendor.display_name}",
                    is_reconciled=False,
                    tax_amount=0,  # Adjust if tax is applicable
                    attachment=attachments_url,
                    created_by=request.user
                )

                # Create a TransactionLine for the expense account
                TransactionLine.objects.create(
                    transaction=transaction,
                    account=expense_account,
                    description=f"Payment to vendor: {vendor.display_name}",
                    debit_amount=total_amount,
                    credit_amount=0
                )
                expense_account.balance -= Decimal(total_amount)
                expense_account.save()
                # Process each item in the invoice
                for item_data in items:
                    account = Account.objects.get(id=item_data['account_id'])
                    description = item_data.get("description","")  # Can be 'tile', 'box', or 'pallet'
                    price = float(item_data['price'])
                

                    # Create invoice item
                    ExpenseItems.objects.create(
                        expense=expense,
                        account=account,
                        price=price,  # Store as selected unit (pallets, boxes, sqf, etc.)
                        description=description,
                        created_by=user
                    )
                    
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=account,
                        description=description,
                        debit_amount=0,
                        credit_amount=price
                    )
                    account.balance += Decimal(price)
                    account.save()

                expense.save()
            return Response({"invoice_id": expense.expense_number, "message": "Expense created successfully."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error occured", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


