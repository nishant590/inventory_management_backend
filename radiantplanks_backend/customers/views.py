from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from .models import Customer, Address, Vendor, VendorAddress, State, City
from radiantplanks_backend.logging import log
import traceback 
import jwt
from django.conf import settings
from authentication.models import NewUser
from authentication.views import audit_log
from rest_framework.parsers import MultiPartParser
import pandas as pd
from accounts.models import VendorPaymentDetails

class CustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        addresses_data = data.get('addresses', [])

        # Basic validation
        errors = {}
        required_fields = ['first_name', 'last_name', 'business_name', 'email', 'phone', 'addresses']
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
        tax_exempt = data.get('tax_exempt', False)
        if isinstance(tax_exempt, str):
            tax_exempt = tax_exempt.lower() == 'true'

        if not addresses_data:
            errors['addresses'] = "At least one address is required."
        else:
            for i, addr in enumerate(addresses_data):
                if 'address_type' not in addr or addr['address_type'] not in ['Billing', 'Shipping', 'Billing and Shipping']:
                    errors[f'addresses[{i}]'] = "Address type must be 'billing' or 'shipping' or 'Billing and Shipping'."
                if 'street_add_1' not in addr :
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
                    company=data.get('company', None),
                    email=data['email'],
                    tax_exempt=tax_exempt,
                    cc_email=data.get('cc_email', None),
                    bcc_email=data.get('bcc_email', None),
                    phone=data.get("phone",None),
                    mobile_number=data.get("mobile_number"),
                    sales_tax_number=data.get("sales_tax_number",None),
                    ein_number=data.get("ein_number",None),
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
                        street_add_2=addr_data.get('street_add_2', None),
                        city=addr_data.get('city', None),
                        state=addr_data.get('state', None),
                        postal_code=addr_data.get('postal_code', None),
                        country=addr_data.get('country', None)
                    )
            audit_log_entry = audit_log(user=request.user,
                              action="Customer created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Customer", 
                              record_id=customer.customer_id)
            log.audit.success(f"Customer created successfully | {customer.business_name} | {request.user} ")

            return Response({'message': 'Customer created successfully'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            log.trace.trace(f"Error : {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkCustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine file type (CSV or Excel)
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                return Response({'error': 'Unsupported file format. Use CSV or Excel.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Error reading file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Expected columns
        required_columns = ['first_name', 'last_name', 'email', 'phone', 'address_type', 'street_add_1', 'street_add_2', 'city', 'state', 'postal_code', 'country', 'tax_exempt']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return Response({'error': f'Missing required columns: {missing_columns}'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate data using pandas
        errors = []
        df['row_index'] = df.index + 1  # Track row index for error reporting

        # Validate required fields
        missing_data = df[required_columns].isnull()
        for col in required_columns:
            if missing_data[col].any():
                errors.extend(
                    [{'row': row_index, 'errors': {col: f'{col} is required.'}} for row_index in df[missing_data[col]]['row_index']]
                )

        # Validate email format
        def validate_email_pandas(email):
            try:
                validate_email(email)
                return None
            except ValidationError:
                return 'Invalid email format.'

        df['email_error'] = df['email'].apply(validate_email_pandas)
        errors.extend(
            [{'row': row.row_index, 'errors': {'email': row.email_error}} for row in df[df['email_error'].notnull()].itertuples()]
        )

        # Validate phone number length
        df['phone_error'] = df['phone'].apply(lambda x: 'Phone number must be at least 10 characters long.' if len(str(x)) < 10 else None)
        errors.extend(
            [{'row': row.row_index, 'errors': {'phone': row.phone_error}} for row in df[df['phone_error'].notnull()].itertuples()]
        )

        # Validate address type
        valid_address_types = ['Billing', 'Shipping', 'Billing and Shipping']
        df['address_type_error'] = df['address_type'].apply(lambda x: "Address type must be 'Billing', 'Shipping', or 'Billing and Shipping'." if x not in valid_address_types else None)
        errors.extend(
            [{'row': row.row_index, 'errors': {'address_type': row.address_type_error}} for row in df[df['address_type_error'].notnull()].itertuples()]
        )

        # Filter valid rows
        invalid_rows = df[df[['email_error', 'phone_error', 'address_type_error']].notnull().any(axis=1)]
        valid_rows = df[~df.index.isin(invalid_rows.index)]
        df[['bcc_email', 'cc_email']].replace("nan", "") 

        successful_creates = 0

        df['tax_exempt'] = df['tax_exempt'].apply(lambda x: x.lower() == 'true')

        try:
            with transaction.atomic():
                # Bulk create customers and addresses
                customers_to_create = []
                addresses_to_create = []

                for row in valid_rows.itertuples():
                    customer = Customer(
                        first_name=row.first_name,
                        middle_name=row.middle_name if 'middle_name' in valid_rows.columns else None,
                        last_name=row.last_name,
                        business_name=row.business_name if 'business_name' in valid_rows.columns else f"{row.first_name} {row.last_name}",
                        company=row.company if 'company' in valid_rows.columns else None,
                        email=row.email,
                        cc_email=row.cc_email if 'cc_email' in valid_rows.columns else None,
                        bcc_email=row.bcc_email if 'bcc_email' in valid_rows.columns else None,
                        phone=row.phone,
                        tax_exempt=row.tax_exempt,
                        mobile_number=row.mobile_number if 'mobile_number' in valid_rows.columns else None,
                        sales_tax_number=row.sales_tax_number if 'sales_tax_number' in valid_rows.columns else None,
                        ein_number=row.ein_number if 'ein_number' in valid_rows.columns else None,
                        created_by=request.user,
                        created_date=timezone.now(),
                        updated_by=request.user,
                        updated_date=timezone.now(),
                        is_active=True
                    )
                    customers_to_create.append(customer)

                Customer.objects.bulk_create(customers_to_create)

                for customer, row in zip(customers_to_create, valid_rows.itertuples()):
                    address = Address(
                        customer=customer,
                        address_type=row.address_type,
                        street_add_1=row.street_add_1,
                        street_add_2=row.street_add_2 if 'street_add_2' in valid_rows.columns else None,
                        city=row.city if 'city' in valid_rows.columns else None,
                        state=row.state if 'state' in valid_rows.columns else None,
                        postal_code=row.postal_code if 'postal_code' in valid_rows.columns else None,
                        country=row.country if 'country' in valid_rows.columns else None,
                    )
                    addresses_to_create.append(address)

                Address.objects.bulk_create(addresses_to_create)

                successful_creates = len(customers_to_create)

            audit_log(user=request.user, action="Bulk customer import", ip_add=request.META.get('HTTP_X_FORWARDED_FOR'))

            return Response({
                'message': 'Bulk customer import completed.',
                'successful_creates': successful_creates,
                'errors': errors
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            traceback_msg = traceback.format_exc()
            log.trace.trace(f"Error during bulk import: {traceback_msg}")
            return Response({'error': f'Error during bulk import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customers = Customer.objects.filter(is_active=True).order_by('business_name')
        customer_list = [
            {
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
                "tax_exempt": customer.tax_exempt,
                "mobile_number": customer.mobile_number,
                "sales_tax_number": customer.sales_tax_number,
                "ein_number": customer.ein_number,
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
                "tax_exempt": customer.tax_exempt,
                "cc_email": customer.cc_email,
                "bcc_email": customer.bcc_email,
                "phone": customer.phone,
                "mobile_number": customer.mobile_number,
                "sales_tax_number": customer.sales_tax_number,
                "ein_number": customer.ein_number,
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
        tax_exempt = data.get('tax_exempt', False)
        if isinstance(tax_exempt, str):
            tax_exempt = tax_exempt.lower() == 'true'
        # Update fields if provided
        customer.first_name = data.get("first_name", customer.first_name)
        customer.middle_name = data.get("middle_name", customer.middle_name)
        customer.last_name = data.get("last_name", customer.last_name)
        customer.business_name = data.get("business_name", customer.business_name)
        customer.company = data.get("company", customer.company)
        customer.email = data.get("email", customer.email)
        customer.cc_email = data.get("cc_email", customer.cc_email)
        customer.bcc_email = data.get("bcc_email", customer.bcc_email)
        customer.sales_tax_number = data.get("sales_tax_number", customer.sales_tax_number)
        customer.ein_number = data.get("ein_number", customer.ein_number)
        customer.phone = data.get("phone", customer.phone)
        customer.tax_exempt = tax_exempt
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
                    street_add_2=addr_data.get('street_add_2', None),
                    city=addr_data.get('city', None),
                    state=addr_data.get('state', None),
                    postal_code=addr_data.get('postal_code', None),
                    country=addr_data.get('country', None)
                )
        audit_log_entry = audit_log(user=request.user,
                              action="Customer Edited", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
                if 'street_add_1' not in addr:
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
                    is_contractor=data.get('is_contractor', False),
                    sales_tax_number=data.get('sales_tax_number', None),
                    ein_number=data.get('ein_number', None),
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
                        street_add_2=addr_data('street_add_2', None),
                        city=addr_data.get('city', None),
                        state=addr_data.get('state', None),
                        postal_code=addr_data.get('postal_code', None),
                        country=addr_data.get('country', None)
                    )
            audit_log_entry = audit_log(user=request.user,
                              action="Vendor Created", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
        vendors = Vendor.objects.filter(is_active=True).order_by('business_name')
        vendor_list = [
            {
                "vendor_id": vendor.vendor_id,
                "first_name": vendor.first_name,
                "middle_name": vendor.middle_name,
                "last_name": vendor.last_name,
                "business_name": vendor.business_name,
                "company": vendor.company,
                "is_contractor": vendor.is_contractor,
                "email": vendor.email,
                "cc_email": vendor.cc_email,
                "bcc_email": vendor.bcc_email,
                "phone": vendor.phone,
                "mobile_number": vendor.mobile_number,
                "sales_tax_number": vendor.sales_tax_number,
                "ein_number": vendor.ein_number,
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
        vendor.mobile_number = data.get("mobile_number", vendor.mobile_number)
        vendor.sales_tax_number = data.get("sales_tax_number", vendor.sales_tax_number)
        vendor.ein_number = data.get("ein_number", vendor.ein_number)
        vendor.is_contractor = data.get("is_contractor", vendor.is_contractor)
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
                    street_add_2=addr_data('street_add_2', None),
                    city=addr_data.get('city', None),
                    state=addr_data.get('state', None),
                    postal_code=addr_data.get('postal_code', None),
                    country=addr_data.get('country', None)
                )
        audit_log_entry = audit_log(user=request.user,
                              action="Vendor Edited", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
                "sales_tax_number": vendor.sales_tax_number,
                "ein_number": vendor.ein_number,
                "is_contractor": vendor.is_contractor,
                "addresses": list(vendor_add)
            }
            return Response({"vendor": vendor_details}, status=status.HTTP_200_OK)

        except Exception as e:
            log.trace.trace(f"Error : {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkVendorCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Determine file type (CSV or Excel)
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file)
            else:
                return Response({'error': 'Unsupported file format. Use CSV or Excel.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Error reading file: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Expected columns
        required_columns = ['first_name', 'last_name', 'email', 'phone', 'address_type', 'street_add_1', 'street_add_2', 'city', 'state', 'postal_code', 'country']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return Response({'error': f'Missing required columns: {missing_columns}'}, status=status.HTTP_400_BAD_REQUEST)

        # Validation logic (same as `BulkCustomerCreateView`)

        # Filter valid rows
        errors = []
        df['row_index'] = df.index + 1  # Track row index for error reporting

        # Validate required fields
        missing_data = df[required_columns].isnull()
        for col in required_columns:
            if missing_data[col].any():
                errors.extend(
                    [{'row': row_index, 'errors': {col: f'{col} is required.'}} for row_index in df[missing_data[col]]['row_index']]
                )

        # Validate email format
        def validate_email_pandas(email):
            try:
                validate_email(email)
                return None
            except ValidationError:
                return 'Invalid email format.'

        df['email_error'] = df['email'].apply(validate_email_pandas)
        errors.extend(
            [{'row': row.row_index, 'errors': {'email': row.email_error}} for row in df[df['email_error'].notnull()].itertuples()]
        )

        # Validate phone number length
        df['phone_error'] = df['phone'].apply(lambda x: 'Phone number must be at least 10 characters long.' if len(str(x)) < 10 else None)
        errors.extend(
            [{'row': row.row_index, 'errors': {'phone': row.phone_error}} for row in df[df['phone_error'].notnull()].itertuples()]
        )

        # Validate address type
        valid_address_types = ['Billing', 'Shipping', 'Billing and Shipping']
        df['address_type_error'] = df['address_type'].apply(lambda x: "Address type must be 'Billing', 'Shipping', or 'Billing and Shipping'." if x not in valid_address_types else None)
        errors.extend(
            [{'row': row.row_index, 'errors': {'address_type': row.address_type_error}} for row in df[df['address_type_error'].notnull()].itertuples()]
        )

        # Filter valid rows
        invalid_rows = df[df[['email_error', 'phone_error', 'address_type_error']].notnull().any(axis=1)]
        valid_rows = df[~df.index.isin(invalid_rows.index)]

        successful_creates = 0

        try:
            with transaction.atomic():
                # Bulk create vendors and vendor addresses
                vendors_to_create = []
                addresses_to_create = []

                for row in valid_rows.itertuples():
                    vendor = Vendor(
                        first_name=row.first_name,
                        middle_name=row.middle_name if 'middle_name' in valid_rows.columns else '',
                        last_name=row.last_name,
                        business_name=row.business_name if 'business_name' in valid_rows.columns else f"{row.first_name} {row.last_name}",
                        company=row.company if 'company' in valid_rows.columns else '',
                        email=row.email,
                        cc_email=row.cc_email if 'cc_email' in valid_rows.columns else '',
                        bcc_email=row.bcc_email if 'bcc_email' in valid_rows.columns else '',
                        phone=row.phone,
                        mobile_number=row.mobile_number if 'mobile_number' in valid_rows.columns else '',
                        sales_tax_number=row.sales_tax_number if 'sales_tax_number' in valid_rows.columns else '',
                        ein_number=row.ein_number if 'ein_number' in valid_rows.columns else '',
                        created_by=request.user,
                        created_date=timezone.now(),
                        updated_by=request.user,
                        updated_date=timezone.now(),
                        is_active=True
                    )
                    vendors_to_create.append(vendor)

                Vendor.objects.bulk_create(vendors_to_create)

                for vendor, row in zip(vendors_to_create, valid_rows.itertuples()):
                    address = VendorAddress(
                        vendor=vendor,
                        address_type=row.address_type,
                        street_add_1=row.street_add_1,
                        street_add_2=row.street_add_2 if 'street_add_2' in valid_rows.columns else None,
                        city=row.city if 'city' in valid_rows.columns else None,
                        state=row.state if 'state' in valid_rows.columns else None,
                        postal_code=row.postal_code if 'postal_code' in valid_rows.columns else None,
                        country=row.country if 'country' in valid_rows.columns else None
                    )
                    addresses_to_create.append(address)

                VendorAddress.objects.bulk_create(addresses_to_create)

                successful_creates = len(vendors_to_create)

            audit_log(user=request.user, action="Bulk vendor import", ip_add=request.META.get('HTTP_X_FORWARDED_FOR'))

            return Response({
                'message': 'Bulk vendor import completed.',
                'successful_creates': successful_creates,
                'errors': errors
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            traceback_msg = traceback.format_exc()
            log.trace.trace(f"Error during bulk import: {traceback_msg}")
            return Response({'error': f'Error during bulk import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class StateAndCityView(APIView):
    def get(self, request):
        # Get query parameters
        state_name = request.query_params.get('state')
        city_name = request.query_params.get('city')

        # If both state and city are provided, find specific city
        if state_name and city_name:
            try:
                state = State.objects.get(name=state_name)
                city = City.objects.get(name=city_name, state=state)
                return Response({
                    'state': state.name,
                    'city': city.name
                })
            except (State.DoesNotExist, City.DoesNotExist):
                return Response({
                    'error': 'State or City not found'
                }, status=status.HTTP_404_NOT_FOUND)

        # If only state is provided, return cities in that state
        if state_name:
            try:
                state = State.objects.get(name=state_name)
                cities = state.cities.all()
                return Response({
                    'state': state.name,
                    'cities': [city.name for city in cities]
                })
            except State.DoesNotExist:
                return Response({
                    'error': 'State not found'
                }, status=status.HTTP_404_NOT_FOUND)

        # If only city is provided, find states with that city
        if city_name:
            cities = City.objects.filter(name=city_name)
            if cities.exists():
                return Response({
                    'city': city_name,
                    'states': [city.state.name for city in cities]
                })
            else:
                return Response({
                    'error': 'City not found'
                }, status=status.HTTP_404_NOT_FOUND)

        # If no parameters, return all states and their cities
        states = State.objects.all()
        return Response({
            'states': [
                {
                    'name': state.name,
                    'cities': [city.name for city in state.cities.all()]
                } for state in states
            ]
        })
    
class GetContractorTransactions(APIView):
    def get(self, request):
        # Fetch all payments for vendors marked as contractors
        try:
            vendor_id = request.GET.get('vendor_id', None)
            contractor_payments = VendorPaymentDetails.objects.filter(
                vendor__is_contractor=True, 
                payment_method__in=['frost_bank','cash', 'check', 'debit_credit_card']
            ).select_related('vendor')

            if vendor_id:
                contractor_payments = contractor_payments.filter(vendor__vendor_id=vendor_id)

            # Format the data as a list of dictionaries
            if not contractor_payments.exists():
                return Response({'message': 'No contractor payment details found.'}, status=status.HTTP_400_BAD_REQUEST)
            data = [
                {
                    'payment_id': payment.id,
                    'vendor_name': payment.vendor.business_name,
                    'payment_method': payment.payment_method,
                    'transaction_reference_id': payment.transaction_reference_id,
                    'bank_name': payment.bank_name,
                    'cheque_number': payment.cheque_number,
                    'payment_amount': str(payment.payment_amount),
                    'payment_date': payment.payment_date,
                }
                for payment in contractor_payments
            ]

            # Return the data as a JSON response
            return Response({'contractor_payments': data}, status=status.HTTP_200_OK)
        except Exception as e:
            traceback_msg = traceback.format_exc()
            log.trace.trace(f"Error fetching contractor payments: {traceback_msg}")
            return Response({'error': f'Error fetching contractor payments: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)