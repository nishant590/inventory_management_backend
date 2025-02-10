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
import shutil
from django.conf import settings
import os
import json
import jwt
from xhtml2pdf import pisa
from io import BytesIO
from customers.models import Customer, Vendor
from django.utils import timezone
from django.core.mail import EmailMessage
from accounts.models import Account, Transaction, TransactionLine, ReceivableTracking, VendorPaymentDetails
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
from radiantplanks_backend.logging import log
from authentication.views import audit_log
import pandas as pd


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
                    description=f"Expense for vendor {vendor.business_name}",
                    is_reconciled=False,
                    tax_amount=0,  # Adjust if tax is applicable
                    attachment=attachments_url,
                    created_by=request.user
                )

                # Create a TransactionLine for the expense account
                TransactionLine.objects.create(
                    transaction=transaction,
                    account=expense_account,
                    description=f"Payment to vendor: {vendor.business_name}",
                    debit_amount=0,
                    credit_amount=total_amount
                )
                expense_account.balance -= Decimal(total_amount)
                expense_account.save()
                # Process each item in the invoice

                VendorPaymentDetails.objects.create(
                    vendor=vendor,
                    transaction=transaction,
                    payment_method=request.data.get("payment_method", ""),
                    transaction_reference_id=request.data.get("transaction_id", ""),
                    bank_name=request.data.get("bank_name", ""),
                    cheque_number=request.data.get("cheque_number", ""),
                    payment_date=payment_date,
                    payment_amount=total_amount,
                )

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
                        debit_amount=price,
                        credit_amount=0
                    )
                    account.balance += Decimal(price)
                    account.save()

                expense.save()
            audit_log_entry = audit_log(user=request.user,
                              action="Expense Created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Expense", 
                              record_id=expense.id)
            log.audit.success(f"Expense created successfully | {expense.id} | {user}")
            return Response({"invoice_id": expense.expense_number, "message": "Expense created successfully."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            log.trace.trace(f"error while creating expense, {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExpenseListView(APIView):
    permission_classes = [IsAuthenticated]
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None
        
    def get(self, request):
        user = self.get_user_from_token(request)
        if not user:
            log.app.error("User not found")
            return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)
        expenses = Expense.objects.filter(is_active=True).order_by('-created_date')
        try:
            expense_list = [
                {
                    "id": expense.id,
                    "vendor": expense.vendor.business_name,  # Assuming the vendor has a `name` field
                    "expense_number": expense.expense_number,
                    "payment_date": expense.payment_date,
                    "total_amount": float(expense.total_amount),
                    "is_paid": expense.is_paid,
                    "created_date": expense.created_date,
                }
                for expense in expenses
            ]
            return Response(expense_list, status=status.HTTP_200_OK)
        except Exception as e:
            log.app.trace(f"Error occurred {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get_object(self, id):
        try:
            return Expense.objects.get(id=id, is_active=True)
        except Expense.DoesNotExist:
            return Response("Expense does not exist", status=status.HTTP_404_NOT_FOUND)

    def get(self, request, id):
        user = self.get_user_from_token(request)
        if not user:
            log.app.error("User not found")
            return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)
        expense = self.get_object(id)
        if not expense:
            log.app.error("Expense not found")
            return Response("Expense does not exist", status=status.HTTP_404_NOT_FOUND)
        try:
            items = ExpenseItems.objects.filter(expense=expense)
            expense_data = {
                "id": expense.id,
                "vendor": expense.vendor.business_name,
                "vendor_id": expense.vendor.vendor_id,
                "expense_number": expense.expense_number,
                "payment_date": expense.payment_date,
                "total_amount": float(expense.total_amount),
                "is_paid": expense.is_paid,
                "memo": expense.memo,
                "tags": expense.tags,
                "attachments": expense.attachments,
                "items": [
                    {
                        "account": item.account.name,  # Assuming account has a `name` field
                        "account_id": item.account.id,  # Assuming account has a `name` field
                        "price": float(item.price),
                        "description": item.description,
                    }
                    for item in items
                ],
                "created_date": expense.created_date,
                "updated_date": expense.updated_date,
            }

            try: 
                transaction_obj = Transaction.objects.get(reference_number=expense.expense_number, transaction_type="expense")
                vendor_payment = VendorPaymentDetails.objects.get(transaction=transaction_obj)
                if vendor_payment:
                    transactions_details_data = {
                        "payment_method":vendor_payment.payment_method,
                        "transaction_reference_id":vendor_payment.transaction_reference_id,
                        "bank_name":vendor_payment.bank_name,
                        "cheque_number":vendor_payment.cheque_number,
                        "payment_date":vendor_payment.payment_date, 
                        "payment_amount":vendor_payment.payment_amount, 
                    }
                expense_data["transactions_details_data"] = transactions_details_data
            except Exception as e:
                log.trace.trace(f"Error occurred in expense transaction: {traceback.format_exc()}")
            return Response(expense_data, status=status.HTTP_200_OK)
        except Exception as e:
            log.app.error(f"Error fetching expense data: {e}")
            log.trace.trace(f"Error: {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class EditExpenseView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def put(self, request, id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            expense = Expense.objects.get(id=id)
        except Expense.DoesNotExist:
            return Response({"detail": "Expense not found."}, status=status.HTTP_404_NOT_FOUND)
        
        data = request.data
        vendor_id = data.get("vendor_id")
        items = data.get("items", [])

        if isinstance(items, str):
            try:
                items = json.loads(items)
            except json.JSONDecodeError:
                return Response({"detail": "Invalid format for items."}, status=status.HTTP_400_BAD_REQUEST)
        
        if not vendor_id or not items:
            return Response({"detail": "Vendor ID and items are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vendor = Vendor.objects.get(vendor_id=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with transaction.atomic():
                # Step 1: Capture original data
                original_total = expense.total_amount
                original_expense_account = expense.expense_account
                original_items = list(ExpenseItems.objects.filter(expense=expense))

                # Step 2: Reverse original accounting entries
                # Revert expense account
                original_expense_account.balance += original_total
                original_expense_account.save()

                # Revert item accounts
                for item in original_items:
                    item.account.balance -= Decimal(item.price)
                    item.account.save()

                # Step 3: Delete existing transaction lines and items
                try:
                    transaction_obj = Transaction.objects.get(reference_number=expense.expense_number, transaction_type="expense")
                except Transaction.DoesNotExist:
                    return Response({"detail": "Associated transaction not found."}, status=status.HTTP_404_NOT_FOUND)
                
                TransactionLine.objects.filter(transaction=transaction_obj).delete()
                ExpenseItems.objects.filter(expense=expense).delete()

                # Step 4: Update Expense fields
                expense.vendor = vendor
                expense.tags = data.get("tags", expense.tags)
                expense.memo = data.get("memo", expense.memo)
                expense.payment_date = data.get("payment_date", expense.payment_date)
                new_total_amount = Decimal(data.get("total_amount", original_total))
                expense.total_amount = new_total_amount
                is_paid = data.get("is_paid", expense.is_paid)
                if isinstance(is_paid, str):
                    is_paid = is_paid.lower() in ['true', '1', 'yes', 'y']
                expense.is_paid = is_paid
                new_expense_account = Account.objects.get(id=data.get("expense_account", original_expense_account.id))
                expense.expense_account = new_expense_account

                # Handle attachments
                attachments = request.FILES.get("attachments")
                if attachments:
                    # Remove old file if exists
                    if expense.attachments:
                        old_path = os.path.join(settings.MEDIA_ROOT, expense.attachments)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    # Save new file
                    ext = os.path.splitext(attachments.name)[1]
                    filename = generate_short_unique_filename(ext)
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'expense_attachments'))
                    saved_path = fs.save(filename, attachments)
                    expense.attachments = posixpath.join('media/expense_attachments', saved_path)
                elif 'attachments' in data and data['attachments'] is None:
                    # Clear attachment if explicitly set to None
                    if expense.attachments:
                        old_path = os.path.join(settings.MEDIA_ROOT, expense.attachments)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    expense.attachments = ""

                expense.save()

                # Step 5: Update Transaction
                transaction_obj.reference_number = data.get("expense_number", expense.expense_number)
                transaction_obj.date = expense.payment_date
                transaction_obj.description = f"Expense for vendor {vendor.business_name}"
                transaction_obj.save()

                # Step 6: Update VendorPaymentDetails
                try:
                    vendor_payment = VendorPaymentDetails.objects.get(transaction=transaction_obj)
                except VendorPaymentDetails.DoesNotExist:
                    vendor_payment = VendorPaymentDetails(vendor=vendor, transaction=transaction_obj)
                
                vendor_payment.payment_method = data.get("payment_method", vendor_payment.payment_method)
                vendor_payment.transaction_reference_id = data.get("transaction_id", vendor_payment.transaction_reference_id)
                vendor_payment.bank_name = data.get("bank_name", vendor_payment.bank_name)
                vendor_payment.cheque_number = data.get("cheque_number", vendor_payment.cheque_number)
                vendor_payment.payment_date = expense.payment_date
                vendor_payment.payment_amount = new_total_amount
                vendor_payment.save()

                # Step 7: Create new expense account transaction line
                TransactionLine.objects.create(
                    transaction=transaction_obj,
                    account=new_expense_account,
                    description=f"Payment to vendor: {vendor.business_name}",
                    debit_amount=0,
                    credit_amount=new_total_amount
                )
                new_expense_account.balance -= new_total_amount
                new_expense_account.save()

                # Step 8: Process new items
                for item_data in items:
                    account = Account.objects.get(id=item_data['account_id'])
                    price = Decimal(str(item_data['price']))  # Ensure proper conversion
                    description = item_data.get("description", "")

                    # Create ExpenseItem
                    ExpenseItems.objects.create(
                        expense=expense,
                        account=account,
                        price=price,
                        description=description,
                        created_by=user
                    )

                    # Create TransactionLine
                    TransactionLine.objects.create(
                        transaction=transaction_obj,
                        account=account,
                        description=description,
                        debit_amount=price,
                        credit_amount=0
                    )
                    account.balance += price
                    account.save()

                # Audit log
                audit_log(
                    user=user,
                    action="Expense Updated",
                    ip_add=request.META.get('REMOTE_ADDR'),
                    model_name="Expense",
                    record_id=expense.id
                )
                log.audit.info(f"Expense updated: {expense.id} by {user}")
                return Response({"expense_id": expense.expense_number, "message": "Expense updated successfully."}, status=status.HTTP_200_OK)

        except Account.DoesNotExist:
            return Response({"detail": "Invalid account ID."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            log.trace.error(f"Error updating expense: {str(e)}")
            return Response({"detail": "An error occurred during update."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class DuplicateExpenseView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def post(self, request, id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
        data = request.data
        new_expense_number = data.get("expense_number", None)
        if not new_expense_number:
            return Response({"detail": "Please provide new expense number"})
        try:
            original_expense = Expense.objects.get(id=id)
        except Expense.DoesNotExist:
            return Response({"detail": "Expense not found."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with transaction.atomic():
                # Step 1: Duplicate the Expense
                new_expense = Expense.objects.create(
                    vendor=original_expense.vendor,
                    tags=original_expense.tags,
                    expense_number=new_expense_number,  # Add a prefix to distinguish
                    payment_date=original_expense.payment_date,
                    memo=original_expense.memo,
                    expense_account=original_expense.expense_account,
                    is_paid=original_expense.is_paid,
                    total_amount=original_expense.total_amount,
                    attachments=original_expense.attachments,  # Duplicate the file path (not the file itself)
                    created_date=timezone.now(),
                    created_by=user,
                    is_active=True
                )

                # Step 2: Duplicate the Transaction
                original_transaction = Transaction.objects.get(reference_number=original_expense.expense_number, transaction_type="expense")
                new_transaction = Transaction.objects.create(
                    reference_number=new_expense.expense_number,
                    transaction_type="expense",
                    date=new_expense.payment_date,
                    description=f"Expense for vendor {new_expense.vendor.business_name}",
                    is_reconciled=False,
                    tax_amount=0,  # Adjust if tax is applicable
                    attachment=new_expense.attachments,
                    created_by=user
                )

                # Step 3: Duplicate TransactionLine for the Expense Account
                original_expense_line = TransactionLine.objects.filter(transaction=original_transaction, account=original_expense.expense_account).first()
                if original_expense_line:
                    TransactionLine.objects.create(
                        transaction=new_transaction,
                        account=original_expense.expense_account,
                        description=original_expense_line.description,
                        debit_amount=original_expense_line.debit_amount,
                        credit_amount=original_expense_line.credit_amount
                    )
                    # Adjust the expense account balance
                    original_expense.expense_account.balance -= original_expense.total_amount
                    original_expense.expense_account.save()

                # Step 4: Duplicate VendorPaymentDetails
                original_vendor_payment = VendorPaymentDetails.objects.filter(transaction=original_transaction).first()
                if original_vendor_payment:
                    VendorPaymentDetails.objects.create(
                        vendor=new_expense.vendor,
                        transaction=new_transaction,
                        payment_method=original_vendor_payment.payment_method,
                        transaction_reference_id=original_vendor_payment.transaction_reference_id,
                        bank_name=original_vendor_payment.bank_name,
                        cheque_number=original_vendor_payment.cheque_number,
                        payment_date=new_expense.payment_date,
                        payment_amount=new_expense.total_amount
                    )

                # Step 5: Duplicate ExpenseItems and TransactionLines for Items
                original_items = ExpenseItems.objects.filter(expense=original_expense)
                for original_item in original_items:
                    # Duplicate ExpenseItem
                    new_item = ExpenseItems.objects.create(
                        expense=new_expense,
                        account=original_item.account,
                        price=original_item.price,
                        description=original_item.description,
                        created_by=user
                    )

                    # Duplicate TransactionLine for the item
                    original_item_line = TransactionLine.objects.filter(transaction=original_transaction, account=original_item.account).first()
                    if original_item_line:
                        TransactionLine.objects.create(
                            transaction=new_transaction,
                            account=original_item.account,
                            description=original_item_line.description,
                            debit_amount=original_item_line.debit_amount,
                            credit_amount=original_item_line.credit_amount
                        )
                        # Adjust the item account balance
                        original_item.account.balance += original_item.price
                        original_item.account.save()

                # Step 6: Duplicate Attachments (if applicable)
                if original_expense.attachments:
                    # Copy the file to a new location
                    old_path = os.path.join(settings.MEDIA_ROOT, original_expense.attachments)
                    if os.path.exists(old_path):
                        ext = os.path.splitext(old_path)[1]
                        new_filename = generate_short_unique_filename(ext)
                        new_path = os.path.join(settings.MEDIA_ROOT, 'expense_attachments', new_filename)
                        shutil.copy2(old_path, new_path)
                        new_expense.attachments = posixpath.join('media/expense_attachments', new_filename)
                        new_expense.save()

                # Step 7: Audit Log
                audit_log(
                    user=user,
                    action="Expense Duplicated",
                    ip_add=request.META.get('REMOTE_ADDR'),
                    model_name="Expense",
                    record_id=new_expense.id
                )
                log.audit.info(f"Expense duplicated: {original_expense.id} -> {new_expense.id} by {user}")
                return Response({"expense_id": new_expense.expense_number, "message": "Expense duplicated successfully."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.trace.trace(f"Error duplicating expense: {str(e)}")
            return Response({"detail": "An error occurred during duplication."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class UploadExpenseCSVView(APIView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        
        file = request.FILES.get('file')
        if not file:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Read the CSV file using Pandas
            df = pd.read_csv(file)
            
            # Validate required columns
            required_columns = [
                'vendor_id', 'expense_number', 'payment_date', 'total_amount', 'is_paid',
                'expense_account', 'item_account_id', 'item_price'
            ]
            if not all(column in df.columns for column in required_columns):
                return Response({"detail": "Missing required columns in CSV."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Group rows by expense_number
            expenses_data = df.groupby('expense_number').apply(lambda x: x.to_dict('records')).to_dict()
            
            # Process each expense
            with transaction.atomic():
                for expense_number, rows in expenses_data.items():
                    # Extract common expense data from the first row
                    first_row = rows[0]
                    vendor_id = first_row['vendor_id']
                    payment_date = first_row['payment_date']
                    total_amount = Decimal(first_row['total_amount'])
                    is_paid = first_row['is_paid'].lower() in ['true', '1', 'yes', 'y']
                    expense_account_id = first_row['expense_account']
                    tags = first_row.get('tags', '').split(',')
                    memo = first_row.get('memo', '')
                    payment_method = first_row.get('payment_method', '')
                    transaction_id = first_row.get('transaction_id', '')
                    bank_name = first_row.get('bank_name', '')
                    cheque_number = first_row.get('cheque_number', '')
                    
                    # Fetch vendor and expense account
                    vendor = Vendor.objects.get(vendor_id=vendor_id)
                    expense_account = Account.objects.get(id=expense_account_id)
                    
                    # Create Expense
                    expense = Expense.objects.create(
                        vendor=vendor,
                        expense_number=expense_number,
                        payment_date=payment_date,
                        total_amount=total_amount,
                        is_paid=is_paid,
                        expense_account=expense_account,
                        tags=tags,
                        memo=memo,
                        created_by=user
                    )
                    
                    # Create Transaction
                    transaction_obj = Transaction.objects.create(
                        reference_number=expense_number,
                        transaction_type="expense",
                        date=payment_date,
                        description=f"Expense for vendor {vendor.business_name}",
                        is_reconciled=False,
                        tax_amount=0,
                        created_by=user
                    )
                    
                    # Create TransactionLine for Expense Account
                    TransactionLine.objects.create(
                        transaction=transaction_obj,
                        account=expense_account,
                        description=f"Payment to vendor: {vendor.business_name}",
                        debit_amount=0,
                        credit_amount=total_amount
                    )
                    expense_account.balance -= total_amount
                    expense_account.save()
                    
                    # Create VendorPaymentDetails
                    VendorPaymentDetails.objects.create(
                        vendor=vendor,
                        transaction=transaction_obj,
                        payment_method=payment_method,
                        transaction_reference_id=transaction_id,
                        bank_name=bank_name,
                        cheque_number=cheque_number,
                        payment_date=payment_date,
                        payment_amount=total_amount
                    )
                    
                    # Create ExpenseItems and TransactionLines for Items
                    for row in rows:
                        item_account_id = row['item_account_id']
                        item_price = Decimal(row['item_price'])
                        item_description = row.get('item_description', '')
                        
                        account = Account.objects.get(id=item_account_id)
                        ExpenseItems.objects.create(
                            expense=expense,
                            account=account,
                            price=item_price,
                            description=item_description,
                            created_by=user
                        )
                        TransactionLine.objects.create(
                            transaction=transaction_obj,
                            account=account,
                            description=item_description,
                            debit_amount=item_price,
                            credit_amount=0
                        )
                        account.balance += item_price
                        account.save()
                
                return Response({"message": "Expenses uploaded successfully."}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class DeleteExpenseView(APIView):
    def delete(self, request, id):
        user = request.user
        if not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            expense = Expense.objects.get(id=id)
        except Expense.DoesNotExist:
            return Response({"detail": "Expense not found."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            with transaction.atomic():
                # Fetch associated transaction
                transaction_obj = Transaction.objects.get(reference_number=expense.expense_number, transaction_type="expense")
                
                # Reverse accounting entries
                # Revert expense account balance
                expense.expense_account.balance += expense.total_amount
                expense.expense_account.save()
                
                # Revert item account balances
                expense_items = ExpenseItems.objects.filter(expense=expense)
                for item in expense_items:
                    item.account.balance -= item.price
                    item.account.save()
                
                # Delete associated records
                VendorPaymentDetails.objects.filter(transaction=transaction_obj).delete()
                TransactionLine.objects.filter(transaction=transaction_obj).update(is_active=False)
                ExpenseItems.objects.filter(expense=expense).update(is_active=False)
                transaction_obj.is_active = False
                transaction_obj.save()
                expense.is_active = False
                expense.save()
                return Response({"message": "Expense and associated records deleted successfully."}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)