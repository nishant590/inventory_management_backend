from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from .models import Customer, Address, Vendor, VendorAddress
from radiantplanks_backend.logging import log
import traceback 
import jwt
from django.conf import settings
from authentication.models import NewUser
from authentication.views import audit_log

class CustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        addresses_data = data.get('addresses', [])

        # Basic validation
        errors = {}
        required_fields = ['first_name', 'last_name', 'email', 'phone', 'addresses']
        for field in required_fields:
            if not data.get(field):
                errors[field] = f"{field} is required."

        # Validate email format
        try:
            validate_email(data['email'])
        except ValidationError:
            errors['email'] = "Invalid email format."

        # Validate phone length
        if 'phone' in data and len(data['phone']) < 10:
            errors['phone'] = "Phone number must be at least 10 characters long."

        # Validate addresses
        if not addresses_data:
            errors['addresses'] = "At least one address is required."
        else:
            for i, addr in enumerate(addresses_data):
                if 'address_type' not in addr or addr['address_type'] not in ['Billing', 'Shipping', 'Billing and Shipping']:
                    errors[f'addresses[{i}]'] = "Address type must be 'billing' or 'shipping' or 'Billing and Shipping'."
                if ('street_add_1' not in addr) or ('street_add_2' not in addr):
                    errors[f'addresses[{i}][street]'] = "Street is required."

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        # If all validations pass, create the customer and addresses
        try:
            with transaction.atomic():
                customer = Customer.objects.create(
                    first_name=data['first_name'],
                    middle_name=data.get('middle_name', ''),
                    last_name=data['last_name'],
                    business_name=data.get('business_name', f"{data['first_name']} {data['last_name']}"),
                    company=data.get('company', ''),
                    email=data['email'],
                    cc_email=data.get('cc_email', ''),
                    bcc_email=data.get('bcc_email', ''),
                    phone=data.get("phone",""),
                    mobile_number=data.get("mobile_number"),
                    created_by=request.user,
                    created_date=timezone.now(),
                    updated_by=request.user,
                    updated_date=timezone.now(),
                    is_active=True
                )

                # Save each address
                for addr_data in addresses_data:
                    Address.objects.create(
                        customer=customer,
                        address_type=addr_data['address_type'],
                        street_add_1=addr_data.get('street_add_1'),
                        street_add_2=addr_data.get('street_add_2'),
                        city=addr_data.get('city', ''),
                        state=addr_data.get('state', ''),
                        postal_code=addr_data.get('postal_code', ''),
                        country=addr_data.get('country', 'Unknown')
                    )
            audit_log_entry = audit_log(user=request.user,
                              action="Customer created", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Customer", 
                              record_id=customer.customer_id)
            log.audit.success(f"Customer created successfully | {customer.business_name} | {request.user} ")

            return Response({'message': 'Customer created successfully'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.trace.trace(f"Error : {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customers = Customer.objects.filter(is_active=True)
        customer_list = [
            {
                "customer_id": customer.customer_id,
                "first_name": customer.first_name,
                "middle_name": customer.middle_name,
                "last_name": customer.last_name,
                "business_name": customer.business_name,
                "company": customer.company,
                "email": customer.email,
                "phone": customer.phone,
                "mobile_number": customer.mobile_number,
                "is_active": customer.is_active,
                "addresses": list(customer.addresses.values()),
                "created_date": customer.created_date,
                "updated_date": customer.updated_date,
            }
            for customer in customers
        ]
        return Response({"customers": customer_list}, status=status.HTTP_200_OK)


class CustomerDetailView(APIView):
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
        try:
            customer = Customer.objects.get(customer_id=customer_id)
            customer_add = Address.objects.filter(customer_id=customer.customer_id).values(    
                "address_type",
                "street_add_1",
                "street_add_2",
                "city",
                "state",
                "postal_code",
                "country"
            )
            customer_details = {
                "customer_id": customer.customer_id,
                "first_name": customer.first_name,
                "middle_name": customer.middle_name,
                "last_name": customer.last_name,
                "business_name": customer.business_name,
                "company": customer.company,
                "email": customer.email,
                "cc_email": customer.cc_email,
                "bcc_email": customer.bcc_email,
                "phone": customer.phone,
                "mobile_number": customer.mobile_number,
                "addresses": list(customer_add)
            }
            return Response({"customer": customer_details}, status=status.HTTP_200_OK)

        except Exception as e:
            log.trace.trace(f"Error : {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerEditView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, customer_id):
        data = request.data
        addresses_data = data.get('addresses', [])

        # Fetch the customer
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

        # Update fields if provided
        customer.first_name = data.get("first_name", customer.first_name)
        customer.middle_name = data.get("middle_name", customer.middle_name)
        customer.last_name = data.get("last_name", customer.last_name)
        customer.business_name = data.get("business_name", customer.business_name)
        customer.company = data.get("company", customer.company)
        customer.email = data.get("email", customer.email)
        customer.cc_email = data.get("cc_email", customer.cc_email)
        customer.bcc_email = data.get("bcc_email", customer.bcc_email)
        customer.phone = data.get("phone", customer.phone)
        customer.mobile_number = data.get("mobile_number", customer.phone)
        customer.updated_by = request.user
        customer.updated_date = timezone.now()
        customer.save()

        # Update or add addresses
        if addresses_data:
            customer.addresses.all().delete()  # Delete existing addresses
            for addr_data in addresses_data:
                Address.objects.create(
                    customer=customer,
                    address_type=addr_data['address_type'],
                    street_add_1=addr_data['street_add_1'],
                    street_add_2=addr_data['street_add_2'],
                    city=addr_data.get('city', ''),
                    state=addr_data.get('state', ''),
                    postal_code=addr_data.get('postal_code', ''),
                    country=addr_data.get('country', 'Unknown')
                )
        audit_log_entry = audit_log(user=request.user,
                              action="Customer Edited", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Customer", 
                              record_id=customer.customer_id)
        log.audit.success(f"Customer updated successfully | {customer.business_name} | {request.user} ")
        return Response({"message": "Customer updated successfully"}, status=status.HTTP_200_OK)
    

class CustomerDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, customer_id):
        try:
            customer = Customer.objects.get(pk=customer_id)
            customer.is_active = False  # Set is_active to False instead of deleting
            customer.updated_by = request.user  # Optionally track who deactivated
            customer.updated_date = timezone.now()
            customer.save()
            log.audit.success(f"Customer deactivated successfully | {customer.business_name} | {request.user}")
            audit_log_entry = audit_log(user=request.user,
                              action="Customer Deleted", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Customer", 
                              record_id=customer.customer_id)
            return Response({"message": "Customer deactivated successfully"}, status=status.HTTP_200_OK)
        except Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        

class VendorCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        addresses_data = data.get('addresses', [])

        # Basic validation
        errors = {}
        required_fields = ['first_name', 'last_name', 'email', 'phone', 'addresses']
        for field in required_fields:
            if not data.get(field):
                errors[field] = f"{field} is required."

        # Validate email format
        try:
            validate_email(data['email'])
        except ValidationError:
            errors['email'] = "Invalid email format."

        # Validate phone length
        if 'phone' in data and len(data['phone']) < 10:
            errors['phone'] = "Phone number must be at least 10 characters long."

        # Validate addresses
        if not addresses_data:
            errors['addresses'] = "At least one address is required."
        else:
            for i, addr in enumerate(addresses_data):
                if 'address_type' not in addr or addr['address_type'] not in ['Billing', 'Shipping', 'Billing and Shipping']:
                    errors[f'addresses[{i}]'] = "Address type must be 'Billing' or 'Shipping' or 'Billing and Shipping'."
                if 'street_add_1' not in addr or 'street_add_2' not in addr:
                    errors[f'addresses[{i}][street]'] = "Street is required."

        if errors:
            log.app.trace("Validation error: {}".format(errors))
            log.trace.trace(f"Validation errors : {errors}")
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        # If all validations pass, create the customer and addresses
        try:
            with transaction.atomic():
                vendor = Vendor.objects.create(
                    first_name=data['first_name'],
                    middle_name=data.get('middle_name', ''),
                    last_name=data['last_name'],
                    business_name=data.get('business_name', f"{data['first_name']} {data['last_name']}"),
                    company=data.get('company', ''),
                    email=data['email'],
                    cc_email=data.get('cc_email', ''),
                    bcc_email=data.get('bcc_email', ''),
                    phone=data['phone'],
                    mobile_number=data['mobile_number'],
                    created_by=request.user,
                    created_date=timezone.now(),
                    updated_by=request.user,
                    updated_date=timezone.now(),
                    is_active=True
                )

                # Save each address
                for addr_data in addresses_data:
                    VendorAddress.objects.create(
                        vendor=vendor,
                        address_type=addr_data['address_type'],
                        street_add_1=addr_data['street_add_1'],
                        street_add_2=addr_data['street_add_2'],
                        city=addr_data.get('city', ''),
                        state=addr_data.get('state', ''),
                        postal_code=addr_data.get('postal_code', ''),
                        country=addr_data.get('country', 'Unknown')
                    )
            audit_log_entry = audit_log(user=request.user,
                              action="Vendor Created", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Vendor", 
                              record_id=vendor.vendor_id)
            log.audit.success(f"Vendor created successfully | {vendor.business_name} | {request.user} ")
            return Response({'message': 'Vendor created successfully'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.app.error(f"Error in vendor creation {str(e)}")
            log.trace.trace(f"Error in vendor creation {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VendorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendors = Vendor.objects.filter(is_active=True)
        vendor_list = [
            {
                "vendor_id": vendor.vendor_id,
                "first_name": vendor.first_name,
                "middle_name": vendor.middle_name,
                "last_name": vendor.last_name,
                "business_name": vendor.business_name,
                "company": vendor.company,
                "email": vendor.email,
                "phone": vendor.phone,
                "mobile_number": vendor.mobile_number,
                "is_active": vendor.is_active,
                "addresses": list(vendor.vendor_addresses.values()),
                "created_date": vendor.created_date,
                "updated_date": vendor.updated_date,
            }
            for vendor in vendors
        ]
        return Response({"vendors": vendor_list}, status=status.HTTP_200_OK)


class VendorEditView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, vendor_id):
        data = request.data
        addresses_data = data.get('addresses', [])

        # Fetch the vendor
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"error": "vendor not found"}, status=status.HTTP_404_NOT_FOUND)
        
        vendor_email = vendor.email
        duplicate_email = Vendor.objects.filter(email=vendor_email).exclude(vendor_id=vendor_id).exists()
        if duplicate_email:
            log.app.trace("Email already exists for another vendor")
            return Response({"error": "Email already exists for another vendor."}, status=status.HTTP_400_BAD_REQUEST)

        # Update fields if provided
        vendor.first_name = data.get("first_name", vendor.first_name)
        vendor.middle_name = data.get("middle_name", vendor.middle_name)
        vendor.last_name = data.get("last_name", vendor.last_name)
        vendor.business_name = data.get("business_name", vendor.business_name)
        vendor.company = data.get("company", vendor.company)
        vendor.email = data.get("email", vendor.email)
        vendor.cc_email = data.get("cc_email", vendor.cc_email)
        vendor.bcc_email = data.get("bcc_email", vendor.bcc_email)
        vendor.phone = data.get("phone", vendor.phone)
        vendor.mobile_number = data.get("mobile_number", vendor.phone)
        vendor.updated_by = request.user
        vendor.updated_date = timezone.now()
        vendor.save()

        # Update or add addresses
        if addresses_data:
            vendor.vendor_addresses.all().delete()  # Delete existing addresses
            for addr_data in addresses_data:
                VendorAddress.objects.create(
                    vendor=vendor,
                    address_type=addr_data['address_type'],
                    street_add_1=addr_data['street_add_1'],
                    street_add_2=addr_data['street_add_2'],
                    city=addr_data.get('city', ''),
                    state=addr_data.get('state', ''),
                    postal_code=addr_data.get('postal_code', ''),
                    country=addr_data.get('country', 'Unknown')
                )
        audit_log_entry = audit_log(user=request.user,
                              action="Vendor Edited", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Vendor", 
                              record_id=vendor.vendor_id)
        log.audit.success(f"Vendor updated successfully | {vendor.business_name} | {request.user} ")
        return Response({"message": "Vendor updated successfully"}, status=status.HTTP_200_OK)
    

class VendorDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
            vendor.is_active = False  # Set is_active to False instead of deleting
            vendor.updated_by = request.user  # Optionally track who deactivated
            vendor.updated_date = timezone.now()
            vendor.save()
            log.audit.success(f"Vendor deactivated successfully | {vendor.business_name} | {request.user}")
            audit_log_entry = audit_log(user=request.user,
                              action="Vendor Deleted", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="Vendor", 
                              record_id=vendor.vendor_id)
            return Response({"message": "vendor deactivated successfully"}, status=status.HTTP_200_OK)
        except Vendor.DoesNotExist:
            log.trace.trace(f"Vendor deactivated failed | {traceback.format_exc()}") 
            return Response({"error": "vendor not found"}, status=status.HTTP_404_NOT_FOUND)
        

class VendorRetriveView(APIView):
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
        try:
            vendor = Vendor.objects.get(vendor_id=vendor_id)
            vendor_add = VendorAddress.objects.filter(vendor_id=vendor.vendor_id).values(    
                "address_type",
                "street_add_1",
                "street_add_2",
                "city",
                "state",
                "postal_code",
                "country"
            )
            vendor_details = {
                "vendor_id": vendor.vendor_id,
                "first_name": vendor.first_name,
                "middle_name": vendor.middle_name,
                "last_name": vendor.last_name,
                "business_name": vendor.business_name,
                "company": vendor.company,
                "email": vendor.email,
                "cc_email": vendor.cc_email,
                "bcc_email": vendor.bcc_email,
                "phone": vendor.phone,
                "mobile_number": vendor.mobile_number,
                "addresses": list(vendor_add)
            }
            return Response({"vendor": vendor_details}, status=status.HTTP_200_OK)

        except Exception as e:
            log.trace.trace(f"Error : {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

