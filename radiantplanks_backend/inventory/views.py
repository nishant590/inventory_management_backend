from rest_framework import generics, exceptions
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import (Invoice, InvoiceItem, Product, Estimate, 
                     EstimateItem, ProductAccountMapping, Bill, 
                     BillItems, InvoiceTransactionMapping, LostProduct,
                     BillTransactionMapping)
from .serializers import CategorySerializer, ProductSerializer
from rest_framework.views import APIView
from django.core.mail import EmailMessage
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Category
from authentication.models import NewUser
from django.http import FileResponse
from accounts.models import Account
import posixpath
import pandas as pd
from django.core.files.storage import FileSystemStorage
import traceback
from django.conf import settings
from django.db.models import Sum, Q
import os
import json
import jwt
from xhtml2pdf import pisa
from io import BytesIO
from customers.models import Customer, Vendor
from django.utils import timezone
from django.core.mail import EmailMessage
from accounts.models import (Account, 
        Transaction, 
        TransactionLine, 
        ReceivableTracking, 
        PayableTracking, 
        CustomerPaymentDetails, 
        VendorPaymentDetails)
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
import nest_asyncio
import base64
import io
from django.db.models import Max
# import logging
from loguru import logger
from radiantplanks_backend.logging import log
import asyncio
from pyppeteer import launch
from authentication.views import audit_log
from expense.models import Expense, ExpenseItems
import pdfkit
import tempfile
# Get the default logger
# logger = logging.getLogger('custom_logger')
# Category Views

# config_path = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

def generate_short_unique_filename(extension):
    # Shortened UUID (6 characters) + Unix timestamp for uniqueness
    unique_id = uuid.uuid4().hex[:6]  # Get the first 6 characters of UUID
    timestamp = str(int(time.time()))  # Unix timestamp as a string
    return f"{unique_id}_{timestamp}{extension}"


def add_inventory_transaction(product_name, quantity, unit_cost, inventory_account, created_by):
    """
    Add an inventory transaction when a new product is added.
    
    :param product_name: Name of the product being added.
    :param quantity: Quantity of the product.
    :param unit_cost: Cost per unit of the product.
    :param created_by: User who created the product (instance of NewUser).
    """
    # inventory_account = Account.objects.filter(account_type='inventory').first()
    # if not inventory_account:
    #     raise ValueError("Inventory account does not exist.")

    # Calculate total value of inventory addition
    try:
        total_cost = Decimal(quantity) * Decimal(unit_cost)

        with db_transaction.atomic():
            # Create a transaction record
            transaction = Transaction.objects.create(
                reference_number=f"INV-{uuid.uuid4().hex[:6].upper()}-{inventory_account.id}",
                transaction_type='journal',
                date=date.today(),
                description=f"Added inventory for {product_name}",
                created_by=created_by,
            )

            # Create transaction lines
            # Debit: Inventory account (increase inventory)
            TransactionLine.objects.create(
                transaction=transaction,
                account=inventory_account,
                description=f"Inventory addition for {product_name}",
                debit_amount=total_cost,
                credit_amount=0,
            )

            # Credit: Assume it's an owner's equity or cash account (to offset the inventory addition)
            owner_equity_account = Account.objects.filter(code='OWN-001').first()
            if not owner_equity_account:
                log.app.error("No owner account for equity found")
                raise ValueError("Owner equity account does not exist.")
            
            TransactionLine.objects.create(
                transaction=transaction,
                account=owner_equity_account,
                description=f"Fund allocation for inventory addition of {product_name}",
                debit_amount=0,
                credit_amount=total_cost,
            )

            # Update inventory account balance
            inventory_account.balance += Decimal(total_cost)
            owner_equity_account.balance -= Decimal(total_cost)
            inventory_account.save()
            owner_equity_account.save()
            log.app.info("Inventory Transaction Success")
            return True
    except Exception as e:
        log.trace.trace(f"Error occures {traceback.format_exc()}")
        return False
    

def create_invoice_transaction(customer, invoice_id, products, total_amount, service_products, tax_amount, user):
    """
    Adjust inventory, create account receivable, and log transactions for cost of goods sold and sales revenue.
    """
    try:
        # Fetch accounts
        inventory_account = Account.objects.get(code='INV-001', is_active=True)  # Inventory account
        receivable_account = Account.objects.get(code='AR-001')  # Accounts Receivable account
        cogs_account = Account.objects.get(code='COGS-001')  # Cost of Goods Sold account
        sales_revenue_account = Account.objects.get(code='INC-001')  # Sales Revenue account
        tax_amount_account = Account.objects.get(code='AP-002')
        untaxed_amount = total_amount - tax_amount
        # Create a new transaction
        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                reference_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
                transaction_type='income',
                date=datetime.now(),
                description=f"Invoice for customer {customer.business_name}, invoice-code {invoice_id}",
                created_by=user
            )
            
            inv_total_cost = 0

            # Adjust inventory and log revenue and COGS
            if products:
                for product in products:
                    product_name = product.get("product_name")
                    quantity = Decimal(product.get("quantity"))
                    unit_cost = Decimal(product.get("unit_cost"))  # Unit cost for inventory valuation
                    unit_price = Decimal(product.get("unit_price"))  # Selling price per unit
                    total_cost = quantity * unit_cost
                    total_revenue = quantity * unit_price
                    inv_total_cost += total_cost

                    # Reduce inventory (credit inventory account)
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=inventory_account,
                        description=f"Inventory adjustment for {product_name}",
                        debit_amount=0,
                        credit_amount=total_cost,
                        invoice_id=invoice_id,
                    )

                    # Log cost of goods sold (debit COGS)
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=cogs_account,
                        description=f"Cost of goods sold for {product_name}",
                        debit_amount=total_cost,
                        credit_amount=0,
                        invoice_id=invoice_id,
                    )

                    # Log sales revenue (credit revenue account)
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=sales_revenue_account,
                        description=f"Sales revenue for {product_name}",
                        debit_amount=0,
                        credit_amount=total_revenue,
                        invoice_id=invoice_id,
                    )
            if service_products:
                for service_product in service_products:
                    service_product_name = service_product.get("product_name")
                    total_cost = Decimal(service_product.get("unit_price"))
                    # inv_total_cost += total_cost
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=sales_revenue_account,
                        description=f"Service Sales revenue for {service_product_name}, invoice_id {invoice_id}",
                        debit_amount=0,
                        credit_amount=total_cost,
                        invoice_id=invoice_id,
                    )

            if tax_amount>0:
                # Log tax revenue (credit tax account)
                tax_amount_account.balance += Decimal(tax_amount)
                TransactionLine.objects.create(
                    transaction=transaction,
                    account=Account.objects.get(code='AP-002'),
                    description=f"Tax Payable for invoice to {customer.business_name}",
                    debit_amount=0,
                    credit_amount=tax_amount,
                    invoice_id=invoice_id,
                )
                tax_amount_account.save()

            # Increase accounts receivable (debit accounts receivable)
            TransactionLine.objects.create(
                transaction=transaction,
                account=receivable_account,
                description=f"Account receivable for invoice to {customer.business_name}",
                debit_amount=total_amount,
                credit_amount=0,
                invoice_id=invoice_id,
            )

            # Update account balances
            inventory_account.balance -= Decimal(inv_total_cost)
            receivable_account.balance += Decimal(total_amount)
            cogs_account.balance += Decimal(inv_total_cost)
            sales_revenue_account.balance += Decimal(untaxed_amount)
            
            CustomerPaymentDetails.objects.create(
                customer=customer,
                transaction=transaction,
                payment_method="Cost of goods sold",
                transaction_reference_id="",
                bank_name="",
                cheque_number="",
                payment_date=datetime.now(),
                payment_amount=total_cost,
            )
            InvoiceTransactionMapping.objects.create(
                transaction=transaction,
                invoice_id=invoice_id,
                is_payment_transaction=False,
                is_active=True
            )
            inventory_account.save()
            receivable_account.save()
            cogs_account.save()
            sales_revenue_account.save()

            # Log receivable tracking
            receivable, created = ReceivableTracking.objects.get_or_create(customer=customer)
            receivable.receivable_amount += Decimal(total_amount)
            receivable.save()

        log.app.info("Invoice Transaction completed successfully")
        return True

    except Exception as e:
        log.trace.trace(f"Error occurred: {traceback.format_exc()}")
        return False


def update_invoice_transaction(customer, invoice_id, new_products, new_service_products, new_total_amount, new_tax_amount, user):
    """
    Reverse the original invoice transaction and create a new transaction with updated data.
    Adjusts inventory, account balances, and logs new transactions.
    """
    try:
        # Fetch the original transaction linked to the invoice
        mapping = InvoiceTransactionMapping.objects.get(invoice_id=invoice_id, is_payment_transaction=False, is_active=True)
        original_transaction = Transaction.objects.get(id=mapping.transaction.id, is_active=True)
        all_transaction_lines = TransactionLine.objects.filter(transaction=mapping.transaction.id, is_active=True).all()
        original_receivable_amount = TransactionLine.objects.filter(transaction=mapping.transaction.id, account__code='AR-001', is_active=True).first().debit_amount
        # Fetch relevant accounts

        with db_transaction.atomic():
            # Calculate original amounts from transaction lines
            # Create reversing transaction lines and adjust accounts
            for line in all_transaction_lines:
                account = line.account
                if account.account_type in ['inventory', 'accounts_receivable', "cash", "bank", "fixed_assets", "other_current_assets"]:
                    # Reverse inventory account logic
                    if line.debit_amount > 0:
                        account.balance -= Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance += Decimal(line.credit_amount)
                #Expense
                elif account.account_type in ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']:
                    # Reverse expense account logic (COGS)
                    if line.debit_amount > 0:
                        account.balance -= Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance += Decimal(line.credit_amount)
                #Income
                elif account.account_type in ['sales_income', 'service_income','other_income']:
                    # Reverse revenue account logic
                    if line.debit_amount > 0:
                        account.balance += Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance -= Decimal(line.credit_amount)
                #Liabilities
                elif account.account_type in ['accounts_payable', 'tax_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities']:
                    # Reverse tax account logic
                    if line.debit_amount > 0:
                        account.balance += Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance -= Decimal(line.credit_amount)
                #Equity
                elif account.account_type in ['owner_equity', 'retained_earnings']:
                    # Reverse tax account logic
                    if line.debit_amount > 0:
                        account.balance += Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance -= Decimal(line.credit_amount)
                else:
                    # Reverse tax account logic
                    if line.debit_amount > 0:
                        account.balance += Decimal(line.debit_amount)
                    if line.credit_amount > 0:
                        account.balance -= Decimal(line.credit_amount)
                account.save()
                line.is_active = False
                line.save()

            inventory_account = Account.objects.get(code='INV-001')
            receivable_account = Account.objects.get(code='AR-001')
            cogs_account = Account.objects.get(code='COGS-001')
            sales_revenue_account = Account.objects.get(code='INC-001')
            tax_account = Account.objects.get(code='AP-002')

            # Update ReceivableTracking
            receivable, _ = ReceivableTracking.objects.get_or_create(customer=customer)
            receivable.receivable_amount -= original_receivable_amount
            receivable.save()
            receivable, _ = ReceivableTracking.objects.get_or_create(customer=customer)

            
            inv_total_cost = Decimal('0.00')
            new_untaxed_amount = new_total_amount - new_tax_amount

            # Process new products (goods)
            for product in new_products:
                product_name = product.get("product_name")
                quantity = Decimal(product.get("quantity"))
                unit_cost = Decimal(product.get("unit_cost"))
                unit_price = Decimal(product.get("unit_price"))
                total_cost = quantity * unit_cost
                total_revenue = quantity * unit_price
                inv_total_cost += total_cost

                # Adjust inventory (credit)
                TransactionLine.objects.create(
                    transaction=original_transaction,
                    account=inventory_account,
                    description=f"Inventory adjustment for {product_name}",
                    debit_amount=0,
                    credit_amount=total_cost,
                    invoice_id=invoice_id,
                )

                # Debit COGS
                TransactionLine.objects.create(
                    transaction=original_transaction,
                    account=cogs_account,
                    description=f"Cost of goods sold for {product_name}",
                    debit_amount=total_cost,
                    credit_amount=0,
                    invoice_id=invoice_id,
                )

                # Credit Sales Revenue
                TransactionLine.objects.create(
                    transaction=original_transaction,
                    account=sales_revenue_account,
                    description=f"Sales revenue for {product_name}",
                    debit_amount=0,
                    credit_amount=total_revenue,
                    invoice_id=invoice_id,
                )

            # Process new service products
            for service in new_service_products:
                service_name = service.get("product_name")
                total_revenue = Decimal(service.get("unit_price"))

                TransactionLine.objects.create(
                    transaction=original_transaction,
                    account=sales_revenue_account,
                    description=f"Service Sales revenue for {service_name}",
                    debit_amount=0,
                    credit_amount=total_revenue,
                    invoice_id=invoice_id,
                )

            # Handle tax
            if new_tax_amount > 0:
                TransactionLine.objects.create(
                    transaction=original_transaction,
                    account=tax_account,
                    description=f"Tax Payable for invoice to {customer.business_name}",
                    debit_amount=0,
                    credit_amount=new_tax_amount,
                    invoice_id=invoice_id,
                )
                tax_account.balance += Decimal(new_tax_amount)

            # Update accounts receivable
            TransactionLine.objects.create(
                transaction=original_transaction,
                account=receivable_account,
                description=f"Account receivable for updated invoice to {customer.business_name}",
                debit_amount=new_total_amount,
                credit_amount=0,
                invoice_id=invoice_id,
            )

            # Update account balances with new transaction amounts
            inventory_account.balance -= inv_total_cost
            cogs_account.balance += inv_total_cost
            sales_revenue_account.balance += new_untaxed_amount
            receivable_account.balance += Decimal(new_total_amount)

            # Save updated account balances
            inventory_account.save()
            cogs_account.save()
            sales_revenue_account.save()
            receivable_account.save()
            tax_account.save()

            # Update ReceivableTracking with new amount
            receivable.receivable_amount += Decimal(new_total_amount)
            receivable.save()


            # Log customer payment details for the new transaction
            update_customer_payment = CustomerPaymentDetails.objects.filter(
                customer=customer,
                transaction=original_transaction,
            ).first()
            update_customer_payment.payment_amount = new_total_amount

        log.app.info("Invoice updated successfully")
        return True

    except Exception as e:
        log.trace.trace(f"Error updating invoice: {traceback.format_exc()}")
        return False
    

def delete_invoice_transaction(invoice_id, user):
    """
    Marks all transactions and related transaction lines for an invoice as inactive,
    and reverses account balance adjustments based on account type.
    """
    try:
        # Fetch the invoice transactions
        invoice_transactions = InvoiceTransactionMapping.objects.filter(invoice_id=invoice_id, is_payment_transaction=False, is_active=True)

        if not invoice_transactions.exists():
            log.app.warning(f"No active transactions found for Invoice ID: {invoice_id}")
            return False

        with db_transaction.atomic():
            for mapping in invoice_transactions:
                transaction = mapping.transaction
                # Mark transaction as inactive
                transaction.is_active = False
                transaction.save()

                # Reverse account balances for related transaction lines
                for line in TransactionLine.objects.filter(transaction=transaction, is_active=True):
                    account = line.account
                    #Assets
                    if account.account_type in ['inventory', 'accounts_receivable', "cash", "bank", "fixed_assets", "other_current_assets"]:
                        # Reverse inventory account logic
                        if line.debit_amount > 0:
                            account.balance -= Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance += Decimal(line.credit_amount)
                    #Expense
                    elif account.account_type in ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']:
                        # Reverse expense account logic (COGS)
                        if line.debit_amount > 0:
                            account.balance -= Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance += Decimal(line.credit_amount)
                    #Income
                    elif account.account_type in ['sales_income', 'service_income','other_income']:
                        # Reverse revenue account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    #Liabilities
                    elif account.account_type in ['accounts_payable', 'tax_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities']:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    #Equity
                    elif account.account_type in ['owner_equity', 'retained_earnings']:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    else:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)

                    # Save updated account balance
                    account.save()

                # Mark the mapping as inactive
                mapping.is_active = False
                mapping.save()

            # Update receivable tracking
            receivable_tracking = ReceivableTracking.objects.filter(customer=transaction.customer).first()
            if receivable_tracking:
                receivable_tracking.receivable_amount -= Decimal(transaction.amount)
                receivable_tracking.save()

        log.app.info(f"Invoice {invoice_id} deleted successfully.")
        return True

    except Exception as e:
        log.trace.trace(f"Error occurred: {traceback.format_exc()}")
        return False


