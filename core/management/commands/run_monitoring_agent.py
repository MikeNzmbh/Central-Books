"""
Django management command to run the Central-Books monitoring agent.

This command:
1. Collects metrics across 7 business domains
2. Sends metrics to OpenAI for analysis
3. Delivers formatted report to Slack/Discord
4. Supports --dry-run mode for testing

Usage:
    python manage.py run_monitoring_agent
    python manage.py run_monitoring_agent --dry-run
"""
import json
import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

MONITORING_SYSTEM_PROMPT = """You are the Central-Books Monitoring Agent. You analyze business health metrics across 7 domains and produce a concise, actionable status report.

**YOUR TASK:**
Analyze the provided metrics JSON and generate a monitoring report in this EXACT format:

```
📊 CENTRAL-BOOKS MONITORING REPORT
Generated: [timestamp]
Environment: [environment]

=== OVERVIEW ===
[2-3 sentence executive summary of overall system health]

=== 🛠️ Product & Engineering ===
[Status and key metrics for features, bugs, deployments, uptime]

=== 📒 Ledger & Accounting ===
[Status of journal entries, account balances, and ledger health]

=== 🏦 Banking & Reconciliation ===
[Bank transaction volume, reconciliation status, unreconciled items]

=== 💰 Tax & FX ===
[Tax rate configuration, multi-currency status, recent calculations]

=== 📈 Business & Revenue ===
[Revenue, expenses, profit, receivables, customer/supplier counts]

=== 📢 Marketing & Traffic ===
[User acquisition, signups, page views, conversion rates]

=== 💬 Support & Feedback ===
[Open tickets, response times, satisfaction scores]
```

**CRITICAL RULES:**
1. Use ONLY the data provided in the metrics JSON
2. If a metric is 0 or missing, state "No data available" or "Not yet tracked"
3. Highlight concerning metrics with ⚠️ emoji
4. Keep each section to 2-3 lines maximum
5. NO RECOMMENDATIONS ALLOWED - This is a status report only
6. Use exact section headers shown above with emojis
7. Be factual and concise

**OUTPUT FORMAT:**
Plain text only, no markdown code blocks, no extra formatting.
"""


class Command(BaseCommand):
    help = 'Run Central-Books monitoring agent and deliver report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print report to stdout without sending to Slack/Discord',
        )
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            help='OpenAI model to use (default: from env MONITORING_MODEL)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        try:
            # Import here to avoid circular dependencies
            from core.metrics import build_central_books_metrics
            
            self.stdout.write(self.style.SUCCESS('🔄 Collecting metrics...'))
            
            # Collect metrics
            metrics = build_central_books_metrics()
            
            # Pretty print metrics in dry-run mode
            if dry_run:
                self.stdout.write(self.style.WARNING('\n📊 METRICS COLLECTED:'))
                self.stdout.write(json.dumps(metrics, indent=2, default=str))
                self.stdout.write('\n')
            
            # Get OpenAI configuration
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        '⚠️  No OPENAI_API_KEY found - skipping AI analysis in dry-run mode'
                    ))
                    return
                else:
                    raise CommandError(
                        'OPENAI_API_KEY environment variable is required. '
                        'Set it in your .env file or environment.'
                    )
            
            model = options['model'] or os.getenv('MONITORING_MODEL', 'gpt-5.1-mini')
            
            self.stdout.write(self.style.SUCCESS(f'🤖 Calling OpenAI ({model})...'))
            
            # Call OpenAI
            report = self._call_openai(metrics, model, api_key)
            
            # Output report
            if dry_run:
                self.stdout.write(self.style.SUCCESS('\n📄 GENERATED REPORT:'))
                self.stdout.write(self.style.SUCCESS('=' * 80))
                self.stdout.write(report)
                self.stdout.write(self.style.SUCCESS('=' * 80))
            else:
                # Send to Slack/Discord
                self._deliver_report(report)
                self.stdout.write(self.style.SUCCESS('✅ Report delivered successfully'))
        
        except Exception as e:
            if dry_run:
                self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
                import traceback
                traceback.print_exc()
            else:
                raise CommandError(f'Monitoring agent failed: {str(e)}')
    
    def _call_openai(self, metrics: dict, model: str, api_key: str) -> str:
        """Call OpenAI API to analyze metrics and generate report."""
        try:
            from openai import OpenAI
        except ImportError:
            raise CommandError(
                'OpenAI Python SDK is not installed. '
                'Install it with: pip install openai>=1.46.0'
            )
        
        client = OpenAI(api_key=api_key)
        
        # Format metrics as JSON string
        metrics_json = json.dumps(metrics, indent=2, default=str)
        
        # Call OpenAI Chat Completions API
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": MONITORING_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze these metrics and generate the monitoring report:\n\n{metrics_json}"}
                ],
                temperature=0.3,  # Lower temperature for more consistent reports
                max_tokens=1500,
            )
            
            report = response.choices[0].message.content
            return report
        
        except Exception as e:
            raise CommandError(f'OpenAI API call failed: {str(e)}')
    
    def _deliver_report(self, report: str):
        """Deliver report to configured channels (Slack/Discord)."""
        slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        
        delivered = False
        
        if slack_webhook:
            self.stdout.write('📤 Sending to Slack...')
            self._send_to_slack(slack_webhook, report)
            delivered = True
        else:
            self.stdout.write(self.style.WARNING(
                '⚠️  SLACK_WEBHOOK_URL not set - skipping Slack notification'
            ))
        
        if discord_webhook:
            self.stdout.write('📤 Sending to Discord...')
            self._send_to_discord(discord_webhook, report)
            delivered = True
        else:
            self.stdout.write(self.style.WARNING(
                '⚠️  DISCORD_WEBHOOK_URL not set - skipping Discord notification'
            ))
        
        if not delivered:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  No webhook URLs configured. Set SLACK_WEBHOOK_URL or DISCORD_WEBHOOK_URL to enable notifications.'
            ))
            self.stdout.write(self.style.SUCCESS('\n📄 REPORT OUTPUT:'))
            self.stdout.write('\n' + report)
    
    def _send_to_slack(self, webhook_url: str, report: str):
        """Send report to Slack via webhook."""
        try:
            import requests
        except ImportError:
            raise CommandError('requests library is required. Install with: pip install requests')
        
        payload = {
            "text": report,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            raise CommandError(f'Failed to send to Slack: {str(e)}')
    
    def _send_to_discord(self, webhook_url: str, report: str):
        """Send report to Discord via webhook."""
        try:
            import requests
        except ImportError:
            raise CommandError('requests library is required. Install with: pip install requests')
        
        # Discord has a 2000 character limit, split if needed
        if len(report) > 1900:
            chunks = self._split_report(report, 1900)
            for i, chunk in enumerate(chunks):
                payload = {
                    "content": f"**Part {i+1}/{len(chunks)}**\n```\n{chunk}\n```"
                }
                try:
                    response = requests.post(webhook_url, json=payload, timeout=10)
                    response.raise_for_status()
                except Exception as e:
                    raise CommandError(f'Failed to send to Discord: {str(e)}')
        else:
            payload = {
                "content": f"```\n{report}\n```"
            }
            try:
                response = requests.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()
            except Exception as e:
                raise CommandError(f'Failed to send to Discord: {str(e)}')
    
    def _split_report(self, report: str, max_length: int) -> list:
        """Split report into chunks that fit within max_length."""
        lines = report.split('\n')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > max_length and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
