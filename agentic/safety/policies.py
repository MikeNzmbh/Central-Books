"""
Safety Policies - Human-Readable Safety Rules

Defines the core safety policies for the Agentic Accounting OS.
These policies are enforced by guards and reviewed by supervisors.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class PolicyCategory(str, Enum):
    """Categories of safety policies."""
    FINANCIAL = "financial"
    DATA = "data"
    PRIVACY = "privacy"
    APPROVAL = "approval"
    ISOLATION = "isolation"


class SafetyPolicy(BaseModel):
    """
    A human-readable safety policy.
    
    Policies define what the system can and cannot do.
    They are enforced by guards and audited by supervisors.
    """
    
    id: str
    name: str
    category: PolicyCategory
    description: str
    rationale: str
    enforcement: str
    severity: str = "high"  # low, medium, high, critical
    enabled: bool = True
    
    class Config:
        frozen = True


# =============================================================================
# CORE SAFETY POLICIES
# =============================================================================

POLICY_NO_MONEY_MOVEMENT = SafetyPolicy(
    id="SAFETY-001",
    name="LLM Cannot Move Money",
    category=PolicyCategory.FINANCIAL,
    description="The LLM cannot directly execute financial transactions, transfers, or payments.",
    rationale="Financial transactions require human authorization to prevent fraud, errors, and ensure accountability.",
    enforcement="All transaction endpoints require human-approved session tokens. LLM can only propose transactions.",
    severity="critical",
)

POLICY_NO_ENTRY_APPROVAL = SafetyPolicy(
    id="SAFETY-002",
    name="LLM Cannot Approve Journal Entries",
    category=PolicyCategory.APPROVAL,
    description="The LLM cannot approve or post journal entries to the ledger.",
    rationale="Journal entries affect financial statements and must be reviewed by humans.",
    enforcement="Entry posting requires human approval flag. LLM generates proposals only.",
    severity="critical",
)

POLICY_NO_DATA_FABRICATION = SafetyPolicy(
    id="SAFETY-003",
    name="LLM Cannot Fabricate Financial Data",
    category=PolicyCategory.DATA,
    description="The LLM cannot create fake transactions, invoices, or financial records.",
    rationale="Fabricated financial data constitutes fraud and violates accounting standards.",
    enforcement="All financial data must trace to source documents. Audit trails required.",
    severity="critical",
)

POLICY_HUMAN_APPROVAL_POSTING = SafetyPolicy(
    id="SAFETY-004",
    name="Human Approval Required for Posting",
    category=PolicyCategory.APPROVAL,
    description="All journal entries must be approved by a human before posting to the ledger.",
    rationale="Double-check mechanism ensures accuracy and prevents automated errors.",
    enforcement="Posting API requires approval token from authenticated user session.",
    severity="high",
)

POLICY_TENANT_ISOLATION = SafetyPolicy(
    id="SAFETY-005",
    name="Tenant Isolation for Vector Memory",
    category=PolicyCategory.ISOLATION,
    description="Vector memory and embeddings are isolated per tenant/business.",
    rationale="Prevent data leakage between different businesses using the system.",
    enforcement="All memory queries include tenant_id filter. Cross-tenant queries blocked.",
    severity="high",
)

POLICY_NO_PII_LEAKAGE = SafetyPolicy(
    id="SAFETY-006",
    name="No PII Leakage",
    category=PolicyCategory.PRIVACY,
    description="Personally identifiable information must not be exposed in logs, prompts, or outputs.",
    rationale="Protect user privacy and comply with data protection regulations.",
    enforcement="PII detection in outputs. Masking in logs. Secure prompt handling.",
    severity="high",
)

POLICY_TRANSACTION_LIMITS = SafetyPolicy(
    id="SAFETY-007",
    name="High-Value Transaction Review",
    category=PolicyCategory.FINANCIAL,
    description="Transactions exceeding $10,000 require additional human review.",
    rationale="Large transactions carry higher risk and warrant extra scrutiny.",
    enforcement="Automatic flagging in compliance step. Supervisor escalation.",
    severity="medium",
)

POLICY_AUDIT_TRAIL = SafetyPolicy(
    id="SAFETY-008",
    name="Complete Audit Trail",
    category=PolicyCategory.DATA,
    description="All agent actions, decisions, and communications must be logged.",
    rationale="Enable post-hoc review, debugging, and regulatory compliance.",
    enforcement="Message bus logging. Workflow step recording. Supervisor daily logs.",
    severity="medium",
)


# =============================================================================
# POLICY REGISTRY
# =============================================================================

ALL_POLICIES: List[SafetyPolicy] = [
    POLICY_NO_MONEY_MOVEMENT,
    POLICY_NO_ENTRY_APPROVAL,
    POLICY_NO_DATA_FABRICATION,
    POLICY_HUMAN_APPROVAL_POSTING,
    POLICY_TENANT_ISOLATION,
    POLICY_NO_PII_LEAKAGE,
    POLICY_TRANSACTION_LIMITS,
    POLICY_AUDIT_TRAIL,
]

POLICY_BY_ID = {p.id: p for p in ALL_POLICIES}


def get_policy(policy_id: str) -> Optional[SafetyPolicy]:
    """Get a policy by ID."""
    return POLICY_BY_ID.get(policy_id)


def get_policies_by_category(category: PolicyCategory) -> List[SafetyPolicy]:
    """Get all policies in a category."""
    return [p for p in ALL_POLICIES if p.category == category]


def get_critical_policies() -> List[SafetyPolicy]:
    """Get all critical severity policies."""
    return [p for p in ALL_POLICIES if p.severity == "critical"]
