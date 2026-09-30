from django.db import migrations

def create_default_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'password123')

class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0031_restrict_salesman_to_pos'),
    ]

    operations = [
        migrations.RunPython(create_default_admin),
    ]
