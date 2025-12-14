"""
Canonical Companion task catalog.

This is the single source of truth for task codes, surfaces, labels, and tiers.
Use these codes to anchor playbook steps, close-readiness messaging, and any
future task routing. Keep concise, accountant-friendly language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional

TaskTier = Literal["basic", "premium"]


@dataclass(frozen=True)
class CompanionTask:
    code: str
    surface: str  # receipts, invoices, bank, books, tax, close
    label: str
    description: str
    tier: TaskTier = "basic"

    @property
    def requires_premium(self) -> bool:
        return self.tier == "premium"


CANONICAL_TASKS: List[CompanionTask] = [
    # Receipts / Expenses
    CompanionTask(
        code="R1",
        surface="receipts",
        label="Review unprocessed receipts",
        description="Manually review receipts that are unprocessed or flagged as risky/ambiguous.",
        tier="basic",
    ),
    CompanionTask(
        code="R2",
        surface="receipts",
        label="Post approved receipts to ledger",
        description="Post cleared receipts to the ledger so expenses stay current.",
        tier="basic",
    ),
    # Invoices / Revenue
    CompanionTask(
        code="I1",
        surface="invoices",
        label="Match payments to invoices",
        description="Apply customer payments to open invoices and clear outstanding AR.",
        tier="basic",
    ),
    CompanionTask(
        code="I1B",
        surface="invoices",
        label="Chase overdue invoices",
        description="Follow up on overdue invoices across 30/60/90+ day buckets.",
        tier="basic",
    ),
    CompanionTask(
        code="I2",
        surface="invoices",
        label="Review revenue recognition anomalies",
        description="Flag and review unusual timing or allocation for revenue recognition.",
        tier="premium",
    ),
    # Banking
    CompanionTask(
        code="B1",
        surface="bank",
        label="Review unreconciled transactions",
        description="Clear unreconciled bank lines and confirm matches.",
        tier="basic",
    ),
    CompanionTask(
        code="B2",
        surface="bank",
        label="Confirm ending cash balance",
        description="Confirm the ending cash balance aligns to statements and ledger.",
        tier="basic",
    ),
    # Books / GL
    CompanionTask(
        code="G1",
        surface="books",
        label="Resolve suspense account balance",
        description="Investigate and clear suspense/clearing account balances.",
        tier="basic",
    ),
    CompanionTask(
        code="G2",
        surface="books",
        label="Fix unbalanced entries",
        description="Identify and correct unbalanced journal entries.",
        tier="basic",
    ),
    CompanionTask(
        code="G2B",
        surface="books",
        label="Validate retained earnings rollforward",
        description="Confirm retained earnings movement matches prior period plus current net income.",
        tier="basic",
    ),
    CompanionTask(
        code="G3",
        surface="books",
        label="Review negative tax payable/receivable",
        description="Confirm negative tax payable/receivable balances are intentional.",
        tier="basic",
    ),
    CompanionTask(
        code="G4",
        surface="books",
        label="Run Books Review and confirm status",
        description="Complete a Books Review and resolve findings for the period.",
        tier="basic",
    ),
    # Tax
    CompanionTask(
        code="T1",
        surface="tax",
        label="Review GST/HST / sales tax summary",
        description="Validate sales tax balances and filings for Canada/US contexts.",
        tier="basic",
    ),
    CompanionTask(
        code="T2",
        surface="tax",
        label="Confirm tax accrual for the period",
        description="Ensure tax accruals are posted and reconciled for the close.",
        tier="basic",
    ),
    CompanionTask(
        code="T3",
        surface="tax",
        label="Tie tax reports to GL",
        description="Reconcile tax collected vs. liability movement and verify report alignment.",
        tier="basic",
    ),
    # Close
    CompanionTask(
        code="C1",
        surface="close",
        label="Run final sanity checks",
        description="Confirm critical Companion issues are cleared and anomalies resolved before close.",
        tier="basic",
    ),
    CompanionTask(
        code="C2",
        surface="close",
        label="Lock this period",
        description="Lock the period once reconciliation and reviews are complete.",
        tier="basic",
    ),
]


TASK_CATALOG: Dict[str, CompanionTask] = {task.code: task for task in CANONICAL_TASKS}
SURFACE_INDEX: Dict[str, List[CompanionTask]] = {}
for task in CANONICAL_TASKS:
    SURFACE_INDEX.setdefault(task.surface, []).append(task)


def get_task(code: str) -> Optional[CompanionTask]:
    return TASK_CATALOG.get(code)


def tasks_for_surface(surface: str) -> List[CompanionTask]:
    return SURFACE_INDEX.get(surface, [])


def first_task_for_surface(surface: str, *, prefer_basic: bool = True) -> Optional[CompanionTask]:
    tasks = tasks_for_surface(surface)
    if not tasks:
        return None
    if not prefer_basic:
        return tasks[0]
    for task in tasks:
        if task.tier == "basic":
            return task
    return tasks[0]


def valid_task_code(code: str) -> bool:
    return code in TASK_CATALOG


def task_codes() -> Iterable[str]:
    return TASK_CATALOG.keys()
