from django.urls import path
from .views import (CustomerCreateView, 
                    CustomerListView, 
                    CustomerEditView, 
                    CustomerDeleteView,
                    VendorCreateView,
                    VendorListView,
                    VendorEditView,
                    VendorDeleteView,
                    VendorRetriveView,
                    CustomerDetailView)


urlpatterns = [
    path('customers/create/', CustomerCreateView.as_view(), name='customer-create'),
    path('customers/', CustomerListView.as_view(), name='customer-list'),  # GET all customers
    path('customers/<int:customer_id>/', CustomerEditView.as_view(), name='customer-edit'),  # PUT to edit customer
    path('customers/<int:customer_id>/delete/', CustomerDeleteView.as_view(), name='customer-delete'),  # DELETE customer
    path('customers/retrive/<int:customer_id>/', CustomerDetailView.as_view(), name='customer-detail'),  # DELETE customer
    path('vendors/create/', VendorCreateView.as_view(), name='vendor-create'),
    path('vendors/', VendorListView.as_view(), name='vendor-list'),  # GET all vendors
    path('vendors/<int:vendor_id>/', VendorEditView.as_view(), name='vendor-edit'),  # PUT to edit vendor
    path('vendors/retrive/<int:vendor_id>/', VendorRetriveView.as_view(), name='vendor-edit'),  # PUT to edit vendor
    path('vendors/<int:vendor_id>/delete/', VendorDeleteView.as_view(), name='customer-delete'),  # DELETE customer
]