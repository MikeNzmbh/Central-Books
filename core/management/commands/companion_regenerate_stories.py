"""
Management command to regenerate dirty companion stories.

Run this from cron every 5 minutes:
    */5 * * * * cd /path/to/project && .venv/bin/python manage.py companion_regenerate_stories

Or with Celery beat if available.
"""
from django.core.management.base import BaseCommand

from core.companion_story import regenerate_dirty_stories


class Command(BaseCommand):
    help = "Regenerate Companion stories for businesses marked as dirty"

    def handle(self, *args, **options):
        count = regenerate_dirty_stories()
        if count:
            self.stdout.write(self.style.SUCCESS(f"Regenerated {count} story/stories"))
        else:
            self.stdout.write("No dirty stories to regenerate")
