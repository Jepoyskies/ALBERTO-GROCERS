# core/cache_utils.py

from django.core.cache import cache

def clear_dashboard_cache():
    """Removes the dashboard data from the cache."""
    # FIX: Updated key to match the one in core/views.py
    cache.delete('dashboard_data_v2')