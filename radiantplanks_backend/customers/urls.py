from django.urls import path
from .views import CustomerCreateView, CustomerListView, CustomerEditView, CustomerDeleteView


urlpatterns = [
    path('customers/create/', CustomerCreateView.as_view(), name='customer-create'),
    path('customers/', CustomerListView.as_view(), name='customer-list'),  # GET all customers
    path('customers/<int:customer_id>/', CustomerEditView.as_view(), name='customer-edit'),  # PUT to edit customer
    path('customers/<int:customer_id>/delete/', CustomerDeleteView.as_view(), name='customer-delete'),  # DELETE customer
]