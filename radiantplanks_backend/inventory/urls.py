from django.urls import path
from .views import (CategoryListCreateView, 
                    CategoryListView,
                    CategoryUpdateView,
                    CategoryDeleteView, 
                    ProductCreateView, 
                    ProductUpdateView,
                    ProductDeleteView)

urlpatterns = [
    # Category URLs
    path('categories/create/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/', CategoryListView.as_view(), name='category-detail'),
    path('categories/update/<int:pk>/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/delete/<int:pk>/', CategoryDeleteView.as_view(), name='category-delete'),

    # Product URLs
    path('products/create', ProductCreateView.as_view(), name='product-create'),
    path('products/update/', ProductUpdateView.as_view(), name='product-update'),
    path('products/delete/', ProductDeleteView.as_view(), name='product-delete'),
]
