# inventory/api_urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'inventory-api'

router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'payments', views.CustomerPaymentViewSet, basename='payment')
router.register(r'sows', views.HydraulicSowViewSet, basename='sow')
router.register(r'pos-sales', views.POSSaleViewSet, basename='possale')
router.register(r'expense-categories', views.ExpenseCategoryViewSet, basename='expense-category')
router.register(r'expenses', views.ExpenseViewSet, basename='expense')

urlpatterns = [
    path('', include(router.urls)),
    path('sales-chart-data/', views.sales_chart_data, name='sales-chart-data'),
]