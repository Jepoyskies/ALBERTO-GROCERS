# inventory/management/commands/rotate_audit_log.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inventory.models import Product

class Command(BaseCommand):
    help = 'Deletes product edit history older than a specified number of days (Audit Log Rotation).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='The number of days of history to keep. Defaults to 365.',
        )

    def handle(self, *args, **options):
        days = options['days']
        
        if days < 30:
            self.stdout.write(self.style.WARNING(f"Warning: {days} days is a very short retention period for audit logs."))
            confirm = input("Are you sure you want to proceed? (y/n): ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f"Cleaning audit logs older than {cutoff_date.strftime('%Y-%m-%d')}...")

        # Get the Historical model from the Product class
        HistoricalProduct = Product.history.model
        
        # Perform the deletion
        deleted_count, _ = HistoricalProduct.objects.filter(history_date__lt=cutoff_date).delete()

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} old history records."))