def create_bill_transaction(bill_id, vendor, products, services, total_amount, user):
    """
    Adjust inventory and create accounts payable for the bill.
    If paid, do not increase accounts payable and reduce bank balance.
    """
    try:
        inventory_account = Account.objects.get(code='INV-001')  # Inventory account
        payable_account = Account.objects.get(code='AP-001')  # Accounts Payable account
        cogs_account = Account.objects.get(code='COGS-001')
        # Create a new transaction
        transaction = Transaction.objects.create(
            reference_number=f"BILL-{uuid.uuid4().hex[:6].upper()}",
            transaction_type='journal',
            date=datetime.now(),
            description=f"Bill for vendor {vendor.business_name}, bill ID {bill_id}",
            created_by=user
        )

        inv_total_cost = 0
        services_total_cost = 0

        # Adjust inventory and handle accounts payable
        for product in products:
            product_name = product.get("product_name")
            quantity = Decimal(product.get("quantity"))
            unit_cost = Decimal(product.get("unit_price"))
            temp_total_cost = quantity * unit_cost
            inv_total_cost += temp_total_cost

            # Add inventory (debit inventory account)
            TransactionLine.objects.create(
                transaction=transaction,
                account=inventory_account,
                description=f"Inventory addition for {product_name}",
                debit_amount=temp_total_cost,
                credit_amount=0,
                bill_id=bill_id,
            )

        for service in services:
            service_name = service.get("service_name")
            temp_total_cost = Decimal(service.get("unit_price"))
            
            TransactionLine.objects.create(
                transaction=transaction,
                account=cogs_account,
                description=f"Service addition for {service_name}",
                debit_amount=temp_total_cost,
                bill_id=bill_id,
                credit_amount=0)
            services_total_cost += temp_total_cost
            
        # Add payable (credit accounts payable account)
        TransactionLine.objects.create(
            transaction=transaction,
            account=payable_account,
            description=f"Accounts payable for bill to {vendor.business_name}",
            debit_amount=0,
            credit_amount=total_amount,
            bill_id=bill_id,
        )

        # Update payable tracking
        payable, created = PayableTracking.objects.get_or_create(vendor=vendor)
        payable.payable_amount += Decimal(total_amount)
        payable.save()
        # Update account balances
        VendorPaymentDetails.objects.create(
            vendor=vendor,
            transaction=transaction,
            payment_method="inventory",
            transaction_reference_id="",
            bank_name="",
            cheque_number="",
            payment_date=datetime.now(),
            payment_amount=total_amount,
        )
        inventory_account.balance += Decimal(inv_total_cost)
        cogs_account.balance += Decimal(services_total_cost)
        payable_account.balance += Decimal(total_amount)
        BillTransactionMapping.objects.create(
            transaction=transaction,
            bill_id=bill_id,
            is_payment_transaction=False,
            is_active=True
        )
        inventory_account.save()
        payable_account.save()

        log.app.info("Bill Transaction completed")
        return True
    except Exception as e:
        log.trace.trace(f"Error occurred while creating bill transaction: {traceback.format_exc()}")
        return False


def delete_bill_transaction(bill_id, user):
    """
    Marks all transactions and related transaction lines for an invoice as inactive,
    and reverses account balance adjustments based on account type.
    """
    try:
        # Fetch the invoice transactions
        bill_transactions = BillTransactionMapping.objects.filter(bill_id=bill_id, is_payment_transaction=False, is_active=True)

        if not bill_transactions.exists():
            log.app.warning(f"No active transactions found for Invoice ID: {bill_id}")
            return False

        with db_transaction.atomic():
            for mapping in bill_transactions:
                transaction = mapping.transaction
                # Mark transaction as inactive
                transaction.is_active = False
                transaction.updated_by = user
                transaction.updated_date = datetime.now()
                transaction.save()

                # Reverse account balances for related transaction lines
                for line in TransactionLine.objects.filter(transaction=transaction, is_active=True):
                    account = line.account
                    #Assets
                    if account.account_type in ['inventory', 'accounts_receivable', "cash", "bank", "fixed_assets", "other_current_assets"]:
                        # Reverse inventory account logic
                        if line.debit_amount > 0:
                            account.balance -= Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance += Decimal(line.credit_amount)
                    #Expense
                    elif account.account_type in ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']:
                        # Reverse expense account logic (COGS)
                        if line.debit_amount > 0:
                            account.balance -= Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance += Decimal(line.credit_amount)
                    #Income
                    elif account.account_type in ['sales_income', 'service_income','other_income']:
                        # Reverse revenue account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    #Liabilities
                    elif account.account_type in ['accounts_payable', 'tax_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities']:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    #Equity
                    elif account.account_type in ['owner_equity', 'retained_earnings']:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)
                    else:
                        # Reverse tax account logic
                        if line.debit_amount > 0:
                            account.balance += Decimal(line.debit_amount)
                        if line.credit_amount > 0:
                            account.balance -= Decimal(line.credit_amount)

                    # Save updated account balance
                    account.save()

                # Mark the mapping as inactive
                mapping.is_active = False
                mapping.save()

            # Update receivable tracking
            receivable_tracking = PayableTracking.objects.filter(customer=transaction.customer).first()
            if receivable_tracking:
                receivable_tracking.payable_amount -= Decimal(transaction.amount)
                receivable_tracking.save()

        log.app.info(f"Invoice {bill_id} deleted successfully.")
        return True

    except Exception as e:
        log.trace.trace(f"Error occurred: {traceback.format_exc()}")
        return False


class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            # Assuming you have a way to get the user model instance, e.g., a User model
            user = NewUser.objects.get(id=user_id)
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def post(self, request):
        user = self.get_user_from_token(request)
        if not user:
            log.app.error("Invalid or expired token.")
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)
        # Check if the user already has a category


        # Extract and validate data from request
        category_name = request.data.get("name")
        if not category_name:
            log.app.error("Invalid category name")
            return Response({"detail": "Category name is required."}, status=status.HTTP_400_BAD_REQUEST)

        if_exists = Category.objects.filter(name=category_name).all()
        if if_exists:
            log.app.error("Category already present.")
            return Response({"detail": "Category already present."}, status=status.HTTP_400_BAD_REQUEST)


        # Create the Category instance
        category = Category.objects.create(name=category_name, created_by=user)
        audit_log_entry = audit_log(user=request.user,
                              action="Category Created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Category", 
                              record_id=category.id)
        log.audit.success(f"Category created successfully | {category.name} | {category.created_by}")
        log.app.info(f"Category created successfully | {category.name} | {category.created_by}")
        # Return the created category data
        return Response({
            "id": category.id,
            "name": category.name,
            "created_by": user.id,
        }, status=status.HTTP_201_CREATED)


class CategoryListView(APIView):
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
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        categories = Category.objects.filter(is_active=True)
        categories_data = [
            {
                "id": category.id,
                "name": category.name,
                "type": category.type,
                "created_date": category.created_date,
                "updated_date": category.updated_date,
                "is_active": category.is_active,
            }
            for category in categories
        ]
        return Response(categories_data, status=status.HTTP_200_OK)


