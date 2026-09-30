"""
Django admin configuration for the inventory application.
Registers models and customizes the admin interface for easy management.
"""

from decimal import Decimal

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

from core.cache_utils import clear_dashboard_cache

from .models import (
    Category, Customer, CustomerPayment, Expense, ExpenseCategory,
    POSSale, PriceOverrideLog, CancellationReason, Product, PurchaseOrder,
    PurchaseOrderItem, StockTransaction, Supplier
)

@admin.register(CancellationReason)
class CancellationReasonAdmin(admin.ModelAdmin):
    list_display = ('pos_sale', 'reason', 'cancelled_by', 'timestamp')
    search_fields = ('pos_sale__receipt_id', 'reason', 'cancelled_by__username')
    list_filter = ('timestamp', 'cancelled_by')
    readonly_fields = ('timestamp',)

admin.site.site_header = "Alberto Grocers Admin"
admin.site.site_title = "Alberto Grocers Admin Portal"
admin.site.index_title = "Welcome to Alberto Grocers Inventory Portal"


# --- Core Inventory ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Category model.
    Manages display, search, and slug pre-population for categories.
    """
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


class StockTransactionInline(admin.TabularInline):
    """Inline view for viewing Stock Transactions within related models."""
    model = StockTransaction
    extra = 0
    fields = ('product', 'quantity', 'selling_price', 'transaction_type', 'transaction_reason')
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    """
    Admin configuration for the Product model, including historical tracking.
    Manages product display, filtering, searching, and cache clearing on changes.
    Quantity is read-only on change forms and excluded on add forms.
    """
    list_display = ('name', 'sku', 'category', 'price', 'quantity', 'status', 'last_edited_on')
    list_filter = ('status', 'category', 'date_updated')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('status', 'price')
    history_list_display = ["status", "quantity", "price"]
    autocomplete_fields = ('category',)
    list_per_page = 25

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_dashboard_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        clear_dashboard_cache()

    def get_readonly_fields(self, request, obj=None):
        if obj: # On the change form, make quantity readonly
            return ('quantity',)
        return () # On the add form, it's not readonly (but will be excluded)

    def get_exclude(self, request, obj=None):
        if obj is None: # On the add form, exclude quantity
            return ('quantity',)
        return () # On the change form, do not exclude it

    @admin.display(description='Last Edited On')
    def last_edited_on(self, obj):
        last_record = obj.history.first()
        if last_record:
            return last_record.history_date.strftime('%Y-%m-%d %H:%M')
        return "N/A"


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the StockTransaction model.
    Manages display, filtering, and searching for stock movements.
    Restores stock on deletion.
    """
    list_display = ('timestamp', 'product', 'transaction_type', 'transaction_reason', 'quantity', 'user', 'pos_sale')
    list_filter = ('transaction_type', 'transaction_reason', 'timestamp')
    search_fields = ('product__name', 'pos_sale__receipt_id', 'notes', 'user__username')
    autocomplete_fields = ('product', 'user', 'pos_sale')
    date_hierarchy = 'timestamp'
    list_per_page = 50

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_dashboard_cache()

    def delete_model(self, request, obj):
        # Restore stock if a transaction is manually deleted
        with transaction.atomic():
            product = obj.product
            if obj.transaction_type == 'IN':
                product.quantity -= obj.quantity
            else:
                product.quantity += obj.quantity
            product.save()
            super().delete_model(request, obj)
            clear_dashboard_cache()

    def has_add_permission(self, request):
        return False

# --- Proxy Model for Refund History ---
class RefundHistory(StockTransaction):
    class Meta:
        proxy = True
        verbose_name = "Refund History"
        verbose_name_plural = "Refund History"

@admin.register(RefundHistory)
class RefundHistoryAdmin(admin.ModelAdmin):
    """
    Admin configuration specifically for Refund History.
    """
    def get_queryset(self, request):
        return RefundHistory.objects.filter(transaction_reason='RETURN')

    list_display = ('timestamp', 'product', 'quantity', 'pos_sale', 'user', 'notes')
    list_filter = ('timestamp', 'user')
    search_fields = ('product__name', 'pos_sale__receipt_id', 'notes')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


