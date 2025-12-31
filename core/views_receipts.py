import json
import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from .agentic_receipts import ReceiptInputDocument, run_receipts_workflow
from .ledger_services import post_journal_entry_from_proposal
from .models import ReceiptDocument, ReceiptRun
from .permissions import has_permission
from .utils import get_current_business

ALLOWED_RECEIPT_EXTS = {"pdf", "jpg", "jpeg", "png", "heic"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_FILES_PER_BATCH = 20
MAX_TOTAL_BATCH_BYTES = 50 * 1024 * 1024  # 50 MB total
RISK_MEDIUM_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("60.0")
DEFAULT_ERROR_BANNER = "Invalid receipt run input."


def _validate_files(files):
    if not files:
        return "No files uploaded."
    if len(files) > MAX_FILES_PER_BATCH:
        return f"Too many files. Max {MAX_FILES_PER_BATCH}."
    total_size = 0
    for f in files:
        ext = os.path.splitext(f.name)[1].lower().lstrip(".")
        if ext not in ALLOWED_RECEIPT_EXTS:
            return f"Unsupported file type: {f.name}"
        total_size += f.size
        if f.size > MAX_FILE_SIZE_BYTES:
            return f"File too large: {f.name}"
    if total_size > MAX_TOTAL_BATCH_BYTES:
        return "Total upload size exceeds limit."
    return None


def _build_storage_path(business_id: int, run_id: int, filename: str) -> str:
    safe_name = os.path.basename(filename)
    unique = uuid.uuid4().hex
    return os.path.join("receipts", str(business_id), str(run_id), f"{unique}_{safe_name}")


def _serialize_doc(doc: ReceiptDocument) -> dict:
    risk_level = None
    if doc.audit_score is not None:
        try:
            score = Decimal(doc.audit_score)
            if score >= RISK_HIGH_THRESHOLD:
                risk_level = "high"
            elif score >= RISK_MEDIUM_THRESHOLD:
                risk_level = "medium"
            else:
                risk_level = "low"
        except Exception:
            risk_level = None
    return {
        "id": doc.id,
        "status": doc.status,
        "storage_key": doc.storage_key,
        "original_filename": doc.original_filename,
        "extracted_payload": doc.extracted_payload,
        "proposed_journal_payload": doc.proposed_journal_payload,
        "audit_flags": doc.audit_flags,
        "audit_score": str(doc.audit_score) if doc.audit_score is not None else None,
        "audit_explanations": doc.audit_explanations,
        "risk_level": risk_level,
        "posted_journal_entry_id": doc.posted_journal_entry_id,
        "error_message": doc.error_message,
    }


@login_required
@require_POST
def api_receipts_run(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "receipts.upload"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    files = request.FILES.getlist("files") or request.FILES.getlist("documents")
    error = _validate_files(files)
    if error:
        return JsonResponse({"error": error}, status=400)

    default_currency = request.POST.get("default_currency") or None
    default_category = request.POST.get("default_category") or None
    default_vendor = request.POST.get("default_vendor") or None
    default_date_raw = request.POST.get("default_date") or request.POST.get("date_hint") or None
    # Design B: hints are optional and never block uploads. We pass raw strings through.
    parsed_default_date = None
    try:
        parsed_default_date = timezone.datetime.fromisoformat(default_date_raw).date() if default_date_raw else None
    except Exception:
        parsed_default_date = None

    run = ReceiptRun.objects.create(
        business=business,
        created_by=request.user,
        status=ReceiptRun.RunStatus.RUNNING,
        total_documents=len(files),
    )

    documents: list[ReceiptInputDocument] = []
    doc_models: list[ReceiptDocument] = []
    try:
        for f in files:
            path = _build_storage_path(business.id, run.id, f.name)
            storage_key = default_storage.save(path, f)
            doc = ReceiptDocument.objects.create(
                business=business,
                run=run,
                storage_key=storage_key,
                original_filename=f.name,
                status=ReceiptDocument.DocumentStatus.PENDING,
            )
            doc_models.append(doc)
            documents.append(
                ReceiptInputDocument(
                    document_id=doc.id,
                    storage_key=storage_key,
                    original_filename=f.name,
                    currency_hint=default_currency,
                    date_hint=default_date_raw or parsed_default_date,
                    category_hint=default_category,
                    vendor_hint=default_vendor,
                )
            )

        workflow_result = run_receipts_workflow(
            business_id=business.id,
            documents=documents,
            default_currency=default_currency,
            default_date=parsed_default_date,
            default_category=default_category,
            default_vendor=default_vendor,
            triggered_by_user_id=request.user.id,
            ai_companion_enabled=business.ai_companion_enabled,
        )

        success_count = 0
        error_count = 0
        warning_count = 0
        high_risk_count = 0
        with transaction.atomic():
            for doc_model, doc_result in zip(doc_models, workflow_result.documents):
                doc_model.extracted_payload = doc_result.extracted_payload
                doc_model.proposed_journal_payload = doc_result.proposed_journal_payload
                doc_model.audit_flags = doc_result.audit_flags
                doc_model.audit_score = doc_result.audit_score
                doc_model.audit_explanations = getattr(doc_result, "audit_explanations", [])
                if doc_result.audit_score is not None and Decimal(doc_result.audit_score) >= RISK_HIGH_THRESHOLD:
                    high_risk_count += 1
                if doc_result.status == "PROCESSED":
                    doc_model.status = ReceiptDocument.DocumentStatus.PROCESSED
                    success_count += 1
                    if getattr(doc_result, "audit_status", None) == "warning":
                        warning_count += 1
                else:
                    doc_model.status = ReceiptDocument.DocumentStatus.ERROR
                    doc_model.error_message = doc_result.error or ""
                    error_count += 1
                doc_model.save()

            run.status = ReceiptRun.RunStatus.COMPLETED
            run.success_count = success_count
            run.error_count = error_count
            run.warning_count = warning_count
            run.engine_run_id = workflow_result.engine_run_id
            run.trace_id = workflow_result.trace_id
            run.metrics = {
                **workflow_result.metrics,
                "documents_high_risk": high_risk_count or workflow_result.metrics.get("documents_high_risk", 0),
                "documents_total": workflow_result.metrics.get("documents_total", len(doc_models)),
            }
            run.llm_explanations = workflow_result.llm_explanations
            run.llm_ranked_documents = workflow_result.llm_ranked_documents
            run.llm_suggested_classifications = workflow_result.llm_suggested_classifications
            run.llm_suggested_followups = workflow_result.llm_suggested_followups
            run.save()
    except Exception as exc:  # pragma: no cover - defensive
        run.status = ReceiptRun.RunStatus.FAILED
        run.error_count = run.total_documents
        run.save(update_fields=["status", "error_count"])
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "run_id": run.id,
            "status": run.status,
            "success_count": run.success_count,
            "warning_count": run.warning_count,
            "error_count": run.error_count,
            "engine_run_id": run.engine_run_id,
            "trace_id": run.trace_id,
            "metrics": run.metrics,
            "llm_explanations": run.llm_explanations,
            "llm_ranked_documents": run.llm_ranked_documents,
            "llm_suggested_classifications": run.llm_suggested_classifications,
            "llm_suggested_followups": run.llm_suggested_followups,
            "documents": [_serialize_doc(d) for d in doc_models],
        }
    )


