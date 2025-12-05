"""
Agentic Demo Views

Django views for the agentic demo pages.
"""

from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime

# In-memory storage for demo runs (in production, use database)
_workflow_runs = []


def receipts_demo_view(request):
    """
    Render the receipts demo page.

    This page hosts the React app for the receipts workflow demo.
    """
    return render(
        request,
        "agentic/receipts_demo.html",
        {"debug": settings.DEBUG},
    )


def console_view(request):
    """
    Render the agentic console page.

    This page hosts the React app for the workflow execution console.
    """
    return render(
        request,
        "agentic/console.html",
        {"debug": settings.DEBUG},
    )


@require_http_methods(["GET"])
def list_runs_view(request):
    """
    List all workflow runs.
    
    Returns:
        JSON response with list of runs.
    """
    runs = [
        {
            "id": run.get("id"),
            "workflow_name": run.get("workflow_name"),
            "status": run.get("status"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "duration_ms": run.get("duration_ms", 0),
            "step_count": len(run.get("steps", [])),
            "document_count": len(run.get("artifacts", {}).get("documents", [])),
        }
        for run in _workflow_runs
    ]
    
    return JsonResponse({"runs": runs})


@require_http_methods(["GET"])
def get_run_view(request, run_id):
    """
    Get details of a specific workflow run.
    
    Args:
        run_id: ID of the workflow run
    
    Returns:
        JSON response with full run details.
    """
    for run in _workflow_runs:
        if run.get("id") == run_id:
            return JsonResponse(run)
    
    return JsonResponse({"error": "Run not found"}, status=404)


def register_workflow_run(result):
    """
    Register a workflow run result for display in console.
    
    Args:
        result: WorkflowRunResult from workflow execution
    """
    run_data = {
        "id": f"run-{len(_workflow_runs) + 1}",
        "workflow_name": result.workflow_name,
        "status": result.status,
        "started_at": result.started_at.isoformat() if hasattr(result.started_at, 'isoformat') else str(result.started_at),
        "finished_at": result.finished_at.isoformat() if hasattr(result.finished_at, 'isoformat') else str(result.finished_at),
        "duration_ms": result.duration_ms,
        "steps": [
            {
                "name": step.name,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "error": step.error,
            }
            for step in result.steps
        ] if hasattr(result, 'steps') else [],
        "artifacts": _serialize_artifacts(result.artifacts) if hasattr(result, 'artifacts') else {},
    }
    
    _workflow_runs.insert(0, run_data)  # Most recent first
    
    # Keep only last 50 runs
    while len(_workflow_runs) > 50:
        _workflow_runs.pop()
    
    return run_data


def _serialize_artifacts(artifacts):
    """Serialize artifacts to JSON-safe format."""
    serialized = {}
    
    for key, value in artifacts.items():
        if value is None:
            serialized[key] = None
        elif isinstance(value, list):
            serialized[key] = [
                item.model_dump() if hasattr(item, 'model_dump') else item
                for item in value
            ]
        elif hasattr(value, 'model_dump'):
            serialized[key] = value.model_dump()
        else:
            serialized[key] = value
    
    return serialized

