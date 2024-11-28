from rest_framework import generics, exceptions
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Invoice, InvoiceItem, Product, Customer, Estimate, EstimateItem, ProductAccountMapping
from .serializers import CategorySerializer, ProductSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Category
from authentication.models import NewUser
from accounts.models import Account
import posixpath
from django.core.files.storage import FileSystemStorage
import traceback
from django.conf import settings
import os
import jwt
from xhtml2pdf import pisa
from io import BytesIO
from customers.models import Customer
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
                reference_number=f"INV-{date.today().strftime('%Y%m%d')}-{inventory_account.id}",
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
            owner_equity_account = Account.objects.filter(account_type='owner_equity').first()
            if not owner_equity_account:
                raise ValueError("Owner equity account does not exist.")
            
            TransactionLine.objects.create(
                transaction=transaction,
                account=owner_equity_account,
                description=f"Fund allocation for inventory addition of {product_name}",
                debit_amount=0,
                credit_amount=total_cost,
            )

            # Update inventory account balance
            inventory_account.balance += total_cost
            owner_equity_account -= total_cost
            inventory_account.save()
            owner_equity_account.save()
            return True
    except Exception as e:
        return False
    
def create_invoice_transaction(customer, products, total_amount, user):
    """
    Adjust inventory and create account receivable for the invoice.
    """
    inventory_account = Account.objects.get(code='INV-001')  # Inventory account
    receivable_account = Account.objects.get(code='AR-001')  # Accounts Receivable account
    
    # Create a new transaction
    transaction = Transaction.objects.create(
        reference_number=f"INV-{uuid.uuid4().hex[:6].upper()}",
        transaction_type='income',
        date=datetime.now(),
        description=f"Invoice for customer {customer.name}",
        created_by=user  # Assuming you have request context
    )

    # Adjust inventory and add account receivable
    for product in products:
        product_name = product["name"]
        quantity = product["quantity"]
        unit_cost = product["unit_cost"]
        total_cost = quantity * unit_cost
        
        # Deduct inventory (credit inventory account)
        TransactionLine.objects.create(
            transaction=transaction,
            account=inventory_account,
            description=f"Inventory adjustment for {product_name}",
            debit_amount=0,
            credit_amount=total_cost,
        )

    # Add receivable (debit receivables account)
    TransactionLine.objects.create(
        transaction=transaction,
        account=receivable_account,
        description=f"Account receivable for invoice to {customer.name}",
        debit_amount=total_amount,
        credit_amount=0,
    )

    # Update receivable tracking
    receivable, created = ReceivableTracking.objects.get_or_create(customer=customer)
    receivable.receivable_amount += total_amount
    receivable.save()


