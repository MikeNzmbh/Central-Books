"""
Agentic API Router - Django REST API endpoints for the agentic system.

Exposes:
- GET /agentic/status/ - System status and health check
- GET /agentic/workflows/ - List available workflows
- GET /agentic/agents/ - List registered agents with profiles
- POST /agentic/demo/receipts-run/ - Run receipts workflow demo

These endpoints return JSON data for the agentic system.
"""

import json
from typing import List

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import path

from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow
from agentic.interfaces.api.schemas import (
    ReceiptsDemoResponse,
    WorkflowStepResult,
)


class AgenticStatusView(View):
    """
    Health check and status endpoint for the agentic system.

    Returns system status, version, and available modules.
    """

    def get(self, request):
        """Return agentic system status."""
        return JsonResponse({
            "status": "ok",
            "version": "0.1.0",
            "phase": "http_demo_api",
            "modules": {
                "engine": {
                    "status": "active",
                    "components": [
                        "ingestion",
                        "normalization",
                        "entry_generation",
                        "compliance",
                        "audit",
                    ],
                },
                "agents": {
                    "status": "active",
                    "registered": [
                        "operations",
                        "support",
                        "sales",
                        "engineering",
                        "data_integrity",
                    ],
                },
                "workflows": {
                    "status": "active",
                    "available": 1,
                },
                "memory": {
                    "status": "placeholder",
                    "vector_store": "not_configured",
                },
            },
            "demo_endpoints": [
                "POST /agentic/demo/receipts-run/",
            ],
            "message": "Agentic system ready. Use POST /agentic/demo/receipts-run/ to run the Residency demo.",
        })


class WorkflowListView(View):
    """
    List available workflows in the agentic system.

    Returns workflow definitions without executing them.
    """

    def get(self, request):
        """Return list of available workflows."""
        return JsonResponse({
            "workflows": [
                {
                    "id": "receipts_to_journal_entries",
                    "name": "Receipts to Journal Entries",
                    "description": "Process uploaded receipts into journal entries with compliance & audit",
                    "status": "active",
                    "endpoint": "POST /agentic/demo/receipts-run/",
                    "steps": [
                        "ingest",
                        "extract",
                        "normalize",
                        "generate_entries",
                        "compliance",
                        "audit",
                    ],
                },
            ],
            "total": 1,
        })


class AgentProfilesView(View):
    """
    List registered AI Employee agents with their profiles.

    Returns agent definitions, capabilities, and risk levels.
    """

    def get(self, request):
        """Return list of registered agent profiles."""
        from agentic.agents.registry import list_agent_profiles

        profiles = list_agent_profiles()

        # Convert profiles to dicts for JSON serialization
        agents_data = {}
        for role, profile in profiles.items():
            agents_data[role] = {
                "name": profile.name,
                "role": profile.role,
                "description": profile.description,
                "capabilities": list(profile.capabilities),
                "max_parallel_tasks": profile.max_parallel_tasks,
                "risk_level": profile.risk_level,
                "llm_model": profile.llm_model,
                "tools": list(profile.tools),
                "owner_team": profile.owner_team,
            }

        return JsonResponse({
            "agents": agents_data,
            "total": len(agents_data),
            "message": "AI Employee agents are registered and ready for invocation.",
        })


@method_decorator(csrf_exempt, name="dispatch")
class ReceiptsDemoRunView(View):
    """
    Run the receipts workflow demo.

    POST /agentic/demo/receipts-run/

    Accepts JSON body with documents array and returns complete workflow results
    including extracted documents, transactions, journal entries, compliance, and audit.
    """

    def post(self, request):
        """Run the receipts workflow and return results."""
        # Parse JSON body
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse(
                {"detail": "Invalid JSON payload"},
                status=400,
            )

        # Validate documents
        docs = payload.get("documents")
        if not docs or not isinstance(docs, list):
            return JsonResponse(
                {"detail": "documents[] is required and must be a non-empty list"},
                status=400,
            )

        # Normalize docs into expected structure
        uploaded_files = []
        for idx, doc in enumerate(docs):
            if isinstance(doc, dict):
                filename = doc.get("filename") or f"doc-{idx + 1}.pdf"
                content = doc.get("content") or ""
            else:
                filename = f"doc-{idx + 1}.pdf"
                content = ""
            uploaded_files.append({
                "filename": filename,
                "content": content,
            })

        # Build and run workflow
        wf = build_receipts_workflow()
        result = wf.run({"uploaded_files": uploaded_files})

        # Build step results
        step_results: List[dict] = []
        for step in result.steps:
            step_results.append({
                "name": step.step_name,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "error": step.error_message,
            })

        # Extract artifacts
        artifacts = result.artifacts or {}
        extracted_docs = artifacts.get("extracted_documents", [])
        transactions = artifacts.get("transactions", [])
        journal_entries = artifacts.get("journal_entries", [])
        compliance = artifacts.get("compliance_result")
        audit = artifacts.get("audit_report")

        # Build summary
        summary = (
            f"Processed {len(extracted_docs)} document(s), "
            f"produced {len(journal_entries)} journal entries."
        )

        # Build notes
        notes = []
        if compliance:
            is_compliant = compliance.get("is_compliant", True) if isinstance(compliance, dict) else getattr(compliance, "is_compliant", True)
            if not is_compliant:
                notes.append("Compliance issues detected.")
        if audit:
            risk_level = audit.get("risk_level", "low") if isinstance(audit, dict) else getattr(audit, "risk_level", "low")
            if risk_level != "low":
                notes.append(f"Audit risk level is {risk_level}.")

        # Build response
        response_data = {
            "workflow_name": result.workflow_name,
            "status": result.status,
            "duration_ms": result.duration_ms,
            "steps": step_results,
            "extracted_documents": extracted_docs,
            "transactions": transactions,
            "journal_entries": journal_entries,
            "compliance": compliance,
            "audit": audit,
            "summary": summary,
            "notes": notes if notes else None,
        }

        return JsonResponse(response_data, status=200)

    def get(self, request):
        """Return usage information."""
        return JsonResponse({
            "endpoint": "POST /agentic/demo/receipts-run/",
            "description": "Run the receipts-to-journal-entries workflow",
            "request_body": {
                "documents": [
                    {"filename": "receipt.pdf", "content": "optional content"},
                ]
            },
            "response": {
                "workflow_name": "string",
                "status": "success | partial | failed",
                "steps": "array of step results",
                "extracted_documents": "array",
                "transactions": "array",
                "journal_entries": "array",
                "compliance": "object",
                "audit": "object",
                "summary": "string",
                "notes": "array | null",
            },
        })


# URL patterns for the agentic API
urlpatterns = [
    path("agentic/status/", AgenticStatusView.as_view(), name="agentic_status"),
    path("agentic/workflows/", WorkflowListView.as_view(), name="agentic_workflows"),
    path("agentic/agents/", AgentProfilesView.as_view(), name="agentic_agents"),
    path("agentic/demo/receipts-run/", ReceiptsDemoRunView.as_view(), name="agentic_receipts_demo_run"),
]

# Import and add demo page view
from agentic.interfaces.views import receipts_demo_view, console_view
urlpatterns.append(
    path("agentic/demo/receipts/", receipts_demo_view, name="agentic_receipts_demo_page"),
)
urlpatterns.append(
    path("agentic/console", console_view, name="agentic_console"),
)
