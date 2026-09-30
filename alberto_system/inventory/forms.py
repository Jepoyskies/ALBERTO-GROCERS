"""
Django forms for the inventory application.
Handles data validation, widget styling (Bootstrap 5), and custom form logic
for products, customers, transactions, and reporting.
"""

import datetime
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.forms import DateInput, ModelChoiceField
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce

from .models import (
    Product, StockTransaction, Category, Supplier, PurchaseOrder, 
    Expense, ExpenseCategory, POSSale, Customer, CustomerPayment
)


# --- CUSTOMER MANAGEMENT FORMS ---

class CustomerForm(forms.ModelForm):
    """Form for registering and updating Customer billing details."""
    
    class Meta:
        model = Customer
        fields =['name', 'email', 'phone', 'address', 'tax_id']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Physical Address'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'TIN / Tax ID'}),
        }



class CustomerPaymentForm(forms.ModelForm):
    """
    Form for recording payments made by customers.
    Dynamically filters the `sale_paid` field to only show unpaid credit sales.
    """
    sale_paid = ModelChoiceField(
        queryset=POSSale.objects.none(),
        required=False,
        label="Apply to Invoice",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="-- General Payment --"
    )

    class Meta:
        model = CustomerPayment
        fields =['sale_paid', 'amount', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Payment details...'}),
        }

    def __init__(self, *args, **kwargs):
        customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        
        if customer:
            # Get all credit sales for the customer that are not fully paid and not cancelled
            unpaid_sales = POSSale.objects.filter(
                customer=customer,
                payment_method='CREDIT'
            ).exclude(status='CANCELLED').annotate(
                paid_amount=Coalesce(Sum('payments_received__amount'), Value(0, output_field=DecimalField()))
            ).annotate(
                outstanding=F('total_amount') - F('paid_amount')
            ).filter(
                outstanding__gte=Decimal('0.01')  # Consider paid if outstanding is less than 1 cent.
            )

            self.fields['sale_paid'].queryset = unpaid_sales
            self.fields['sale_paid'].label_from_instance = lambda obj: f"{obj.receipt_id} (Outstanding: {obj.outstanding:,.2f})"


# --- PRODUCT MANAGEMENT FORMS ---

class ProductCreateForm(forms.ModelForm):
    """Form to add a new product into the inventory system."""
    
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'image', 'price', 'reorder_level']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class ProductUpdateForm(forms.ModelForm):
    """Form to update existing products, including status modifications."""
    
    class Meta:
        model = Product
        fields = ['name', 'sku', 'category', 'image', 'price', 'reorder_level', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


# --- TRANSACTION FORMS ---

class StockTransactionForm(forms.ModelForm):
    """General form for administrators to manually adjust stock."""
    
    class Meta:
        model = StockTransaction
        fields = ['transaction_type', 'transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class StockOutForm(forms.ModelForm):
    """
    Strictly for REMOVING stock (Sales, Damage, Internal Use).
    Automatically filters out transaction reasons that would add stock.
    """
    
    class Meta:
        model = StockTransaction
        fields = ['transaction_reason', 'quantity', 'notes']
        widgets = {
            'transaction_reason': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g. Customer Name, Invoice #, or Reason for Damage'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude reasons that don't make sense for a manual Stock Out
        excluded_reasons =[
            StockTransaction.TransactionReason.PURCHASE_ORDER,
            StockTransaction.TransactionReason.RETURN,
            StockTransaction.TransactionReason.INITIAL,
            StockTransaction.TransactionReason.SALE
        ]
        valid_choices = [c for c in StockTransaction.TransactionReason.choices if c[0] not in excluded_reasons]
        self.fields['transaction_reason'].choices = valid_choices


class RefundForm(forms.ModelForm):
    """Strictly for ADDING stock back into inventory from a Customer Return."""
    
    pos_sale = forms.ModelChoiceField(
        queryset=POSSale.objects.none(),
        label="Receipt ID",
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Receipt..."
    )
    
    class Meta:
        model = StockTransaction
        fields = ['pos_sale', 'quantity', 'notes']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for return (REQUIRED: e.g. Defective, Wrong Item)'}),
        }

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        self.fields['notes'].required = True
        if product:
            self.fields['pos_sale'].queryset = POSSale.objects.filter(
                items__product=product,
                items__transaction_type='OUT',
                items__transaction_reason=StockTransaction.TransactionReason.SALE
            ).distinct().order_by('-timestamp')
            
            self.fields['pos_sale'].label_from_instance = lambda obj: f"{obj.receipt_id} - {obj.timestamp.strftime('%b %d, %Y')}"


# --- SEARCH/FILTER FORMS ---

class CustomerFilterForm(forms.Form):
    """Search functionality for the customer database."""
    q = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search Name, ID, Email, Phone...'})
    )


class ProductFilterForm(forms.Form):
    """Advanced filtering and sorting options for the product catalog."""
    
    STOCK_STATUS_CHOICES = (
        ("", "All Stock Levels"), 
        ("in_stock", "In Stock (>10)"), 
        ("low_stock", "Low Stock (1-10)"), 
        ("out_of_stock", "Out of Stock")
    )
    PRODUCT_STATUS_CHOICES = (
        ("ACTIVE", "Active"), 
        ("DEACTIVATED", "Deactivated"), 
        ("", "All Statuses")
    )
    SORT_BY_CHOICES = (
        ("-date_created", "Newest First"), 
        ("date_created", "Oldest First"), 
        ("name", "Name (A-Z)"), 
        ("-name", "Name (Z-A)"), 
        ("price", "Price (Low to High)"), 
        ("-price", "Price (High to Low)")
    )
    
    q = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search Name or SKU...'})
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        required=False, 
        label="Category", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Category...'})
    )
    
    stock_status = forms.ChoiceField(
        choices=STOCK_STATUS_CHOICES, 
        required=False, 
        label="Stock Level", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    product_status = forms.ChoiceField(
        choices=PRODUCT_STATUS_CHOICES, 
        required=False, 
        label="Product Status", 
        initial='ACTIVE', 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sort_by = forms.ChoiceField(
        choices=SORT_BY_CHOICES, 
        required=False, 
        label="Sort By", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class TransactionFilterForm(forms.Form):
    """Filters for analyzing stock transactions and adjustments."""
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    transaction_type = forms.ChoiceField(
        choices=(("", "All Types"), ("IN", "Stock In"), ("OUT", "Stock Out")), 
        required=False, 
        label="Type", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    transaction_reason = forms.ChoiceField(
        choices=[], 
        required=False, 
        label="Reason", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    start_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_reason'].choices = [('', 'All Reasons')] + list(StockTransaction.TransactionReason.choices)


class ProductHistoryFilterForm(forms.Form):
    """Filters for auditing product model changes via SimpleHistory."""
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(), 
        required=False, 
        label="Product", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Product...'})
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all(), 
        required=False, 
        label="User", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select User...'})
    )
    action = forms.ChoiceField(
        choices=[
            ('', 'All Actions'), 
            ('+', 'Created'), 
            ('-', 'Deleted'),
            ('~', 'Updated'),
        ],
        required=False,
        label="Action",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )


class PurchaseOrderFilterForm(forms.Form):
    """Search functionality for procurement and supplier orders."""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(), 
        required=False, 
        label="Supplier", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'Select Supplier...'})
    )
    status = forms.ChoiceField(
        choices=[], 
        required=False, 
        label="Status", 
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = (("", "All Statuses"),) + PurchaseOrder.STATUS_CHOICES


# --- REPORTING FORMS ---

class TransactionReportForm(forms.Form):
    """Date range filtering for general transaction reports."""
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))


