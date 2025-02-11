from django.urls import path
from .views import (CreateExpenseView, ExpenseDetailView, ExpenseListView,
                    EditExpenseView, DuplicateExpenseView,DeleteExpenseView, UploadExpenseCSVView)

urlpatterns = [
    path('expense/create/', CreateExpenseView.as_view(), name='expense-create'),
    path('expense/', ExpenseListView.as_view(), name='expense-list'),
    path('expense/retrive/<int:id>/', ExpenseDetailView.as_view(), name='expense-retrieve'),
    path('expense/update/<int:id>/', EditExpenseView.as_view(), name='expense-update'),
    path('expense/delete/<int:id>/', DeleteExpenseView.as_view(), name='expense-delete'),
    path('expense/upload-csv/', UploadExpenseCSVView.as_view(), name='expense-csv-upload'),
    path('expense/duplicate-expense/<int:id>/', DuplicateExpenseView.as_view(), name='expense-duplicate')
]
