from django.core.management.base import BaseCommand, CommandError

from companion.llm import LLMProfile
from core.models import Business
from taxes.llm_observer import enrich_tax_period_snapshot_llm
from taxes.models import TaxAnomaly, TaxPeriodSnapshot


class Command(BaseCommand):
    """
    Populate TaxPeriodSnapshot.llm_summary/llm_notes via DeepSeek (observer only).

    Guardrails:
    - No amounts are computed by the model; it only summarizes deterministic outputs.
    - Never runs on page load; this is an explicit CLI/cron step (Option B infra).
    - Keep prompts and responses compact (token efficient).

    Spec: docs/tax_engine_v1_blueprint.md, docs/llm_safety_and_tokens.md
    """

    help = "Generate an LLM observer narrative for a tax period snapshot (advisory only)."

    def add_arguments(self, parser):
        parser.add_argument("--business-id", required=True, help="Business UUID/ID")
        parser.add_argument("--period", required=True, help="Period key, e.g., 2025Q2 or 2025-04")
        parser.add_argument(
            "--profile",
            choices=["light", "heavy"],
            default="light",
            help="LLM profile (light=deepseek-chat, heavy=deepseek-reasoner).",
        )
        parser.add_argument(
            "--soft",
            action="store_true",
            help="Do not error if LLM is disabled/unavailable; store a placeholder instead.",
        )

    def handle(self, *args, **options):
        business_id = options["business_id"]
        period_key = options["period"]
        profile_opt = options["profile"]
        soft = bool(options.get("soft"))

        try:
            business = Business.objects.get(pk=business_id)
        except Business.DoesNotExist:
            raise CommandError(f"Business {business_id} not found")

        snapshot = TaxPeriodSnapshot.objects.filter(business=business, period_key=period_key).first()
        if not snapshot:
            raise CommandError("Snapshot not found. Run tax_refresh_period first.")

        anomalies = list(TaxAnomaly.objects.filter(business=business, period_key=period_key).order_by("-created_at")[:50])
        profile = LLMProfile.LIGHT_CHAT if profile_opt == "light" else LLMProfile.HEAVY_REASONING
        enrichment = enrich_tax_period_snapshot_llm(
            business=business,
            snapshot=snapshot,
            anomalies=anomalies,
            profile=profile,
        )

        if not enrichment:
            if not soft:
                raise CommandError(
                    "LLM enrichment unavailable (LLM disabled or call failed). "
                    "Check COMPANION_LLM_ENABLED + COMPANION_LLM_API_* settings, or pass --soft."
                )
            snapshot.llm_summary = "AI summary unavailable (LLM disabled or failed). Amounts remain deterministic."
            snapshot.llm_notes = ""
            snapshot.save(update_fields=["llm_summary", "llm_notes"])
            self.stdout.write(self.style.WARNING(f"Saved placeholder enrichment for snapshot {snapshot.id}"))
            return

        snapshot.llm_summary = enrichment.summary
        snapshot.llm_notes = "\n".join([f"- {n}" for n in enrichment.notes])
        snapshot.save(update_fields=["llm_summary", "llm_notes"])
        self.stdout.write(self.style.SUCCESS(f"LLM enrichment saved for snapshot {snapshot.id}"))