class AnalyticsFilterForm(forms.Form):
    """Month and Year selection for the Analytics Dashboard."""
    month = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    year = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        months =[
            ('', 'All Months'),
            ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
            ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
            ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
        ]
        self.fields['month'].choices = months
        
        current_year = datetime.date.today().year
        years =[(str(y), str(y)) for y in range(current_year - 2, current_year + 3)]
        self.fields['year'].choices = years


# --- MISC FORMS ---

class CategoryCreateForm(forms.ModelForm):
    """Quick inline form to generate product categories."""
    class Meta:
        model = Category
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'form-control'})}


# --- EXPENSE FORMS ---

class ExpenseForm(forms.ModelForm):
    """Form to record company expenses with automated category creation."""
    category = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category'}),
        label="Category"
    )

    class Meta:
        model = Expense
        fields =['category', 'description', 'amount', 'expense_date', 'receipt']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'expense_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'receipt': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.target_month = kwargs.pop('target_month', None)
        self.target_year = kwargs.pop('target_year', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.category:
            self.initial['category'] = self.instance.category.name

    def clean_category(self):
        name = self.cleaned_data.get('category')
        if name:
            category, _ = ExpenseCategory.objects.get_or_create(name=name.strip())
            return category
        return None

    def clean_expense_date(self):
        date = self.cleaned_data.get('expense_date')
        if date and self.target_year:
            try:
                t_year = int(self.target_year)
                if date.year != t_year:
                    raise forms.ValidationError(f"Expense date must be within {t_year}.")
                
                if self.target_month:
                    t_month = int(self.target_month)
                    if date.month != t_month:
                        month_name = datetime.date(t_year, t_month, 1).strftime('%B')
                        raise forms.ValidationError(f"Expense date must be within {month_name} {t_year}.")
            except (ValueError, TypeError):
                pass
        return date


class ExpenseFilterForm(forms.Form):
    """Filters to query expense records by description, category, or date."""
    q = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search description...'})
    )
    category = forms.ModelChoiceField(
        queryset=ExpenseCategory.objects.all(), 
        required=False, 
        label="Category", 
        widget=forms.Select(attrs={'class': 'form-select searchable-select', 'placeholder': 'All Categories'})
    )
    month = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    year = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        months =[
            ('', 'All Months'),
            ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
            ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
            ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
        ]
        self.fields['month'].choices = months
        
        current_year = datetime.date.today().year
        years =[(str(y), str(y)) for y in range(current_year - 2, current_year + 3)]
        self.fields['year'].choices = years