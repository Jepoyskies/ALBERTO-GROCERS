"""
Main URL Configuration for Alberto Grocers Inventory POS.

This module acts as the central router for the entire application, 
delegating URLs to specific apps (like inventory), handling authentication, 
serving API documentation, and managing static/media files in development.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView, 
    SpectacularRedocView, 
    SpectacularSwaggerView
)

from inventory.views import CustomLoginView
from . import views

urlpatterns =[
    # --- 1. Main Entry Point & Dashboard ---
    # The bare domain opens the POS terminal (cashiers live on the till);
    # the dashboard is preserved at /dashboard/ and linked from the terminal.
    path('', views.landing, name='home'),
    path('dashboard/', views.home, name='dashboard'),
    
    # --- 2. Admin Interface ---
    path('admin/', admin.site.urls),
    
    # --- 3. Authentication ---
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # --- 4. REST API & Documentation (Swagger/ReDoc) ---
    path('api/', include(('inventory.api_urls', 'inventory-api'))),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # --- 5. Core Application Routing ---
    path('inventory/', include(('inventory.urls', 'inventory'), namespace='inventory')),
]

# Serve Static and Media files automatically during local development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)