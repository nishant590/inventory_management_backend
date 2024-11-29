from django.urls import path
from .views import (CreateExpenseView)

urlpatterns = [
    path('expense/create/', CreateExpenseView.as_view(), name='invoice-create')
]
