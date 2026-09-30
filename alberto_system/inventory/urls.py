"""
Inventory Application URL Configuration

This module handles all URL routing for the inventory system.
It is logically divided into core inventory management, analytics, 
procurement, point-of-sale, customer relationship management, and expenses.
"""

from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

app_name = 'inventory'

urlpatterns =[
    # ==========================================
    # CORE INVENTORY MANAGEMENT
    # ==========================================
    path('', views.ProductListView.as_view(), name='product_list'),
    path('product/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:product_id>/price/', views.get_product_price, name='get_product_price'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('product/<slug:slug>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('product/<slug:slug>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    # Custom Product Actions
    path('product/<slug:slug>/toggle_status/', views.product_toggle_status, name='product_toggle_status'),
    path('pos/refund/', views.refund_portal, name='refund_portal'),
    path('pos/refund/search/', views.refund_search, name='refund_search'),
    path('pos/refund/process/', views.refund_process, name='refund_process'),
    path('products/import/', views.import_products, name='product_import'),
    
    # AJAX & API Endpoints
    path('ajax/category/add/', views.add_category_ajax, name='add_category_ajax'),
    path('ajax/expense-category/add/', views.add_expense_category_ajax, name='add_expense_category_ajax'),
    path('products/search/', views.search_products, name='product_search'),
    path('api/sales-chart-data/', views.sales_chart_data, name='sales_chart_data'),

    # ==========================================
    # ANALYTICS & REPORTING
    # ==========================================
    path('history/', views.ProductHistoryListView.as_view(), name='product_history_list'),
    path('product/<slug:slug>/history/', views.ProductHistoryDetailView.as_view(), name='product_history_detail'),
    path('transactions/', views.TransactionListView.as_view(), name='transaction_list'),
    path('reports/', views.ReportingView.as_view(), name='reporting'),
    path('analytics/', views.analytics_dashboard, name='analytics'),

    # ==========================================
    # SUPPLIERS & PROCUREMENT
    # ==========================================
    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchaseorder_list'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchaseorder_detail'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order, name='purchaseorder_receive'),
    
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<int:pk>/import/', views.import_supplier_deliveries, name='supplier_deliveries_import'),

    # ==========================================
    # POINT OF SALE (POS)
    # ==========================================
    path('pos/', views.pos_dashboard, name='pos_dashboard'),
    path('pos/checkout/', views.pos_checkout, name='pos_checkout'),
    path('pos/history/', views.POSHistoryListView.as_view(), name='pos_history'),
    path('pos/receipt/<str:receipt_id>/', views.POSReceiptDetailView.as_view(), name='pos_receipt_detail'),

    # --- POS Terminal toolbar actions ---
    path('pos/hold/save/', views.pos_hold_save, name='pos_hold_save'),
    path('pos/hold/list/', views.pos_hold_list, name='pos_hold_list'),
    path('pos/hold/<str:ticket_id>/resume/', views.pos_hold_resume, name='pos_hold_resume'),
    path('pos/hold/<str:ticket_id>/discard/', views.pos_hold_discard, name='pos_hold_discard'),
    path('pos/repeat-last/', views.pos_repeat_last, name='pos_repeat_last'),
    path('pos/customers/search/', views.pos_customer_search, name='pos_customer_search'),

    # --- Cash drawer (open / close a shift) ---
    path('pos/drawer/status/', views.pos_drawer_status, name='pos_drawer_status'),
    path('pos/drawer/open/', views.pos_drawer_open, name='pos_drawer_open'),
    path('pos/drawer/close/', views.pos_drawer_close, name='pos_drawer_close'),

    # ==========================================
    # CUSTOMERS & CRM
    # ==========================================
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/update/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<int:pk>/payment/', views.customer_payment, name='customer_payment'),
    path('customers/<int:pk>/cancel-debt/<int:sale_pk>/', views.cancel_debt, name='cancel_debt'),
    path('customers/<int:pk>/export/', views.export_statement, name='customer_statement_export'),
    
    # Customer Ledger Imports
    path('customers/<int:pk>/import-ledger/', views.import_ledger_entries, name='customer_ledger_import'),
    path('customers/templates/ledger/', views.download_ledger_template, name='download_ledger_template'),
    
    # ==========================================
    # FINANCIALS & EXPENSES
    # ==========================================
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/update/', views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('expenses/<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    
    # Expense Imports
    path('expenses/import/', views.import_expenses, name='expense_import'),
    path('expenses/templates/download/', views.download_expense_template, name='download_expense_template'),

    # Feedback Page
    path('feedback/', views.feedback_view, name='feedback'),
]