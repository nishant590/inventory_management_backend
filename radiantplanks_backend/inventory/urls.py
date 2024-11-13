from django.urls import path
from .views import (CategoryListCreateView, 
                    CategoryListView,
                    CategoryUpdateView,
                    CategoryDeleteView, 
                    ProductCreateView, 
                    ProductListView,
                    ProductUpdateView,
                    ProductDeleteView)

urlpatterns = [
    # Category URLs
    path('categories/create/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/', CategoryListView.as_view(), name='category-detail'),
    path('categories/update/<int:category_id>/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/delete/<int:category_id>/', CategoryDeleteView.as_view(), name='category-delete'),

    # Product URLs
    
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/create/', ProductCreateView.as_view(), name='product-create'),
    path('products/update/<int:product_id>/', ProductUpdateView.as_view(), name='product-update'),
    path('products/delete/<int:product_id>/', ProductDeleteView.as_view(), name='product-delete'),
]
