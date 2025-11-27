"""
Django management command to create or update a superuser from environment variables.

USAGE:
  Local development (DEBUG=True):
    python manage.py ensure_local_admin
  
  Production (requires explicit --force flag):
    python manage.py ensure_local_admin --force

ENVIRONMENT VARIABLES:
  LOCAL_ADMIN_USERNAME  - Username for superuser (default: 'admin')
  LOCAL_ADMIN_EMAIL     - Email for superuser (default: 'admin@example.com')
  LOCAL_ADMIN_PASSWORD  - Password (required, no default for security)

SAFETY:
  - Only runs in DEBUG mode unless --force is specified
  - Warns when using default values on production
  - Fails fast if password is not set
  - Creates or updates user idempotently
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create or reset a superuser using LOCAL_ADMIN_* environment variables. "
        "Safe for local development (DEBUG=True). Requires --force for production use."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running when DEBUG is False (required for staging/production).",
        )

    def handle(self, *args, **options):
        debug = getattr(settings, "DEBUG", False)
        force = options["force"]
        
        # Safety check: prevent accidental production runs
        if not debug and not force:
            raise CommandError(
                "Refusing to run with DEBUG=False. This command modifies user credentials.\n"
                "If you really need to run this on production/staging, use:\n"
                "  python manage.py ensure_local_admin --force"
            )

        # Read environment variables
        username = os.getenv("LOCAL_ADMIN_USERNAME")
        email = os.getenv("LOCAL_ADMIN_EMAIL")
        password = os.getenv("LOCAL_ADMIN_PASSWORD")

        # Validate required password
        if not password:
            raise CommandError(
                "LOCAL_ADMIN_PASSWORD environment variable is required.\n"
                "Set it before running this command:\n"
                "  export LOCAL_ADMIN_PASSWORD='YourStrongPassword123!'"
            )

        # Use defaults for optional fields, with warnings on production
        if not username:
            username = "admin"
            if force:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️  LOCAL_ADMIN_USERNAME not set, using default: 'admin'"
                    )
                )

        if not email:
            email = "admin@example.com"
            if force:
                self.stdout.write(
                    self.style.WARNING(
                        "⚠️  LOCAL_ADMIN_EMAIL not set, using default: 'admin@example.com'"
                    )
                )

        # Create or update user
        User = get_user_model()
        try:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email}
            )
        except Exception as e:
            raise CommandError(f"Failed to get or create user: {e}")

        # Update user properties
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        
        try:
            user.save()
        except Exception as e:
            raise CommandError(f"Failed to save user: {e}")

        # Report success
        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {action} superuser '{username}' (email: {email})"
            )
        )
        
        if created:
            self.stdout.write(f"   • is_superuser: True")
            self.stdout.write(f"   • is_staff: True")
            self.stdout.write(f"   • is_active: True")
        else:
            self.stdout.write(f"   • Password has been reset")
            self.stdout.write(f"   • Email updated to: {email}")

        if force:
            self.stdout.write(
                self.style.WARNING(
                    "\n🔒 Security reminder: Change this password after first login "
                    "and use a password manager for production credentials."
                )
            )
