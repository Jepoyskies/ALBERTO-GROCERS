"""
App configuration for the Inventory module.

This file configures the inventory application and connects signals,
such as automatically creating default user groups and permissions 
after database migrations are applied.
"""

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class InventoryConfig(AppConfig):
    """Configuration class for the inventory application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        """
        Executes when the application is fully loaded.
        Connects the post_migrate signal to the setup_default_roles function.
        """
        post_migrate.connect(setup_default_roles, sender=self)


def setup_default_roles(sender, **kwargs):
    """
    Signal receiver triggered automatically after migrations. 
    Ensures default roles ('Manager', 'Salesman') exist and assigns 
    the necessary application permissions to them.
    """
    from django.contrib.auth.models import Group, Permission
    
    roles = {
        'Manager':[
            'view_product', 'add_product', 'change_product', 'delete_product',
            'view_category', 'add_category', 'change_category', 'delete_category',
            'view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier',
            'view_purchaseorder', 'add_purchaseorder', 'change_purchaseorder', 'delete_purchaseorder',
            'view_expense', 'add_expense', 'change_expense', 'delete_expense',
            'view_expensecategory', 'add_expensecategory', 'change_expensecategory', 'delete_expensecategory',
            'view_stocktransaction', 'add_stocktransaction', 'change_stocktransaction', 'delete_stocktransaction',
            'can_adjust_stock', 'can_view_reports', 'can_view_history',
            'view_possale', 'add_possale', 'change_possale', 'delete_possale',
            'view_priceoverridelog',
            'view_hydraulicsow', 'add_hydraulicsow', 'change_hydraulicsow', 'delete_hydraulicsow',
            'view_customer', 'change_customer', 'delete_customer',
            'view_customerpayment', 'add_customerpayment', 'change_customerpayment', 'delete_customerpayment',
        ],
        'Salesman':[
            'view_possale', 'add_possale', 
            'view_priceoverridelog',
            'view_hydraulicsow', 'add_hydraulicsow', 'change_hydraulicsow',
            'view_customer', 'change_customer',
            'view_customerpayment', 'add_customerpayment',
            'view_product', 'view_category',
        ],
    }

    # Loop through roles and assign permissions
    for role_name, permissions in roles.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        perms_to_add = Permission.objects.filter(codename__in=permissions)
        group.permissions.set(perms_to_add)