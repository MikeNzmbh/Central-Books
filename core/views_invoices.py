import os
import uuid
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .agentic_invoices import InvoiceInputDocument, run_invoices_workflow
from .ledger_services import post_journal_entry_from_proposal
from .models import InvoiceDocument, InvoiceRun
from .utils import get_current_business

ALLOWED_INVOICE_EXTS = {"pdf", "jpg", "jpeg", "png", "heic"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_FILES_PER_BATCH = 20
MAX_TOTAL_BATCH_BYTES = 50 * 1024 * 1024  # 50 MB total
RISK_MEDIUM_THRESHOLD = Decimal("40.0")
RISK_HIGH_THRESHOLD = Decimal("60.0")


def _validate_files(files):
    if not files:
        return "No files uploaded."
    if len(files) > MAX_FILES_PER_BATCH:
        return f"Too many files. Max {MAX_FILES_PER_BATCH}."
    total_size = 0
    for f in files:
        ext = os.path.splitext(f.name)[1].lower().lstrip(".")
        if ext not in ALLOWED_INVOICE_EXTS:
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
    return os.path.join("invoices", str(business_id), str(run_id), f"{unique}_{safe_name}")


def _serialize_doc(doc: InvoiceDocument) -> dict:
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
def api_invoices_run(request):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")

    files = request.FILES.getlist("files") or request.FILES.getlist("documents")
    error = _validate_files(files)
    if error:
        return JsonResponse({"error": error}, status=400)

    default_currency = request.POST.get("default_currency") or None
    default_category = request.POST.get("default_category") or None
    default_vendor = request.POST.get("default_vendor") or None
    default_due_date_raw = request.POST.get("default_due_date")
    default_issue_date_raw = request.POST.get("default_issue_date")
    default_due_date = None
    default_issue_date = None
    for raw, target in ((default_due_date_raw, "due"), (default_issue_date_raw, "issue")):
        if raw:
            try:
                parsed = timezone.datetime.fromisoformat(raw).date()
                if target == "due":
                    default_due_date = parsed
                else:
                    default_issue_date = parsed
            except Exception:
                return JsonResponse({"error": f"Invalid default_{target}_date"}, status=400)

    run = InvoiceRun.objects.create(
        business=business,
        created_by=request.user,
        status=InvoiceRun.RunStatus.RUNNING,
        total_documents=len(files),
    )

    documents: list[InvoiceInputDocument] = []
    doc_models: list[InvoiceDocument] = []
    try:
        for f in files:
            path = _build_storage_path(business.id, run.id, f.name)
            storage_key = default_storage.save(path, f)
            doc = InvoiceDocument.objects.create(
                business=business,
                run=run,
                storage_key=storage_key,
                original_filename=f.name,
                status=InvoiceDocument.DocumentStatus.PENDING,
            )
            doc_models.append(doc)
            documents.append(
                InvoiceInputDocument(
                    document_id=doc.id,
                    storage_key=storage_key,
                    original_filename=f.name,
                    currency_hint=default_currency,
                    issue_date_hint=default_issue_date,
                    due_date_hint=default_due_date,
                    category_hint=default_category,
                    vendor_hint=default_vendor,
                )
            )

        workflow_result = run_invoices_workflow(
            business_id=business.id,
            documents=documents,
            default_currency=default_currency,
            default_issue_date=default_issue_date,
            default_due_date=default_due_date,
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
                    doc_model.status = InvoiceDocument.DocumentStatus.PROCESSED
                    success_count += 1
                    if getattr(doc_result, "audit_status", None) == "warning":
                        warning_count += 1
                else:
                    doc_model.status = InvoiceDocument.DocumentStatus.ERROR
                    doc_model.error_message = doc_result.error or ""
                    error_count += 1
                doc_model.save()

            run.status = InvoiceRun.RunStatus.COMPLETED
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
        run.status = InvoiceRun.RunStatus.FAILED
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
def api_invoices_runs(request):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    runs = InvoiceRun.objects.filter(business=business).order_by("-created_at")[:50]
    data = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "total_documents": r.total_documents,
            "success_count": r.success_count,
            "warning_count": r.warning_count,
            "error_count": r.error_count,
            "metrics": r.metrics,
            "trace_id": r.trace_id,
        }
        for r in runs
    ]
    return JsonResponse({"runs": data})


@login_required
@require_GET
def api_invoices_run_detail(request, run_id: int):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    run = InvoiceRun.objects.filter(business=business, pk=run_id).first()
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
def api_invoice_detail(request, invoice_id: int):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    doc = InvoiceDocument.objects.filter(business=business, pk=invoice_id).first()
    if not doc:
        return JsonResponse({"error": "Invoice not found"}, status=404)
    return JsonResponse(_serialize_doc(doc))


