from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from inventory.models import Product, StockTransaction


@login_required
def home(request):
    """
    Renders the main dashboard for authenticated users.
    
    Aggregates product stock levels, calculating out-of-stock and low-stock 
    alerts dynamically. Uses Django's caching framework to store heavy 
    database queries (monthly revenue, stock values, and recent transactions) 
    for 5 minutes (300 seconds) to optimize performance.
    """
    
    # --- PART 1: LIVE DATA (Critical Alerts) ---
    active_products = Product.objects.filter(status=Product.Status.ACTIVE)
    
    # Out of Stock
    out_of_stock_products = active_products.filter(quantity=0).order_by('name')
    out_of_stock_count = out_of_stock_products.count()

    # Low Stock
    low_stock_products = active_products.filter(
        quantity__gt=0, 
        quantity__lte=F('reorder_level')
    ).order_by('quantity')
    low_stock_count = low_stock_products.count()

    # --- PART 2: CACHED DATA ---
    cache_key = 'dashboard_data_v2' 
    dashboard_data = cache.get(cache_key)

    if not dashboard_data:
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # --- PRODUCT COUNTS ---
        total_active = active_products.count()
        total_inactive = Product.objects.filter(status=Product.Status.DEACTIVATED).count()
        
        # --- STOCK VALUE ---
        total_stock_value_agg = active_products.aggregate(
            total_value=Sum(F('price') * F('quantity'))
        )
        total_stock_value = total_stock_value_agg['total_value'] or 0
        
        # --- TREND INDICATORS ---
        revenue_current = StockTransaction.objects.filter(
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            timestamp__gte=thirty_days_ago
        ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

        revenue_previous = StockTransaction.objects.filter(
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            timestamp__gte=sixty_days_ago,
            timestamp__lt=thirty_days_ago
        ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

        if revenue_previous > 0:
            revenue_trend = ((revenue_current - revenue_previous) / revenue_previous) * 100
        else:
            revenue_trend = 100 if revenue_current > 0 else 0

        # --- TABLES ---
        recent_products = Product.objects.order_by('-date_created')[:5]
        
        top_stocked_in = StockTransaction.objects.filter(
            transaction_type='IN', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_in=Sum('quantity')).order_by('-total_in')[:5]

        top_stocked_out = StockTransaction.objects.filter(
            transaction_type='OUT', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_out=Sum('quantity')).order_by('-total_out')[:5]

        dashboard_data = {
            'total_products': total_active,
            'total_inactive': total_inactive,
            'total_stock_value': total_stock_value,
            'recent_products': recent_products,
            'top_stocked_in': top_stocked_in,
            'top_stocked_out': top_stocked_out,
            'monthly_revenue': revenue_current,
            'revenue_trend': revenue_trend,
        }
        cache.set(cache_key, dashboard_data, 300) 
    
    # --- MERGE CONTEXT ---
    context = dashboard_data.copy()
    context['out_of_stock_products'] = out_of_stock_products
    context['out_of_stock_count'] = out_of_stock_count
    context['low_stock_products'] = low_stock_products
    context['low_stock_count'] = low_stock_count
    
    return render(request, 'home.html', context)