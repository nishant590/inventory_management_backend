from django.urls import path
from .views import AddAccountAPI, AccountListView, AccountReceivablesView, AccountPayablesView, BalanceSheetView

urlpatterns = [
    path('accounts/create/', AddAccountAPI.as_view(), name='add_account'),
    path('accounts/', AccountListView.as_view(), name='account-list'),
    # path('accounts-payable/'),
    path('accounts-payable/', AccountPayablesView.as_view(), name='account-payables'),
    path('accounts-recievable/', AccountReceivablesView.as_view(), name='account-receivables'),
    path('balancesheet/', BalanceSheetView.as_view(), name='balancesheet'),
]