@login_required
@require_POST
def api_invoice_approve(request, invoice_id: int):
    """
    Approve an invoice and post the journal entry.
    
    Accepts optional JSON body with override fields:
    - vendor, invoice_number, issue_date, due_date, amount, currency, category, description
    
    If overrides are provided, they are used to recompute the journal entry.
    No LLM calls are made in this path - it's pure validation + posting.
    """
    import json
    from .accounting_defaults import ensure_default_accounts
    
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    doc = InvoiceDocument.objects.select_related("run").filter(business=business, pk=invoice_id).first()
    if not doc:
        return JsonResponse({"error": "Invoice not found"}, status=404)
    if doc.status not in {InvoiceDocument.DocumentStatus.PROCESSED, InvoiceDocument.DocumentStatus.POSTED}:
        return JsonResponse({"error": "Invoice is not ready for approval"}, status=400)

    if doc.posted_journal_entry_id:
        return JsonResponse({"journal_entry_id": doc.posted_journal_entry_id, "status": doc.status})

    # Parse JSON body for overrides (if any)
    overrides = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            overrides = json.loads(request.body.decode("utf-8")) or {}
        except json.JSONDecodeError:
            pass
    
    # If overrides provided, recompute the journal entry
    proposal = doc.proposed_journal_payload or {}
    if overrides:
        # Get default accounts for journal entry computation
        defaults = ensure_default_accounts(business)
        expense_account = defaults.get("opex")
        ap_account = defaults.get("ap")
        tax_account = defaults.get("tax_recoverable")
        
        # Extract override values
        vendor = overrides.get("vendor") or (doc.extracted_payload or {}).get("vendor", "")
        invoice_number = overrides.get("invoice_number") or (doc.extracted_payload or {}).get("invoice_number", "")
        issue_date = overrides.get("issue_date") or (doc.extracted_payload or {}).get("issue_date", "")
        amount_str = overrides.get("amount") or (doc.extracted_payload or {}).get("total", "0")
        currency = overrides.get("currency") or (doc.extracted_payload or {}).get("currency", business.currency)
        category = overrides.get("category") or (doc.extracted_payload or {}).get("category_hint", "expense")
        description = overrides.get("description") or f"Invoice {invoice_number} from {vendor}"
        
        # Parse amount
        try:
            amount = Decimal(str(amount_str).replace(",", "")).quantize(Decimal("0.01"))
        except Exception:
            amount = Decimal("0.00")
        
        # Compute tax (10% default if not explicitly provided)
        tax_str = overrides.get("tax") or (doc.extracted_payload or {}).get("tax", "")
        try:
            tax_amount = Decimal(str(tax_str).replace(",", "")).quantize(Decimal("0.01"))
        except Exception:
            tax_amount = (amount * Decimal("0.10")).quantize(Decimal("0.01"))
        
        # Build new proposal
        proposal = {
            "date": issue_date,
            "description": description,
            "lines": [
                {
                    "account_id": expense_account.id if expense_account else None,
                    "debit": str(amount - tax_amount),
                    "credit": "0",
                    "description": "Expense",
                },
                {
                    "account_id": tax_account.id if tax_account else (expense_account.id if expense_account else None),
                    "debit": str(tax_amount),
                    "credit": "0",
                    "description": "Tax",
                },
                {
                    "account_id": ap_account.id if ap_account else None,
                    "debit": "0",
                    "credit": str(amount),
                    "description": "Accounts Payable",
                },
            ],
        }
        
        # Store user overrides in extracted_payload for audit trail
        extracted = doc.extracted_payload or {}
        extracted["user_overrides"] = overrides
        doc.extracted_payload = extracted
        doc.proposed_journal_payload = proposal

    try:
        entry = post_journal_entry_from_proposal(business, proposal, request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    doc.posted_journal_entry = entry
    doc.status = InvoiceDocument.DocumentStatus.POSTED
    doc.approved_by = request.user
    doc.approved_at = timezone.now()
    doc.save(
        update_fields=["posted_journal_entry", "status", "approved_by", "approved_at", "extracted_payload", "proposed_journal_payload"]
    )
    return JsonResponse({"journal_entry_id": entry.id, "status": doc.status})


@login_required
@require_POST
def api_invoice_discard(request, invoice_id: int):
    business = get_current_business(request.user)
    if business is None:
        return HttpResponseBadRequest("No business context")
    doc = InvoiceDocument.objects.filter(business=business, pk=invoice_id).first()
    if not doc:
        return JsonResponse({"error": "Invoice not found"}, status=404)
    reason = request.POST.get("reason", "")
    doc.status = InvoiceDocument.DocumentStatus.DISCARDED
    doc.discard_reason = reason[:255]
    doc.discarded_by = request.user
    doc.discarded_at = timezone.now()
    doc.save(update_fields=["status", "discard_reason", "discarded_by", "discarded_at"])
    return JsonResponse({"status": doc.status})


@login_required
def invoices_page(request):
    business = get_current_business(request.user)
    if business is None:
        return redirect("business_setup")
    return render(
        request,
        "invoices.html",
        {
            "business": business,
            "default_currency": business.currency,
        },
    )
