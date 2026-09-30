"""
Database models for the inventory management system.
Contains data structures for customers, inventory, point of sale, and expenses.
"""

import uuid
from decimal import Decimal
from django.db import models, transaction
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from simple_history.models import HistoricalRecords
from django.core.validators import MinValueValidator
from django.db.models import Sum


# --- HELPER FUNCTIONS ---

def generate_po_number():
    """Generates a unique PO number like 'PO-1A2B3C4D'"""
    return f"PO-{uuid.uuid4().hex[:8].upper()}"


def generate_supplier_id():
    """Generates a unique Supplier ID like 'SUP-1A2B3C4D'"""
    return f"SUP-{uuid.uuid4().hex[:8].upper()}"


def generate_customer_id():
    """Generates a unique Customer ID like 'CUST-1A2B3C4D'"""
    return f"CUST-{uuid.uuid4().hex[:8].upper()}"


def generate_sow_id():
    """Generates a unique SOW ID like 'JOB-1A2B3C4D'"""
    return f"JOB-{uuid.uuid4().hex[:8].upper()}"


# --- CUSTOMER & BILLING MODELS ---

class Customer(models.Model):
    """
    Represents a client or business entity that purchases products or services.
    Tracks contact information, tax details, and financial credit limits for accounts.
    """
    customer_id = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    name = models.CharField(max_length=150, unique=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True, help_text="TIN or Tax ID")
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Maximum allowed credit balance.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def get_balance(self):
        """Calculates current outstanding balance by subtracting total payments from credit sales."""
        # Sum of credit sales (Total Amount of sales marked as CREDIT)
        # Exclude CANCELLED transactions
        credit_sales = self.purchases.filter(payment_method='CREDIT').exclude(status='CANCELLED').aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')

        # Sum of payments made
        payments = self.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        return credit_sales - payments
    def get_absolute_url(self):
        return reverse('inventory:customer_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = generate_customer_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CustomerPayment(models.Model):
    """
    Tracks payments made by customers towards their balance.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    sale_paid = models.ForeignKey('POSSale', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_received', help_text="The specific credit sale this payment is for.")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(default=timezone.now)
    reference_number = models.CharField(max_length=50, blank=True, help_text="Check No., Transaction ID, or Receipt No.")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.amount} - {self.customer.name}"


class HydraulicSow(models.Model):
    """
    Represents a Scope of Work (SOW) for custom hydraulic hose assemblies.
    Stores technical specifications such as hose type, diameter, fittings, and associated costs.
    """
    sow_id = models.CharField(max_length=20, unique=True, editable=False, null=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sows')
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    hose_type = models.CharField(max_length=100, blank=True)
    diameter = models.CharField(max_length=50, blank=True)
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pressure = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    application = models.CharField(max_length=200, blank=True)
    
    fitting_a = models.CharField(max_length=100, blank=True)
    fitting_b = models.CharField(max_length=100, blank=True)
    orientation = models.IntegerField(null=True, blank=True, help_text="Angle in degrees")
    protection = models.CharField(max_length=50, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cost of the customization service.")
    
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_created']

    def save(self, *args, **kwargs):
        if not self.sow_id:
            self.sow_id = generate_sow_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sow_id} - {self.customer.name}"


# --- EXPENSE TRACKING ---

class ExpenseCategory(models.Model):
    """
    Categories for expenses, e.g., Rent, Utilities, Supplies.
    """
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    Represents a single business expense.
    """
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    expense_date = models.DateField(default=timezone.now, db_index=True)
    receipt = models.FileField(upload_to='expense_receipts/', blank=True, null=True, help_text="Optional: Upload a receipt image or PDF.")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date']

    def __str__(self):
        return f"{self.description} - {self.amount}"


# --- CORE INVENTORY MODELS ---

class POSSale(models.Model):
    """
    Represents a single POS transaction (Receipt).
    Groups multiple StockTransactions (items) together.
    """
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        CREDIT = 'CREDIT', 'Charge/Credit'
        CARD = 'CARD', 'Card/Digital'
        GCASH = 'GCASH', 'GCash'
        BANK = 'BANK', 'Bank Transfer'

    class Status(models.TextChoices):
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        REFUNDED = 'REFUNDED', 'Refunded'

    receipt_id = models.CharField(max_length=50, unique=True, editable=False)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED)
    
    # Customer Linking
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    due_date = models.DateField(null=True, blank=True, help_text="If Credit, when is payment due?")

    # Financials
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, help_text="Transaction notes or description")
    has_price_override = models.BooleanField(default=False, help_text="Flagged if any item's price was manually lowered.")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "POS Sale"
        verbose_name_plural = "POS Sales"

    def __str__(self):
        return f"Receipt #{self.receipt_id}"


