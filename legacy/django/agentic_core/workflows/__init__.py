"""
Workflow subpackage for the agentic accounting core.

This subpackage contains end-to-end workflow implementations that
orchestrate multiple agents and processing steps.

Current workflows:
- ReceiptsWorkflow: Document upload → extraction → journaling

Future workflows (Phase 2+):
- InvoiceWorkflow: Invoice processing and matching
- ReconciliationWorkflow: Bank reconciliation automation
- MonthEndWorkflow: Month-end close procedures
- AuditWorkflow: Continuous audit monitoring
"""

from agentic_core.workflows.receipts_workflow import ReceiptsWorkflow

__all__ = [
    "ReceiptsWorkflow",
]
