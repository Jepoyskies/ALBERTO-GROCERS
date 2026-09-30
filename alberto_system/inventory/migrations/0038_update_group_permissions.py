from django.db import migrations

def update_group_permissions(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Manager: Expanded to cover all operations except system settings
    # Manager: Full access to all Inventory operations
    manager_perms = [
        'add_cancellationreason', 'change_cancellationreason', 'delete_cancellationreason', 'view_cancellationreason',
        'add_category', 'change_category', 'delete_category', 'view_category',
        'add_customer', 'change_customer', 'delete_customer', 'view_customer',
        'add_customerpayment', 'change_customerpayment', 'delete_customerpayment', 'view_customerpayment',
        'add_expense', 'change_expense', 'delete_expense', 'view_expense',
        'add_expensecategory', 'change_expensecategory', 'delete_expensecategory', 'view_expensecategory',
        'add_hydraulicsow', 'change_hydraulicsow', 'delete_hydraulicsow', 'view_hydraulicsow',
        'add_possale', 'change_possale', 'delete_possale', 'view_possale',
        'add_priceoverridelog', 'change_priceoverridelog', 'delete_priceoverridelog', 'view_priceoverridelog',
        'add_product', 'change_product', 'delete_product', 'view_product',
        'add_purchaseorder', 'change_purchaseorder', 'delete_purchaseorder', 'view_purchaseorder',
        'add_purchaseorderitem', 'change_purchaseorderitem', 'delete_purchaseorderitem', 'view_purchaseorderitem',
        'add_stocktransaction', 'change_stocktransaction', 'delete_stocktransaction', 'view_stocktransaction',
        'add_supplier', 'change_supplier', 'delete_supplier', 'view_supplier',
        'can_adjust_stock', 'can_view_reports', 'can_view_history',
    ]

    # Salesman: Focus on operational transaction processing
    salesman_perms = [
        'view_possale', 'add_possale', 'delete_possale', 'view_priceoverridelog',
        'view_hydraulicsow', 'add_hydraulicsow', 'change_hydraulicsow',
        'view_customer', 'change_customer',
        'view_customerpayment', 'add_customerpayment',
        'view_product', 'view_category', 'can_adjust_stock', 'view_cancellationreason'
    ]

    # Map roles to their updated permissions
    config = {
        'Manager': manager_perms,
        'Salesman': salesman_perms,
    }

    for role_name, perms in config.items():
        try:
            group = Group.objects.get(name=role_name)
            # Find the permissions objects
            perms_to_add = Permission.objects.filter(codename__in=perms)
            group.permissions.set(perms_to_add)
        except Group.DoesNotExist:
            continue

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0037_merge_20260510_1907'),
    ]

    operations = [
        migrations.RunPython(update_group_permissions),
    ]
