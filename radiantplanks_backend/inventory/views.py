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
from django.template.loader import render_to_string
import math
import uuid
import time
# Category Views

def generate_short_unique_filename(extension):
    # Shortened UUID (6 characters) + Unix timestamp for uniqueness
    unique_id = uuid.uuid4().hex[:6]  # Get the first 6 characters of UUID
    timestamp = str(int(time.time()))  # Unix timestamp as a string
    return f"{unique_id}_{timestamp}{extension}"


def add_inventory_value(stock_quantity, stock_price):
    pass


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
                "product_name": product.product_name,
                "category": product.category_id.name if product.category_id else None,
                "price": str(product.selling_price),
                "stock_quantity": product.stock_quantity,
                "created_date": product.created_date,
                "updated_date": product.updated_date,
                "is_active": product.is_active,
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
                total_amount = 0

                # Create temporary invoice
                invoice = Invoice.objects.create(
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
                invoice.total_amount = total_amount
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
                    "product": item.product,
                    "quantity": item.quantity,
                    "unit_type": "tiles",  # Adjust based on your logic
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

            # Render the HTML template
            html_string = render_to_string("invoices2.html", context)
            
            # Generate PDF from HTML using xhtml2pdf
            pdf_file = BytesIO()
            pisa_status = pisa.CreatePDF(BytesIO(html_string.encode("utf-8")), dest=pdf_file)

            if pisa_status.err:
                return Response({"detail": "Error creating PDF"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Email setup
            email = EmailMessage(
                subject=f"Invoice #{invoice.id}",
                body="Please find attached your invoice.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[invoice.customer.email],
            )
            email.attach(f"Invoice_{invoice.id}.pdf", pdf_file.getvalue(), "application/pdf")
            email.send()

            return Response({"message": "Invoice sent successfully"}, status=status.HTTP_200_OK)

        except Invoice.DoesNotExist:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(traceback.format_exc())
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
