from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User

class Command(BaseCommand):
    help = 'Ensures permissions are set correctly for groups and assigns users to groups'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, help='Assign this user to a group')
        parser.add_argument('--group', type=str, help='The group name to assign the user to')

    def handle(self, *args, **options):
        # Ensure permissions
        try:
            salesman, _ = Group.objects.get_or_create(name='Salesman')
            perms = Permission.objects.filter(codename__in=['can_adjust_stock', 'delete_possale'])
            salesman.permissions.add(*perms)
            self.stdout.write(self.style.SUCCESS('Successfully ensured Salesman group has required permissions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting permissions: {e}'))

        # Assign user to group if provided
        username = options.get('user')
        group_name = options.get('group')
        if username and group_name:
            try:
                user = User.objects.get(username=username)
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
                self.stdout.write(self.style.SUCCESS(f'Successfully assigned user {username} to group {group_name}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error assigning user to group: {e}'))
