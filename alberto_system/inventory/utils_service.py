
from .models import Product

def get_service_product():
    """Helper to retrieve the service product."""
    return Product.objects.get_or_create(
        sku="SVC-HYD-001",
        defaults={'name': 'Hydraulic Service', 'price': 0}
    )[0]
