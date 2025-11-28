import os
import json
import logging

from django.core.management.base import BaseCommand, CommandError
from openai import OpenAI

from core.metrics import build_central_books_metrics

import requests


logger = logging.getLogger(__name__)


def send_to_slack(report: str) -> None:
    """
    Send the monitoring report to Slack via incoming webhook.
    If SLACK_WEBHOOK_URL is not set, print to stdout instead.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        # Fallback: just print the report
        logger.info("SLACK_WEBHOOK_URL not set; printing report to stdout")
        print(report)
        return

    payload = {
        "text": report  # plain ASCII text only (enforced by prompt)
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to send report to Slack: %r", e)
        # do not raise, this should not break the command


class Command(BaseCommand):
    help = "Run Central-Books monitoring agent and send report to Slack"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print metrics and prompt, do not call OpenAI or Slack",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        try:
            self.stdout.write("[*] Collecting metrics...")
            metrics = build_central_books_metrics()

            # Make metrics JSON ASCII-safe so no encoding issues occur
            metrics_json = json.dumps(
                metrics,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                raise CommandError("OPENAI_API_KEY is not set")

            model_name = os.getenv("MONITORING_MODEL", "gpt-4o-mini")
            monitoring_env = os.getenv("MONITORING_ENV", "production")

            prompt = (
                "You are the Central-Books monitoring agent.\n"
                "You receive a JSON metrics payload with 7 domains:\n"
                "- meta\n"
                "- product_engineering\n"
                "- ledger_accounting\n"
                "- banking_reconciliation\n"
                "- tax_fx\n"
                "- business_revenue\n"
                "- marketing_traffic\n"
                "- support_feedback\n\n"
                "Task:\n"
                "1. Analyze the metrics.\n"
                "2. Produce a concise status report in plain ASCII text.\n"
                "3. Use headings like:\n"
                "   OVERVIEW\n"
                "   PRODUCT AND ENGINEERING\n"
                "   LEDGER AND ACCOUNTING\n"
                "   BANKING AND RECONCILIATION\n"
                "   TAX AND FX\n"
                "   BUSINESS AND REVENUE\n"
                "   MARKETING AND TRAFFIC\n"
                "   SUPPORT AND FEEDBACK\n"
                "4. Do NOT use emojis or any non-ASCII characters.\n"
                "5. Do NOT give recommendations, only observations.\n\n"
                f"Environment: {monitoring_env}\n\n"
                "Here is the metrics JSON:\n"
                f"{metrics_json}\n"
            )

            if dry_run:
                self.stdout.write("=== DRY RUN ===")
                self.stdout.write(prompt)
                return

            self.stdout.write("[*] Calling OpenAI for monitoring report...")

            client = OpenAI(api_key=openai_api_key)

            try:
                response = client.responses.create(
                    model=model_name,
                    input=prompt,
                )
            except Exception as api_err:
                # Ensure the error string is ASCII-safe
                safe_err = repr(api_err)
                raise CommandError(
                    f"Monitoring agent failed: OpenAI API call failed: {safe_err}"
                )

            # Extract text from response in an ASCII-safe way
            try:
                # For openai>=1.46.0 responses API
                content_item = response.output[0].content[0]
                if hasattr(content_item, "text") and hasattr(content_item.text, "value"):
                    report_text = content_item.text.value
                else:
                    # Fallback: best-effort string conversion
                    report_text = str(response)
            except Exception as parse_err:
                safe_err = repr(parse_err)
                raise CommandError(
                    f"Monitoring agent failed: could not parse OpenAI response: {safe_err}"
                )

            # Send to Slack or stdout
            try:
                send_to_slack(report_text)
            except Exception as slack_err:
                logger.error("Slack sending failed: %r", slack_err)

            self.stdout.write("[OK] Monitoring report generated and dispatched.")

        except CommandError:
            # Re-raise CommandError as-is
            raise
        except Exception as err:
            # Final catch-all with ASCII-safe error message
            safe_err = repr(err)
            raise CommandError(f"Monitoring agent failed: {safe_err}")
