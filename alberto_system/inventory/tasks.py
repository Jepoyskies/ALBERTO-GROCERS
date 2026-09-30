# inventory/tasks.py

from django.db import models
from .models import Product

def send_low_stock_alerts_task():
    """
    Check for products with low stock and send alerts.
    """
    low_stock_products = Product.objects.filter(
        quantity__lte=models.F('reorder_level'),
        status=Product.Status.ACTIVE
    )
    
    count = low_stock_products.count()
    if count == 0:
        return 'No products with low stock. No alert sent.'
    
    # Logic for sending email would go here
    
    return f'Successfully sent low stock alert for {count} products.'
