"""
Tests for the POS terminal (new tax breakdown + terminal toolbar actions).

These cover the money-critical paths that the browser cannot prove on its own:
the VAT split that lands on every sale, and the parked-order / cash-drawer
endpoints that the toolbar buttons call.
"""

import json
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from .models import CashDrawerSession, Category, HeldSale, POSSale, Product, StockTransaction
from .views import split_vat


class POSPermissionMixin:
    def setUp(self):
        self.user = User.objects.create_user('cashier', password='pw')
        self.user.user_permissions.add(
            Permission.objects.get(codename='add_possale', content_type__app_label='inventory')
        )
        self.client.force_login(self.user)


class VATSplitTests(TestCase):
    """
    Shelf prices are VAT-INCLUSIVE, so the terminal extracts tax from the
    price the customer actually pays. 1000.00 @ 15% -> 869.57 net + 130.43 tax.
    """

    def test_extracts_15_percent_from_gross(self):
        net, tax = split_vat(Decimal('1000.00'))
        self.assertEqual(net, Decimal('869.57'))
        self.assertEqual(tax, Decimal('130.43'))

    def test_net_plus_tax_always_equals_gross(self):
        for gross in ['0.00', '0.05', '12.50', '869.57', '1000.00', '12345.67']:
            net, tax = split_vat(Decimal(gross))
            self.assertEqual(net + tax, Decimal(gross), f'failed for {gross}')

    def test_zero_rate_returns_net_and_no_tax(self):
        net, tax = split_vat(Decimal('500.00'), Decimal('0'))
        self.assertEqual(net, Decimal('500.00'))
        self.assertEqual(tax, Decimal('0.00'))

    def test_broken_rate_does_not_divide_by_zero(self):
        """A misconfigured rate of -100% must not crash the checkout."""
        net, tax = split_vat(Decimal('500.00'), Decimal('-100'))
        self.assertEqual(net, Decimal('500.00'))
        self.assertEqual(tax, Decimal('0.00'))