# --- Customer Relationship Management ---

class CustomerPaymentInline(admin.TabularInline):
    """Inline view for viewing Customer Payments."""
    model = CustomerPayment
    extra = 0
    fields = ('payment_date', 'amount', 'reference_number', 'notes')
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CustomerSaleInline(admin.TabularInline):
    """Inline view for viewing POS Sales within the Customer admin."""
    model = POSSale
    extra = 0
    fields = ('receipt_id', 'timestamp', 'total_amount', 'payment_method', 'status')
    readonly_fields = fields
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Customer model.
    Displays customer information, allows searching, and shows current balance.
    Includes inlines for Customer Payments and POS Sales.
    """
    list_display = ('name', 'customer_id', 'email', 'phone', 'current_balance_display')
    search_fields = ('name', 'customer_id', 'email', 'phone', 'tax_id')
    exclude = ('credit_limit',)
    inlines =[CustomerPaymentInline, CustomerSaleInline]
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25

    def get_queryset(self, request):
        # Optimized to avoid Cartesian product issues when summing multiple relations
        qs = super().get_queryset(request)
        
        credit_sales_subquery = POSSale.objects.filter(
            customer=OuterRef('pk'),
            payment_method='CREDIT'
        ).values('customer').annotate(
            total=Sum('total_amount')
        ).values('total')

        payments_subquery = CustomerPayment.objects.filter(
            customer=OuterRef('pk')
        ).values('customer').annotate(
            total=Sum('amount')
        ).values('total')

        return qs.annotate(
            _total_credit_sales=Coalesce(Subquery(credit_sales_subquery), Decimal('0.00'), output_field=DecimalField()),
            _total_payments_made=Coalesce(Subquery(payments_subquery), Decimal('0.00'), output_field=DecimalField())
        ).annotate(
            _balance=F('_total_credit_sales') - F('_total_payments_made')
        )

    @admin.display(description='Current Balance', ordering='_balance')
    def current_balance_display(self, obj):
        return f"{obj._balance:,.2f}"


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CustomerPayment model.
    Manages display, filtering, searching, and autocomplete fields for customer payments.
    Clears dashboard cache on save.
    """
    list_display = ('customer', 'amount', 'payment_date', 'reference_number', 'sale_paid', 'recorded_by')
    list_filter = ('payment_date', 'recorded_by')
    search_fields = ('customer__name', 'reference_number', 'sale_paid__receipt_id', 'notes')
    autocomplete_fields = ('customer', 'sale_paid', 'recorded_by')
    date_hierarchy = 'payment_date'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_dashboard_cache()


# --- Point of Sale ---

