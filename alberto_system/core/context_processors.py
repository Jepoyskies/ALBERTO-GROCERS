"""
core/context_processors.py

Template context processors that are available on every page.

Currently provides the low-stock notification feed used by the navbar
notification bell in ``templates/base.html``. Doing this in a context processor
means the badge and dropdown stay correct on every screen, not just the
dashboard, without each view having to remember to add it.
"""

from django.db.models import F


def notifications(request):
    """Expose low-stock alerts to every template.

    Returns an empty dict for anonymous users (so nothing renders on the login
    page) and for users who cannot view products (so the feed never leaks
    product data to a restricted account).

    Two deliberate choices here:

    * The keys are ``notif_*`` rather than ``low_stock_*``. ``core.views.home``
      already puts its own ``low_stock_count`` in the view context, and a view's
      context wins over a context processor - so reusing that name made the bell
      show a different number on the dashboard than on every other page.

    * Out-of-stock items (quantity 0) ARE included. The dashboard counts those
      separately as "Out of Stock", but for an alert feed a product at zero is
      the most urgent thing on the list, not something to omit.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}

    if not user.has_perm('inventory.view_product'):
        return {}

    # Imported lazily to avoid a circular import at app-loading time.
    from inventory.models import Product

    low_stock = Product.objects.filter(
        status=Product.Status.ACTIVE,
        quantity__lte=F('reorder_level'),
    ).order_by('quantity', 'name')

    count = low_stock.count()
    return {
        'notif_count': count,
        # Cap the list: a big catalogue could otherwise dump hundreds of rows
        # into the navbar dropdown. The badge still shows the true total.
        'notif_items': list(low_stock[:8]),
        'notif_extra': max(count - 8, 0),
    }