@login_required
@require_GET
def api_receipts_runs(request):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "receipts.view"):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    runs = ReceiptRun.objects.filter(business=business).order_by("-created_at")[:50]
    data = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "total_documents": r.total_documents,
            "success_count": r.success_count,
            "warning_count": r.warning_count,
            "error_count": r.error_count,
        }
        for r in runs
    ]
    return JsonResponse({"runs": data})


@login_required
@require_GET
def api_receipts_run_detail(request, run_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "receipts.view"):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    run = ReceiptRun.objects.filter(business=business, pk=run_id).first()
    if not run:
        return JsonResponse({"error": "Run not found"}, status=404)
    docs = run.documents.all()
    return JsonResponse(
        {
            "id": run.id,
            "created_at": run.created_at.isoformat(),
            "status": run.status,
            "total_documents": run.total_documents,
            "success_count": run.success_count,
            "warning_count": run.warning_count,
            "error_count": run.error_count,
            "metrics": run.metrics,
            "trace_id": run.trace_id,
            "llm_explanations": run.llm_explanations,
            "llm_ranked_documents": run.llm_ranked_documents,
            "llm_suggested_classifications": run.llm_suggested_classifications,
            "llm_suggested_followups": run.llm_suggested_followups,
            "documents": [_serialize_doc(doc) for doc in docs],
        }
    )


