from rest_framework import generics, exceptions
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Invoice, InvoiceItem, Product, Customer, Estimate, EstimateItem
from .serializers import CategorySerializer, ProductSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Category
from authentication.models import NewUser
import traceback
from django.conf import settings
import jwt
from xhtml2pdf import pisa
from io import BytesIO
from customers.models import Customer
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
import math

# Category Views

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
                "category": product.category.name if product.category else None,
                "price": str(product.price),
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


    def calculate_tiles(self, box_quantity=None, area_sqf=None, pallet_quantity=None, tile_quantity=None):
        if box_quantity:
            return box_quantity * 10  # 10 tiles per box
        elif area_sqf:
            return int(area_sqf / 23.33)  # Calculate tiles from sqf
        elif pallet_quantity:
            return pallet_quantity * 550  # 550 tiles per pallet
        elif tile_quantity:
            return tile_quantity  # Direct tile count
        return None
    
    def post(self, request):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        category_id = request.data.get("category_id")
        product_name = request.data.get("product_name")
        price = request.data.get("price")
        box_quantity = request.data.get("box_quantity")
        area_sqf = request.data.get("area_sqf")
        pallet_quantity = request.data.get("pallet_quantity")
        tile_quantity = request.data.get("tile_quantity")

        if not category_id or not product_name or price is None:
            return Response({"detail": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if category exists
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        # Calculate stock quantity based on provided input type
        stock_quantity = self.calculate_tiles(box_quantity, area_sqf, pallet_quantity, tile_quantity)
        
        if stock_quantity is None:
            return Response({"detail": "Provide either box_quantity, area_sqf, pallet_quantity, or tile_quantity."}, 
                            status=status.HTTP_400_BAD_REQUEST)

        if_exists = Product.objects.filter(product_name=product_name, is_active=True).all()
        if if_exists:
            return Response({"detail": "Product already present."}, status=status.HTTP_400_BAD_REQUEST)      


        # Create the Product instance
        product = Product.objects.create(
            category=category,
            product_name=product_name,
            price=price,
            stock_quantity=stock_quantity,
            created_by=user
        )

        return Response({
            "id": product.id,
            "product_name": product.product_name,
            "price": str(product.price),
            "stock_quantity": product.stock_quantity,
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


    def calculate_tiles(self, box_quantity=None, area_sqf=None, pallet_quantity=None, tile_quantity=None):
        if box_quantity:
            return box_quantity * 10  # 10 tiles per box
        elif area_sqf:
            return int(area_sqf / 23.33)  # Calculate tiles from sqf
        elif pallet_quantity:
            return pallet_quantity * 550  # 550 tiles per pallet
        elif tile_quantity:
            return tile_quantity  # Direct tile count
        return None
    

    def put(self, request, product_id):
        user = self.get_user_from_token(request)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        # Update fields if provided
        product_name = request.data.get("product_name")
        price = request.data.get("price")
        box_quantity = request.data.get("box_quantity")
        area_sqf = request.data.get("area_sqf")
        pallet_quantity = request.data.get("pallet_quantity")
        tile_quantity = request.data.get("tile_quantity")

        stock_quantity = self.calculate_tiles(box_quantity, area_sqf, pallet_quantity, tile_quantity)
        
        if stock_quantity is None:
            return Response({"detail": "Provide either box_quantity, area_sqf, pallet_quantity, or tile_quantity."}, 
                            status=status.HTTP_400_BAD_REQUEST)

        if_same_name = Product.objects.filter(product_name=product_name, is_active=True).exclude(id=product_id).all()
        if if_same_name:
            return Response({"detail": "Product name already present."}, status=status.HTTP_400_BAD_REQUEST)


        if product_name:
            product.product_name = product_name
        if price is not None:
            product.price = price
        if stock_quantity is not None:
            product.stock_quantity = stock_quantity

        product.updated_by = user
        product.save()

        return Response({
            "id": product.id,
            "product_name": product.product_name,
            "price": str(product.price),  # Convert Decimal to string for JSON compatibility
            "stock_quantity": product.stock_quantity,
            "updated_date": product.updated_date,
            "is_active": product.is_active,
        }, status=status.HTTP_200_OK)


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
            product = Product.objects.get(id=product_id, created_by=user)
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
            html_string = render_to_string("invoice.html", context)
            
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
