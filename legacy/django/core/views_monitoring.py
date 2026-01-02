"""
Django view for Slack slash command integration with monitoring agent.

Handles `/cb-report` slash command to generate on-demand monitoring reports.
"""
import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def slack_monitoring_report(request):
    """
    Handle Slack slash command for on-demand monitoring reports.
    
    Usage: /cb-report
    
    Environment Variables:
    - SLACK_VERIFICATION_TOKEN (optional): Slack app verification token for security
    - OPENAI_API_KEY (required): OpenAI API key
    - MONITORING_MODEL (optional): Model to use (default: gpt-4o-mini)
    """
    # TODO: Verify Slack token for production
    verification_token = os.getenv('SLACK_VERIFICATION_TOKEN')
    if verification_token:
        provided_token = request.POST.get('token', '')
        if provided_token != verification_token:
            return JsonResponse({"text": "❌ Invalid verification token"}, status=401)
    
    # Immediate acknowledgment to Slack (required within 3 seconds)
    # We'll send the actual report as a follow-up
    trigger_id = request.POST.get('trigger_id')
    response_url = request.POST.get('response_url')
    
    # Return immediate response
    if not response_url:
        # Synchronous mode (testing)
        try:
            report = _generate_report_sync()
            return JsonResponse({
                "response_type": "in_channel",  # Visible to everyone
                "text": report
            })
        except Exception as e:
            return JsonResponse({
                "response_type": "ephemeral",  # Only visible to user
                "text": f"❌ Error generating report: {str(e)}"
            })
    
    # Asynchronous mode (production) - respond immediately, send report via response_url
    import threading
    threading.Thread(target=_send_async_report, args=(response_url,)).start()
    
    return JsonResponse({
        "response_type": "ephemeral",
        "text": "🔄 Generating monitoring report... (this may take a few seconds)"
    })


def _generate_report_sync():
    """Generate monitoring report synchronously."""
    from core.metrics import build_central_books_metrics
    from openai import OpenAI
    
    # Collect metrics
    metrics = build_central_books_metrics()
    
    # Get OpenAI config
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    model = os.getenv('MONITORING_MODEL', 'gpt-5.1-mini')
    
    # Call OpenAI
    client = OpenAI(api_key=api_key)
    
    # Use the same system prompt as the management command
    from core.management.commands.run_monitoring_agent import MONITORING_SYSTEM_PROMPT
    
    metrics_json = json.dumps(metrics, indent=2, default=str)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MONITORING_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze these metrics and generate the monitoring report:\n\n{metrics_json}"}
        ],
        temperature=0.3,
        max_tokens=1500,
    )
    
    return response.choices[0].message.content


def _send_async_report(response_url):
    """Send monitoring report asynchronously via Slack response_url."""
    import requests
    
    try:
        report = _generate_report_sync()
        
        # Send to Slack via response_url
        payload = {
            "response_type": "in_channel",
            "text": report
        }
        
        requests.post(response_url, json=payload, timeout=10)
    
    except Exception as e:
        # Send error back to Slack
        error_payload = {
            "response_type": "ephemeral",
            "text": f"❌ Error generating report: {str(e)}"
        }
        requests.post(response_url, json=error_payload, timeout=10)
