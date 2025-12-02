from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Verify Companion LLM configuration settings"

    def handle(self, *args, **options):
        enabled = getattr(settings, "COMPANION_LLM_ENABLED", False)
        api_base = getattr(settings, "COMPANION_LLM_API_BASE", "")
        model = getattr(settings, "COMPANION_LLM_MODEL", "")
        timeout = getattr(settings, "COMPANION_LLM_TIMEOUT_SECONDS", 0)
        max_tokens = getattr(settings, "COMPANION_LLM_MAX_TOKENS", 0)
        api_key = getattr(settings, "COMPANION_LLM_API_KEY", "")

        self.stdout.write(f"Companion LLM Enabled: {enabled}")
        self.stdout.write(f"API Base: {api_base}")
        self.stdout.write(f"Model: {model}")
        self.stdout.write(f"Timeout: {timeout} seconds")
        self.stdout.write(f"Max Tokens: {max_tokens}")
        self.stdout.write(f"API Key Present: {'Yes' if api_key else 'No'}")
