"""
Data serializers for the inventory API.
Converts complex Django database models into native Python datatypes 
that can be easily rendered into JSON for the frontend POS and external clients.
"""

from rest_framework import serializers

from .models import (
    Product, Category, Customer, CustomerPayment, 
    HydraulicSow, POSSale, Expense, ExpenseCategory
)


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for the Product model.
    Exposes core product details for the POS interface and inventory APIs.
    """
    class Meta:
        model = Product
        fields =['id', 'name', 'sku', 'price', 'quantity', 'date_created', 'date_updated']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for the product Category model."""
    class Meta:
        model = Category
        fields = '__all__'


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for the Customer billing profile model."""
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ['id', 'customer_id', 'name', 'email', 'phone', 'address', 'tax_id', 'created_at', 'updated_at', 'balance']

    def get_balance(self, obj):
        return obj.get_balance()


class CustomerPaymentSerializer(serializers.ModelSerializer):
    """Serializer for tracking Customer Payments."""
    class Meta:
        model = CustomerPayment
        fields = '__all__'


class HydraulicSowSerializer(serializers.ModelSerializer):
    """Serializer for Hydraulic Scope of Work (SOW) custom jobs."""
    class Meta:
        model = HydraulicSow
        fields = '__all__'


class ProductInventorySerializer(serializers.ModelSerializer):
    """Includes low-stock indicators for frontend health dashboards."""
    is_low_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'price', 'quantity', 'is_low_stock']
        
    def get_is_low_stock(self, obj):
        return obj.quantity <= 10


class POSSaleSerializer(serializers.ModelSerializer):
    """Enhanced POSSale serializer exposing new status fields and audit-relevant info."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    cashier_name = serializers.CharField(source='cashier.username', read_only=True)
    
    class Meta:
        model = POSSale
        fields = [
            'id', 'receipt_id', 'timestamp', 'customer_name', 'cashier_name',
            'payment_method', 'total_amount', 'amount_paid', 'status', 'notes'
        ]
        read_only_fields = fields


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for company Expense records."""
    class Meta:
        model = Expense
        fields = '__all__'


class ExpenseCategorySerializer(serializers.ModelSerializer):
    """Serializer for Expense Categories."""
    class Meta:
        model = ExpenseCategory
        fields = '__all__'