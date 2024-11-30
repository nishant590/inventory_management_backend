from django.urls import path
from .views import (CategoryListCreateView, 
                    CategoryListView,
                    CategoryUpdateView,
                    CategoryDeleteView, 
                    ProductCreateView, 
                    ProductListView,
                    ProductRetrieveView,
                    ProductUpdateView,
                    ProductDeleteView,
                    CreateInvoiceView,
                    ListInvoicesView,
                    RetrieveInvoiceView,
                    GetLatestInvoiceId,
                    SendInvoiceView,
                    CreateBillView,
                    ListBillsView,
                    RetrieveBillView)

urlpatterns = [
    # Category URLs
    path('categories/create/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/', CategoryListView.as_view(), name='category-detail'),
    path('categories/update/<int:category_id>/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/delete/<int:category_id>/', CategoryDeleteView.as_view(), name='category-delete'),

    # Product URLs
    
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/create/', ProductCreateView.as_view(), name='product-create'),
    path('products/retrive/<int:product_id>/', ProductRetrieveView.as_view(), name='product-retrive'),
    path('products/update/<int:product_id>/', ProductUpdateView.as_view(), name='product-update'),
    path('products/delete/<int:product_id>/', ProductDeleteView.as_view(), name='product-delete'),

    path('invoice/getid/', GetLatestInvoiceId.as_view(), name='invoice-get'),
    path('invoice/create/', CreateInvoiceView.as_view(), name='invoice-create'),
    path('invoice/', ListInvoicesView.as_view(), name='invoice-create'),
    path('invoice/retrive/<int:id>/', RetrieveInvoiceView.as_view(), name='invoice-create'),
    path('invoice/send/<int:invoice_id>/', SendInvoiceView.as_view(), name='invoice-send'),
    path('bill/create/', CreateBillView.as_view(), name='bill-create'),
    path('bill/', ListBillsView.as_view(), name='bill-list'),
    path('bill/retrive/<int:id>/', RetrieveBillView.as_view(), name='bill-get'),
    
]