def process_payment(customer, payment_amount, user):
    """
    Process payment for a customer and update accounts.
    """
    receivable_account = Account.objects.get(code='AR-001')  # Accounts Receivable account
    bank_account = Account.objects.get(code='BANK-001')  # Bank account
    
    # Create a new transaction
    transaction = Transaction.objects.create(
        reference_number=f"PAY-{uuid.uuid4().hex[:6].upper()}",
        transaction_type='income',
        date=datetime.now(),
        description=f"Payment received from {customer.name}",
        created_by=user  # Assuming you have request context
    )

    # Debit bank account (increase bank balance)
    TransactionLine.objects.create(
        transaction=transaction,
        account=bank_account,
        description=f"Payment received from {customer.name}",
        debit_amount=payment_amount,
        credit_amount=0,
    )

    # Credit receivables account (decrease receivables)
    TransactionLine.objects.create(
        transaction=transaction,
        account=receivable_account,
        description=f"Clear receivable for {customer.name}",
        debit_amount=0,
        credit_amount=payment_amount,
    )

    # Update receivable tracking
    receivable = ReceivableTracking.objects.get(customer=customer)
    receivable.receivable_amount -= payment_amount
    receivable.save()


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
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)
        # Check if the user already has a category


        # Extract and validate data from request
        category_name = request.data.get("name")
        if not category_name:
            return Response({"detail": "Category name is required."}, status=status.HTTP_400_BAD_REQUEST)

        if_exists = Category.objects.filter(name=category_name).all()
        if if_exists:
            return Response({"detail": "Category already present."}, status=status.HTTP_400_BAD_REQUEST)


        # Create the Category instance
        category = Category.objects.create(name=category_name, created_by=user)

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
                "product_name": product.product_name,
                "category": product.category_id.name if product.category_id else None,
                "sku": product.sku,
                "product_length": product.tile_length,
                "product_width": product.tile_width,
                "price": str(product.selling_price),
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
        area = length * width * no_of_tiles
        area = round(area, 2)
        return area

    def calculate_stock_quantity(self, quantity=None, unit=None):
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
        sell_description = data.get("sell_description")
        barcode = data.get("barcode")
        quantity = data.get("quantity")
        unit = data.get("unit")
        reorder_level = data.get("reorder_level")
        as_on_date = data.get("as_on_date")
        batch_lot_number = data.get("batch_lot_number")
        tile_length = data.get("tile_length")
        tile_width = data.get("tile_width")
        no_of_tiles = data.get("no_of_tiles")
        purchase_price = data.get("purchase_price")
        selling_price = data.get("selling_price")
        specifications = data.get("specifications")  # Expect JSON
        tags = data.get("tags")  # Comma-separated string
        inventory_account = data.get("inventory_account")
        income_account = data.get("income_account")


        if not product_name or not selling_price or not product_type:
            return Response({"detail": "Product type, name, and selling_price are required."}, status=status.HTTP_400_BAD_REQUEST)

        if product_image:
            extension = os.path.splitext(product_image.name)[1]  # Get the file extension
            short_unique_filename = generate_short_unique_filename(extension)
            fs = FileSystemStorage(location=os.path.join(settings.STATIC_ROOT, 'product_images'))
            logo_path = fs.save(short_unique_filename, product_image)
            logo_url = posixpath.join('static/product_images', logo_path)
        else:
            logo_url = ""

        if product_type == "product" and not category_id:
            return Response({"detail": "Category is required for products."}, status=status.HTTP_400_BAD_REQUEST)

        if product_type == "product" and not tile_length or not tile_width or not no_of_tiles:
            return Response({"detail": "Tile length and width and number of tiles are required to calculate the area."}, status=status.HTTP_400_BAD_REQUEST)

        if product_type == "product" and not inventory_account or not income_account:
            return Response({"detail": "Inventory and Income account are required."}, status=status.HTTP_400_BAD_REQUEST)
        # Validate category and subcategory
        category = None
        subcategory = None
        if category_id:
            try:
                category_id = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        # Calculate stock quantity for products
        tile_area = self.calculate_area(float(tile_length), float(tile_width), int(no_of_tiles))

        stock_quantity = None
        if product_type == "product":
            stock_quantity = self.calculate_stock_quantity(quantity, unit)
            if stock_quantity is None:
                return Response({"detail": "Provide either box_quantity or pallet_quantity."},
                                status=status.HTTP_400_BAD_REQUEST)
            

        # Calculate tile area

        # Prevent duplicate product names
        if Product.objects.filter(product_name=product_name, is_active=True).exists():
            return Response({"detail": "Product with this name already exists."}, status=status.HTTP_400_BAD_REQUEST)
        
        if Product.objects.filter(sku=sku, is_active=True).exists():
            return Response({"detail": "Product with this SKU already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Create product/service
        product = Product.objects.create(
            product_name = product_name, 
            sku = sku, 
            barcode = barcode, 
            category_id = category_id, 
            purchase_description = purchase_description, 
            sell_description = sell_description, 
            stock_quantity = stock_quantity, 
            reorder_level = reorder_level, 
            batch_lot_number = batch_lot_number, 
            tile_length = tile_length, 
            tile_width = tile_width, 
            as_on_date = as_on_date,
            no_of_tiles = no_of_tiles,
            tile_area = tile_area,
            purchase_price = purchase_price, 
            selling_price = selling_price, 
            specifications = specifications, 
            tags = tags, 
            images = logo_url, 
            created_by = user, 
        )

        if product_type == "product":
            income_account = Account.objects.get(id=income_account, is_active=True)
            inventory_account = Account.objects.get(id=inventory_account, is_active=True)
            accountmapping = ProductAccountMapping.objects.create(
                product = product,
                inventory_account = inventory_account,
                income_account = income_account
            )
            # inventory_add = add_inventory_transaction(product_name = product_name, 
            #                                           quantity = stock_quantity, 
            #                                           unit_cost = purchase_price, 
            #                                           inventory_account = inventory_account, 
            #                                           created_by = user)

        return Response({
            "id": product.id,
            "product_name": product.product_name,
            "product_type": product.product_type,
            "price": str(product.selling_price),
            "stock_quantity": product.stock_quantity,
            "tile_area": product.tile_area,
            "created_date": product.created_date,
            "is_active": product.is_active,
        }, status=status.HTTP_201_CREATED)


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
        area = length * width * no_of_tiles
        area = round(area, 2)
        return area

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
        unit = data.get("unit")
        tile_area = product.tile_area
        if unit:
            tile_area = self.calculate_area(float(tile_length), float(tile_width), int(no_of_tiles))
        
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
        product.sell_description = data.get("sell_description", product.sell_description)
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
        product.selling_price = data.get("selling_price", product.selling_price)
        product.specifications = data.get("specifications", product.specifications)
        product.tags = data.get("tags", product.tags)

        if product_image:
            extension = os.path.splitext(product_image.name)[1]  # Get the file extension
            short_unique_filename = generate_short_unique_filename(extension)
            fs = FileSystemStorage(location=os.path.join(settings.STATIC_ROOT, 'product_images'))
            logo_path = fs.save(short_unique_filename, product_image)
            logo_url = posixpath.join('static/product_images', logo_path)
            product.images = logo_url

        if product.product_type == 'product_type':
            account_mapping = ProductAccountMapping.objects.get(product=product.id)
            income_account = data.get("income_account")
            inventory_account = data.get("inventory_account")
            income_account = Account.objects.get(id=income_account, is_active=True)
            inventory_account = Account.objects.get(id=inventory_account, is_active=True)
            accountmapping = ProductAccountMapping.objects.create(
                product = product,
                inventory_account = inventory_account,
                income_account = income_account
            )
            account_mapping.save()

        # Save updated product
        product.updated_by = user
        product.save()

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
            "sku": product.sku,
            "barcode": product.barcode,
            "category_id": product.category_id.id if product.category_id else None,
            "sell_description": product.sell_description,
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
            "selling_price": product.selling_price,
            "specifications": product.specifications,
            "tags": product.tags,
            "images": product.images,
            "created_date": product.created_date,
            "updated_date": product.updated_date,
            "is_active": product.is_active,
            "income_account":product_accounts.income_account.name,
            "income_account_id":product_accounts.income_account.id,
            "inventory_account": product_accounts.inventory_account.name,
            "inventory_account_id": product_accounts.inventory_account.id,
        }

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

        return Response({"detail": "Product deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class CreateInvoiceView(APIView):
    def post(self, request):
        data = request.data
        customer_id = data.get("customer_id")
        items = data.get("items", [])  # List of { product_id, quantity, unit_price, unit_type }

        if not customer_id or not items:
            return Response({"detail": "Customer ID and items are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                customer = Customer.objects.get(customer_id=customer_id)
                data = request.data
                customer_email = data.get("customer_email")
                customer_email_cc = data.get("customer_email_cc")
                customer_email_bcc = data.get("customer_email_bcc")
                billing_address = data.get("billing_address")
                shipping_address = data.get("shipping_address")
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
                is_paid = data.get("is_paid")
                if isinstance(is_paid, str):
                    is_paid = is_paid.lower() in ['true', '1', 'yes', 'y']
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
                    billing_address = billing_address,
                    shipping_address = shipping_address,
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
                    is_paid = is_paid,
                    total_amount=total_amount,
                    attachments=attachments_url,
                    created_date=timezone.now(),
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
                        quantity_in_tiles = quantity * 55
                    elif unit_type == 'box':
                        quantity_in_tiles = quantity
                    elif unit_type == 'sqf':
                        quantity_in_tiles = math.ceil(float(quantity) / float(product.tile_area))  # Calculate approx tiles for sqf
                    else:
                        quantity_in_tiles = quantity  # Assume 'box' is the base unit

                    # Check if enough stock is available
                    if product.stock_quantity < quantity_in_tiles:
                        return Response({"detail": f"Insufficient stock for product {product.product_name}."}, status=status.HTTP_400_BAD_REQUEST)

                    # Deduct stock and calculate the line total
                    product.stock_quantity -= quantity_in_tiles
                    product.save()
                    line_total = unit_price * quantity_in_tiles

                    # Create invoice item
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=product,
                        quantity=quantity_in_tiles,  # Store as selected unit (pallets, boxes, sqf, etc.)
                        unit_price=unit_price,
                        created_by=request.user
                    )
                    
                    # Accumulate total amount
                    total_amount += line_total

                # Update the invoice's total amount after processing all items
                # invoice.total_amount = total_amount
                invoice.save()

            return Response({"invoice_id": invoice.id, "message": "Invoice created successfully."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class SendInvoiceView(APIView):
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