@admin.register(POSSale)
class POSSaleAdmin(admin.ModelAdmin):
    """
    Admin configuration for the POSSale model.
    Manages display, filtering, and searching for Point-of-Sale transactions.
    Includes stock transaction inlines and restores stock on sale deletion.
    Prevents direct addition or modification of sales via admin.
    """
    list_display = ('receipt_id', 'timestamp', 'customer', 'total_amount', 'payment_method', 'cashier', 'notes', 'has_price_override')
    list_filter = ('payment_method', 'has_price_override', 'timestamp', 'cashier')
    search_fields = ('receipt_id', 'customer__name', 'notes')
    inlines = [StockTransactionInline]
    autocomplete_fields = ('customer', 'cashier')
    date_hierarchy = 'timestamp'
    list_per_page = 50

    def delete_model(self, request, obj):
        # Crucial: Restore stock when a sale is deleted from the admin
        with transaction.atomic():
            for item in obj.items.all():
                product = item.product
                product.quantity += item.quantity
                product.save()
            super().delete_model(request, obj)
            clear_dashboard_cache()

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PriceOverrideLog)
class PriceOverrideLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for the PriceOverrideLog model.
    Displays read-only price override details, allowing filtering and searching.
    Prevents adding, changing, or deleting log entries via admin.
    """
    list_display = ('timestamp', 'pos_sale', 'product', 'salesman', 'original_price', 'override_price', 'price_difference')
    list_filter = ('timestamp', 'salesman')
    search_fields = ('pos_sale__receipt_id', 'product__name', 'salesman__username', 'reason')
    date_hierarchy = 'timestamp'
    readonly_fields = ('pos_sale', 'product', 'salesman', 'original_price', 'override_price', 'reason', 'timestamp')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# --- Suppliers & Purchasing ---

class PurchaseOrderItemInline(admin.TabularInline):
    """Inline view for adding items directly to a Purchase Order."""
    model = PurchaseOrderItem
    extra = 1
    autocomplete_fields = ['product']
    readonly_fields = ('line_total_display',) # price is NOT readonly so it can be edited/set
    fields = ('product', 'quantity', 'price', 'line_total_display')

    def line_total_display(self, instance):
        if instance.pk:
            return f"{instance.line_total:,.2f}"
        return "-"
    line_total_display.short_description = "Total Amount"


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Supplier model.
    Manages display and searching for supplier information.
    """
    list_display = ('name', 'supplier_id', 'contact_person', 'email', 'phone')
    search_fields = ('name', 'supplier_id', 'contact_person', 'email', 'phone')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """
    Admin configuration for the PurchaseOrder model.
    Manages display, filtering, searching, and inlines for purchase order items.
    Includes logic for stock-in upon status change to 'RECEIVED'.
    """
    list_display = ('order_id', 'supplier', 'order_date', 'status')
    list_filter = ('status', 'order_date')
    search_fields = ('order_id', 'supplier__name')
    inlines = [PurchaseOrderItemInline]
    date_hierarchy = 'order_date'
    autocomplete_fields = ('supplier',)
    actions = ['receive_purchase_order']

    def receive_purchase_order(self, request, queryset):
        """Admin action to receive selected purchase orders."""
        received_count = 0
        for po in queryset:
            if po.status != 'RECEIVED':
                po.complete_order(request.user)
                received_count += 1
        
        if received_count:
            self.message_user(request, f"{received_count} purchase order(s) successfully received.")
            clear_dashboard_cache()
        else:
            self.message_user(request, "Selected purchase order(s) already received or could not be processed.", level='warning')
    
    receive_purchase_order.short_description = "Receive Selected Purchase Orders"

    class Media:
        js = (
            'admin/js/vendor/jquery/jquery.min.js',
            'admin/js/jquery.init.js',
            'inventory/js/purchase_order_admin.js',
        )

    def save_model(self, request, obj, form, change):
        if change:
            # Detect if status was changed to RECEIVED in the admin
            original = PurchaseOrder.objects.get(pk=obj.pk)
            if original.status != 'RECEIVED' and obj.status == 'RECEIVED':
                # Trigger the stock-in logic
                obj.status = original.status # Temporarily revert to trigger correctly
                obj.complete_order(request.user)
                clear_dashboard_cache()
                return # complete_order handles the save
        
        super().save_model(request, obj, form, change)
        clear_dashboard_cache()


# --- Expenses ---

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the ExpenseCategory model.
    Manages display and searching for expense categories.
    """
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Expense model.
    Manages display, filtering, searching, and autocomplete fields for expenses.
    Clears dashboard cache on save and delete.
    """
    list_display = ('expense_date', 'description', 'category', 'amount', 'recorded_by')
    list_filter = ('category', 'expense_date', 'recorded_by')
    search_fields = ('description', 'category__name', 'recorded_by__username')
    autocomplete_fields = ('category', 'recorded_by')
    date_hierarchy = 'expense_date'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_dashboard_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        clear_dashboard_cache()


# --- User & Group Management (Simplified for Owner) ---

# Robustly unregister default models
if admin.site.is_registered(User):
    admin.site.unregister(User)
if admin.site.is_registered(Group):
    admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin that makes role (Group) assignment easier.
    Permissions are moved to a collapsed section.
    """
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_groups')
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = 'Roles (Groups)'

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Roles & Access', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
            'description': 'Assign user to a Group (e.g., Manager, Salesman) to grant permissions automatically.'
        }),
        ('Advanced Permissions', {
            'classes': ('collapse',),
            'fields': ('user_permissions',),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    """
    Custom GroupAdmin with filter_horizontal for permissions.
    """
    filter_horizontal = ('permissions',)