class POSCheckoutTests(POSPermissionMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='Groceries')
        self.product = Product.objects.create(
            name='Rice 5kg', sku='RICE-5', category=self.category,
            price=Decimal('250.00'), quantity=100,
        )

    def checkout(self, **overrides):
        payload = {
            'items': [{'id': self.product.pk, 'qty': 4}],
            'amount_paid': 1000.00,
            'payment_method': 'CASH',
            'payment_description': '',
            'customer_id': '',
        }
        payload.update(overrides)
        return self.client.post(
            reverse('inventory:pos_checkout'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_checkout_stores_vat_breakdown_and_keeps_gross_as_total(self):
        """total_amount stays the gross (what every report already sums)."""
        res = self.checkout()
        self.assertEqual(res.status_code, 200)
        sale = POSSale.objects.get(receipt_id=res.json()['receipt_id'])

        self.assertEqual(sale.total_amount, Decimal('1000.00'))
        self.assertEqual(sale.subtotal_amount, Decimal('869.57'))
        self.assertEqual(sale.tax_amount, Decimal('130.43'))
        self.assertEqual(sale.tax_rate, Decimal('15.00'))
        self.assertEqual(sale.amount_paid, Decimal('1000.00'))
        self.assertEqual(sale.change_given, Decimal('0.00'))

    def test_checkout_rate_comes_from_the_server_not_the_client(self):
        """A tampered client rate must not be trusted."""
        self.checkout(tax_rate=99)
        sale = POSSale.objects.latest('timestamp')
        self.assertEqual(sale.tax_rate, Decimal('15.00'))

    def test_checkout_persists_line_comment(self):
        self.checkout(items=[{'id': self.product.pk, 'qty': 2, 'comment': 'customer wanted a bag'}])
        sale = POSSale.objects.latest('timestamp')
        self.assertEqual(sale.items.get().comment, 'customer wanted a bag')

    def test_checkout_records_discount_given_away(self):
        self.checkout(items=[{
            'id': self.product.pk, 'qty': 2,
            'price': 200.00, 'original_price': 250.00,
            'override_reason': 'staff discount',
        }])
        sale = POSSale.objects.latest('timestamp')
        self.assertEqual(sale.discount_amount, Decimal('100.00'))
        self.assertTrue(sale.has_price_override)
        self.assertEqual(sale.total_amount, Decimal('400.00'))

    def test_checkout_decrements_stock(self):
        self.checkout()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 96)
        self.assertEqual(
            StockTransaction.objects.filter(pos_sale__isnull=False).count(), 1)

    def test_checkout_rejects_underpayment(self):
        res = self.checkout(amount_paid=10.00)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(POSSale.objects.count(), 0)

    def test_checkout_rejects_insufficient_stock(self):
        res = self.checkout(items=[{'id': self.product.pk, 'qty': 500}])
        self.assertEqual(res.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 100)  # untouched


class HeldSaleTests(POSPermissionMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='Groceries')
        self.product = Product.objects.create(
            name='Coke', sku='COKE', category=self.category,
            price=Decimal('60.00'), quantity=50,
        )
        self.payload = {
            'label': 'Maria - 2 bags',
            'total': '120.00',
            'items': [{'id': self.product.pk, 'name': 'Coke', 'qty': 2,
                       'price': 60.0, 'original_price': 60.0, 'comment': ''}],
        }

    def test_park_then_list_then_resume(self):
        res = self.client.post(reverse('inventory:pos_hold_save'),
                               data=json.dumps(self.payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        ticket_id = res.json()['ticket_id']
        self.assertEqual(HeldSale.objects.filter(status=HeldSale.Status.ACTIVE).count(), 1)

        listed = self.client.get(reverse('inventory:pos_hold_list')).json()
        self.assertEqual(len(listed['tickets']), 1)
        self.assertEqual(listed['tickets'][0]['label'], 'Maria - 2 bags')

        resumed = self.client.post(
            reverse('inventory:pos_hold_resume', kwargs={'ticket_id': ticket_id}))
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(len(resumed.json()['payload']['items']), 1)

        # Resuming flips status; the audit row survives.
        self.assertEqual(HeldSale.objects.get(ticket_id=ticket_id).status,
                         HeldSale.Status.RESUMED)
        self.assertEqual(HeldSale.objects.filter(status=HeldSale.Status.ACTIVE).count(), 0)

    def test_parked_order_cannot_be_resumed_twice(self):
        res = self.client.post(reverse('inventory:pos_hold_save'),
                               data=json.dumps(self.payload), content_type='application/json')
        ticket_id = res.json()['ticket_id']
        url = reverse('inventory:pos_hold_resume', kwargs={'ticket_id': ticket_id})
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_cannot_park_an_empty_cart(self):
        res = self.client.post(reverse('inventory:pos_hold_save'),
                               data=json.dumps({'items': []}), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(HeldSale.objects.count(), 0)

    def test_discard_keeps_the_audit_row(self):
        res = self.client.post(reverse('inventory:pos_hold_save'),
                               data=json.dumps(self.payload), content_type='application/json')
        ticket_id = res.json()['ticket_id']
        self.client.post(reverse('inventory:pos_hold_discard',
                                 kwargs={'ticket_id': ticket_id}))
        self.assertEqual(HeldSale.objects.get(ticket_id=ticket_id).status,
                         HeldSale.Status.DISCARDED)


class CashDrawerTests(POSPermissionMixin, TestCase):

    def test_open_and_close_balanced_shift(self):
        res = self.client.post(reverse('inventory:pos_drawer_open'),
                               data=json.dumps({'opening_float': 500}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)

        status = self.client.get(reverse('inventory:pos_drawer_status')).json()
        self.assertTrue(status['is_open'])

        closed = self.client.post(reverse('inventory:pos_drawer_close'),
                                  data=json.dumps({'counted_cash': 500}),
                                  content_type='application/json').json()
        # No cash sales in this shift, so expected == float == 500.
        self.assertEqual(closed['expected'], '500.00')
        self.assertEqual(closed['difference'], '0.00')

        session = CashDrawerSession.objects.get()
        self.assertEqual(session.status, CashDrawerSession.Status.CLOSED)
        self.assertIsNotNone(session.closed_at)

    def test_variance_is_recorded_as_short(self):
        self.client.post(reverse('inventory:pos_drawer_open'),
                         data=json.dumps({'opening_float': 500}),
                         content_type='application/json')
        closed = self.client.post(reverse('inventory:pos_drawer_close'),
                                  data=json.dumps({'counted_cash': 480}),
                                  content_type='application/json').json()
        self.assertEqual(closed['difference'], '-20.00')
        self.assertEqual(CashDrawerSession.objects.get().difference, Decimal('-20.00'))

    def test_cannot_open_two_sessions_at_once(self):
        self.client.post(reverse('inventory:pos_drawer_open'),
                         data=json.dumps({'opening_float': 500}),
                         content_type='application/json')
        res = self.client.post(reverse('inventory:pos_drawer_open'),
                               data=json.dumps({'opening_float': 100}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(CashDrawerSession.objects.count(), 1)

    def test_cannot_close_when_nothing_is_open(self):
        res = self.client.post(reverse('inventory:pos_drawer_close'),
                               data=json.dumps({'counted_cash': 100}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_rejects_negative_count(self):
        self.client.post(reverse('inventory:pos_drawer_open'),
                         data=json.dumps({'opening_float': 500}),
                         content_type='application/json')
        res = self.client.post(reverse('inventory:pos_drawer_close'),
                               data=json.dumps({'counted_cash': -5}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_expected_cash_tracks_cash_sales_in_the_shift(self):
        from .views import get_walkin_customer
        self.client.post(reverse('inventory:pos_drawer_open'),
                         data=json.dumps({'opening_float': 500}),
                         content_type='application/json')
        POSSale.objects.create(
            receipt_id='REC-TEST01', cashier=self.user, customer=get_walkin_customer(),
            payment_method=POSSale.PaymentMethod.CASH, total_amount=Decimal('300.00'),
            amount_paid=Decimal('300.00'), change_given=Decimal('0.00'),
        )
        status = self.client.get(reverse('inventory:pos_drawer_status')).json()
        self.assertEqual(status['expected_cash'], '800.00')  # 500 float + 300 sale


class RepeatLastSaleTests(POSPermissionMixin, TestCase):

    def test_no_previous_sale_is_reported_gracefully(self):
        res = self.client.get(reverse('inventory:pos_repeat_last'))
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()['status'], 'error')

    def test_repeat_returns_the_last_basket(self):
        from .views import get_walkin_customer
        category = Category.objects.create(name='Groceries')
        product = Product.objects.create(
            name='Bread', sku='BRD', category=category,
            price=Decimal('80.00'), quantity=20)
        sale = POSSale.objects.create(
            receipt_id='REC-ABC12345', cashier=self.user, customer=get_walkin_customer(),
            payment_method=POSSale.PaymentMethod.CASH, total_amount=Decimal('160.00'),
            amount_paid=Decimal('160.00'),
        )
        StockTransaction.objects.create(
            product=product, pos_sale=sale, transaction_type='OUT',
            transaction_reason=StockTransaction.TransactionReason.SALE,
            quantity=2, selling_price=Decimal('80.00'), comment='no bag please',
        )
        data = self.client.get(reverse('inventory:pos_repeat_last')).json()
        self.assertEqual(data['receipt_id'], 'REC-ABC12345')
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['qty'], 2)
        self.assertEqual(data['items'][0]['comment'], 'no bag please')


class POSRenderTests(POSPermissionMixin, TestCase):
    """
    Guards the terminal's markup. The browser is not available in CI, so the
    landmarks the layout depends on are asserted here instead.
    """

    def setUp(self):
        super().setUp()
        category = Category.objects.create(name='Groceries')
        Product.objects.create(
            name='Rice 5kg', sku='RICE-5', category=category,
            price=Decimal('250.00'), quantity=10)

    def test_terminal_renders_with_its_landmarks(self):
        res = self.client.get(reverse('inventory:pos_dashboard'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()

        # Layout landmarks from the till layout staff know.
        for landmark in ['pos-shell', 'pos-toolbar', 'cart-pane', 'catalog-pane',
                         'cart-head', 'cart-list', 'cart-foot', 'cart-actions',
                         'catalog-bar', 'catalog-grid', 'catalog-foot']:
            self.assertIn(landmark, html, f'missing .{landmark}')

        # Header cells and the totals figure. Shelf prices are fixed and
        # VAT-inclusive, so the terminal shows a single Total: no Subtotal
        # row and no tax line. VAT is still stored server-side.
        self.assertIn('Quantity', html)
        self.assertIn('Total', html)
        self.assertNotIn('Subtotal', html)
        self.assertNotIn('Tax (', html)
        self.assertNotIn('rcptTax', html)
        # The TOTAL label is clean: no stray asterisk beside the figure.
        self.assertNotIn('Total*', html)

        # Bottom action bar.
        for label in ['Void order', 'Lock', 'Repeat']:
            self.assertIn(label, html)

        # Toolbar actions + F-keys.
        for label in ['Search', 'Transfer', 'Discount', 'Comment', 'New sale',
                      'Refund', 'Cash drawer']:
            self.assertIn(label, html)
        for fkey in ['F9', 'F10', 'F12']:
            self.assertIn(fkey, html)

        # Catalogue products are handed to the terminal as JSON.
        self.assertIn('RICE-5', html)
        self.assertIn('pos-boot', html)

    def test_terminal_uses_the_shared_brand_tokens(self):
        """The POS must not reintroduce a private palette.

        The palette now lives in ag-tokens.css (extracted from the AG logo)
        with the shared component library alongside it. The old
        brand-tokens.css is a deprecated shim and must not be the one loaded.
        """
        html = self.client.get(reverse('inventory:pos_dashboard')).content.decode()
        self.assertIn('css/ag-tokens.css', html)
        self.assertIn('css/ag-components.css', html)
        self.assertIn('pos/pos.css', html)

    def test_tax_rate_is_handed_to_the_terminal_config(self):
        """The rate is no longer printed on screen, but the boot config still
        carries it so the client and the stored sale record cannot disagree."""
        res = self.client.get(reverse('inventory:pos_dashboard'))
        boot = json.loads(
            res.content.decode().split('id="pos-boot"')[1].split('>', 1)[1].split('<')[0]
        )
        self.assertEqual(boot['tax_rate'], 15.0)


class POSAccessTests(TestCase):
    """The terminal endpoints must not be open to anonymous users."""

    def test_endpoints_require_login(self):
        for name in ['pos_hold_list', 'pos_drawer_status', 'pos_repeat_last',
                     'pos_customer_search']:
            res = self.client.get(reverse(f'inventory:{name}'))
            self.assertIn(res.status_code, (302, 403), f'{name} was reachable anonymously')

    def test_terminal_requires_permission(self):
        """A logged-in user without add_possale cannot ring up a sale."""
        user = User.objects.create_user('clerk', password='pw')
        self.client.force_login(user)
        res = self.client.get(reverse('inventory:pos_dashboard'))
        self.assertEqual(res.status_code, 403)
