from django.urls import path
from .views import (AddAccountAPI, 
                    AccountListView, 
                    AccountReceivablesView,
                    AccountsReceivableAPIView, 
                    AccountsPayableAPIView,
                    AccountPayablesView, 
                    BalanceSheetView,
                    ProfitLossStatementView,
                    ProfitLossStatementCustomerView)

urlpatterns = [
    path('accounts/create/', AddAccountAPI.as_view(), name='add_account'),
    path('accounts/', AccountListView.as_view(), name='account-list'),
    # path('accounts-payable/'),
    path('accounts-payable/', AccountPayablesView.as_view(), name='account-payables'),
    path('accounts-payable-datewise/', AccountsPayableAPIView.as_view(), name='account-payables-datewise'),
    path('accounts-recievable/', AccountReceivablesView.as_view(), name='account-receivables'),
    path('accounts-recievable-datewise/', AccountsReceivableAPIView.as_view(), name='account-receivables-datewise'),
    path('balancesheet/', BalanceSheetView.as_view(), name='balancesheet'),
    path('profitandloss/', ProfitLossStatementView.as_view(), name='profitandloss'),
    path('profitandloss-customer/', ProfitLossStatementCustomerView.as_view(), name='profitandloss-customer'),
]
