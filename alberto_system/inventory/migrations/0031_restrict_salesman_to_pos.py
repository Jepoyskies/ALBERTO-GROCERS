from django.db import migrations

def restrict_salesman_role(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    salesman_group = Group.objects.filter(name='Salesman').first()
    if salesman_group:
        # Define the strict set of permissions for Salesman
        # POS only + Read-only Stock Inquiry
        allowed_permissions = [
            # Point of Sale
            'view_possale', 'add_possale', 'view_priceoverridelog',
            # Stock Inquiry (Read-only)
            'view_product', 'view_category',
        ]
        
        perms_objs = Permission.objects.filter(codename__in=allowed_permissions)
        salesman_group.permissions.set(perms_objs)

def restore_salesman_role(apps, schema_editor):
    # This would ideally restore the previous state, but since we are moving towards 
    # a new definition, we can leave it or re-add the CRM perms if needed.
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0030_create_default_groups'),
    ]

    operations = [
        migrations.RunPython(restrict_salesman_role, reverse_code=restore_salesman_role),
    ]
