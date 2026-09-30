from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from inventory.models import Product, StockTransaction, Customer, POSSale


@login_required
def landing(request):
    """
    Entry point for the whole system.

    Staff live on the till all day, so signing in (and typing the bare domain)
    drops them straight onto the POS terminal. Anyone without the POS
    permission - an office-only account, say - still gets the dashboard.
    The dashboard itself is always reachable at /dashboard/.
    """
    if request.user.has_perm('inventory.add_possale') or request.user.has_perm('inventory.view_possale'):
        return redirect('inventory:pos_dashboard')
    return redirect('dashboard')


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

        # Gametech Time Windows
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        def calc_sales(start_time, end_time=None):
            # Prefer POSSale total amounts
            pos_qs = POSSale.objects.exclude(status=POSSale.Status.CANCELLED).filter(timestamp__gte=start_time)
            if end_time:
                pos_qs = pos_qs.filter(timestamp__lt=end_time)
            pos_total = pos_qs.aggregate(total=Sum('total_amount'))['total']
            if pos_total and pos_total > 0:
                return float(pos_total)
            
            # Fallback to StockTransaction SALE items
            st_qs = StockTransaction.objects.filter(
                transaction_type='OUT',
                transaction_reason=StockTransaction.TransactionReason.SALE,
                timestamp__gte=start_time
            )
            if end_time:
                st_qs = st_qs.filter(timestamp__lt=end_time)
            st_total = st_qs.aggregate(val=Sum(F('quantity') * F('selling_price')))['val']
            return float(st_total or 0)

        today_sales = calc_sales(today_start)
        yesterday_sales = calc_sales(yesterday_start, today_start)
        week_sales = calc_sales(week_start)
        month_sales = calc_sales(month_start)
        year_sales = calc_sales(year_start)

        # Customer & Collection Metrics
        total_customers = Customer.objects.count()
        new_customers = Customer.objects.filter(created_at__gte=month_start).count()
        if new_customers == 0 and total_customers > 0:
            new_customers = total_customers

        # Collection rate (Paid sales / Total non-cancelled sales)
        total_sales_val = POSSale.objects.exclude(status=POSSale.Status.CANCELLED).aggregate(val=Sum('total_amount'))['val'] or 0
        paid_sales_val = POSSale.objects.exclude(status=POSSale.Status.CANCELLED).aggregate(val=Sum('amount_paid'))['val'] or 0
        if total_sales_val > 0:
            collection_rate = round(float((paid_sales_val / total_sales_val) * 100), 1)
        else:
            collection_rate = 100.0

        # --- PRODUCT COUNTS ---
        total_active = active_products.count()
        total_inactive = Product.objects.filter(status=Product.Status.DEACTIVATED).count()
        
        # --- STOCK VALUE ---
        total_stock_value_agg = active_products.aggregate(
            total_value=Sum(F('price') * F('quantity'))
        )
        total_stock_value = total_stock_value_agg['total_value'] or 0
        
        # --- TREND INDICATORS ---
        revenue_current = month_sales if month_sales > 0 else (
            StockTransaction.objects.filter(
                transaction_type='OUT',
                transaction_reason=StockTransaction.TransactionReason.SALE,
                timestamp__gte=thirty_days_ago
            ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0
        )

        revenue_previous = StockTransaction.objects.filter(
            transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            timestamp__gte=sixty_days_ago,
            timestamp__lt=thirty_days_ago
        ).aggregate(val=Sum(F('quantity') * F('selling_price')))['val'] or 0

        if revenue_previous > 0:
            revenue_trend = ((revenue_current - revenue_previous) / revenue_previous) * 100
        else:
            revenue_trend = 100.0 if revenue_current > 0 else 100.0

        # --- TABLES ---
        recent_products = Product.objects.order_by('-date_created')[:5]
        
        top_stocked_in = StockTransaction.objects.filter(
            transaction_type='IN', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_in=Sum('quantity')).order_by('-total_in')[:5]

        top_stocked_out = StockTransaction.objects.filter(
            transaction_type='OUT', timestamp__gte=thirty_days_ago
        ).values('product__name', 'product__slug').annotate(total_out=Sum('quantity')).order_by('-total_out')[:5]

        dashboard_data = {
            'today_sales': today_sales,
            'yesterday_sales': yesterday_sales,
            'week_sales': week_sales,
            'month_sales': month_sales,
            'year_sales': year_sales,
            'total_customers': total_customers,
            'new_customers': new_customers,
            'collection_rate': collection_rate,
            'total_products': total_active,
            'total_inactive': total_inactive,
            'total_stock_value': total_stock_value,
            'recent_products': recent_products,
            'top_stocked_in': top_stocked_in,
            'top_stocked_out': top_stocked_out,
            'monthly_revenue': revenue_current,
            'revenue_trend': revenue_trend,
        }
        cache.set(cache_key, dashboard_data, 60) 
    
    # --- MERGE CONTEXT ---
    context = dashboard_data.copy()
    context['out_of_stock_products'] = out_of_stock_products
    context['out_of_stock_count'] = out_of_stock_count
    context['low_stock_products'] = low_stock_products
    context['low_stock_count'] = low_stock_count
    
    return render(request, 'home.html', context)