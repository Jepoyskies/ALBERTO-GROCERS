from django.db import migrations

def create_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Define roles and their corresponding permission codenames
    roles = {
        'Manager': [
            # Products & Categories
            'view_product', 'add_product', 'change_product', 'delete_product',
            'view_category', 'add_category', 'change_category', 'delete_category',
            # Suppliers & Procurement
            'view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier',
            'view_purchaseorder', 'add_purchaseorder', 'change_purchaseorder', 'delete_purchaseorder',
            # Expenses
            'view_expense', 'add_expense', 'change_expense', 'delete_expense',
            'view_expensecategory', 'add_expensecategory', 'change_expensecategory',
            # Transactions & Adjustments
            'view_stocktransaction', 'add_stocktransaction', 'can_adjust_stock',
            # Reporting
            'can_view_reports', 'can_view_history',
            # POS & SOW (Managers usually oversee these)
            'view_possale', 'add_possale', 'view_priceoverridelog',
            'view_hydraulicsow', 'add_hydraulicsow', 'change_hydraulicsow',
            # Customers & Payments
            'view_customer', 'add_customer', 'change_customer',
            'view_customerpayment', 'add_customerpayment',
        ],
        'Salesman': [
            # Point of Sale
            'view_possale', 'add_possale', 'view_priceoverridelog',
            # Service Orders (Hydraulic SOW)
            'view_hydraulicsow', 'add_hydraulicsow', 'change_hydraulicsow',
            # Customer Management
            'view_customer', 'add_customer', 'change_customer',
            # Payments
            'view_customerpayment', 'add_customerpayment',
            # Stock Inquiry (Read-only)
            'view_product', 'view_category',
            'can_adjust_stock',
        ],
    }

    for role_name, permissions in roles.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        
        # Get permissions objects
        perms_to_add = Permission.objects.filter(codename__in=permissions)
        
        # Assign permissions to the group
        group.permissions.set(perms_to_add)

def remove_default_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Manager', 'Salesman']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0029_possale_has_price_override_priceoverridelog'),
        ('auth', '__latest__'),
        ('contenttypes', '__latest__'),
    ]

    operations = [
        migrations.RunPython(create_default_groups, reverse_code=remove_default_groups),
    ]
