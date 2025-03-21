from django.urls import path
from .views import (CategoryListCreateView, 
                    CategoryListView,
                    CategoryUpdateView,
                    CategoryDeleteView, 
                    ProductCreateView, 
                    ProductListView,
                    InventoryStockView,
                    ProductRetrieveView,
                    ProductUpdateView,
                    ProductDeleteView,
                    CreateInvoiceView,
                    UpdateInvoiceView,
                    FinalizeInvoiceView,
                    ListInvoicesView,
                    ListCustomerInvoicesView,
                    RetrieveInvoiceView,
                    GetLatestInvoiceId,
                    SendInvoiceView,
                    DownloadInvoiceView,
                    DownloadPackingSlipView,
                    CreateBillView,
                    ListBillsView,
                    ListVendorBillsView,
                    RetrieveBillView,
                    InvoicePaidView,
                    BillPaidView,
                    SendEmailPdfToClient,
                    SendInvoiceRenderData,
                    CreateLostProductView,
                    ListLostProductsView,
                    LostProductDetailView,
                    UpdateLostProductView,
                    DeleteLostProductView,

                    TestEmailView,
                    InventoryHistoryReportView,
                    InventoryHistoryXLSXReportView,
                    DetailedInventoryReportView,
                    DetailedInventoryReportExcelExportView,
                    DetailedSalesReportView,
                    DetailedSalesReportExcelExportView,
                    ExpenseReportView,
                    ExpenseReportExcelExportView,
                    CustomerPaymentsReportView,
                    CustomerPaymentsExcelExportView,
                    )

urlpatterns = [
    # Category URLs
    path('categories/create/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/', CategoryListView.as_view(), name='category-detail'),
    path('categories/update/<int:category_id>/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/delete/<int:category_id>/', CategoryDeleteView.as_view(), name='category-delete'),

    # Product URLs
    
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/create/', ProductCreateView.as_view(), name='product-create'),
    path('products/stock/', InventoryStockView.as_view(), name='product-stock'),
    path('products/retrive/<int:product_id>/', ProductRetrieveView.as_view(), name='product-retrive'),
    path('products/update/<int:product_id>/', ProductUpdateView.as_view(), name='product-update'),
    path('products/delete/<int:product_id>/', ProductDeleteView.as_view(), name='product-delete'),

    path('invoice/getid/', GetLatestInvoiceId.as_view(), name='invoice-get'),
    path('invoice/create/', CreateInvoiceView.as_view(), name='invoice-create'),
    path('invoice/update/<int:invoice_id>/', UpdateInvoiceView.as_view(), name='invoice-update'),
    path('invoice/finalize/', FinalizeInvoiceView.as_view(), name='invoice-finalize'),
    path('invoice/', ListInvoicesView.as_view(), name='invoice-list'),
    path('invoice/customer/<int:customer_id>/', ListCustomerInvoicesView.as_view(), name='invoice-list'),
    path('invoice/retrive/<int:id>/', RetrieveInvoiceView.as_view(), name='invoice-retrive'),
    path('invoice/makepaid/', InvoicePaidView.as_view(), name='invoice-paid'),
    path('invoice/send/<int:invoice_id>/', SendInvoiceView.as_view(), name='invoice-send'),
    path('invoice/download/<int:invoice_id>/', DownloadInvoiceView.as_view(), name='invoice-download'),
    path('invoice/get-invoice-data/<int:invoice_id>/', SendInvoiceRenderData.as_view(), name="get-invoice-render-data"),
    path('invoice/send-invoice/<int:invoice_id>/', SendEmailPdfToClient.as_view(), name="send-email-invoice-to-client"),

    path('packingslip/download/<int:invoice_id>/', DownloadPackingSlipView.as_view(), name='packing-slip-download'),
    
    path('bill/create/', CreateBillView.as_view(), name='bill-create'),
    path('bill/', ListBillsView.as_view(), name='bill-list'),
    path('bill/vendor/<int:vendor_id>/', ListVendorBillsView.as_view(), name='bill-list'),
    path('bill/retrive/<int:id>/', RetrieveBillView.as_view(), name='bill-get'),
    path('bill/makepaid/', BillPaidView.as_view(), name='bill-paid'),
    
    path('lost-product/create/', CreateLostProductView.as_view(), name='lost-product-create'),
    path('lost-product/', ListLostProductsView.as_view(), name='lost-product-list'),
    # path('lost-product/vendor/<int:vendor_id>/', LostProductDetailView.as_view(), name='lost-product-list'),
    path('lost-product/update/<int:id>/', UpdateLostProductView.as_view(), name='lost-product-update'),
    path('lost-product/delete/<int:id>/', DeleteLostProductView.as_view(), name='lost-product-delete'),

    path('test/email-server/', TestEmailView.as_view(), name='test-email-server'),
    path('inventory-history-report/', InventoryHistoryReportView.as_view(), name='inventory-history-report'),
    path('inventory-history-report/xlsx/', InventoryHistoryXLSXReportView.as_view(), name='inventory-history-report-xlsx'),
    path('detailed-inventory-report/', DetailedInventoryReportView.as_view(), name='detailed-inventory-report'),
    path('detailed-inventory-report/xlsx/', DetailedInventoryReportExcelExportView.as_view(), name='detailed-inventory-report-xlsx'),
    path('detailed-sales-report/', DetailedSalesReportView.as_view(), name='detailed-sales-report'),
    path('detailed-sales-report/xlsx/', DetailedSalesReportExcelExportView.as_view(), name='detailed-sales-report-xlsx'),
    path('detailed-expense-report/', ExpenseReportView.as_view(), name='detailed-expense-report'),
    path('detailed-expense-report/xlsx/', ExpenseReportExcelExportView.as_view(), name='detailed-expense-report-xlsx'),
    path('detailed-customer-payment-report/', CustomerPaymentsReportView.as_view(), name='detailed-customer-payment-report'),
    path('detailed-customer-payment-report/xlsx/', CustomerPaymentsExcelExportView.as_view(), name='detailed-customer-payment-excel'),
]