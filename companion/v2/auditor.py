from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType

from companion.models import CanonicalLedgerProvenance
from core.models import Account, JournalEntry


FORBIDDEN_ACCOUNT_TOKENS = (
    "payroll",
    "wages",
    "salary",
    "equity",
    "shareholder",
    "owner draw",
    "owners draw",
    "owner's draw",
    "shareholder loan",
    "intercompany",
    "due to",
    "due from",
)


@dataclass(frozen=True)
class AuditFinding:
    content_type_id: int
    object_id: int
    reasons: list[str]
    details: dict[str, Any]


def _account_risk_reasons(account: Account) -> list[str]:
    reasons: list[str] = []
    if account.type == Account.AccountType.EQUITY:
        reasons.append("equity_account")
    if getattr(account, "is_suspense", False):
        reasons.append("suspense_account")
    name = (account.name or "").lower()
    if any(tok in name for tok in FORBIDDEN_ACCOUNT_TOKENS):
        reasons.append("scope_boundary_account")
    return sorted(set(reasons))


def audit_journal_entry(entry: JournalEntry) -> list[AuditFinding]:
    reasons: list[str] = []
    accounts: list[dict[str, Any]] = []
    for line in entry.lines.select_related("account").all():
        acc = line.account
        acc_reasons = _account_risk_reasons(acc)
        if acc_reasons:
            reasons.extend(acc_reasons)
        accounts.append(
            {
                "account_id": acc.id,
                "account_name": acc.name,
                "account_type": acc.type,
                "debit": str(line.debit),
                "credit": str(line.credit),
                "reasons": acc_reasons,
            }
        )

    if not reasons:
        return []

    return [
        AuditFinding(
            content_type_id=ContentType.objects.get_for_model(JournalEntry).id,
            object_id=entry.id,
            reasons=sorted(set(reasons)),
            details={
                "date": entry.date.isoformat(),
                "description": entry.description,
                "accounts": accounts,
            },
        )
    ]


def audit_workspace(
    *,
    workspace,
    period_start: date,
    period_end: date,
) -> tuple[dict[str, Any], list[AuditFinding]]:
    """
    Rules-first auditor. No LLM.
    """
    prov_qs = CanonicalLedgerProvenance.objects.filter(
        workspace=workspace,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).select_related("content_type")

    journal_entry_ct = ContentType.objects.get_for_model(JournalEntry)
    je_ids = list(prov_qs.filter(content_type=journal_entry_ct).values_list("object_id", flat=True))
    entries = JournalEntry.objects.filter(business=workspace, id__in=je_ids).prefetch_related("lines__account")

    findings: list[AuditFinding] = []
    for entry in entries:
        findings.extend(audit_journal_entry(entry))

    summary = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "canonical_items_reviewed": len(je_ids),
        "flagged_count": len(findings),
        "rules": {
            "scope_boundary_account": True,
            "suspense_account": True,
            "equity_account": True,
        },
    }
    return summary, findings

