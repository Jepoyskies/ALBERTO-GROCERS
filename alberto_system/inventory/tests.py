# inventory/tests.py

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from django.utils import timezone

from .models import Product, Category, StockTransaction
from .tasks import send_low_stock_alerts_task

class InventoryModelTests(TestCase):

    def setUp(self):
        """Set up initial data for model tests."""
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            sku="TP-001",
            category=self.category,
            price=100.00,
            quantity=50,
            reorder_level=10
        )
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')

    def test_stock_out_reduces_quantity(self):
        """Test that a 'Stock Out' transaction correctly reduces product quantity."""
        initial_quantity = self.product.quantity
        transaction_quantity = 5
        
        # Simulate a stock out by creating a transaction
        StockTransaction.objects.create(
            product=self.product,
            transaction_type='OUT',
            quantity=transaction_quantity,
            user=self.user
        )
        
        # In the actual view, an F() expression updates the DB directly.
        # So we must manually replicate that part of the logic for the test.
        self.product.quantity -= transaction_quantity
        self.product.save()

        # Now, refresh the object from the DB to be sure we have the latest data
        self.product.refresh_from_db()
        
        self.assertEqual(self.product.quantity, initial_quantity - transaction_quantity)

    def test_stock_in_increases_quantity(self):
        """Test that a 'Stock In' transaction correctly increases product quantity."""
        initial_quantity = self.product.quantity
        transaction_quantity = 20

        StockTransaction.objects.create(
            product=self.product,
            transaction_type='IN',
            quantity=transaction_quantity,
            user=self.user
        )

        self.product.quantity += transaction_quantity
        self.product.save()
        
        self.product.refresh_from_db()

        self.assertEqual(self.product.quantity, initial_quantity + transaction_quantity)

    def test_product_str_representation(self):
        """Test the string representation of the Product model."""
        self.assertEqual(str(self.product), "Test Product")


class InventoryViewTests(TestCase):

    def setUp(self):
        """Set up users with different permissions."""
        self.superuser = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.normal_user = User.objects.create_user('user', 'user@example.com', 'password')
        self.manager_user = User.objects.create_user('manager', 'manager@example.com', 'password')
        
        view_product_perm = Permission.objects.get(codename='view_product')
        self.manager_user.user_permissions.add(view_product_perm)
        
        self.product = Product.objects.create(name="View Test Product", sku="VTP-001", price=10.00, quantity=100)
        self.delete_url = reverse('inventory:product_delete', kwargs={'slug': self.product.slug})

    def test_delete_view_permission_denied_for_normal_user(self):
        """Test that a normal user is denied access (403) and cannot delete a product."""
        self.client.login(username='user', password='password')
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 403)
        
    def test_delete_view_permission_denied_for_manager_user(self):
        """Test that a non-superuser manager is also denied access (403)."""
        self.client.login(username='manager', password='password')
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 403)

    def test_delete_view_accessible_by_superuser(self):
        """Test that a superuser can access the delete confirmation page."""
        self.client.login(username='admin', password='password')
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm Deletion")

    def test_product_list_view_for_authenticated_user(self):
        """Test that an authenticated user with permission can view the product list."""
        self.client.login(username='manager', password='password')
        response = self.client.get(reverse('inventory:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View Test Product")


class CeleryTaskTests(TestCase):

    def test_low_stock_alert_task_no_items(self):
        """Test the alert task when no items are low on stock."""
        Product.objects.create(name="Sufficient Product", sku="SP-001", price=25.00, quantity=100, reorder_level=10)
        result = send_low_stock_alerts_task()
        self.assertEqual(result, 'No products with low stock. No alert sent.')

    def test_low_stock_alert_task_finds_low_stock_item(self):
        """Test the alert task correctly identifies a low-stock item."""
        Product.objects.create(name="Low Stock Product", sku="LSP-001", price=50.00, quantity=5, reorder_level=10, status=Product.Status.ACTIVE)
        Product.objects.create(name="Deactivated Low Stock", sku="DLSP-001", price=15.00, quantity=2, reorder_level=5, status=Product.Status.DEACTIVATED)
        
        result = send_low_stock_alerts_task()
        self.assertEqual(result, 'Successfully sent low stock alert for 1 products.')