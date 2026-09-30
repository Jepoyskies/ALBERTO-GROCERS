#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.

This is the primary entry point for running your Django project locally,
executing management commands, and starting the development server.
"""
import os
import sys


def main():
    """
    Run administrative tasks.
    Sets the default environment settings module and executes commands passed via the CLI.
    """
    # Point to the core settings file by default
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
        
    # Execute the management command passed from the terminal
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()