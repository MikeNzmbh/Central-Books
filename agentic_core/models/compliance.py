"""
Compliance models for regulatory checks and validations.

These models support the compliance agent's ability to check transactions
and entries against accounting rules, tax regulations, and business policies.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ComplianceSeverity(str, Enum):
    """Severity level for compliance issues."""

    INFO = "info"  # Informational, no action required
    WARNING = "warning"  # Should be reviewed
    ERROR = "error"  # Must be fixed before posting
    CRITICAL = "critical"  # Potential fraud or major regulatory violation


class ComplianceCategory(str, Enum):
    """Category of compliance check."""

    DOUBLE_ENTRY = "double_entry"  # Balance validation
    TAX = "tax"  # Tax compliance
    REGULATORY = "regulatory"  # Regulatory requirements
    POLICY = "policy"  # Internal business policies
    DATA_QUALITY = "data_quality"  # Data completeness/quality
    AUDIT_TRAIL = "audit_trail"  # Audit requirements
    OTHER = "other"


class ComplianceIssue(BaseModel):
    """
    A single compliance issue detected by the compliance agent.

    Represents a problem, warning, or informational note about a
    transaction or journal entry.

    Attributes:
        issue_id: Unique identifier for this issue.
        category: Type of compliance issue.
        severity: How serious the issue is.
        code: Unique code for this type of issue (e.g., "TAX-001").
        title: Short summary of the issue.
        description: Detailed explanation of the problem.
        affected_entity_type: What type of entity is affected.
        affected_entity_id: ID of the affected entity.
        field_name: Specific field with the issue (if applicable).
        expected_value: What the value should be.
        actual_value: What the value actually is.
        recommendation: Suggested fix or action.
        auto_fixable: Whether this can be automatically corrected.
        auto_fix_action: Action to auto-fix if applicable.
        reference_url: Link to relevant documentation/regulation.
        detected_at: When this issue was found.
    """

    issue_id: str = Field(default_factory=lambda: str(uuid4()))
    category: ComplianceCategory
    severity: ComplianceSeverity
    code: str
    title: str
    description: str
    affected_entity_type: str  # "transaction", "journal_entry", "document"
    affected_entity_id: Optional[str] = None
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    recommendation: Optional[str] = None
    auto_fixable: bool = False
    auto_fix_action: Optional[str] = None
    reference_url: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def is_blocking(self) -> bool:
        """Check if this issue blocks posting."""
        return self.severity in (ComplianceSeverity.ERROR, ComplianceSeverity.CRITICAL)


class ComplianceCheckResult(BaseModel):
    """
    Result of a compliance check run by the compliance agent.

    Contains all issues found during the check along with metadata
    about the check itself.

    Attributes:
        check_id: Unique identifier for this check run.
        check_name: Name of the compliance check performed.
        check_version: Version of the check logic.
        target_entity_type: What type of entity was checked.
        target_entity_id: ID of the checked entity.
        passed: Whether the check passed overall.
        issues: List of issues found.
        total_issues: Count of all issues.
        blocking_issues: Count of issues that block posting.
        checked_rules: List of rule codes that were evaluated.
        skipped_rules: List of rules skipped and why.
        metadata: Additional context about the check.
        started_at: When the check started.
        completed_at: When the check finished.
        duration_ms: How long the check took.
    """

    check_id: str = Field(default_factory=lambda: str(uuid4()))
    check_name: str
    check_version: str = "1.0.0"
    target_entity_type: str
    target_entity_id: Optional[str] = None
    passed: bool = True
    issues: list[ComplianceIssue] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)
    skipped_rules: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def total_issues(self) -> int:
        """Count of all issues."""
        return len(self.issues)

    @property
    def blocking_issues(self) -> int:
        """Count of issues that block posting."""
        return sum(1 for issue in self.issues if issue.is_blocking)

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are any blocking issues."""
        return self.blocking_issues > 0

    def add_issue(self, issue: ComplianceIssue) -> None:
        """Add an issue to this result."""
        self.issues.append(issue)
        if issue.is_blocking:
            self.passed = False

    def complete(self) -> None:
        """Mark the check as complete."""
        self.completed_at = datetime.utcnow()
        self.duration_ms = (
            (self.completed_at - self.started_at).total_seconds() * 1000
        )

    def get_issues_by_severity(
        self, severity: ComplianceSeverity
    ) -> list[ComplianceIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(
        self, category: ComplianceCategory
    ) -> list[ComplianceIssue]:
        """Get all issues of a specific category."""
        return [i for i in self.issues if i.category == category]