class Category(models.Model):
    """
    Used to logically group related products together for easier filtering, 
    inventory management, and reporting.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        
    def __str__(self):
        return self.name
        
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


from cloudinary.models import CloudinaryField

class Product(models.Model):
    """
    The core inventory item. Tracks current stock quantity, pricing, and active status.
    Includes a SimpleHistory tracker to monitor all modifications for auditing purposes.
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DEACTIVATED = 'DEACTIVATED', 'Deactivated'

    image = CloudinaryField('image', blank=True, null=True)
    name = models.CharField(max_length=200, unique=True, help_text='Enter the product name', db_index=True)
    sku = models.CharField(max_length=100, unique=True, help_text='Enter the Stock Keeping Unit (SKU)', db_index=True)
    
    slug = models.SlugField(max_length=200, unique=True, blank=True, help_text='Unique URL-friendly name, leave blank to auto-generate')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text='Enter the price in PHP',
        validators=[MinValueValidator(Decimal('0.00'))] 
    )
    
    quantity = models.PositiveIntegerField(default=0, help_text='Enter the available quantity')
    reorder_level = models.PositiveIntegerField(default=5, help_text="Automatically alert when stock quantity falls to this level.")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    last_purchase_date = models.DateTimeField(null=True, blank=True, help_text="Date this product was last restocked.")

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['-date_created']
        
    def get_absolute_url(self):
        return reverse('inventory:product_detail', kwargs={'slug': self.slug})
        
    def save(self, *args, **kwargs):
        if not self.slug:
            slug_base = slugify(self.name)
            slug = slug_base
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{slug_base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.name


class StockTransaction(models.Model):
    """
    Records every individual instance of stock moving in or out of the system.
    Provides an audit trail for stock modifications.
    """
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'
    
    class TransactionReason(models.TextChoices):
        SALE = 'SALE', 'Sale (Revenue)'
        PURCHASE_ORDER = 'PO', 'Purchase Order (Restock)'
        DAMAGE = 'DAMAGE', 'Damaged / Expired (Loss)'
        INTERNAL = 'INTERNAL', 'Internal Use / Demo'
        CORRECTION = 'CORRECTION', 'Inventory Correction / Mistake'
        RETURN = 'RETURN', 'Customer Return'
        INITIAL = 'INITIAL', 'Initial Stock'
        OTHER = 'OTHER', 'Other'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    
    # Linked POS Sale (Optional)
    pos_sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    transaction_reason = models.CharField(max_length=20, choices=TransactionReason.choices, default=TransactionReason.SALE)
    
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True, null=True, help_text="Reason for the transaction")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    selling_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Price per item at the time of a 'Stock Out' transaction.",
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        ordering = ['-timestamp', '-id']
        permissions =[
            ("can_adjust_stock", "Can adjust stock quantities"),
            ("can_view_history", "Can view product edit history"),
            ("can_view_reports", "Can view and generate reports"),
        ]
        indexes =[
            models.Index(fields=['transaction_type', 'timestamp']),
            models.Index(fields=['transaction_reason']),
        ]

    def __str__(self):
        return f'{self.transaction_type} ({self.get_transaction_reason_display()}) - {self.product.name}'


class PriceOverrideLog(models.Model):
    """
    Logs instances where a product's price was manually lowered in the POS.
    """
    pos_sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, related_name='price_overrides')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='price_overrides')
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    override_price = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255, default='Not provided', help_text="Reason for the price change.")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Price Override Log"
        verbose_name_plural = "Price Override Logs"

    def __str__(self):
        return f"Override on {self.product.name} in Sale {self.pos_sale.receipt_id}"

    @property
    def price_difference(self):
        return self.original_price - self.override_price


class CancellationReason(models.Model):
    pos_sale = models.OneToOneField(POSSale, on_delete=models.CASCADE, related_name='cancellation_reason')
    reason = models.TextField(help_text='Reason for cancelling the debt.')
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Cancellation Reason"
        verbose_name_plural = "Cancellation Reasons"

    def __str__(self):
        return f"Reason for {self.pos_sale.receipt_id}: {self.reason[:50]}"


class Supplier(models.Model):
    """
    Vendors or manufacturers that provide products for the business.
    """
    supplier_id = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    
    def get_absolute_url(self):
        return reverse('inventory:supplier_detail', kwargs={'pk': self.pk})

    def save(self, *args, **kwargs):
        if not self.supplier_id:
            self.supplier_id = generate_supplier_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """
    Tracks orders placed with suppliers for restocking products.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending (In Delivery)'),
        ('COMPLETED', 'Arrived (Ready to Receive)'),
        ('RECEIVED', 'Received & Stocked'),
        ('CANCELED', 'Canceled'),
    )
    
    order_id = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False,
        null=True
    )
    
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    def get_absolute_url(self):
        return reverse('inventory:purchaseorder_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.order_id} from {self.supplier.name}"

    def save(self, *args, **kwargs):
        """Overrides save to auto-generate PO number if not present."""
        if not self.order_id:
            self.order_id = generate_po_number()
        super().save(*args, **kwargs)

    def complete_order(self, user):
        """Processes a received PO by automatically adding items into stock."""
        if self.status == 'RECEIVED':
            return 

        with transaction.atomic():
            self.status = 'RECEIVED'
            self.save()

            PurchaseOrderReceiptLog.objects.create(
                purchase_order=self,
                received_by=user,
                notes=f"Automatically received via system action."
            )

            for item in self.items.all():
                product = item.product
                
                StockTransaction.objects.create(
                    product=product,
                    transaction_type='IN',
                    transaction_reason=StockTransaction.TransactionReason.PURCHASE_ORDER,
                    quantity=item.quantity,
                    user=user,
                    notes=f'Received from Purchase Order {self.order_id}'
                )
                
                product.quantity += item.quantity
                product.last_purchase_date = timezone.now()
                product.save()


class PurchaseOrderItem(models.Model):
    """
    Individual items included within a specific Purchase Order.
    """
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Price per item in PHP at time of purchase",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    @property
    def line_total(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"


class PurchaseOrderReceiptLog(models.Model):
    """
    Tracks the audit history of when a Purchase Order was received.
    """
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='receipt_logs')
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Any additional notes about the receipt.")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Purchase Order Receipt Log"
        verbose_name_plural = "Purchase Order Receipt Logs"

    def __str__(self):
        return f"PO {self.purchase_order.order_id} received by {self.received_by} on {self.timestamp}"