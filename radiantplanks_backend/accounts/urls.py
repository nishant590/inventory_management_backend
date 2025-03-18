from django.urls import path
from .views import (AddAccountAPI, 
                    AccountListView, 
                    AccountReceivablesView,
                    AccountsReceivableAPIView, 
                    AccountsPayableAPIView,
                    AccountPayableSingleView,
                    AccountPayableView,
                    AccountReceivablesSingleView, 
                    BalanceSheetView,
                    BalanceSheetXLSXView,
                    ProfitLossStatementView,
                    ProfitLossStatementCustomerView,
                    OwnerContributionAPI,
                    GetAllOwnerTransactionsAPI,
                    OwnerTakeOutMoneyAPI,
                    EditOwnerTransactionAPI,
                    DeleteOwnerTransactionAPI,
                    CompareBalanceSheetView,
                    ProfitLossXLSXView,
                    ProfitLossComparisonView,
                    ProfitLossComparisonAccrualView,
                    ProfitLossComparisonXLSXView,
                    BankAccountTransactionsAPIView,
                    BankAccountTransactionsExportAPIView
                    )

urlpatterns = [
    path('accounts/create/', AddAccountAPI.as_view(), name='add_account'),
    path('accounts/', AccountListView.as_view(), name='account-list'),
    # path('accounts-payable/'),
    path('accounts-payable/', AccountPayableView.as_view(), name='account-payables'),
    path('accounts-payable/<int:vendor_id>/', AccountPayableSingleView.as_view(), name='account-payables'),
    path('accounts-payable-datewise/', AccountsPayableAPIView.as_view(), name='account-payables-datewise'),
    path('accounts-recievable/', AccountReceivablesView.as_view(), name='account-receivables'),
    path('accounts-recievable/<int:customer_id>/', AccountReceivablesSingleView.as_view(), name='account-receivables'),
    path('accounts-recievable-datewise/', AccountsReceivableAPIView.as_view(), name='account-receivables-datewise'),
    
    path('balancesheet/', BalanceSheetView.as_view(), name='balancesheet'),
    path('balancesheet/compare/', CompareBalanceSheetView.as_view(), name='balancesheet-compare'),
    path('balancesheet-xlsx/', BalanceSheetXLSXView.as_view(), name='balancesheet-xlsx'),
    path('profitandloss/', ProfitLossStatementView.as_view(), name='profitandloss'),
    path('profitandloss-customer/', ProfitLossStatementCustomerView.as_view(), name='profitandloss-customer'),
    path('profitandloss-xlsx/', ProfitLossXLSXView.as_view(), name='profitandloss-xlsx'),
    path('profitandloss-compare/', ProfitLossComparisonView.as_view(), name='profitandloss-compare'),
    path('profitandloss-xlsx-compare/', ProfitLossComparisonXLSXView.as_view(), name='profitandloss-xlsx-compare'),
    # path('profitandloss-accrual/', ProfitLossComparisonAccrualView.as_view(), name='profitandloss-compare-accrual'),
    
    path('owner-contribution/', OwnerContributionAPI.as_view(), name='owner-contribution'),
    path('owner-transactions/', GetAllOwnerTransactionsAPI.as_view(), name='owner-transactions'),
    path('owner-takeout-money/', OwnerTakeOutMoneyAPI.as_view(), name='owner-takeout-money'),
    path('owner-contribution-edit/<int:id>/', EditOwnerTransactionAPI.as_view(), name='owner-contribution-edit'),
    path('owner-contribution-delete/<int:id>/', DeleteOwnerTransactionAPI.as_view(), name='owner-contribution-delete'),
  
    path('view-bank-transactions/', BankAccountTransactionsAPIView.as_view(), name='view-bank-transactions'),
    path('view-bank-transactions/xlsx/', BankAccountTransactionsExportAPIView.as_view(), name='view-bank-transactions-xlsx'),
] 
