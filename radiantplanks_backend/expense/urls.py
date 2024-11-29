from django.urls import path
from .views import (CreateExpenseView, ExpenseDetailView, ExpenseListView)

urlpatterns = [
    path('expense/create/', CreateExpenseView.as_view(), name='expense-create'),
    path('expense/', ExpenseListView.as_view(), name='expense-list'),
    path('expense/retrive/<int:id>/', ExpenseDetailView.as_view(), name='expense-retrive')
]