@login_required
@require_GET
def api_receipt_detail(request, receipt_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "receipts.view"):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    doc = ReceiptDocument.objects.filter(business=business, pk=receipt_id).first()
    if not doc:
        return JsonResponse({"error": "Receipt not found"}, status=404)
    return JsonResponse(_serialize_doc(doc))


@login_required
@require_POST
def api_receipt_approve(request, receipt_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "receipts.approve"):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    doc = ReceiptDocument.objects.select_related("run").filter(business=business, pk=receipt_id).first()
    if not doc:
        return JsonResponse({"error": "Receipt not found"}, status=404)
    if doc.status not in {ReceiptDocument.DocumentStatus.PROCESSED, ReceiptDocument.DocumentStatus.POSTED}:
        return JsonResponse({"error": "Receipt is not ready for approval"}, status=400)

    if doc.posted_journal_entry_id:
        return JsonResponse({"journal_entry_id": doc.posted_journal_entry_id, "status": doc.status})

    # Apply user overrides (Design B: review & edit before posting)
    overrides: dict = {}
    if request.body:
        try:
            parsed = json.loads(request.body)
            if isinstance(parsed, dict):
                overrides = parsed.get("overrides") if "overrides" in parsed else parsed
                if not isinstance(overrides, dict):
                    overrides = {}
        except Exception:
            overrides = {}
    else:
        # Support form submissions as a fallback
        overrides = {k: v for k, v in request.POST.items() if k in {"date", "amount", "currency", "vendor", "category"}}

    proposal = doc.proposed_journal_payload or {}
    extracted_payload = doc.extracted_payload or {}

    def _apply_overrides(base: dict, override_data: dict) -> dict:
        updated = {**base}
        if "date" in override_data and override_data.get("date"):
            updated["date"] = override_data["date"]
        if "vendor" in override_data and override_data.get("vendor"):
            vendor_val = override_data["vendor"]
            updated["description"] = f"Receipt - {vendor_val}"
            extracted_payload["vendor"] = vendor_val
        if "currency" in override_data and override_data.get("currency"):
            updated["currency"] = override_data["currency"]
            extracted_payload["currency"] = override_data["currency"]
        if "amount" in override_data and override_data.get("amount") not in (None, ""):
            amount_val = Decimal(str(override_data["amount"]))
            lines = updated.get("lines", [])
            if len(lines) >= 2:
                lines[0]["debit"] = str(amount_val)
                lines[1]["credit"] = str(amount_val)
            updated["lines"] = lines
            extracted_payload["total"] = str(amount_val)
        if "category" in override_data and override_data.get("category"):
            extracted_payload["category_hint"] = override_data["category"]
        return updated

    try:
        proposal_to_post = _apply_overrides(proposal, overrides) if overrides else proposal
        if overrides:
            doc.proposed_journal_payload = proposal_to_post
            user_edits = extracted_payload.get("user_edits", {})
            if isinstance(user_edits, dict):
                user_edits.update(overrides)
            else:
                user_edits = overrides
            extracted_payload["user_edits"] = user_edits
            doc.extracted_payload = extracted_payload
            doc.save(update_fields=["proposed_journal_payload", "extracted_payload"])
        entry = post_journal_entry_from_proposal(business, proposal_to_post, request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    doc.posted_journal_entry = entry
    doc.status = ReceiptDocument.DocumentStatus.POSTED
    doc.approved_by = request.user
    doc.approved_at = timezone.now()
    doc.save(
        update_fields=["posted_journal_entry", "status", "approved_by", "approved_at"]
    )
    return JsonResponse({"journal_entry_id": entry.id, "status": doc.status})


@login_required
@require_POST
def api_receipt_discard(request, receipt_id: int):
    business = get_current_business(request.user)
    if business is None:
        return JsonResponse({"error": "No business context"}, status=400)
    
    if not has_permission(request.user, business, "expenses.delete"):
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    doc = ReceiptDocument.objects.filter(business=business, pk=receipt_id).first()
    if not doc:
        return JsonResponse({"error": "Receipt not found"}, status=404)
    reason = request.POST.get("reason", "")
    doc.status = ReceiptDocument.DocumentStatus.DISCARDED
    doc.discard_reason = reason[:255]
    doc.discarded_by = request.user
    doc.discarded_at = timezone.now()
    doc.save(update_fields=["status", "discard_reason", "discarded_by", "discarded_at"])
    return JsonResponse({"status": doc.status})


@login_required
def receipts_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(
        request,
        "receipts.html",
        {
            "business": business,
            "default_currency": business.currency,
        },
    )
