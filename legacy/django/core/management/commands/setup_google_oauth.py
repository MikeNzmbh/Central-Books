"""
Management command to set up Google OAuth for django-allauth.

This command:
1. Checks for required environment variables (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
2. Updates the Site domain to match the current environment
3. Creates or updates the Google SocialApp in the database
4. Links the SocialApp to the current site

Usage:
    python manage.py setup_google_oauth

Environment Variables Required:
    GOOGLE_CLIENT_ID: OAuth 2.0 Client ID from Google Cloud Console
    GOOGLE_CLIENT_SECRET: OAuth 2.0 Client Secret from Google Cloud Console

Optional Environment Variables:
    SITE_DOMAIN: Domain for the site (default: 127.0.0.1:8000 in DEBUG mode)
"""

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.sites.models import Site
from django.conf import settings
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = "Set up Google OAuth for django-allauth"

    def add_arguments(self, parser):
        parser.add_argument(
            "--site-domain",
            type=str,
            help="Override the site domain (default: auto-detect based on DEBUG setting)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Setting up Google OAuth for django-allauth..."))
        
        # Step 1: Check for required environment variables
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        
        if not client_id or not client_secret:
            raise CommandError(
                "Missing required environment variables!\n"
                "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.\n\n"
                "For local development, add to .env:\n"
                "  GOOGLE_CLIENT_ID=your-client-id\n"
                "  GOOGLE_CLIENT_SECRET=your-client-secret\n\n"
                "See GOOGLE_LOGIN_SETUP.md for detailed setup instructions."
            )
        
        # Step 2: Update Site domain
        site_domain = options.get("site_domain") or os.environ.get("SITE_DOMAIN") or getattr(settings, "SITE_DOMAIN", None)

        if not site_domain:
            render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
            candidate_hosts = []
            if render_host:
                candidate_hosts.append(render_host)
            candidate_hosts.extend([h for h in settings.ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1"}])

            if settings.DEBUG:
                site_domain = "127.0.0.1:8000"
            elif candidate_hosts:
                site_domain = candidate_hosts[0]
            elif settings.ALLOWED_HOSTS:
                site_domain = settings.ALLOWED_HOSTS[0]
            else:
                site_domain = "localhost"
        
        site = Site.objects.get(id=settings.SITE_ID)
        old_domain = site.domain
        site.domain = site_domain
        site.name = site_domain
        site.save()
        
        self.stdout.write(
            self.style.SUCCESS(f"✓ Updated site domain: {old_domain} → {site_domain}")
        )
        
        # Step 3: Create or update Google SocialApp
        social_app, created = SocialApp.objects.get_or_create(
            provider="google",
            defaults={
                "name": "Google",
                "client_id": client_id,
                "secret": client_secret,
            }
        )
        
        if not created:
            # Update existing app
            social_app.client_id = client_id
            social_app.secret = client_secret
            social_app.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Updated existing Google SocialApp")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created new Google SocialApp")
            )
        
        # Step 4: Link SocialApp to Site
        if site not in social_app.sites.all():
            social_app.sites.add(site)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Linked SocialApp to site: {site_domain}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"✓ SocialApp already linked to site: {site_domain}")
            )
        
        # Final summary
        protocol = "http" if settings.DEBUG else "https"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Google OAuth setup complete! ✓"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write(f"Provider:    google")
        self.stdout.write(f"Site:        {site_domain}")
        self.stdout.write(f"Client ID:   {client_id[:20]}..." if len(client_id) > 20 else f"Client ID:   {client_id}")
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Ensure your Google Cloud Console OAuth redirect URI is set to:")
        self.stdout.write(f"     {protocol}://{site_domain}/accounts/google/login/callback/")
        self.stdout.write("  2. Visit /login/ and click 'Continue with Google'")
        self.stdout.write("")
