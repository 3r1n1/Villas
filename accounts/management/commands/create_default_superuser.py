"""
Create a superuser if none exist. Use environment variables so no password is hardcoded:

  DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL (optional)
  DJANGO_SUPERUSER_PASSWORD

Example (Windows PowerShell):
  $env:DJANGO_SUPERUSER_USERNAME="admin"; $env:DJANGO_SUPERUSER_PASSWORD="yourpassword"; python manage.py create_default_superuser
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser if no superuser exists (uses DJANGO_SUPERUSER_* env vars)."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS("A superuser already exists. Skipping."))
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not username or not password:
            self.stderr.write(
                self.style.ERROR(
                    "Set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD to create the first superuser."
                )
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email or "",
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