class CategoryUpdateView(APIView):
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

    def put(self, request, category_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            category = Category.objects.get(id=category_id, created_by=user)
        except Category.DoesNotExist:
            return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        category_name = request.data.get("name")
        category_type = request.data.get("type")

        if category_name:
            category.name = category_name
        if category_type in ['expense', 'income']:
            category.type = category_type

        category.updated_by = user
        category.save()
        audit_log_entry = audit_log(user=request.user,
                              action="Category Edited", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Category", 
                              record_id=category.id)
        log.audit.success(f"Category updated successfully | {category.name} | {category.created_by}")
        
        return Response({
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "created_date": category.created_date,
            "updated_date": category.updated_date,
            "is_active": category.is_active,
        }, status=status.HTTP_200_OK)


class CategoryDeleteView(APIView):
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

    def delete(self, request, category_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            category = Category.objects.get(id=category_id, created_by=user)
        except Category.DoesNotExist:
            return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        # Soft delete by setting `is_active` to False
        category.is_active = False
        category.save()
        audit_log_entry = audit_log(user=request.user,
                              action="Category Deleted", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Category", 
                              record_id=category.id)
        log.audit.success(f"Category {category.name} deleted successfully | {category.name} | {user}")
        return Response({"detail": "Category deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class ProductListView(APIView):
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
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        products = Product.objects.filter(is_active=True)
        products_data = [
            {
                "id": product.id,
                "product_image": product.images,
                "product_type": product.product_type,
                "product_name": product.product_name,
                "product_description": product.purchase_description,
                "category": product.category_id.name if product.category_id else None,
                "sku": product.sku,
                "product_barcode": product.barcode,
                "product_length": product.tile_length,
                "product_area": product.tile_area,
                "product_width": product.tile_width,
                "stock_quantity": product.stock_quantity,
            }
            for product in products
        ]
        return Response(products_data, status=status.HTTP_200_OK)


# Product Views
class ProductCreateView(APIView):
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

    def calculate_area(self, length, width, no_of_tiles):
        # Calculate area in square inches
        area_in_sq_inches = length * width * no_of_tiles
        # Convert to square feet
        area_in_sq_feet = area_in_sq_inches / 144
        # Round to 2 decimal places
        area_in_sq_feet = round(area_in_sq_feet, 2)
        return area_in_sq_feet


    def calculate_stock_quantity(self, quantity=0, unit=None):
        if unit == "box":
            return quantity * 1  # 10 tiles per box
        elif unit == "pallet":
            return quantity * 55  # 550 tiles per pallet
        return None

    def post(self, request):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        product_image = request.FILES.get("product_image")
        # Extract fields
        product_type = data.get("product_type")  # 'product' or 'service'
        category_id = data.get("category_id")
        product_name = data.get("product_name")
        sku = data.get("sku")
        purchase_description = data.get("purchase_description")
        # sell_description = data.get("sell_description")
        barcode = data.get("barcode")
        quantity = data.get("quantity")
        unit = data.get("unit")
        reorder_level = data.get("reorder_level")
        as_on_date = data.get("as_on_date")
        tile_area = data.get("total_sq_ft", None)
        batch_lot_number = data.get("batch_lot_number")
        tile_length = data.get("tile_length")
        tile_width = data.get("tile_width")
        no_of_tiles = data.get("no_of_tiles")
        purchase_price = data.get("purchase_price")
        # selling_price = data.get("selling_price")
        specifications = data.get("specifications")  # Expect JSON
        tags = data.get("tags")  # Comma-separated string
        inventory_account = data.get("inventory_account")
        # income_account = data.get("income_account")


        if not product_name or not product_type:
            log.app.error(f"Product type and name  are required.")
            return Response({"detail": "Product type and name are required."}, status=status.HTTP_400_BAD_REQUEST)

        if product_image:
            extension = os.path.splitext(product_image.name)[1]  # Get the file extension
            short_unique_filename = generate_short_unique_filename(extension)
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'product_images'))
            logo_path = fs.save(short_unique_filename, product_image)
            logo_url = posixpath.join('media/product_images', logo_path)
        else:
            logo_url = ""

        if product_type == "product" and not category_id:
            return Response({"detail": "Category is required for products."}, status=status.HTTP_400_BAD_REQUEST)

        if product_type == "product":
            if not tile_length or not tile_width or not no_of_tiles:
                return Response({"detail": "Tile length and width and number of tiles are required to calculate the area."}, status=status.HTTP_400_BAD_REQUEST)

        if product_type == "product" and not inventory_account:
            return Response({"detail": "Inventory account is required."}, status=status.HTTP_400_BAD_REQUEST)
        # Validate category and subcategory
        category = None
        subcategory = None
        if category_id:
            try:
                category_id = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                log.app.error(f"Category with id {category_id} does not exist.")
                return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        # Calculate stock quantity for products
        if product_type == "product":
            if not tile_area:
                tile_area = self.calculate_area(float(tile_length), float(tile_width), int(no_of_tiles))
        else:
            tile_area = None

        stock_quantity = 0
        if product_type == "product":
            stock_quantity = self.calculate_stock_quantity(quantity, unit)
            # if stock_quantity is None:
            #     return Response({"detail": "Provide either box_quantity or pallet_quantity."},
            #                     status=status.HTTP_400_BAD_REQUEST)
            

        # Calculate tile area

        
        if Product.objects.filter(sku=sku, is_active=True).exists():
            return Response({"detail": "Product with this SKU already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Create product/service
        product = Product.objects.create(
            product_type = product_type,
            product_name = product_name, 
            sku = sku, 
            barcode = barcode, 
            category_id = category_id, 
            purchase_description = purchase_description,
            stock_quantity = stock_quantity, 
            reorder_level = reorder_level, 
            batch_lot_number = batch_lot_number, 
            tile_length = tile_length, 
            tile_width = tile_width, 
            as_on_date = as_on_date,
            no_of_tiles = no_of_tiles,
            tile_area = tile_area,
            purchase_price = purchase_price,
            specifications = specifications, 
            tags = tags, 
            images = logo_url, 
            created_by = user, 
        )

        if product_type == "product":
            inventory_account = Account.objects.get(id=inventory_account, is_active=True)
            accountmapping = ProductAccountMapping.objects.create(
                product = product,
                inventory_account = inventory_account
            )
            inventory_add = add_inventory_transaction(product_name = product_name, 
                                                      quantity = stock_quantity, 
                                                      unit_cost = purchase_price, 
                                                      inventory_account = inventory_account, 
                                                      created_by = user)

        log.audit.success(f"Product added to inventory successfully | {product_name} | {user}")
        audit_log_entry = audit_log(user=request.user,
                              action="Product created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Product", 
                              record_id=product.id)
        return Response({
            "id": product.id,
            "product_name": product.product_name,
            "product_type": product.product_type,
            "stock_quantity": product.stock_quantity,
            "tile_area": product.tile_area,
            "created_date": product.created_date,
            "is_active": product.is_active,
        }, status=status.HTTP_201_CREATED)


class InventoryStockView(APIView):
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
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        products = Product.objects.filter(is_active=True, product_type="product")
        products_data = [
            {
                "id": product.id,
                "product_image": product.images,
                "product_type": product.product_type,
                "product_name": product.product_name,
                "product_description": product.purchase_description,
                "category": product.category_id.name if product.category_id else None,
                "sku": product.sku,
                "product_barcode": product.barcode,
                "product_length": product.tile_length,
                "product_width": product.tile_width,
                "product_price": product.purchase_price,
                "product_price_per_sqf": round((product.purchase_price/product.tile_area), 2),
                "product_area": product.tile_area,
                "stock_quantity": product.stock_quantity,
            }
            for product in products
        ]
        return Response(products_data, status=status.HTTP_200_OK)


class ProductUpdateView(APIView):
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

    def calculate_area(self, length, width, no_of_tiles):
        # Calculate area in square inches
        area_in_sq_inches = length * width * no_of_tiles
        # Convert to square feet
        area_in_sq_feet = area_in_sq_inches / 144
        # Round to 2 decimal places
        area_in_sq_feet = round(area_in_sq_feet, 2)
        return area_in_sq_feet


    def calculate_stock_quantity(self, quantity=None, unit=None):
        if unit == "box":
            return quantity * 1  # 10 tiles per box
        elif unit == "pallet":
            return quantity * 55  # 550 tiles per pallet
        return None

    def patch(self, request, product_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        product_image = request.FILES.get("product_image")
        product_type = data.get("product_type")
        tile_length = data.get("tile_length", product.tile_length)
        tile_width = data.get("tile_width", product.tile_width)
        no_of_tiles = data.get("no_of_tiles", product.no_of_tiles)
        quantity = data.get("quantity", product.stock_quantity)
        tile_area = data.get("tile_area", product.tile_area)
        unit = data.get("unit")
        # tile_area = product.tile_area
        if unit:
            # tile_area = self.calculate_area(float(tile_length), float(tile_width), int(no_of_tiles))
        
            stock_quantity = None
            if product_type == "product":
                stock_quantity = self.calculate_stock_quantity(quantity, unit)
                if stock_quantity is None:
                    return Response({"detail": "Provide either box_quantity or pallet_quantity."},
                                    status=status.HTTP_400_BAD_REQUEST)
        
        category_id = data.get("category_id")
        if category_id != product.category_id:
            try:
                category_id = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            category_id = product.category_id
        
        # Update fields if provided
        product.product_name = data.get("product_name", product.product_name)
        product.sku = data.get("sku", product.sku)
        product.barcode = data.get("barcode", product.barcode)
        product.category_id = category_id
        # product.sell_description = data.get("sell_description", product.sell_description)
        product.purchase_description = data.get("purchase_description", product.purchase_description)
        product.stock_quantity = data.get("stock_quantity", product.stock_quantity)
        product.reorder_level = data.get("reorder_level", product.reorder_level)
        product.batch_lot_number = data.get("batch_lot_number", product.batch_lot_number)
        product.as_on_date = data.get("as_on_date", product.as_on_date)
        product.tile_length = data.get("tile_length", product.tile_length)
        product.tile_width = data.get("tile_width", product.tile_width)
        product.no_of_tiles = data.get("no_of_tiles", product.no_of_tiles)
        product.tile_area = tile_area
        product.purchase_price = data.get("purchase_price", product.purchase_price)
        # product.selling_price = data.get("selling_price", product.selling_price)
        product.specifications = data.get("specifications", product.specifications)
        product.tags = data.get("tags", product.tags)

        if product_image:
            extension = os.path.splitext(product_image.name)[1]  # Get the file extension
            short_unique_filename = generate_short_unique_filename(extension)
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'product_images'))
            logo_path = fs.save(short_unique_filename, product_image)
            logo_url = posixpath.join('media/product_images', logo_path)
            product.images = logo_url

        if product.product_type == 'product':
            # income_account = data.get("income_account")
            inventory_account = data.get("inventory_account")
            # income_account = Account.objects.get(id=income_account, is_active=True)
            inventory_account = Account.objects.get(id=inventory_account, is_active=True)
            account_mapping = ProductAccountMapping.objects.get(product_id=product_id)
            if not account_mapping:
                product_account = ProductAccountMapping.objects.create(product_id=product_id, inventory_account=inventory_account)
            else:
                account_mapping.inventory_account = inventory_account
                account_mapping.save()

        # Save updated product
        product.updated_by = user
        product.save()

        audit_log_entry = audit_log(user=request.user,
                              action="Product Updated", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Product", 
                              record_id=product.id)
        log.audit.success(f"Product updated successfully | {product.product_name} | {user}")

        return Response({"detail": "Product updated successfully."}, status=status.HTTP_200_OK)


class ProductRetrieveView(APIView):
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

    def get(self, request, product_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        if product.product_type == "product":
            product_accounts = ProductAccountMapping.objects.get(product=product.id)
            

        product_data = {
            "id": product.id,
            "product_name": product.product_name,
            "product_type": product.product_type,
            "sku": product.sku,
            "barcode": product.barcode,
            "category_id": product.category_id.id if product.category_id else None,
            "purchase_description": product.purchase_description,
            "stock_quantity": product.stock_quantity,
            "reorder_level": product.reorder_level,
            "batch_lot_number": product.batch_lot_number,
            "tile_length": product.tile_length,
            "tile_width": product.tile_width,
            "tile_area": product.tile_area,
            "no_of_tiles": product.no_of_tiles,
            "as_on_date": product.as_on_date,
            "purchase_price": product.purchase_price,
            "purchase_price_per_sqf": round((product.purchase_price/product.tile_area), 2) if product.tile_area else None,
            "specifications": product.specifications,
            "tags": product.tags,
            "images": product.images,
            "created_date": product.created_date,
            "updated_date": product.updated_date,
            "is_active": product.is_active,
        }

        if product.product_type == "product":
            product_data["inventory_account"] = product_accounts.inventory_account.name
            product_data["inventory_account_id"] = product_accounts.inventory_account.id


        return Response(product_data, status=status.HTTP_200_OK)


class ProductDeleteView(APIView):
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

    def delete(self, request, product_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        # Soft delete by setting `is_active` to False
        product.is_active = False
        product.save()
        audit_log_entry = audit_log(user=request.user,
                              action="Product created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Product", 
                              record_id=product.id)
        log.audit.success(f"Product deleted successfully | {product.product_name} | {user}")
        return Response({"detail": "Product deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class GetLatestInvoiceId(APIView):
    def get(self, request):
        """
        API endpoint to retrieve the latest invoice ID
        """
        try:
            latest_invoice_id = Invoice.objects.aggregate(max_id=Max('id'))['max_id']
            new_invoice_id = (latest_invoice_id or 0) + 1  # Start with 1 if no invoices exist

            return Response({'latest_invoice_id': new_invoice_id}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)      


class CreateInvoiceView(APIView):
    def post(self, request):
        data = request.data
        customer_id = data.get("customer_id")
        items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }

        if isinstance(items, str):  # Convert to dictionary if received as a JSON string
            items = json.loads(items)
        if not customer_id or not items:
            return Response({"detail": "Customer ID and items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                customer = Customer.objects.get(customer_id=customer_id)
                data = request.data
                customer_email = data.get("customer_email")
                customer_email_cc = data.get("customer_email_cc")
                customer_email_bcc = data.get("customer_email_bcc")
                billing_address_street_1 = data.get("billing_address_street_1","")
                billing_address_street_2 = data.get("billing_address_street_2",None)
                billing_address_city = data.get("billing_address_city","")
                billing_address_state = data.get("billing_address_state","")
                billing_address_postal_code = data.get("billing_address_postal_code","")
                billing_address_country = data.get("billing_address_country","")
                shipping_address_street_1 = data.get("shipping_address_street_1","")
                shipping_address_street_2 = data.get("shipping_address_street_2",None)
                shipping_address_city = data.get("shipping_address_city","")
                shipping_address_state = data.get("shipping_address_state","")
                shipping_address_postal_code = data.get("shipping_address_postal_code","")
                shipping_address_country = data.get("shipping_address_country","")
                tags = data.get("tags")
                terms = data.get("terms")
                bill_date = data.get("bill_date")
                due_date = data.get("due_date")
                message_on_invoice = data.get("message_on_invoice")
                message_on_statement = data.get("message_on_statement")
                sum_amount = float(data.get("sum_amount"))
                is_taxed = data.get("is_taxed")
                if isinstance(is_taxed, str):
                    is_taxed = is_taxed.lower() in ['true', '1', 'yes', 'y']
                tax_percentage = float(data.get("tax_percentage"))
                tax_amount = float(data.get("tax_amount"))
                total_amount = float(data.get("total_amount"))
                payment_status = data.get("payment_status")
                if isinstance(payment_status, str):
                    payment_status = payment_status.lower()
                else:
                    payment_status = "unpaid"
                attachments = request.FILES.get("attachments")

                if attachments:
                    extension = os.path.splitext(attachments.name)[1]  # Get the file extension
                    short_unique_filename = generate_short_unique_filename(extension)
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'invoice_attachments'))
                    logo_path = fs.save(short_unique_filename, attachments)
                    attachments_url = posixpath.join('media/invoice_attachments', logo_path)
                else:
                    attachments_url = ""

                # Create temporary invoice
                invoice = Invoice.objects.create(
                    customer=customer,
                    customer_email = customer_email,
                    customer_email_cc = customer_email_cc,
                    customer_email_bcc = customer_email_bcc,
                    billing_address_street_1 = billing_address_street_1,
                    billing_address_street_2 = billing_address_street_2,
                    billing_address_city = billing_address_city,
                    billing_address_state = billing_address_state,
                    billing_address_postal_code = billing_address_postal_code,
                    billing_address_country = billing_address_country,
                    shipping_address_street_1 = shipping_address_street_1,
                    shipping_address_street_2 = shipping_address_street_2,
                    shipping_address_city = shipping_address_city,
                    shipping_address_state = shipping_address_state,
                    shipping_address_postal_code = shipping_address_postal_code,
                    shipping_address_country = shipping_address_country,
                    tags = tags,
                    terms = terms,
                    bill_date = bill_date, 
                    due_date = due_date, 
                    message_on_invoice = message_on_invoice, 
                    message_on_statement = message_on_statement, 
                    sum_amount = sum_amount, 
                    is_taxed = is_taxed, 
                    tax_percentage = tax_percentage, 
                    tax_amount = tax_amount, 
                    payment_status = payment_status,
                    total_amount=total_amount,
                    paid_amount=0,
                    unpaid_amount=total_amount,
                    attachments=attachments_url,
                    created_date=timezone.now(),
                    created_by=request.user,
                    is_active=True  # Mark as temporary
                )

                # Process each item in the invoice
                transaction_products = []
                service_products = []
                for item_data in items:
                    product = Product.objects.get(id=item_data['product_id'])
                    quantity = float(item_data['quantity'])
                    unit_price = float(item_data['unit_price'])
                    unit_type = item_data['unit_type']  # Can be 'tile', 'box', or 'pallet'
                    description = item_data.get("description","")

                    # Convert quantity to tiles based on the unit type
                    if unit_type == 'pallet':
                        quantity_in_tiles = quantity * 55
                    elif unit_type == 'box':
                        quantity_in_tiles = quantity
                    elif unit_type == 'sqf':
                        quantity_in_tiles = math.ceil(float(quantity) / float(product.tile_area))  # Calculate approx tiles for sqf
                    else:
                        quantity_in_tiles = quantity  # Assume 'box' is the base unit

                    # Check if enough stock is available
                    if product.product_type == 'product':
                        if product.stock_quantity < quantity_in_tiles:
                            return Response({"detail": f"Insufficient stock for product {product.product_name}."}, status=status.HTTP_400_BAD_REQUEST)

                    # Deduct stock and calculate the line total
                        product.stock_quantity -= quantity_in_tiles
                        transaction_products.append({'quantity': quantity_in_tiles, 
                                                    "product_name": product.product_name,
                                                    "unit_price": unit_price,
                                                    "unit_cost": product.purchase_price})
                        product.save()
                        line_total = round((unit_price * quantity_in_tiles),2)
                    elif product.product_type == 'service':
                        line_total = round(unit_price,2)
                        service_products.append({'product_name': product.product_name,
                                                    'unit_price': line_total})

                    # Create invoice item
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=product,
                        description=description,
                        quantity=quantity_in_tiles,
                        amount=line_total,
                        unit_price=unit_price,
                        created_by=request.user
                    )
                    
                    # Accumulate total amount
                    # total_amount += line_total

                # Update the invoice's total amount after processing all items
                # invoice.total_amount = total_amount
                invoice_transactions = create_invoice_transaction(customer=customer, invoice_id=invoice.id, 
                                    products=transaction_products, 
                                    total_amount=total_amount, 
                                    tax_amount=tax_amount, 
                                    service_products=service_products,
                                    user=request.user)
                if not invoice_transactions:
                    log.app.error("Invoice Creation Failed | Error in creating transaction | ")
                    return Response("Invoice Creation Failed due to errors in transactions", status=status.HTTP_400_BAD_REQUEST)
                invoice.save()
            audit_log_entry = audit_log(user=request.user,
                              action="Invoice created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            log.audit.success(f"Invoice created successfully | {invoice.id} | {request.user}")
            return Response({"invoice_id": invoice.id, "message": "Invoice created successfully."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.trace.trace(f"Error occured while creating Invoice {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class ListInvoicesView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get(self, request):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        invoices = Invoice.objects.filter(is_active=True).values(
            "id", "customer__business_name", "customer__customer_id",  "customer_email", "customer__mobile_number", "total_amount", "unpaid_amount", "bill_date", "due_date", "payment_date", "payment_status"
        ).order_by("-bill_date")
        invoice_list = list(invoices)  # Convert queryset to list of dicts
        return Response(invoice_list, status=status.HTTP_200_OK)


class ListCustomerInvoicesView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get(self, request, customer_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        invoices = Invoice.objects.filter(
            customer=customer_id, 
            payment_status__in=["unpaid","partially_paid"],
            is_active=True).values(
            "id", "customer__business_name", "customer__customer_id",  
            "customer_email", "customer__mobile_number", 
            "total_amount", "unpaid_amount", "bill_date", "paid_amount", "payment_date", 
            "due_date", "payment_status"
        )
        invoice_list = list(invoices)  # Convert queryset to list of dicts
        return Response(invoice_list, status=status.HTTP_200_OK)


class RetrieveInvoiceView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None
        
    def get(self, request, id):
        try:
            user = self.get_user_from_token(request)
            invoice = Invoice.objects.get(id=id, is_active=True)
            invoice_items = InvoiceItem.objects.filter(invoice=invoice).values(
                "product__id", "product__product_name", "quantity", "unit_price", "description", "product__tile_area"
            )

            invoice_data = {
                "id": invoice.id,
                "customer": invoice.customer.business_name,
                "customer_id": invoice.customer.customer_id,
                "customer_email": invoice.customer_email,
                "customer_email_cc": invoice.customer_email_cc,
                "customer_email_bcc": invoice.customer_email_bcc,
                "billing_address_street_1" : invoice.billing_address_street_1,
                "billing_address_street_2" : invoice.billing_address_street_2,
                "billing_address_city" : invoice.billing_address_city,
                "billing_address_state" : invoice.billing_address_state,
                "billing_address_postal_code" : invoice.billing_address_postal_code,
                "billing_address_country" : invoice.billing_address_country,
                "shipping_address_street_1" : invoice.shipping_address_street_1,
                "shipping_address_street_2" : invoice.shipping_address_street_2,
                "shipping_address_city" : invoice.shipping_address_city,
                "shipping_address_state" : invoice.shipping_address_state,
                "shipping_address_postal_code" : invoice.shipping_address_postal_code,
                "shipping_address_country" : invoice.shipping_address_country,
                "tags": invoice.tags,
                "terms": invoice.terms,
                "bill_date": invoice.bill_date,
                "due_date": invoice.due_date,
                "payment_date": invoice.payment_date,
                "message_on_invoice": invoice.message_on_invoice,
                "message_on_statement": invoice.message_on_statement,
                "sum_amount": invoice.sum_amount,
                "is_taxed": invoice.is_taxed,
                "tax_percentage": invoice.tax_percentage,
                "tax_amount": invoice.tax_amount,
                "total_amount": invoice.total_amount,
                "payment_status": invoice.payment_status,
                "attachments": invoice.attachments,
                "created_date": invoice.created_date,
                "items": list(invoice_items),
            }
            payment_details = InvoiceTransactionMapping.objects.filter(invoice_id=id, is_payment_transaction=True)

            # Fetch transaction lines related to the bill
            transaction_lines = []
            for mapping in payment_details:
                transaction = mapping.transaction
                lines = TransactionLine.objects.filter(transaction=transaction, invoice_id=id).values(
                    "id", "description", "debit_amount", "credit_amount", "account__code", "account__name"
                )
                for line in lines:
                    transaction_lines.append({
                        "transaction_date": transaction.date,
                        "value": line.get("credit_amount")
                    })
            if transaction_lines:
                invoice_data["transaction_lines"] = transaction_lines
            return Response(invoice_data, status=status.HTTP_200_OK)

        except Invoice.DoesNotExist:
            log.trace.trace(f"Invoice does not exist, {traceback.format_exc()}")
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error retrieving invoice {traceback.format_exc()}", exc_info=True)
            return Response({"detail": "Error retrieving invoice."}, status=status.HTTP_400_BAD_REQUEST)


class UpdateInvoiceView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None
    def put(self, request, invoice_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)
        data = request.data
        items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }
        if isinstance(items, str):  # Convert to dictionary if received as a JSON string
            items = json.loads(items)
        updated_items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }
        if isinstance(updated_items, str):  # Convert JSON string to dict if received as a string
            updated_items = json.loads(updated_items)
        is_taxed = data.get("is_taxed")
        if isinstance(is_taxed, str):
            is_taxed = is_taxed.lower() == 'true'
        try:
            with transaction.atomic():
                # Fetch the existing invoice
                invoice = Invoice.objects.get(id=invoice_id, is_active=True)
                original_items = InvoiceItem.objects.filter(invoice=invoice)
                new_total_amount = Decimal(data.get("total_amount"))
                new_tax_amount = Decimal(data.get("tax_amount"))
                new_tax_percent = Decimal(data.get("tax_percentage"))
                if not is_taxed:
                    if new_tax_amount > Decimal(0) or new_tax_percent > Decimal(0):
                        new_tax_amount = Decimal(0) 
                        new_tax_percent = Decimal(0)
                invoice_paid_amount = Decimal(data.get("invoice_paid_amount", invoice.paid_amount))
                invoice_unpaid_amount = Decimal(new_total_amount - invoice_paid_amount)

                attachments = data.get("attachments")
                if attachments:
                    extension = os.path.splitext(attachments.name)[1]  # Get the file extension
                    short_unique_filename = generate_short_unique_filename(extension)
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'invoice_attachments'))
                    logo_path = fs.save(short_unique_filename, attachments)
                    attachments_url = posixpath.join('media/invoice_attachments', logo_path)
                else:
                    attachments_url = invoice.attachments

                # Create a mapping of product_id to original quantities for comparison
                original_product_map = {item.product.id: item.quantity for item in original_items}
                customer_id = data.get("customer_id")
                customer = Customer.objects.get(customer_id=customer_id)
                invoice.customer = customer
                invoice.customer_email = data.get("customer_email", invoice.customer_email)
                invoice.customer_email_cc = data.get("customer_email_cc", invoice.customer_email_cc)
                invoice.customer_email_bcc = data.get("customer_email_bcc", invoice.customer_email_bcc)
                invoice.billing_address_street_1 = data.get("billing_address_street_1", invoice.billing_address_street_1)
                invoice.billing_address_street_2 = data.get("billing_address_street_2", invoice.billing_address_street_2)
                invoice.billing_address_city = data.get("billing_address_city", invoice.billing_address_city)
                invoice.billing_address_state = data.get("billing_address_state", invoice.billing_address_state)
                invoice.billing_address_country = data.get("billing_address_country", invoice.billing_address_country)
                invoice.billing_address_postal_code = data.get("billing_address_postal_code", invoice.billing_address_postal_code)
                invoice.shipping_address_street_1 = data.get("shipping_address_street_1", invoice.shipping_address_street_1)
                invoice.shipping_address_street_2 = data.get("shipping_address_street_2", invoice.shipping_address_street_2)
                invoice.shipping_address_city = data.get("shipping_address_city", invoice.shipping_address_city)
                invoice.shipping_address_state = data.get("shipping_address_state", invoice.shipping_address_state)
                invoice.shipping_address_country = data.get("shipping_address_country", invoice.shipping_address_country)
                invoice.shipping_address_postal_code = data.get("shipping_address_postal_code", invoice.shipping_address_postal_code)
                invoice.tags = data.get("tags", invoice.tags)
                invoice.terms = data.get("terms", invoice.terms)
                invoice.bill_date = data.get("bill_date", invoice.bill_date)
                invoice.due_date = data.get("due_date", invoice.due_date)
                invoice.payment_date = data.get("payment_date", invoice.payment_date)
                invoice.sum_amount = Decimal(data.get("sum_amount", invoice.sum_amount))
                invoice.is_taxed = is_taxed
                invoice.tax_percentage = Decimal(data.get("tax_percentage", invoice.tax_percentage))
                invoice.tax_amount = Decimal(data.get("tax_amount", invoice.tax_amount))
                invoice.total_amount = Decimal(data.get("total_amount", invoice.total_amount))
                invoice.payment_status = data.get("payment_status", invoice.payment_status)
                invoice.paid_amount = invoice_paid_amount
                invoice.unpaid_amount = invoice_unpaid_amount
                invoice.attachments = attachments_url
                invoice.message_on_invoice = data.get("message_on_invoice", invoice.message_on_invoice)
                invoice.message_on_statement = data.get("message_on_statement", invoice.message_on_statement)

                updated_items = []
                new_services = []
                # Process updated items
                for item_data in items:
                    product_id = item_data['product_id']
                    new_quantity = float(item_data['quantity'])
                    unit_price = float(item_data['unit_price'])
                    unit_type = item_data['unit_type']

                    product = Product.objects.get(id=product_id)
                    if product.product_type == 'product':
                        # Convert new quantity to tiles based on the unit type
                        if unit_type == 'pallet':
                            quantity_in_tiles = new_quantity * 55
                        elif unit_type == 'box':
                            quantity_in_tiles = new_quantity
                        elif unit_type == 'sqf':
                            quantity_in_tiles = math.ceil(float(new_quantity) / float(product.tile_area))
                        else:
                            quantity_in_tiles = new_quantity  # Assume 'box' is the base unit

                        # Check if product exists in the original invoice
                        if product_id in original_product_map:
                            original_quantity = original_product_map[product_id]

                            # Compare and adjust inventory
                            if quantity_in_tiles > original_quantity:
                                # More quantity requested; deduct the extra amount
                                extra_needed = quantity_in_tiles - original_quantity
                                updated_items.append({"product_id": product_id,
                                                      "product_name":product.product_name, 
                                                      "quantity": quantity_in_tiles, 
                                                      "unit_price": unit_price,
                                                      "unit_cost": product.purchase_price})
                                if product.stock_quantity < extra_needed:
                                    return Response({"detail": f"Insufficient stock for product {product.product_name}."},
                                                    status=status.HTTP_400_BAD_REQUEST)
                                product.stock_quantity -= extra_needed
                            elif quantity_in_tiles < original_quantity:
                                # Less quantity requested; return the extra amount to inventory
                                extra_returned = original_quantity - quantity_in_tiles
                                updated_items.append({"product_id": product_id, 
                                                      "product_name":product.product_name,
                                                      "quantity": quantity_in_tiles, 
                                                      "unit_price": unit_price,
                                                      "unit_cost": product.purchase_price})
                                product.stock_quantity += extra_returned
                            elif quantity_in_tiles == original_quantity:
                                updated_items.append({"product_id": product_id, 
                                                      "product_name":product.product_name,
                                                      "quantity": quantity_in_tiles, 
                                                      "unit_price": unit_price,
                                                      "unit_cost": product.purchase_price})
                            product.save()
                            # Update existing invoice item
                            invoice_item = InvoiceItem.objects.get(invoice=invoice, product=product)
                            invoice_item.quantity = quantity_in_tiles
                            invoice_item.unit_price = unit_price
                            invoice_item.amount = round((quantity_in_tiles * unit_price),2)
                            invoice_item.save()

                            # Remove from the original_product_map after processing
                            del original_product_map[product_id]
                        else:
                            # New product in the updated invoice; deduct its quantity
                            if product.stock_quantity < quantity_in_tiles:
                                return Response({"detail": f"Insufficient stock for new product {product.product_name}."},
                                                status=status.HTTP_400_BAD_REQUEST)
                            product.stock_quantity -= quantity_in_tiles
                            updated_items.append({"product_id": product.id, 
                                                  "product_name": product.product_name,
                                                  "quantity": quantity_in_tiles, 
                                                  "unit_price": unit_price,
                                                  "unit_cost":product.purchase_price})
                            product.save()
                            # Add new invoice item
                            InvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                description=item_data.get("description", ""),
                                amount=round((quantity_in_tiles * unit_price),2),
                                quantity=quantity_in_tiles,
                                unit_price=unit_price,
                                created_by=request.user
                            )
                    elif product.product_type == "service":
                        if product_id in original_product_map:
                            original_quantity = original_product_map[product_id]
                            invoice_item = InvoiceItem.objects.get(invoice=invoice, product=product)
                            invoice_item.quantity = new_quantity
                            invoice_item.unit_price = unit_price
                            invoice_item.amount = round((new_quantity * unit_price),2)
                            invoice_item.save()
                            
                            new_services.append({"product_name": product.product_name, "unit_price": unit_price})
                            # Remove from the original_product_map after processing
                            del original_product_map[product_id]
                        else:
                           # Add new invoice item
                            new_services.append({'product_name': product.product_name,
                                                    'unit_price': unit_price})
                            InvoiceItem.objects.create(
                                invoice=invoice,
                                product=product,
                                description=item_data.get("description", ""),
                                quantity=new_quantity,
                                amount=round((new_quantity * unit_price), 2),
                                unit_price=unit_price,
                                created_by=request.user
                            )

                # Handle products removed from the updated items
                for removed_product_id, removed_quantity in original_product_map.items():
                    product = Product.objects.get(id=removed_product_id)
                    product.stock_quantity += removed_quantity
                    product.save()

                    # Remove the invoice item
                    InvoiceItem.objects.get(invoice=invoice, product=product).delete()

                # Update invoice details                
                # invoice.sum_amount = sum(float(item['quantity']) * float(item['unit_price']) for item in updated_items)
                # invoice.total_amount = Decimal(invoice.sum_amount) + Decimal(invoice.tax_amount)
                invoice.updated_by = request.user
                invoice.updated_date = timezone.now()
                update_invoice = update_invoice_transaction(customer=customer,
                                                            invoice_id=invoice.id,
                                                            new_products=updated_items,
                                                            new_service_products=new_services,
                                                            new_total_amount=new_total_amount,
                                                            new_tax_amount=new_tax_amount,
                                                            user=request.user)
                if not update_invoice:
                    return Response({"detail": "Failed to update invoice transactions."}, status=status.HTTP_400_BAD_REQUEST)
                invoice.save()

                audit_log(user=request.user,
                          action="Invoice updated",
                          ip_add=request.META.get('HTTP_X_FORWARDED_FOR'),
                          model_name="Invoice",
                          record_id=invoice.id)
                log.audit.success(f"Invoice updated successfully | {invoice.id} | {request.user}")
                return Response({"invoice_id": invoice.id, "message": "Invoice updated successfully."},
                                status=status.HTTP_200_OK)

        except Exception as e:
            log.trace.trace(f"Error occurred while updating invoice {traceback.format_exc()}")
            print(traceback.format_exc())
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FinalizeInvoiceView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None
    
    def patch(self, request, invoice_id):
        try:
            user = self.get_user_from_token(request)
            if not user:
                return Response({"detail": "Invalid user token."}, status=status.HTTP_401_UNAUTHORIZED)
            invoice = Invoice.objects.get(id=invoice_id, is_active=True)
            if not invoice:
                return Response({"detail": "Invoice not found or inactive."}, status=status.HTTP_404_NOT_FOUND)
            invoice_items = InvoiceItem.objects.filter(invoice=invoice)
            if not invoice_items:
                return Response({"detail": "No items found in the invoice."}, status=status.HTTP_400_BAD_REQUEST)
            customer = invoice.customer.customer_id
            total_amount = invoice.total_amount
            tax_amount = invoice.tax_amount
            transaction_products = []
            service_products = []  
            for item in invoice_items:
                product = Product.objects.get(id=item.product.id)
                quantity = float(item.quantity)
                unit_price = float(item.unit_price)
                if product.product_type == "product":
                    transaction_products.append({'quantity': quantity, 
                                                "product_name": product.product_name,
                                                "unit_price": unit_price,
                                                "unit_cost": product.purchase_price})
                elif product.product_type == 'service':
                    line_total = unit_price
                    service_products.append({'product_name': product.product_name,
                                                'unit_price': line_total})
            invoice_transactions = create_invoice_transaction(customer=customer, invoice_id=invoice.id, 
                                products=transaction_products, 
                                total_amount=total_amount, 
                                tax_amount=tax_amount, 
                                service_products=service_products,
                                user=user)
            if not invoice_transactions:
                return Response({"detail": "Transaction Failed"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            log.trace.trace(f"Error occurred while finalizing invoice {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoicePaidView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def patch(self, request):
        """
        Mark one or more invoices as fully or partially paid, handle tracking, 
        and record the payment details for the customer.
        """
        try:
            user = self.get_user_from_token(request)
            if not user:
                return Response({"detail": "Invalid user token."}, status=status.HTTP_401_UNAUTHORIZED)

            # Get the request data
            invoices_data = request.data.get("invoices", [])  # List of invoice IDs and amounts
            payment_amount = Decimal(request.data.get("payment_amount"))
            payment_amount = round(payment_amount, 2)
            # payment_details = request.data.get("payment_details", {}) # JSON with method, transaction ID, etc.
            customer_id = request.data.get("customer_id")
            credit_account_id = request.data.get("credit_account_id")  # Bank/Cash account ID
            use_advanced_payment = request.data.get("use_advanced_payment", False)
            invoice_payment_date = request.data.get('payment_date')



            if not use_advanced_payment and payment_amount <= 0:
                return Response({"detail": "Invalid payment amount."}, status=status.HTTP_400_BAD_REQUEST)

            # Retrieve customer, receivable tracking, and credit account
            customer = Customer.objects.get(customer_id=customer_id, is_active=True)
            receivable, created = ReceivableTracking.objects.get_or_create(
                customer=customer,
                defaults={'receivable_amount': Decimal("0.00"), 'advance_payment': Decimal("0.00")}
            )
            accounts_recievable = Account.objects.get(code='AR-001')
            credit_account = Account.objects.get(id=credit_account_id, is_active=True)

            if use_advanced_payment:
                payment_amount = receivable.advance_payment
                receivable.advance_payment = 0
                payment_amount = Decimal(payment_amount)
                if payment_amount <= Decimal("0.00"):
                    return Response({"detail": "Payment amount exceeds advance payment."}, status=status.HTTP_400_BAD_REQUEST)

            total_allocated = Decimal("0.00")
            transactions_to_log = []

            # Loop through each invoice and allocate payment
            with db_transaction.atomic():
                for invoice_data in invoices_data:
                    invoice_id = invoice_data.get("invoice_id")
                    allocated_amount = Decimal(invoice_data.get("allocated_amount", 0))
                    if not invoice_payment_date:
                        invoice_payment_date = datetime.now().date()
                    allocated_amount = round(allocated_amount,2)

                    if allocated_amount <= 0:
                        continue  # Skip invalid or zero allocations

                    invoice = Invoice.objects.get(id=invoice_id, customer=customer, is_active=True)

                    # Calculate payment for the invoice
                    if invoice.unpaid_amount == 0:
                        return Response({"Details":"Invoice are already paid"}, status=status.HTTP_400_BAD_REQUEST)
                    payment_for_invoice = min(allocated_amount, invoice.unpaid_amount)

                    # Update invoice
                    invoice.paid_amount += payment_for_invoice
                    invoice.unpaid_amount -= payment_for_invoice
                    invoice.payment_status = "paid" if invoice.unpaid_amount == Decimal(0) else "partially_paid"
                    invoice.payment_date = invoice_payment_date 
                    # Add to total allocated
                    total_allocated += payment_for_invoice
                    if total_allocated > payment_amount:
                        return Response({"detail": "Payment amount is insufficient for allocation."}, status=status.HTTP_400_BAD_REQUEST)

                    invoice.save()
                    # Record invoice transaction
                    transactions_to_log.append({
                        "invoice_id": invoice.id,
                        "description": f"Payment for invoice {invoice.id}",
                        "debit_amount": payment_for_invoice,
                        "credit_amount": 0,
                    })

                # Update receivable tracking
                receivable.receivable_amount -= Decimal(total_allocated)
                accounts_recievable.balance -= Decimal(total_allocated)

                # Handle overpayment
                overpayment = Decimal(payment_amount) - Decimal(total_allocated)
                if overpayment > 0:
                    receivable.advance_payment += Decimal(overpayment)

                transaction = Transaction.objects.create(
                    reference_number=f"PAY-{uuid.uuid4().hex[:6].upper()}",
                    transaction_type="income",
                    date=invoice_payment_date,
                    description=f"Payment received from customer {customer.business_name}",
                    tax_amount=0,
                    is_active=True,
                    created_by=user,
                )

                # Log each transaction line
                for line in transactions_to_log:
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=Account.objects.get(code="AR-001"),
                        description=line["description"],
                        debit_amount=line['credit_amount'],
                        credit_amount=line["debit_amount"],
                        invoice_id=line.get("invoice_id"),
                    )

                # Log credit to bank/cash account
                TransactionLine.objects.create(
                    transaction=transaction,
                    account=credit_account,
                    description=f"Payment credited for customer {customer.business_name}",
                    debit_amount=payment_amount,
                    credit_amount=0,
                )

                # Save payment details in CustomerPaymentDetail
                CustomerPaymentDetails.objects.create(
                    customer=customer,
                    transaction=transaction,
                    payment_method=request.data.get("payment_method", ""),
                    transaction_reference_id=request.data.get("transaction_id", ""),
                    bank_name=request.data.get("bank_name", ""),
                    cheque_number=request.data.get("cheque_number", ""),
                    payment_date=datetime.now(),
                    payment_amount=payment_amount,
                )
                credit_account.balance += Decimal(payment_amount)
                for line in transactions_to_log:
                    InvoiceTransactionMapping.objects.create(
                        transaction=transaction,
                        invoice_id=line.get("invoice_id"),
                        is_payment_transaction=True,
                        is_active=True
                    )

                receivable.save()

                credit_account.save()
                accounts_recievable.save()

            # Log and return response
            log.audit.success(f"Payments applied for customer {customer.business_name} | User: {user}")
            return Response({"detail": f"Payment processed successfully for customer {customer.business_name}."}, status=status.HTTP_200_OK)

        except Customer.DoesNotExist:
            log.app.error("Customer Not found")
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        except Invoice.DoesNotExist:
            log.app.error("Invoice Not found")
            return Response({"detail": "One or more invoices not found."}, status=status.HTTP_404_NOT_FOUND)
        except ReceivableTracking.DoesNotExist:
            log.app.error("Receivable tracking Not found")
            return Response({"detail": "Receivable tracking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Account.DoesNotExist:
            log.app.error("Account Not found")
            return Response({"detail": "Specified credit account not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.app.error(f"Error processing payment: {str(e)}")
            log.trace.trace(f"Error processing invoice payments {traceback.format_exc()}")
            return Response({"detail": "Error processing payment."}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceDeleteView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def patch(self, request):
        """
        Mark one or more invoices as fully or partially paid, handle tracking, 
        and record the payment details for the customer.
        """
        try:
            user = self.get_user_from_token(request)
            if not user:
                return Response({"detail": "Invalid user token."}, status=status.HTTP_401_UNAUTHORIZED)

            # Get the request data
            invoice_id = request.data.get("invoice")  # List of invoice IDs and amounts
            invoice = Invoice.objects.get(id=invoice_id)
            with transaction.atomic():
                invoice.is_active = False
                delete_transactions = delete_invoice_transaction(invoice_id=invoice_id, user=user)
                if not delete_transactions:
                    return Response({"detail": "Error deleting transactions."}, status=status.HTTP_400_BAD_REQUEST)
                invoice.save()

            # Log and return response
            log.audit.success(f"Invoice deleted successfully | {invoice_id} | {user}")
            audit_log_entry = audit_log(user=request.user,
                                        action="delete_invoice",
                                        ip_add=request.META.get('HTTP_X_FORWARDED_FOR'),
                                        model_name="Invoice",
                                        model_id=invoice_id)
            return Response({"detail": f"Invoice deleted successfully {invoice_id}."}, status=status.HTTP_200_OK)
        except Invoice.DoesNotExist:
            log.app.error("Invoice Not found")
            return Response({"detail": "One or more invoices not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.app.error(f"Error processing payment: {str(e)}")
            log.trace.trace(f"Error processing invoice payments {traceback.format_exc()}")
            return Response({"detail": "Error processing payment."}, status=status.HTTP_400_BAD_REQUEST)


class SendInvoiceView_v1(APIView):
    def post(self, request, invoice_id):
        try:
            # Fetch the invoice and related items
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)

            # Prepare data for template rendering
            items_data = [
                {
                    "product_image": item.product.images if item.product.images else None,
                    "product": item.product.product_name,
                    "sku": item.product.sku,
                    "dim": f"{item.product.tile_length} x {item.product.tile_width}",
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            context = {
                "invoice": invoice,
                "customer": invoice.customer,
                "items": items_data
            }

            # Render the HTML template
            html_string = render_to_string("invoice_template.html", context)
            
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(traceback.format_exc())
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            # Initialize webdriver
            driver = webdriver.Chrome(options=chrome_options)

            # Use a local HTML file instead of trying to reverse a URL
            # Save the HTML to a temporary file
            pdf_folder = os.path.join(settings.MEDIA_ROOT, 'pdfs')
            os.makedirs(pdf_folder, exist_ok=True)
            
            temp_html_path = os.path.join(pdf_folder, f"Invoice_{invoice.id}.html")
            with open(temp_html_path, 'w', encoding='utf-8') as f:
                f.write(html_string)

            # Navigate to the local file
            driver.get(f"file://{temp_html_path}")

            # Wait for page to load (adjust as needed)
            driver.implicitly_wait(10)

            # Generate unique filename
            unique_filename = f"Invoice_{invoice.id}.pdf"
            pdf_path = os.path.join(pdf_folder, unique_filename)

            # Print page to PDF
            print_options = {
                'landscape': False,
                'paperWidth': 8.27,  # A4 width in inches
                'paperHeight': 11.69,  # A4 height in inches
                'marginTop': 0.39,
                'marginBottom': 0.39,
                'marginLeft': 0.39,
                'marginRight': 0.39,
            }
            pdf_data = driver.execute_cdp_cmd('Page.printToPDF', print_options)
            
            # Save PDF
            with open(pdf_path, 'wb') as f:
                f.write(base64.b64decode(pdf_data['data']))

            # Close the driver
            driver.quit()

        except Exception as e:
            print(traceback.format_exc())
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        with open(pdf_path, 'rb') as pdf_file:
            # Compose and send email
            email = EmailMessage(
                subject=f"Invoice #{invoice.id}",
                body="Please find attached your invoice.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[invoice.customer.email],
            )
            email.attach(f"Invoice_{invoice.id}.pdf", pdf_file.read(), "application/pdf")
            
            try:
                email.send()
                return Response({"message": "Invoice sent successfully"}, status=status.HTTP_200_OK)
            except Exception as e:
                # Log the error
                print(f"Email sending failed: {e}")
                return Response({"message": "Error in sending mail please check the customer email"}, status=status.HTTP_400_BAD_REQUEST)


class SendInvoiceView(APIView):
    def post(self, request, invoice_id):
        try:
            # Fetch the invoice and related items
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)

            # Prepare data for template rendering
            items_data = [
                {
                    "product_image": os.path.join(settings.BASE_DIR, item.product.images) if item.product.images else None,
                    "product": item.product.product_name,
                    "product_type": item.product.product_type,
                    "sku": item.product.sku,
                    "dim": f'{round(item.product.tile_width)}" x {round(item.product.tile_length)}"' if item.product.tile_length and item.product.tile_width else "-",
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            context = {
                "invoice": invoice,
                "customer": invoice.customer,
                "items": items_data,
                "logo_url": 'media/logo/RPLogo.png'
            }
            css_file_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'css', 'style.css')
            logo_file_path = os.path.join(settings.BASE_DIR, 'media', 'logo', 'RPlogo.png')

            context['css_file_path'] = css_file_path
            context['logo_file_path'] = logo_file_path
            cc_email = invoice.customer_email_cc
            if cc_email:
                cc_email = cc_email.split(",")
            else:
                cc_email = []
            bcc_email = invoice.customer_email_bcc
            if bcc_email:
                bcc_email = bcc_email.split(",")
            else:
                bcc_email = []

            email_html_body = render_to_string("mail_template.html", context)

                # Render the HTML template
            html_string = render_to_string("invoice_template_1.html", context)

            # Generate PDF
            pdf_buffer = generate_pdf_v3(html_string)

            # Send email with the PDF
            send_email_with_pdf(email=invoice.customer_email,  email_body=email_html_body,
                                pdf_buffer=pdf_buffer, invoice_id=invoice.id,
                                cc_email=cc_email, bcc_email=bcc_email)
            audit_log_entry = audit_log(user=request.user,
                              action="Invoice Sent", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            log.audit.success(f"Invoice send successfully | {invoice.id} | {request.user}")
            return Response({"message": "Invoice sent successfully"}, status=status.HTTP_200_OK)

        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error while sending Invoice | {invoice.id} | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendInvoiceRenderData(APIView):
    def post(self, request, invoice_id):
        try:
            # Fetch the invoice and related items
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)

            # Prepare data for template rendering
            items_data = [
                {
                    "invoice_id":invoice.id,
                    "product_image": item.product.images if item.product.images else None,
                    "product": item.product.product_name,
                    "product_type": item.product.product_type,
                    "sku": item.product.sku,
                    "dim": f'{round(item.product.tile_width)}" x {round(item.product.tile_length)}"' if item.product.tile_length and item.product.tile_width else "-",
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            invoice_data = {
                "customer": invoice.customer.business_name,
                "customer_id": invoice.customer.customer_id,
                "customer_email": invoice.customer_email,
                "customer_email_cc": invoice.customer_email_cc,
                "customer_email_bcc": invoice.customer_email_bcc,
                "billing_address_street_1" : invoice.billing_address_street_1,
                "billing_address_street_2" : invoice.billing_address_street_2,
                "billing_address_city" : invoice.billing_address_city,
                "billing_address_state" : invoice.billing_address_state,
                "billing_address_postal_code" : invoice.billing_address_postal_code,
                "billing_address_country" : invoice.billing_address_country,
                "shipping_address_street_1" : invoice.shipping_address_street_1,
                "shipping_address_street_2" : invoice.shipping_address_street_2,
                "shipping_address_city" : invoice.shipping_address_city,
                "shipping_address_state" : invoice.shipping_address_state,
                "shipping_address_postal_code" : invoice.shipping_address_postal_code,
                "shipping_address_country" : invoice.shipping_address_country,
                "bill_date": invoice.bill_date,
                "terms": invoice.terms,
                "due_date": invoice.due_date,
                "message_on_invoice": invoice.message_on_invoice,
                "sum_amount": invoice.sum_amount,
                "is_taxed": invoice.is_taxed,
                "tax_percentage": invoice.tax_percentage,
                "tax_amount": invoice.tax_amount,
                "total_amount": invoice.total_amount,
                "paid_amount":invoice.paid_amount,
                "unpaid_amount":invoice.unpaid_amount,
            }
            context = {
                "invoice": invoice_data,
                "items": items_data
            }

            audit_log_entry = audit_log(user=request.user,
                              action="Invoice Sent", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            log.audit.success(f"Invoice send successfully | {invoice.id} | {request.user}")
            return Response({"message": "Invoice sent successfully",
                             "data":context}, status=status.HTTP_200_OK)
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error while sending Invoice | {invoice.id} | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendEmailPdfToClient(APIView):
    def post(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)
            attachments = request.FILES.get("invoice_pdf")
            if not attachments:
                Response({"message":"Error while fetching file"}, status=status.HTTP_400_BAD_REQUEST)
            extension = os.path.splitext(attachments.name)[1]
            if extension != "pdf":
                Response({"message":"Unsupported file format"}, status=status.HTTP_400_BAD_REQUEST)
            # Prepare data for template rendering
            items_data = [
                {
                    "product_image": os.path.join(settings.BASE_DIR, item.product.images) if item.product.images else None,
                    "product": item.product.product_name,
                    "product_type": item.product.product_type,
                    "sku": item.product.sku,
                    "dim": f'{round(item.product.tile_width)}" x {round(item.product.tile_length)}"' if item.product.tile_length and item.product.tile_width else "-",
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            context = {
                "invoice": invoice,
                "customer": invoice.customer,
                "items": items_data,
                "logo_url": 'media/logo/RPLogo.png'
            }
            css_file_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'css', 'style.css')
            logo_file_path = os.path.join(settings.BASE_DIR, 'media', 'logo', 'RPlogo.png')

            context['css_file_path'] = css_file_path
            context['logo_file_path'] = logo_file_path
            cc_email = invoice.customer_email_cc
            if cc_email:
                cc_email = cc_email.split(",")
            else:
                cc_email = []
            bcc_email = invoice.customer_email_bcc
            if bcc_email:
                bcc_email = bcc_email.split(",")
            else:
                bcc_email = []

            email_html_body = render_to_string("mail_template.html", context)


            # Send email with the PDF
            check_email = send_email_with_pdf(email=invoice.customer_email,  email_body=email_html_body,
                                pdf_buffer=attachments, invoice_id=invoice.id,
                                cc_email=cc_email, bcc_email=bcc_email, is_new_method=True)
            if not check_email:
                log.app.error("Error while sending email")
                return Response({"message": "Error while sending email"}, status=status.HTTP_400_BAD_REQUEST)
            audit_log_entry = audit_log(user=request.user,
                              action="Invoice Sent", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            log.audit.success(f"Invoice send successfully | {invoice.id} | {request.user}")
            return Response({"message": "Invoice sent successfully"}, status=status.HTTP_200_OK)

        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error while sending Invoice | {invoice.id} | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def generate_pdf_v3(html_string, options=None):
    """
    Generate a PDF from an HTML string using pdfkit and BytesIO.
    
    :param html_string: HTML content to convert to PDF
    :param options: Optional dictionary of wkhtmltopdf configuration options
    :return: Bytes object containing the PDF
    """
    # Default options if none provided
    default_options = {
        'enable-local-file-access': '',
        'page-size': 'A4',
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'encoding': "UTF-8",
        'no-outline': None,
        'zoom': "0.99",
        'no-pdf-compression': '',
        'disable-smart-shrinking': ''
    }


    # Merge default options with any user-provided options
    if options:
        default_options.update(options)
    
    try:
        # Create a BytesIO object to store the PDF
        pdf_buffer = io.BytesIO()
        # path_to_wfk = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        path_to_wfk = settings.PATH_TO_WFK

        config = pdfkit.configuration(wkhtmltopdf = path_to_wfk)
        # Attempt to generate PDF directly to BytesIO
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf_path = temp_pdf.name
        
        # Generate PDF to temporary file
        pdfkit.from_string(
            html_string, 
            temp_pdf_path, 
            options=default_options, 
            configuration=config
        )
        
        # Read the PDF into a BytesIO object
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_buffer = io.BytesIO(pdf_file.read())
        
        # Clean up the temporary file
        import os
        os.unlink(temp_pdf_path)
        
        # Reset the buffer position to the beginning
        pdf_buffer.seek(0)
        
        print("PDF generated successfully in memory")
        return pdf_buffer
    
    except OSError as e:
        # Common error if wkhtmltopdf is not installed
        log.trace.trace(f"Error generating PDF | | {traceback.format_exc()}")
        return None
    except Exception as e:
        log.trace.trace(f"Error generating PDF | | {traceback.format_exc()}")
        return None     

def generate_pdf_sync(html_string, pdf_path):
    # Apply nest_asyncio to allow nested event loops
    nest_asyncio.apply()

    async def generate_pdf(html_string, pdf_path):
        # Launch the browser
        browser = await launch(
            headless=True,
            executablePath='C:/Program Files/Google/Chrome/Application/chrome.exe',
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()

        # Set the page content
        await page.setContent(html_string)

        # Generate the PDF
        await page.pdf({
            'path': pdf_path,
            'format': 'A4',
            'margin': {
                'top': '0.39in',
                'bottom': '0.39in', 
                'left': '0.39in',
                'right': '0.39in'
            },
            'printBackground': True
        })

        print(f"PDF generated at: {pdf_path}")
        await browser.close()

    # Run the async function using the current event loop
    asyncio.get_event_loop().run_until_complete(generate_pdf(html_string, pdf_path))


def generate_pdf(html_string, pdf_path):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import base64

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    # Save the HTML to a temporary file
    temp_html_path = pdf_path.replace(".pdf", ".html")
    with open(temp_html_path, 'w', encoding='utf-8') as f:
        f.write(html_string)

    # Navigate to the local file
    driver.get(f"file://{temp_html_path}")
    driver.implicitly_wait(10)

    # Generate PDF
    print_options = {
        'landscape': False,
        'paperWidth': 8.27,  # A4 width in inches
        'paperHeight': 11.69,  # A4 height in inches
        'marginTop': 0.39,
        'marginBottom': 0.39,
        'marginLeft': 0.39,
        'marginRight': 0.39,
    }
    pdf_data = driver.execute_cdp_cmd('Page.printToPDF', print_options)

    with open(pdf_path, 'wb') as f:
        f.write(base64.b64decode(pdf_data['data']))

    driver.quit()


def send_email_with_pdf(email, pdf_buffer, email_body, invoice_id, cc_email = [], bcc_email = [], is_new_method=False):
    # html_content = render_to_string('mail_template.html')
    try:
        email = EmailMessage(
            subject=f"Invoice #{invoice_id}",
            body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
            cc=cc_email,
            bcc=bcc_email
        )
        email.content_subtype = 'html'
        if is_new_method:
            if pdf_buffer:
                email.attach(f'Invoice_{invoice_id}.pdf', pdf_buffer.read(), 'application/pdf')
                email.send()
        else:
            if pdf_buffer:
                email.attach(f'Invoice_{invoice_id}.pdf', pdf_buffer.getvalue(), 'application/pdf')
                email.send()
        return True
    except Exception as e:
        log.trace.trace(f"Error while sending email | {invoice_id} | {traceback.format_exc()}")
        return False


class TestEmailView(APIView):
    def get(self, request):
        try:
            email = EmailMessage(
                subject="Test Email",
                body="This is a test email.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["nishant@pruthatek.com"]
            )
            email.send()
            return Response({"message": "Email sent successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            log.trace.trace(f"Error while sending email | | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class DownloadInvoiceView(APIView):
    def get(self, request, invoice_id):
        try:
            # Fetch the invoice and related items
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)

            # Prepare data for template rendering
            items_data = [
                {
                    "product_image": os.path.join(settings.BASE_DIR, item.product.images) if item.product.images else None,
                    # "product_image": item.product.images if item.product.images else None,
                    "product": item.product.product_name,
                    "sku": item.product.sku,
                    "dim": f'{round(item.product.tile_width)}" x {round(item.product.tile_length)}"' if item.product.tile_length and item.product.tile_width else "-",
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            context = {
                "invoice": invoice,
                "customer": invoice.customer,
                "items": items_data,
            }
            css_file_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'css', 'style.css')
            logo_file_path = os.path.join(settings.BASE_DIR, 'media', 'logo', 'RPlogo.png')

            context['css_file_path'] = css_file_path
            context['logo_file_path'] = logo_file_path

            html_string = render_to_string("invoice_template_1.html", context)

            
            pdf_buffer = generate_pdf_v3(html_string)

            # Return the PDF as a response
            audit_log_entry = audit_log(user=request.user,
                              action="Invoice Downloaded", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            log.app.info(f"Invoice generated successfully | {invoice_id} | {request.user}")
            pdf_buffer.seek(0)
            return FileResponse(pdf_buffer, as_attachment=True,  filename=f"Invoice_{invoice_id}.pdf")

        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error while downloading Invoice | {invoice_id} | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DownloadPackingSlipView(APIView):
    def get(self, request, invoice_id):
        try:
            # Fetch the invoice and related items
            invoice = Invoice.objects.get(id=invoice_id)
            items = InvoiceItem.objects.filter(invoice=invoice)

            # Prepare data for template rendering
            items_data = [
                {
                    "product_image": os.path.join(settings.BASE_DIR, item.product.images) if item.product.images else None,
                    "product": item.product.product_name,
                    "sku": item.product.sku,
                    "dim": f'{round(item.product.tile_width)}" x {round(item.product.tile_length)}"' if item.product.tile_length and item.product.tile_width else "-",
                    "quantity": item.quantity,
                    "unit_type": "box",
                    "unit_price": item.unit_price,
                    "total_price": item.unit_price * item.quantity,
                }
                for item in items
            ]
            context = {
                "invoice": invoice,
                "customer": invoice.customer,
                "items": items_data,
            }
            css_file_path = os.path.join(settings.BASE_DIR, 'staticfiles', 'css', 'style.css')
            logo_file_path = os.path.join(settings.BASE_DIR, 'media', 'logo', 'RPlogo.png')

            context['css_file_path'] = css_file_path
            context['logo_file_path'] = logo_file_path
            # Define PDF path
            # pdf_folder = os.path.join(settings.MEDIA_ROOT, 'pdfs')
            # os.makedirs(pdf_folder, exist_ok=True)
            # pdf_path = os.path.join(pdf_folder, f"Invoice_{invoice_id}.pdf")

            # # Check if PDF exists, generate if not
            # if not os.path.exists(pdf_path):
            #     # Render the HTML template
            html_string = render_to_string("invoice_template_2.html", context)

            
            pdf_buffer = generate_pdf_v3(html_string)

            # Return the PDF as a response
            audit_log_entry = audit_log(user=request.user,
                              action="Packing Slip Downloaded", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Invoice", 
                              record_id=invoice.id)
            pdf_buffer.seek(0)
            log.app.info(f"Packing slip generated successfully | {invoice_id} | {request.user}")
            return FileResponse(pdf_buffer, as_attachment=True,  filename=f"Packing_slip_{invoice_id}.pdf")

        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error while downloading Invoice | {invoice_id} | {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateEstimateView(APIView):
    def post(self, request):
        data = request.data
        customer_id = data.get("customer_id")
        items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }

        if not customer_id or not items:
            return Response({"detail": "Customer ID and items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                customer = Customer.objects.get(customer_id=customer_id)
                total_amount = 0

                # Create temporary invoice
                estimate = Estimate.objects.create(
                    customer=customer,
                    date=timezone.now(),
                    total_amount=total_amount,
                    created_by=request.user,
                    is_active=True  # Mark as temporary
                )

                # Process each item in the invoice
                for item_data in items:
                    product = Product.objects.get(id=item_data['product_id'])
                    quantity = item_data['quantity']
                    unit_price = item_data['unit_price']
                    unit_type = item_data['unit_type']  # Can be 'tile', 'box', or 'pallet'
                    
                    # Convert quantity to tiles based on the unit type
                    if unit_type == 'pallet':
                        quantity_in_tiles = quantity * 55 * 10
                    elif unit_type == 'box':
                        quantity_in_tiles = quantity * 10
                    elif unit_type == 'sqf':
                        quantity_in_tiles = math.ceil(quantity / 23.33 * 10)  # Calculate approx tiles for sqf
                    else:
                        quantity_in_tiles = quantity  # Assume 'tile' is the base unit

                    # Check if enough stock is available
                    if product.stock_quantity < quantity_in_tiles:
                        return Response({"detail": f"Insufficient stock for product {product.name}."}, status=status.HTTP_400_BAD_REQUEST)

                    # Deduct stock and calculate the line total
                    product.stock_quantity -= quantity_in_tiles
                    product.save()
                    line_total = unit_price * quantity

                    # Create invoice item
                    EstimateItem.objects.create(
                        estimate=estimate,
                        product=product,
                        quantity=quantity,  # Store as selected unit (pallets, boxes, sqf, etc.)
                        unit_price=unit_price,
                        created_by=request.user
                    )
                    
                    # Accumulate total amount
                    total_amount += line_total

                # Update the invoice's total amount after processing all items
                estimate.total_amount = total_amount
                estimate.save()

            return Response({"estimate_id": estimate.id, "message": "estimate created successfully."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateBillView(APIView):
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
            with transaction.atomic():
                vendor = Vendor.objects.get(vendor_id=vendor_id)
                data = request.data

                bill_number = data.get("bill_number")
                mailing_address_street_1 = data.get("mailing_address_street_1","")
                mailing_address_street_2 = data.get("mailing_address_street_2","")
                mailing_address_city = data.get("mailing_address_city","")
                mailing_address_state = data.get("mailing_address_state","")
                mailing_address_postal_code = data.get("mailing_address_postal_code","")
                mailing_address_country = data.get("mailing_address_country","")
                # shipping_address = data.get("shipping_address")
                tags = data.get("tags")
                terms = data.get("terms")
                bill_date = data.get("bill_date")
                due_date = data.get("due_date")
                memo = data.get("memo")
                total_amount = float(data.get("total_amount"))
                payment_status = data.get("payment_status")
                if isinstance(payment_status, str):
                    payment_status = payment_status.lower()
                else:
                    payment_status = "unpaid"
                attachments = request.FILES.get("attachments")

                if attachments:
                    extension = os.path.splitext(attachments.name)[1]  # Get the file extension
                    short_unique_filename = generate_short_unique_filename(extension)
                    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'bill_attachments'))
                    logo_path = fs.save(short_unique_filename, attachments)
                    attachments_url = posixpath.join('media/bill_attachments', logo_path)
                else:
                    attachments_url = ""

                # Create temporary invoice
                bill = Bill.objects.create(
                    vendor=vendor,
                    mailing_address_street_1 = mailing_address_street_1,
                    mailing_address_street_2 = mailing_address_street_2,
                    mailing_address_city = mailing_address_city,
                    mailing_address_state = mailing_address_state,
                    mailing_address_postal_code = mailing_address_postal_code,
                    mailing_address_country = mailing_address_country,
                    tags = tags,
                    terms = terms,
                    bill_number = bill_number,
                    bill_date = bill_date, 
                    due_date = due_date,
                    memo = memo,
                    payment_status = payment_status,
                    total_amount=total_amount,
                    paid_amount=0,
                    unpaid_amount=total_amount,
                    attachments=attachments_url,
                    created_date=timezone.now(),
                    created_by=request.user,
                    is_active=True  # Mark as temporary
                )

                # Process each item in the invoice
                inv_total_amount = 0
                transaction_products = []
                service_products = []
                for item_data in items:
                    product = Product.objects.get(id=item_data['product_id'])
                    if product.product_type == "product":
                        quantity = float(item_data['quantity'])
                        unit_price = float(item_data['unit_price'])
                        unit_type = item_data['unit_type']  # Can be 'tile', 'box', or 'pallet'
                        description = item_data.get("description","")  # Can be 'tile', 'box', or 'pallet'
                        
                        # Convert quantity to tiles based on the unit type
                        if unit_type == 'pallet':
                            quantity_in_tiles = quantity * 55
                        elif unit_type == 'box':
                            quantity_in_tiles = quantity
                        elif unit_type == 'sqf':
                            quantity_in_tiles = math.ceil(float(quantity) / float(product.tile_area))  # Calculate approx tiles for sqf
                        else:
                            quantity_in_tiles = quantity  # Assume 'box' is the base unit

                        #calculating weighted average
                        current_stock_value = Decimal(product.stock_quantity) * Decimal(product.purchase_price)
                        new_stock_value = Decimal(quantity_in_tiles) * Decimal(unit_price)
                        total_stock_value = current_stock_value + new_stock_value
                        total_stock_quantity = Decimal(product.stock_quantity) + Decimal(quantity_in_tiles)
                        weighted_average = round(total_stock_value / total_stock_quantity, 2)
                        product.purchase_price = weighted_average

                        # Deduct stock and calculate the line total
                        product.stock_quantity += quantity_in_tiles
                        transaction_products.append({'quantity': quantity_in_tiles, 
                                                    "product_name": product.product_name,
                                                    "unit_price": unit_price})
                        product.save()
                        line_total = unit_price * quantity_in_tiles
                    elif product.product_type == 'service':
                        quantity = float(item_data['quantity'])
                        unit_price = float(item_data['unit_price'])
                        description = item_data.get("description","")
                        line_total = 0
                        quantity_in_tiles = 1
                        service_products.append({'service_name': product.product_name,
                                                    'unit_price': unit_price})                        

                    # Create invoice item
                    BillItems.objects.create(
                        bill=bill,
                        product=product,
                        quantity=quantity_in_tiles,  # Store as selected unit (pallets, boxes, sqf, etc.)
                        description=description,
                        unit_price=unit_price,
                        created_by=request.user
                    )
                    
                    # Accumulate total amount
                    inv_total_amount += line_total

                # Update the invoice's total amount after processing all items
                # invoice.total_amount = total_amount
                bill_payment = create_bill_transaction(bill_id=bill.id, vendor=vendor, products=transaction_products, services=service_products,
                                                       total_amount=total_amount, user=request.user)
                if not bill_payment:
                    log.app.error("Bill Creation Failed | Error in creating transaction | ")
                    return Response("Bill Creation Failed due to errors in transactions", status=status.HTTP_400_BAD_REQUEST)
                bill.save()

            audit_log_entry = audit_log(user=request.user,
                              action="Bill Created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Bill", 
                              record_id=bill.id)
            log.audit.success(f"Bill created successfully | {bill.id} | {user}")
            return Response({"bill_id":bill.id, "bill_number": bill.bill_number, "message": "Bill created successfully."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.trace.trace(f"Error occured while creating bill, {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ListBillsView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get(self, request):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        bills = Bill.objects.filter(is_active=True).values("id",
            "bill_number", "vendor__business_name", "vendor__vendor_id", "vendor__email", "total_amount", "unpaid_amount", "bill_date", "due_date", "payment_date", "payment_status"
        )
        bill_list = list(bills)  # Convert queryset to list of dicts
        return Response(bill_list, status=status.HTTP_200_OK)


class ListVendorBillsView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get(self, request, vendor_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        bills = Bill.objects.filter(vendor=vendor_id, 
                                    payment_status__in=["unpaid","partially_paid"], 
                                    is_active=True).values("id",
            "bill_number", "vendor__business_name", 
            "vendor__vendor_id", "vendor__email", 
            "total_amount", "unpaid_amount", "paid_amount",
            "bill_date", "due_date", "payment_date", "payment_status"
        ).order_by('-bill_date')
        bill_list = list(bills)  # Convert queryset to list of dicts
        return Response(bill_list, status=status.HTTP_200_OK)


class RetrieveBillView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def get(self, request, id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            bill = Bill.objects.get(id=id, is_active=True)
            items = BillItems.objects.filter(bill=bill).values(
                "product__id", "product__product_name", "quantity", "unit_price", "description"
            )
            bill_data = {
                "bill_number": bill.bill_number,
                "vendor": bill.vendor.business_name,
                "mailing_address_street_1": bill.mailing_address_street_1,
                "mailing_address_street_2": bill.mailing_address_street_2,
                "mailing_address_city": bill.mailing_address_city,
                "mailing_address_state": bill.mailing_address_state,
                "mailing_address_postal_code": bill.mailing_address_postal_code,
                "mailing_address_country": bill.mailing_address_country,
                "bill_date": bill.bill_date,
                "due_date": bill.due_date,
                "payment_date": bill.payment_date,
                "total_amount": bill.total_amount,
                "payment_status": bill.payment_status,
                "attachments": bill.attachments,
                "items": list(items)
            }
            payment_details = BillTransactionMapping.objects.filter(bill_id=id, is_payment_transaction=True)

            # Fetch transaction lines related to the bill
            transaction_lines = []
            for mapping in payment_details:
                transaction = mapping.transaction
                lines = TransactionLine.objects.filter(transaction=transaction, bill_id=id).values(
                    "id", "description", "debit_amount", "credit_amount", "account__code", "account__name"
                )
                for line in lines:
                    transaction_lines.append({
                        "transaction_date": transaction.date,
                        "value": line.get("debit_amount")
                    })
            if transaction_lines:
                bill_data["transaction_lines"] = transaction_lines
            return Response(bill_data, status=status.HTTP_200_OK)
        except Bill.DoesNotExist:
            return Response({"detail": "Bill not found."}, status=status.HTTP_404_NOT_FOUND)


class BillDeleteView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def patch(self, request):
        """
        Mark one or more invoices as fully or partially paid, handle tracking, 
        and record the payment details for the customer.
        """
        try:
            user = self.get_user_from_token(request)
            if not user:
                return Response({"detail": "Invalid user token."}, status=status.HTTP_401_UNAUTHORIZED)

            # Get the request data
            bill_id = request.data.get("Bill")  # List of Bill IDs and amounts
            bill = Bill.objects.get(id=bill_id)
            with transaction.atomic():
                Bill.is_active = False
                delete_transactions = delete_bill_transaction(bill_id=bill_id, user=user)
                if not delete_transactions:
                    return Response({"detail": "Error deleting transactions."}, status=status.HTTP_400_BAD_REQUEST)
                bill.save()

            # Log and return response
            log.audit.success(f"bill deleted successfully | {bill_id} | {user}")
            audit_log_entry = audit_log(user=request.user,
                                        action="delete bill",
                                        ip_add=request.META.get('HTTP_X_FORWARDED_FOR'),
                                        model_name="Bill",
                                        model_id=bill_id)
            return Response({"detail": f"bill deleted successfully {bill_id}."}, status=status.HTTP_200_OK)
        except Bill.DoesNotExist:
            log.app.error("Bill Not found")
            return Response({"detail": "bill not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.app.error(f"Error processing payment: {str(e)}")
            log.trace.trace(f"Error processing bill payments {traceback.format_exc()}")
            return Response({"detail": "Error processing payment."}, status=status.HTTP_400_BAD_REQUEST)


class BillPaidView(APIView):
    def get_user_from_token(self, request):
        token = request.headers.get("Authorization", "").split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return NewUser.objects.get(id=user_id)
        except (jwt.ExpiredSignatureError, jwt.DecodeError, NewUser.DoesNotExist):
            return None

    def patch(self, request):
        """
        Mark one or more bills as fully or partially paid, handle tracking, 
        and record the payment details for the vendor.
        """
        try:
            user = self.get_user_from_token(request)
            if not user:
                return Response({"detail": "Invalid user token."}, status=status.HTTP_401_UNAUTHORIZED)

            # Get the request data
            bills_data = request.data.get("bills", [])  # List of bill IDs and amounts
            payment_amount = Decimal(request.data.get("payment_amount"))
            payment_amount = round(payment_amount,2)
            vendor_id = request.data.get("vendor_id")
            debit_account_id = request.data.get("debit_account_id")  # Bank/Cash account ID
            use_advanced_payment = request.data.get("use_advanced_payment", False)
            bill_payment_date = request.data.get("payment_date")
            if not use_advanced_payment and payment_amount <= 0:
                return Response({"detail": "Invalid payment amount."}, status=status.HTTP_400_BAD_REQUEST)

            # Retrieve vendor, payable tracking, and debit account
            vendor = Vendor.objects.get(vendor_id=vendor_id, is_active=True)
            payable, created = PayableTracking.objects.get_or_create(vendor=vendor,
                    defaults={'payable_amount': Decimal("0.00"), 'advance_payment': Decimal("0.00")})
            accounts_payable = Account.objects.get(code='AP-001', is_active=True)
            debit_account = Account.objects.get(id=debit_account_id, is_active=True)

            if use_advanced_payment:
                payment_amount = payable.advance_payment
                payment_amount = Decimal(payment_amount)
                payable.advance_payment = Decimal("0.00")

            total_allocated = Decimal("0.00")
            transactions_to_log = []

            # Loop through each bill and allocate payment
            with db_transaction.atomic():
                for bill_data in bills_data:
                    bill_id = bill_data.get("bill_id")
                    
                    if not bill_payment_date:
                        bill_payment_date = datetime.now().date()
                    allocated_amount = Decimal(bill_data.get("allocated_amount", 0))
                    allocated_amount = round(allocated_amount, 2)

                    if allocated_amount <= 0:
                        continue  # Skip invalid or zero allocations

                    bill = Bill.objects.get(id=bill_id, vendor=vendor, is_active=True)

                    # Calculate payment for the bill
                    if bill.unpaid_amount == 0:
                        return Response({"Details": "Bill is already paid."}, status=status.HTTP_400_BAD_REQUEST)
                    payment_for_bill = min(allocated_amount, bill.unpaid_amount)

                    # Update bill
                    bill.paid_amount += payment_for_bill
                    bill.unpaid_amount -= payment_for_bill
                    bill.payment_status = "paid" if bill.unpaid_amount == 0 else "partially_paid"
                    bill.payment_date = bill_payment_date

                    # Add to total allocated
                    total_allocated += payment_for_bill
                    if total_allocated > payment_amount:
                        return Response({"detail": "Payment amount is insufficient for allocation."}, status=status.HTTP_400_BAD_REQUEST)
                    bill.save()

                    # Record bill transaction
                    transactions_to_log.append({
                        "bill_id": bill.id,
                        "description": f"Payment for bill {bill.id}",
                        "credit_amount": payment_for_bill,
                        "debit_amount": 0,
                    })


                # Update payable tracking
                payable.payable_amount -= Decimal(total_allocated)
                accounts_payable.balance -= Decimal(total_allocated)

                # Handle overpayment
                overpayment = Decimal(payment_amount) - Decimal(total_allocated)
                if overpayment > 0:
                    payable.advance_payment += Decimal(overpayment)

                transaction = Transaction.objects.create(
                    reference_number=f"PAY-{uuid.uuid4().hex[:6].upper()}",
                    transaction_type="expense",
                    date=bill_payment_date,
                    description=f"Payment made to vendor {vendor.business_name}",
                    tax_amount=0,
                    is_active=True,
                    created_by=user,
                )

                # Log each transaction line
                for line in transactions_to_log:
                    TransactionLine.objects.create(
                        transaction=transaction,
                        account=Account.objects.get(code="AP-001"),
                        description=f"Payment for bill {bill.id}",
                        debit_amount=line.get("credit_amount"),
                        credit_amount=0,
                        bill_id=line.get("bill_id"),
                    )

                # Log debit from bank/cash account
                TransactionLine.objects.create(
                    transaction=transaction,
                    account=debit_account,
                    description=f"Payment debited for vendor {vendor.business_name}",
                    credit_amount=payment_amount,
                    debit_amount=0,
                )

                # Save payment details in VendorPaymentDetail
                VendorPaymentDetails.objects.create(
                    vendor=vendor,
                    transaction=transaction,
                    payment_method=request.data.get("payment_method", ""),
                    transaction_reference_id=request.data.get("transaction_id", ""),
                    bank_name=request.data.get("bank_name", ""),
                    cheque_number=request.data.get("cheque_number", ""),
                    payment_date=datetime.now(),
                    payment_amount=payment_amount,
                )
                debit_account.balance -= Decimal(payment_amount)
                payable.save()

                for line in transactions_to_log:
                    BillTransactionMapping.objects.create(
                        transaction=transaction,
                        bill_id=line.get("bill_id"),
                        is_payment_transaction=True,
                        is_active=True
                    )

                debit_account.save()
                accounts_payable.save()

            # Log and return response
            log.audit.success(f"Payments applied for vendor {vendor.business_name} | User: {user}")
            return Response({"detail": f"Payment processed successfully for vendor {vendor.business_name}."}, status=status.HTTP_200_OK)

        except Vendor.DoesNotExist:
            log.app.error("Vendor Not found")
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        except Bill.DoesNotExist:
            log.app.error("Bill Not found")
            return Response({"detail": "One or more bills not found."}, status=status.HTTP_404_NOT_FOUND)
        except PayableTracking.DoesNotExist:
            log.app.error("Payable tracking Not found")
            return Response({"detail": "Payable tracking not found."}, status=status.HTTP_404_NOT_FOUND)
        except Account.DoesNotExist:
            log.app.error("Account Not found")
            return Response({"detail": "Specified debit account not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.app.error(f"Error processing payment: {str(e)}")
            log.trace.trace(f"Error processing bill payments {traceback.format_exc()}")
            return Response({"detail": "Error processing payment."}, status=status.HTTP_400_BAD_REQUEST)


class CreateLostProductView(APIView):
    def post(self, request):
        try:
            # Extract data from the request
            data = request.data
            product_id = data.get('product')
            quantity_lost = int(data.get('quantity_lost'))
            reason = data.get('reason', 'damaged')
            loss_date = data.get('loss_date', timezone.now().date())
            invoice_id = data.get('invoice')
            notes = data.get('notes', '')

            # Fetch related objects
            product = Product.objects.get(id=product_id)
            created_by = request.user
            invoice = Invoice.objects.get(id=invoice_id) if invoice_id else None
            unit_cost = product.purchase_price

            # Calculate total loss
            total_loss = quantity_lost * unit_cost

            # Deduct lost quantity from product stock
            if product.stock_quantity < quantity_lost:
                log.app.error(f"Insufficient stock for product {product.product_name}")
                return Response({"detail": "Insufficient stock for product."}, status=status.HTTP_400_BAD_REQUEST)
            product.stock_quantity -= quantity_lost
            product.save()

            # Fetch relevant accounts
            inventory_account = Account.objects.get(code='INV-001', is_active=True)
            loss_account = Account.objects.get(code='MIS-001', is_active=True)

            with transaction.atomic():
                # Create a new transaction
                transaction_obj = Transaction.objects.create(
                    description=f"Loss of product {product.product_name}",
                    created_by=created_by,
                    date=loss_date,
                    reference_number=f"LOSS-{uuid.uuid4().hex[:6].upper()}",
                    transaction_type='expense',
                )

                lost_product = LostProduct.objects.create(
                    product=product,
                    quantity_lost=quantity_lost,
                    unit_cost=unit_cost,
                    total_loss=total_loss,
                    reason=reason,
                    loss_date=loss_date,
                    invoice=invoice,
                    transaction = transaction_obj,
                    notes=notes,
                    created_by=created_by,
                )

                # Create transaction lines
                TransactionLine.objects.create(
                    transaction=transaction_obj,
                    account=loss_account,
                    debit_amount=total_loss,
                    credit_amount=0,
                    description=f"Loss due to {reason} for product {product.product_name}",
                )

                TransactionLine.objects.create(
                    transaction=transaction_obj,
                    account=inventory_account,
                    debit_amount=0,
                    credit_amount=total_loss,
                    description=f"Inventory adjustment for lost product {product.product_name}",
                )

                # Update account balances
                loss_account.balance += total_loss
                inventory_account.balance -= total_loss
                loss_account.save()
                inventory_account.save()

            # Prepare response
            response_data = {
                "id": lost_product.id,
                "product": product.id,
                "quantity_lost": quantity_lost,
                "unit_cost": unit_cost,
                "total_loss": total_loss,
                "reason": reason,
                "loss_date": loss_date,
                "invoice": invoice.id if invoice else None,
                "notes": notes,
                "created_by": created_by.id,
                "created_date": lost_product.created_date,
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error occurred {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ListLostProductsView(APIView):
    def get(self, request):
        try:
            # Fetch all LostProduct entries
            lost_products = LostProduct.objects.all()

            # Prepare response data
            response_data = []
            for lost_product in lost_products:
                response_data.append({
                    "id": lost_product.id,
                    "product": lost_product.product.id,
                    "product_name": lost_product.product.product_name,
                    "quantity_lost": lost_product.quantity_lost,
                    "unit_cost": float(lost_product.unit_cost),
                    "total_loss": float(lost_product.total_loss),
                    "reason": lost_product.reason,
                    "loss_date": lost_product.loss_date,
                    "invoice": lost_product.invoice.id if lost_product.invoice else None,
                    "notes": lost_product.notes,
                    "created_by": lost_product.created_by.id,
                    "created_date": lost_product.created_date,
                })

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class LostProductDetailView(APIView):
    def get(self, request, lost_product_id):
        try:
            # Fetch the LostProduct entry
            lost_product = LostProduct.objects.get(id=lost_product_id)

            # Prepare response data
            response_data = {
                "id": lost_product.id,
                "product": lost_product.product.id,
                "product_name": lost_product.product.product_name,
                "quantity_lost": lost_product.quantity_lost,
                "unit_cost": float(lost_product.unit_cost),
                "total_loss": float(lost_product.total_loss),
                "reason": lost_product.reason,
                "loss_date": lost_product.loss_date,
                "invoice": lost_product.invoice.id if lost_product.invoice else None,
                "notes": lost_product.notes,
                "created_by": lost_product.created_by.id,
                "created_date": lost_product.created_date,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except LostProduct.DoesNotExist:
            return Response({"detail": "LostProduct not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UpdateLostProductView(APIView):
    def put(self, request, id):
        try:
            # Fetch the existing LostProduct entry
            lost_product = LostProduct.objects.get(id=id)

            # Extract data from the request
            data = request.data
            product_id = data.get('product', lost_product.product.id)
            quantity_lost = int(data.get('quantity_lost', lost_product.quantity_lost))
            reason = data.get('reason', lost_product.reason)
            loss_date = data.get('loss_date', lost_product.loss_date)
            invoice_id = data.get('invoice', lost_product.invoice.id if lost_product.invoice else None)
            notes = data.get('notes', lost_product.notes)

            # Fetch related objects
            product = Product.objects.get(id=product_id)
            invoice = Invoice.objects.get(id=invoice_id) if invoice_id else None
            transaction_obj = Transaction.objects.get(id=lost_product.transaction.id)

            unit_cost = product.purchase_price

            # Calculate new total loss
            new_total_loss = quantity_lost * unit_cost

            # Adjust inventory and financial transactions if quantity_lost or unit_cost changes
            if quantity_lost != lost_product.quantity_lost:
                # Fetch relevant accounts
                inventory_account = Account.objects.get(code='INV-001')
                loss_account = Account.objects.get(code='MIS-001')

                # Reverse the old transaction
                old_total_loss = lost_product.total_loss
                inventory_account.balance += old_total_loss
                loss_account.balance -= old_total_loss
                inventory_account.save()
                loss_account.save()

                # Deduct new lost quantity from product stock
                product.stock_quantity += lost_product.quantity_lost  # Reverse old deduction
                product.stock_quantity -= quantity_lost  # Apply new deduction
                product.save()

                # Create a new transaction for the updated loss
                transaction_obj.description = f"Updated loss of product {product.product_name}"

                old_transaction_lines = TransactionLine.objects.filter(transaction=transaction_obj, is_active=True).delete()

                # Create transaction lines
                TransactionLine.objects.create(
                    transaction=transaction_obj,
                    account=loss_account,
                    debit_amount=new_total_loss,
                    credit_amount=0,
                    description=f"Updated loss due to {reason} for product {product.product_name}",
                )

                TransactionLine.objects.create(
                    transaction=transaction_obj,
                    account=inventory_account,
                    debit_amount=0,
                    credit_amount=new_total_loss,
                    description=f"Updated inventory adjustment for lost product {product.product_name}",
                )

                # Update account balances
                loss_account.balance += new_total_loss
                inventory_account.balance -= new_total_loss
                loss_account.save()
                transaction_obj.save()
                inventory_account.save()

            # Update the LostProduct entry
            lost_product.product = product
            lost_product.quantity_lost = quantity_lost
            lost_product.unit_cost = unit_cost
            lost_product.total_loss = new_total_loss
            lost_product.reason = reason
            lost_product.loss_date = loss_date
            lost_product.invoice = invoice
            lost_product.notes = notes
            lost_product.updated_by = request.user
            lost_product.save()

            # Prepare response
            response_data = {
                "id": lost_product.id,
                "product": product.id,
                "quantity_lost": quantity_lost,
                "unit_cost": unit_cost,
                "total_loss": new_total_loss,
                "reason": reason,
                "loss_date": loss_date,
                "invoice": invoice.id if invoice else None,
                "notes": notes,
                "created_by": lost_product.created_by.id,
                "created_date": lost_product.created_date,
                "updated_by": lost_product.updated_by.id,
                "updated_date": lost_product.updated_date,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except LostProduct.DoesNotExist:
            return Response({"detail": "LostProduct not found."}, status=status.HTTP_404_NOT_FOUND)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class DeleteLostProductView(APIView):
    def delete(self, request, id):
        try:
            # Fetch the existing LostProduct entry
            lost_product = LostProduct.objects.get(id=id)

            # Fetch relevant accounts
            inventory_account = Account.objects.get(code='INV-001')
            loss_account = Account.objects.get(code='MIS-001')

            transaction_details = Transaction.objects.filter(id=lost_product.transaction.id, is_active=True).first()
            transaction_lines = TransactionLine.objects.filter(transaction=transaction_details, is_active=True) 
            # Reverse the inventory and financial transactions
            with transaction.atomic():
                # Reverse inventory deduction
                lost_product.product.stock_quantity += lost_product.quantity_lost
                lost_product.product.save()

                # Reverse account balances
                inventory_account.balance += lost_product.total_loss
                loss_account.balance -= lost_product.total_loss
                inventory_account.save()
                loss_account.save()
                # Delete the LostProduct entry
                lost_product.delete()
                transaction_lines.delete()
                transaction_details.delete()

            return Response({"detail": "LostProduct deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

        except LostProduct.DoesNotExist:
            log.app.error("LostProduct Not found")
            return Response({"detail": "LostProduct not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log.trace.trace(f"Error occurred {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class InventoryHistoryReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            return Response({"error": "Please provide start_date and end_date parameters."})
        
        # Fetching all relevant transactions
        sales = InvoiceItem.objects.filter(invoice__bill_date__range=[start_date, end_date])
        purchases = BillItems.objects.filter(bill__bill_date__range=[start_date, end_date])
        losses = LostProduct.objects.filter(loss_date__range=[start_date, end_date])
        
        report_data = []
        
        # Calculating initial inventory
        initial_inventory = {}
        for product in Product.objects.filter(product_type="product"):
            initial_stock = 0
            # initial_stock = product.stock_quantity
            # Adjust initial stock based on transactions before the start date
            previous_purchases = BillItems.objects.filter(bill__bill_date__lt=start_date, product=product)
            previous_sales = InvoiceItem.objects.filter(invoice__bill_date__lt=start_date, product=product)
            previous_losses = LostProduct.objects.filter(loss_date__lt=start_date, product=product)
            
            for purchase in previous_purchases:
                initial_stock += purchase.quantity
            for sale in previous_sales:
                initial_stock -= sale.quantity
            for loss in previous_losses:
                initial_stock -= loss.quantity_lost
            
            initial_inventory[product.product_name] = initial_stock
        
        # Processing transactions
        for sale in sales:
            transaction = {
                'date': sale.invoice.bill_date.date(),
                'type': 'Sale',
                'product_name': sale.product.product_name,
                'quantity': -sale.quantity,  # Negative for sales
                'unit_price': sale.unit_price,
            }
            report_data.append(transaction)
        
        for purchase in purchases:
            transaction = {
                'date': purchase.bill.bill_date.date(),
                'type': 'Purchase',
                'product_name': purchase.product.product_name,
                'quantity': purchase.quantity,  # Positive for purchases
                'unit_price': purchase.unit_price,
            }
            report_data.append(transaction)
        
        for loss in losses:
            transaction = {
                'date': loss.loss_date,
                'type': 'Loss',
                'product_name': loss.product.product_name,
                'quantity': -loss.quantity_lost,  # Negative for losses
                'unit_price': loss.unit_cost,
            }
            report_data.append(transaction)
        
        # Sorting transactions by date
        report_data.sort(key=lambda x: x['date'])
        
        # Calculating closing inventory
        closing_inventory = {}
        for product in Product.objects.filter(product_type="product"):
            closing_stock = initial_inventory.get(product.product_name, 0)
            # Adjust closing stock based on transactions within the period
            period_purchases = BillItems.objects.filter(bill__bill_date__range=[start_date, end_date], product=product)
            period_sales = InvoiceItem.objects.filter(invoice__bill_date__range=[start_date, end_date], product=product)
            period_losses = LostProduct.objects.filter(loss_date__range=[start_date, end_date], product=product)
            
            for purchase in period_purchases:
                closing_stock += purchase.quantity
            for sale in period_sales:
                closing_stock -= sale.quantity
            for loss in period_losses:
                closing_stock -= loss.quantity_lost
            
            closing_inventory[product.product_name] = closing_stock
        
        # Combining initial inventory, transactions, and closing inventory into the report
        report = {
            'initial_inventory': initial_inventory,
            'transactions': report_data,
            'closing_inventory': closing_inventory,
        }
        
        return Response(report)


class InventoryHistoryXLSXReportView(APIView):
    def get(self, request):
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            return Response({"error": "Please provide start_date and end_date parameters."})
        
        # Fetching all relevant transactions
        sales = InvoiceItem.objects.filter(invoice__bill_date__range=[start_date, end_date])
        purchases = BillItems.objects.filter(bill__bill_date__range=[start_date, end_date])
        losses = LostProduct.objects.filter(loss_date__range=[start_date, end_date])
        
        report_data = []
        
        # Calculating initial inventory
        initial_inventory = {}
        for product in Product.objects.filter(product_type="product"):
            initial_stock = 0
            # Adjust initial stock based on transactions before the start date
            previous_purchases = BillItems.objects.filter(bill__bill_date__lt=start_date, product=product)
            previous_sales = InvoiceItem.objects.filter(invoice__bill_date__lt=start_date, product=product)
            previous_losses = LostProduct.objects.filter(loss_date__lt=start_date, product=product)
            
            for purchase in previous_purchases:
                initial_stock += purchase.quantity
            for sale in previous_sales:
                initial_stock -= sale.quantity
            for loss in previous_losses:
                initial_stock -= loss.quantity_lost
            
            initial_inventory[product.product_name] = initial_stock
        
        # Processing transactions
        for sale in sales:
            transaction = {
                'date': sale.invoice.bill_date.date(),
                'type': 'Sale',
                'product_name': sale.product.product_name,
                'quantity': -sale.quantity,  # Negative for sales
                'unit_price': sale.unit_price,
            }
            report_data.append(transaction)
        
        for purchase in purchases:
            transaction = {
                'date': purchase.bill.bill_date.date(),
                'type': 'Purchase',
                'product_name': purchase.product.product_name,
                'quantity': purchase.quantity,  # Positive for purchases
                'unit_price': purchase.unit_price,
            }
            report_data.append(transaction)
        
        for loss in losses:
            transaction = {
                'date': loss.loss_date,
                'type': 'Loss',
                'product_name': loss.product.product_name,
                'quantity': -loss.quantity_lost,  # Negative for losses
                'unit_price': loss.unit_cost,
            }
            report_data.append(transaction)
        
        # Sorting transactions by date
        report_data.sort(key=lambda x: x['date'])
        
        # Calculating closing inventory
        closing_inventory = {}
        for product in Product.objects.filter(product_type="product"):
            closing_stock = initial_inventory.get(product.product_name, 0)
            # Adjust closing stock based on transactions within the period
            period_purchases = BillItems.objects.filter(bill__bill_date__range=[start_date, end_date], product=product)
            period_sales = InvoiceItem.objects.filter(invoice__bill_date__range=[start_date, end_date], product=product)
            period_losses = LostProduct.objects.filter(loss_date__range=[start_date, end_date], product=product)
            
            for purchase in period_purchases:
                closing_stock += purchase.quantity
            for sale in period_sales:
                closing_stock -= sale.quantity
            for loss in period_losses:
                closing_stock -= loss.quantity_lost
            
            closing_inventory[product.product_name] = closing_stock
            
        # Create Excel file using pandas
        output = io.BytesIO()
        
        # Create a pandas Excel writer using XlsxWriter as the engine
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Convert initial inventory to DataFrame and write to Excel
            initial_df = pd.DataFrame(
                [{'Product': k, 'Initial Stock': v} for k, v in initial_inventory.items()]
            )
            initial_df.to_excel(writer, sheet_name='Initial Inventory', index=False)
            
            # Convert transactions to DataFrame and write to Excel
            if report_data:
                trans_df = pd.DataFrame(report_data)
                trans_df.columns = ['Date', 'Transaction Type', 'Product', 'Quantity', 'Unit Price']
                # Format the date column
                trans_df['Date'] = pd.to_datetime(trans_df['Date']).dt.strftime('%Y-%m-%d')
                trans_df.to_excel(writer, sheet_name='Transactions', index=False)
            else:
                pd.DataFrame(columns=['Date', 'Transaction Type', 'Product', 'Quantity', 'Unit Price']).to_excel(
                    writer, sheet_name='Transactions', index=False
                )
            
            # Convert closing inventory to DataFrame and write to Excel
            closing_df = pd.DataFrame(
                [{'Product': k, 'Closing Stock': v} for k, v in closing_inventory.items()]
            )
            closing_df.to_excel(writer, sheet_name='Closing Inventory', index=False)
            
            # Add Summary sheet with period information
            summary_data = {
                'Start Date': [start_date.strftime('%Y-%m-%d')],
                'End Date': [end_date.strftime('%Y-%m-%d')],
                'Report Generated': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Auto-adjust columns width
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
        
        # Get the value from the output buffer
        output.seek(0)
        
        # Create the HttpResponse with Excel content type
        filename = f"inventory_history_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class DetailedInventoryReportView(APIView):
    def get(self, request):
        products = Product.objects.filter(product_type="product",is_active=True)
        inventory_data = []
        total_inventory_value = 0
        
        for product in products:
            item = {
                'product_name': product.product_name,
                'sku': product.sku,
                'barcode': product.barcode,
                'stock_quantity': product.stock_quantity,
                'stock_purchase_price': product.purchase_price,
                'stock_value': round(Decimal(product.stock_quantity * product.purchase_price), 2),
                'reorder_level': product.reorder_level,
                'batch_lot_number': product.batch_lot_number,
                'as_on_date': product.as_on_date,
                'specifications': product.specifications,
                'description': product.purchase_description,
                'tags': product.tags,
                'images': product.images,
            }
            inventory_data.append(item)
            total_inventory_value += item['stock_value']
        
        return Response(inventory_data)



class DetailedInventoryReportExcelExportView(APIView):
    def get(self, request):
        try:
            # Fetch active products of type "product"
            products = Product.objects.filter(product_type="product", is_active=True)
            
            # Prepare inventory data
            inventory_data = []
            total_inventory_value = 0
            
            for product in products:
                try:
                    # Calculate stock value
                    stock_value = round(Decimal(product.stock_quantity * product.purchase_price), 2)
                    
                    # Prepare item data
                    item = {
                        'Product Name': product.product_name,
                        'UPC': product.sku,
                        'Item Code': product.barcode,
                        'Stock Quantity': product.stock_quantity,
                        'Purchase Price': float(product.purchase_price),  # Convert Decimal to float for Excel
                        'Stock Value': float(stock_value),  # Convert Decimal to float for Excel
                        'Reorder Level': product.reorder_level,
                        'Batch/Lot Number': product.batch_lot_number,
                        'As On Date': product.as_on_date.strftime('%Y-%m-%d') if product.as_on_date else None,
                        'Specifications': product.specifications,
                        'Description': product.purchase_description,
                        'Tags': product.tags,
                        'Images': product.images,
                    }
                    inventory_data.append(item)
                    total_inventory_value += item['Stock Value']
                except Exception as e:
                    # Log errors for individual products
                    log.app.error(f"Error processing product {product.id}: {str(e)}")
                    log.trace.trace(traceback.format_exc())
                    continue  # Skip this product and continue with the next one
            
            # Convert inventory data to a pandas DataFrame
            df = pd.DataFrame(inventory_data)

            # Add a row for the total inventory value
            total_row = {
                'Product Name': 'Total Inventory Value',
                'UPC': '',
                'Item Code': '',
                'Stock Quantity': '',
                'Purchase Price': '',
                'Stock Value': float(total_inventory_value),  # Convert Decimal to float for Excel
                'Reorder Level': '',
                'Batch/Lot Number': '',
                'As On Date': '',
                'Specifications': '',
                'Description': '',
                'Tags': '',
                'Images': '',
            }
            total_df = pd.DataFrame([total_row])
            df = pd.concat([df, total_df], ignore_index=True)

            # Create the HttpResponse object with the appropriate Excel headers
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=detailed_inventory_report.xlsx'

            # Save the DataFrame to the HttpResponse as an Excel file
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Inventory Report')

            return response

        except Exception as e:
            # Log the error and return a 500 response
            log.app.error(f"Error generating inventory report: {str(e)}")
            log.trace.trace(traceback.format_exc())
            return Response(
                {"detail": "An error occurred while generating the inventory report. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DetailedSalesReportView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        invoices = Invoice.objects.filter(is_active=True)
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            invoices = invoices.filter(bill_date__range=[start_date, end_date])
        
        sales_data = []
        
        for invoice in invoices:
            invoice_items = InvoiceItem.objects.filter(invoice=invoice, is_active=True)
            for item in invoice_items:
                sales_item = {
                    'invoice_id': invoice.id,
                    'invoice_date': invoice.bill_date,
                    'customer_name': invoice.customer.business_name,
                    'customer_email': invoice.customer_email,
                    'payment_status': invoice.payment_status,
                    'product_name': item.product.product_name,
                    'sku': item.product.sku,
                    'quantity_sold': item.quantity,
                    'unit_price': item.unit_price,
                    'total_amount': item.amount,
                }
                sales_data.append(sales_item)
        
        return Response(sales_data)


class DetailedSalesReportExcelExportView(APIView):
    def get(self, request):
        # Extract query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Fetch invoices
        invoices = Invoice.objects.filter(is_active=True)
        
        # Apply date filters if provided
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            invoices = invoices.filter(bill_date__range=[start_date, end_date])
        
        # Prepare sales data
        sales_data = []
        for invoice in invoices:
            invoice_items = InvoiceItem.objects.filter(invoice=invoice, is_active=True)
            for item in invoice_items:
                sales_item = {
                    'Invoice ID': invoice.id,
                    'Invoice Date': invoice.bill_date.strftime('%Y-%m-%d'),
                    'Customer Name': invoice.customer.business_name,
                    'Customer Email': invoice.customer_email,
                    'Payment Status': invoice.payment_status,
                    'Product Name': item.product.product_name,
                    'SKU': item.product.sku,
                    'Quantity Sold': item.quantity,
                    'Unit Price': item.unit_price,
                    'Total Amount': item.amount,
                }
                sales_data.append(sales_item)
        
        # Convert sales data to a pandas DataFrame
        df = pd.DataFrame(sales_data)

        # Create the HttpResponse object with the appropriate Excel headers
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=detailed_sales_report_{start_date}_{end_date}.xlsx'

        # Save the DataFrame to the HttpResponse as an Excel file
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sales Report')

        return response


class ExpenseReportView(APIView):
    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            report_type = request.GET.get('report_type')
            
            if start_date and end_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                return Response({"error": "Please provide start_date and end_date parameters."})
            
            if report_type not in ['accrual', 'cash']:
                return Response({"error": "Invalid report_type. Please use 'accrual' or 'cash'."})
            
            report_data = []
            
            if report_type == 'accrual':
                # Fetching all relevant expenses and bills
                expenses = Expense.objects.filter(payment_date__range=[start_date, end_date])
                bills = Bill.objects.filter(bill_date__range=[start_date, end_date])
                
                # Processing expenses
                for expense in expenses:
                    expense_items = ExpenseItems.objects.filter(expense=expense, is_active=True)
                    for item in expense_items:
                        expense_item = {
                            'date': expense.payment_date,
                            'type': 'Expense',
                            'vendor_name': expense.vendor.business_name,
                            'description': item.description,
                            'amount': item.price,
                            'vendor_expense': expense.expense_number,
                        }
                        report_data.append(expense_item)
                
                # Processing bills
                for bill in bills:
                    bill_items = BillItems.objects.filter(bill=bill, is_active=True)
                    for item in bill_items:
                        bill_item = {
                            'date': bill.bill_date.date(),
                            'type': 'Bill',
                            'vendor_name': bill.vendor.business_name,
                            'description': item.description,
                            'amount': item.line_total(),
                            'vendor_bill': bill.bill_number,
                        }
                        report_data.append(bill_item)
            
            elif report_type == 'cash':
                # Fetching all relevant vendor payments
                vendor_payments = VendorPaymentDetails.objects.filter(payment_date__range=[start_date, end_date]).exclude(payment_method='inventory')
                
                for payment in vendor_payments:
                    payment_item = {
                        'date': payment.payment_date,
                        'type': 'Payment',
                        'vendor_name': payment.vendor.business_name,
                        'payment_method': payment.payment_method,
                        'amount': payment.payment_amount,
                        'transaction_reference': payment.transaction_reference_id,
                    }
                    report_data.append(payment_item)
            
            # Sorting transactions by date
            report_data.sort(key=lambda x: x['date'], reverse=True)
            
            return Response(report_data, status=status.HTTP_200_OK)
        except Exception as e:
            log.trace.trace(f"Error occurred {traceback.format_exc()}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExpenseReportExcelExportView(APIView):
    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            report_type = request.GET.get('report_type')
            
            if start_date and end_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                return Response({"error": "Please provide start_date and end_date parameters."}, status=status.HTTP_400_BAD_REQUEST)
            
            if report_type not in ['accrual', 'cash']:
                return Response({"error": "Invalid report_type. Please use 'accrual' or 'cash'."}, status=status.HTTP_400_BAD_REQUEST)
            
            report_data = []
            
            if report_type == 'accrual':
                # Fetching all relevant expenses and bills
                expenses = Expense.objects.filter(payment_date__range=[start_date, end_date])
                bills = Bill.objects.filter(bill_date__range=[start_date, end_date])
                
                # Processing expenses
                for expense in expenses:
                    expense_items = ExpenseItems.objects.filter(expense=expense, is_active=True)
                    for item in expense_items:
                        expense_item = {
                            'Date': expense.payment_date,
                            'Type': 'Expense',
                            'Vendor Name': expense.vendor.business_name,
                            'Description': item.description,
                            'Amount': item.price,
                            'Vendor Expense': expense.expense_number,
                        }
                        report_data.append(expense_item)
                
                # Processing bills
                for bill in bills:
                    bill_items = BillItems.objects.filter(bill=bill, is_active=True)
                    for item in bill_items:
                        bill_item = {
                            'Date': bill.bill_date.date(),
                            'Type': 'Bill',
                            'Vendor Name': bill.vendor.business_name,
                            'Description': item.description,
                            'Amount': item.line_total(),
                            'Vendor Bill': bill.bill_number,
                        }
                        report_data.append(bill_item)
            
            elif report_type == 'cash':
                # Fetching all relevant vendor payments
                vendor_payments = VendorPaymentDetails.objects.filter(payment_date__range=[start_date, end_date]).exclude(payment_method='inventory')
                
                for payment in vendor_payments:
                    payment_item = {
                        'Date': payment.payment_date,
                        'Type': 'Payment',
                        'Vendor Name': payment.vendor.business_name,
                        'Payment Method': payment.payment_method,
                        'Amount': payment.payment_amount,
                        'Transaction Reference': payment.transaction_reference_id,
                    }
                    report_data.append(payment_item)
            
            # Convert report data to a pandas DataFrame
            report_data.sort(key=lambda x: x['Date'], reverse=True)
            df = pd.DataFrame(report_data)

            # Create the HttpResponse object with the appropriate Excel headers
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=expense_report_{report_type}_{start_date}_{end_date}.xlsx'

            # Save the DataFrame to the HttpResponse as an Excel file
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Expense Report')

            return response
        except Exception as e:
            log.trace.trace(traceback.format_exc())
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CustomerPaymentsReportView(APIView):
    def get(self, request):
        # Extract query parameters
        customer_id = request.GET.get('customer_id')
        payment_method = request.GET.get('payment_method')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        transaction_reference_id = request.GET.get('transaction_reference_id')
        cheque_number = request.GET.get('cheque_number')
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        # Build the base queryset
        queryset = CustomerPaymentDetails.objects.all()

        # Apply filters
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            queryset = queryset.filter(payment_date__lte=end_date)
        if transaction_reference_id:
            queryset = queryset.filter(transaction_reference_id=transaction_reference_id)
        if cheque_number:
            queryset = queryset.filter(cheque_number=cheque_number)
        queryset = queryset.order_by('-payment_date')
        # Pagination
        total_count = queryset.count()
        offset = (page - 1) * page_size
        queryset = queryset[offset:offset + page_size]

        # Prepare the response data
        results = []
        for payment in queryset:
            results.append({
                'customer_id': payment.customer.customer_id,
                'customer_name': payment.customer.business_name,  # Assuming Customer model has a `name` field
                'transaction_id': payment.transaction.id,
                'payment_method': payment.payment_method,
                'payment_amount': str(payment.payment_amount),  # Convert Decimal to string
                'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
                'transaction_reference_id': payment.transaction_reference_id,
                'bank_name': payment.bank_name,
                'cheque_number': payment.cheque_number,
                'is_invoice': payment.payment_method.lower() == 'cost of goods sold',
            })

        response_data = {
            'count': total_count,
            'next': self._get_next_page_url(request, page, page_size, total_count),
            'previous': self._get_previous_page_url(request, page, page_size),
            'results': results,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _get_next_page_url(self, request, page, page_size, total_count):
        if page * page_size >= total_count:
            return None
        return self._get_page_url(request, page + 1)

    def _get_previous_page_url(self, request, page, page_size):
        if page <= 1:
            return None
        return self._get_page_url(request, page - 1)

    def _get_page_url(self, request, page):
        url = request.build_absolute_uri()
        if 'page=' in url:
            url = url.split('page=')[0] + f'page={page}'
        else:
            url += f'&page={page}' if '?' in url else f'?page={page}'
        return url
    


class CustomerPaymentsExcelExportView(APIView):
    def get(self, request):
        # Extract query parameters
        customer_id = request.GET.get('customer_id')
        payment_method = request.GET.get('payment_method')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        transaction_reference_id = request.GET.get('transaction_reference_id')
        cheque_number = request.GET.get('cheque_number')

        # Build the base queryset
        queryset = CustomerPaymentDetails.objects.all()

        # Apply filters
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            queryset = queryset.filter(payment_date__lte=end_date)
        if transaction_reference_id:
            queryset = queryset.filter(transaction_reference_id=transaction_reference_id)
        if cheque_number:
            queryset = queryset.filter(cheque_number=cheque_number)

        # Convert queryset to a pandas DataFrame
        data = list(queryset.values(
            'customer__customer_id', 'customer__business_name', 'transaction__id', 'payment_method',
            'payment_amount', 'payment_date', 'transaction_reference_id',
            'bank_name', 'cheque_number'
        ))
        df = pd.DataFrame(data)

        # Rename columns for better readability
        df.rename(columns={
            'customer__id': 'Customer ID',
            'customer__name': 'Customer Name',
            'transaction__id': 'Transaction ID',
            'payment_method': 'Payment Method',
            'payment_amount': 'Payment Amount',
            'payment_date': 'Payment Date',
            'transaction_reference_id': 'Transaction Reference ID',
            'bank_name': 'Bank Name',
            'cheque_number': 'Cheque Number',
        }, inplace=True)

        # Add a column for "Is Invoice"
        df['Is Invoice'] = df['Payment Method'].str.lower() == 'cost of goods sold'

        # Create the HttpResponse object with the appropriate Excel headers
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=customer_payments_report.xlsx'

        # Save the DataFrame to the HttpResponse as an Excel file
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Customer Payments Report')

        return response
