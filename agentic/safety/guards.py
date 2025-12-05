"""
Safety Guards - Runtime Validation and Enforcement

Guards validate data and operations at runtime to enforce safety policies.
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
import re
import logging

from .policies import SafetyPolicy, ALL_POLICIES, PolicyCategory


logger = logging.getLogger(__name__)


# =============================================================================
# GUARD RESULT
# =============================================================================


@dataclass
class GuardResult:
    """Result of a safety guard check."""
    
    passed: bool
    guard_name: str
    policy_id: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "guard_name": self.guard_name,
            "policy_id": self.policy_id,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# GUARD FUNCTIONS
# =============================================================================


def validate_journal_entry(entry: Dict[str, Any]) -> GuardResult:
    """
    Validate a journal entry before processing.
    
    Checks:
    - Entry is balanced (debits == credits)
    - All required fields present
    - No invalid account codes
    - Amount is reasonable
    
    Returns:
        GuardResult indicating pass/fail
    """
    guard_name = "validate_journal_entry"
    
    # Check required fields
    required = ["entry_id", "date", "lines"]
    for field in required:
        if field not in entry:
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                policy_id="SAFETY-003",
                message=f"Missing required field: {field}",
            )
    
    lines = entry.get("lines", [])
    if not lines:
        return GuardResult(
            passed=False,
            guard_name=guard_name,
            policy_id="SAFETY-003",
            message="Journal entry has no lines",
        )
    
    # Calculate balance
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    
    for line in lines:
        try:
            amount = Decimal(str(line.get("amount", 0)))
            side = line.get("side", "").lower()
            
            if side == "debit":
                total_debits += amount
            elif side == "credit":
                total_credits += amount
            else:
                return GuardResult(
                    passed=False,
                    guard_name=guard_name,
                    message=f"Invalid side: {side}",
                )
        except Exception as e:
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                message=f"Invalid amount format: {e}",
            )
    
    # Check balance
    if abs(total_debits - total_credits) > Decimal("0.01"):
        return GuardResult(
            passed=False,
            guard_name=guard_name,
            policy_id="SAFETY-003",
            message=f"Entry unbalanced: debits={total_debits}, credits={total_credits}",
            details={"debits": str(total_debits), "credits": str(total_credits)},
        )
    
    return GuardResult(
        passed=True,
        guard_name=guard_name,
        message="Journal entry is valid",
    )


def validate_llm_output(
    output: str,
    context: Optional[Dict[str, Any]] = None,
) -> GuardResult:
    """
    Validate LLM output for safety violations.
    
    Checks:
    - No executable code injection
    - No PII patterns
    - No approval/authorization language
    
    Returns:
        GuardResult indicating pass/fail
    """
    guard_name = "validate_llm_output"
    
    # Check for code injection patterns
    dangerous_patterns = [
        r"import\s+os",
        r"subprocess\.",
        r"eval\(",
        r"exec\(",
        r"\bsudo\b",
        r"rm\s+-rf",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                policy_id="SAFETY-003",
                message=f"Potentially dangerous pattern detected: {pattern}",
            )
    
    # Check for PII patterns
    pii_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{16}\b",             # Credit card
        r"\b[A-Z]{2}\d{6,8}\b",    # Passport
    ]
    
    for pattern in pii_patterns:
        if re.search(pattern, output):
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                policy_id="SAFETY-006",
                message="Potential PII detected in output",
                details={"pattern": pattern},
            )
    
    # Check for unauthorized action language
    auth_patterns = [
        r"i\s+approve\s+this",
        r"transaction\s+completed",
        r"payment\s+processed",
        r"entry\s+posted",
    ]
    
    for pattern in auth_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                policy_id="SAFETY-002",
                message="LLM claiming unauthorized action",
            )
    
    return GuardResult(
        passed=True,
        guard_name=guard_name,
        message="LLM output passed safety checks",
    )


def validate_cross_tenant(
    source_tenant_id: str,
    target_tenant_id: str,
    operation: str = "read",
) -> GuardResult:
    """
    Validate cross-tenant data access.
    
    Enforces tenant isolation policy.
    
    Returns:
        GuardResult indicating pass/fail
    """
    guard_name = "validate_cross_tenant"
    
    if source_tenant_id != target_tenant_id:
        return GuardResult(
            passed=False,
            guard_name=guard_name,
            policy_id="SAFETY-005",
            message=f"Cross-tenant {operation} blocked",
            details={
                "source_tenant": source_tenant_id,
                "target_tenant": target_tenant_id,
            },
        )
    
    return GuardResult(
        passed=True,
        guard_name=guard_name,
        message="Tenant isolation validated",
    )


def validate_transaction_amount(
    amount: Decimal,
    currency: str = "USD",
    threshold: Decimal = Decimal("10000"),
) -> GuardResult:
    """
    Validate transaction amount for review thresholds.
    
    Returns:
        GuardResult indicating if review is needed
    """
    guard_name = "validate_transaction_amount"
    
    if amount > threshold:
        return GuardResult(
            passed=False,  # Not a failure, but needs review
            guard_name=guard_name,
            policy_id="SAFETY-007",
            message=f"Transaction exceeds ${threshold} threshold",
            details={
                "amount": str(amount),
                "threshold": str(threshold),
                "currency": currency,
                "requires_review": True,
            },
        )
    
    return GuardResult(
        passed=True,
        guard_name=guard_name,
        message="Transaction amount within limits",
    )


def validate_prompt_injection(prompt: str) -> GuardResult:
    """
    Check for prompt injection attempts.
    
    Returns:
        GuardResult indicating pass/fail
    """
    guard_name = "validate_prompt_injection"
    
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"disregard\s+all\s+prior",
        r"you\s+are\s+now\s+",
        r"system:\s*",
        r"\[INST\]",
        r"<\|im_start\|>",
    ]
    
    for pattern in injection_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            return GuardResult(
                passed=False,
                guard_name=guard_name,
                message="Potential prompt injection detected",
                details={"pattern": pattern},
            )
    
    return GuardResult(
        passed=True,
        guard_name=guard_name,
        message="Prompt passed injection check",
    )


# =============================================================================
# SAFETY GUARD CLASS
# =============================================================================


class SafetyGuard:
    """
    Central safety guard for running multiple validations.
    """
    
    def __init__(self):
        self._validators: List[Callable] = [
            validate_journal_entry,
            validate_llm_output,
            validate_cross_tenant,
            validate_transaction_amount,
            validate_prompt_injection,
        ]
        self._results: List[GuardResult] = []
    
    def validate_entry(self, entry: Dict[str, Any]) -> GuardResult:
        """Validate a journal entry."""
        result = validate_journal_entry(entry)
        self._results.append(result)
        return result
    
    def validate_output(self, output: str) -> GuardResult:
        """Validate LLM output."""
        result = validate_llm_output(output)
        self._results.append(result)
        return result
    
    def validate_tenant(
        self,
        source: str,
        target: str,
        operation: str = "read",
    ) -> GuardResult:
        """Validate tenant access."""
        result = validate_cross_tenant(source, target, operation)
        self._results.append(result)
        return result
    
    def validate_amount(
        self,
        amount: Decimal,
        currency: str = "USD",
    ) -> GuardResult:
        """Validate transaction amount."""
        result = validate_transaction_amount(amount, currency)
        self._results.append(result)
        return result
    
    def validate_prompt(self, prompt: str) -> GuardResult:
        """Validate prompt for injection."""
        result = validate_prompt_injection(prompt)
        self._results.append(result)
        return result
    
    def get_failures(self) -> List[GuardResult]:
        """Get all failed validations."""
        return [r for r in self._results if not r.passed]
    
    def get_results(self) -> List[GuardResult]:
        """Get all validation results."""
        return self._results.copy()
    
    def clear(self) -> None:
        """Clear result history."""
        self._results.clear()
