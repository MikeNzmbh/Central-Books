from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def api_health(request):
    """Legacy health check at /api/health."""
    return JsonResponse({"ok": True, "service": "backend"})


@require_GET
def api_healthz(request):
    """Kubernetes-style health probe at /healthz."""
    return JsonResponse({"status": "ok"})
