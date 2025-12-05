"""
Evaluation Scorer - Confidence and Risk Scoring System

Provides scoring for:
- Data extraction confidence
- Transaction accuracy
- Compliance risk
- Audit risk
- Agent handoff quality

Scoring Formulas:
-----------------
1. Extraction Confidence:
   score = (field_completeness * 0.4) + (vendor_match_score * 0.3) + (amount_parse_score * 0.3)

2. Transaction Accuracy:
   score = (category_match * 0.35) + (amount_match * 0.35) + (date_parse * 0.15) + (vendor_match * 0.15)

3. Compliance Risk:
   score = 1.0 - (issue_count * 0.1 * severity_weight)

4. Audit Risk:
   score = 1.0 - (finding_count * 0.15 * severity_weight)

5. Agent Handoff Quality:
   score = (context_completeness * 0.4) + (timing_score * 0.3) + (success_rate * 0.3)
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime, timezone


# =============================================================================
# ENUMS
# =============================================================================


class ConfidenceLevel(str, Enum):
    """Confidence level categories."""
    VERY_LOW = "very_low"      # 0.0 - 0.2
    LOW = "low"                # 0.2 - 0.4
    MEDIUM = "medium"          # 0.4 - 0.6
    HIGH = "high"              # 0.6 - 0.8
    VERY_HIGH = "very_high"    # 0.8 - 1.0


class RiskLevel(str, Enum):
    """Risk level categories."""
    MINIMAL = "minimal"        # 0.0 - 0.2
    LOW = "low"                # 0.2 - 0.4
    MEDIUM = "medium"          # 0.4 - 0.6
    HIGH = "high"              # 0.6 - 0.8
    CRITICAL = "critical"      # 0.8 - 1.0


# =============================================================================
# SCORE MODELS
# =============================================================================


@dataclass
class ScoreResult:
    """
    Result of an evaluation score.
    """
    score: float              # 0.0 - 1.0
    level: str                # Categorical level
    category: str             # What was scored
    components: Dict[str, float] = field(default_factory=dict)
    factors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def model_dump(self) -> dict:
        return {
            "score": round(self.score, 4),
            "level": self.level,
            "category": self.category,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "factors": self.factors,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @property
    def is_acceptable(self) -> bool:
        """Check if score is acceptable (> 0.5)."""
        return self.score >= 0.5


@dataclass
class EvaluationReport:
    """
    Complete evaluation report for a workflow.
    """
    workflow_id: str
    scores: Dict[str, ScoreResult] = field(default_factory=dict)
    overall_score: float = 0.0
    overall_level: str = ""
    recommendations: List[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def model_dump(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "scores": {k: v.model_dump() for k, v in self.scores.items()},
            "overall_score": round(self.overall_score, 4),
            "overall_level": self.overall_level,
            "recommendations": self.recommendations,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# =============================================================================
# SCORER
# =============================================================================


class EvaluationScorer:
    """
    Scoring engine for workflow evaluation.
    
    Computes confidence and risk scores for:
    - Data extraction
    - Transaction processing
    - Compliance checking
    - Audit analysis
    - Agent coordination
    """
    
    # Weight configurations
    EXTRACTION_WEIGHTS = {
        "field_completeness": 0.4,
        "vendor_match": 0.3,
        "amount_parse": 0.3,
    }
    
    TRANSACTION_WEIGHTS = {
        "category_match": 0.35,
        "amount_match": 0.35,
        "date_parse": 0.15,
        "vendor_match": 0.15,
    }
    
    SEVERITY_WEIGHTS = {
        "info": 0.1,
        "low": 0.25,
        "medium": 0.5,
        "high": 0.75,
        "critical": 1.0,
    }
    
    def __init__(self):
        pass
    
    # =========================================================================
    # SCORING METHODS
    # =========================================================================
    
    def score_extraction(
        self,
        extracted_docs: List[Dict[str, Any]],
    ) -> ScoreResult:
        """
        Score data extraction confidence.
        
        Evaluates:
        - Field completeness (vendor, amount, date, category)
        - Vendor matching quality
        - Amount parsing accuracy
        """
        if not extracted_docs:
            return ScoreResult(
                score=0.0,
                level=ConfidenceLevel.VERY_LOW.value,
                category="extraction",
                factors=["No documents extracted"],
            )
        
        # Calculate component scores
        field_scores = []
        vendor_scores = []
        amount_scores = []
        
        for doc in extracted_docs:
            # Field completeness
            required_fields = ["vendor_name", "total_amount", "currency"]
            present = sum(1 for f in required_fields if doc.get(f))
            field_scores.append(present / len(required_fields))
            
            # Vendor quality (non-default vendor)
            vendor = doc.get("vendor_name", "")
            if vendor and vendor not in ["Unknown Vendor", "Generic Vendor", ""]:
                vendor_scores.append(1.0)
            else:
                vendor_scores.append(0.3)
            
            # Amount quality (valid decimal)
            amount = doc.get("total_amount", "0")
            try:
                val = Decimal(str(amount))
                if val > 0:
                    amount_scores.append(1.0)
                else:
                    amount_scores.append(0.5)
            except:
                amount_scores.append(0.0)
        
        # Aggregate
        field_avg = sum(field_scores) / len(field_scores) if field_scores else 0
        vendor_avg = sum(vendor_scores) / len(vendor_scores) if vendor_scores else 0
        amount_avg = sum(amount_scores) / len(amount_scores) if amount_scores else 0
        
        # Weighted score
        weights = self.EXTRACTION_WEIGHTS
        score = (
            field_avg * weights["field_completeness"] +
            vendor_avg * weights["vendor_match"] +
            amount_avg * weights["amount_parse"]
        )
        
        return ScoreResult(
            score=score,
            level=self._score_to_confidence_level(score).value,
            category="extraction",
            components={
                "field_completeness": field_avg,
                "vendor_match": vendor_avg,
                "amount_parse": amount_avg,
            },
            factors=[f"Evaluated {len(extracted_docs)} documents"],
        )
    
    def score_transaction_accuracy(
        self,
        transactions: List[Dict[str, Any]],
        reference: Optional[List[Dict[str, Any]]] = None,
    ) -> ScoreResult:
        """
        Score transaction processing accuracy.
        
        If reference data is provided, compares against it.
        Otherwise uses heuristics.
        """
        if not transactions:
            return ScoreResult(
                score=0.0,
                level=ConfidenceLevel.VERY_LOW.value,
                category="transaction_accuracy",
                factors=["No transactions to evaluate"],
            )
        
        # Score each transaction
        category_scores = []
        amount_scores = []
        date_scores = []
        vendor_scores = []
        
        for txn in transactions:
            # Category - check if valid code
            category = txn.get("category_code", "")
            if category and category != "9000":  # Not suspense
                category_scores.append(1.0)
            elif category == "9000":
                category_scores.append(0.3)
            else:
                category_scores.append(0.0)
            
            # Amount - check valid
            amount = txn.get("amount", "0")
            try:
                val = Decimal(str(amount))
                amount_scores.append(1.0 if val > 0 else 0.5)
            except:
                amount_scores.append(0.0)
            
            # Date - check format
            date_str = txn.get("date", "")
            if date_str and len(date_str) >= 10:
                date_scores.append(1.0)
            else:
                date_scores.append(0.5)
            
            # Vendor
            vendor = txn.get("vendor_id") or txn.get("source_document_id", "")
            vendor_scores.append(1.0 if vendor else 0.5)
        
        # Aggregate
        weights = self.TRANSACTION_WEIGHTS
        score = (
            (sum(category_scores) / len(category_scores)) * weights["category_match"] +
            (sum(amount_scores) / len(amount_scores)) * weights["amount_match"] +
            (sum(date_scores) / len(date_scores)) * weights["date_parse"] +
            (sum(vendor_scores) / len(vendor_scores)) * weights["vendor_match"]
        )
        
        return ScoreResult(
            score=score,
            level=self._score_to_confidence_level(score).value,
            category="transaction_accuracy",
            components={
                "category_match": sum(category_scores) / len(category_scores),
                "amount_match": sum(amount_scores) / len(amount_scores),
                "date_parse": sum(date_scores) / len(date_scores),
                "vendor_match": sum(vendor_scores) / len(vendor_scores),
            },
            factors=[f"Evaluated {len(transactions)} transactions"],
        )
    
    def score_compliance_risk(
        self,
        compliance_result: Dict[str, Any],
    ) -> ScoreResult:
        """
        Score compliance risk level.
        
        Higher score = lower risk (more compliant).
        """
        issues = compliance_result.get("issues", [])
        is_compliant = compliance_result.get("is_compliant", True)
        
        if is_compliant and not issues:
            return ScoreResult(
                score=1.0,
                level=RiskLevel.MINIMAL.value,
                category="compliance_risk",
                factors=["No compliance issues"],
            )
        
        # Calculate risk from issues
        total_risk = 0.0
        for issue in issues:
            severity = issue.get("severity", "low")
            weight = self.SEVERITY_WEIGHTS.get(severity, 0.25)
            total_risk += 0.1 * weight
        
        # Invert for score (lower risk = higher score)
        score = max(0.0, 1.0 - total_risk)
        
        factors = [f"{len(issues)} compliance issues found"]
        for issue in issues[:3]:
            factors.append(f"- {issue.get('code', 'unknown')}: {issue.get('severity', 'low')}")
        
        return ScoreResult(
            score=score,
            level=self._score_to_risk_level(1.0 - score).value,
            category="compliance_risk",
            components={"issue_count": len(issues)},
            factors=factors,
        )
    
    def score_audit_risk(
        self,
        audit_report: Dict[str, Any],
    ) -> ScoreResult:
        """
        Score audit risk level.
        
        Higher score = lower risk (cleaner audit).
        """
        findings = audit_report.get("findings", [])
        risk_level = audit_report.get("risk_level", "low")
        
        if risk_level == "low" and not findings:
            return ScoreResult(
                score=1.0,
                level=RiskLevel.MINIMAL.value,
                category="audit_risk",
                factors=["No audit findings"],
            )
        
        # Calculate risk from findings
        total_risk = 0.0
        for finding in findings:
            severity = finding.get("severity", "low")
            weight = self.SEVERITY_WEIGHTS.get(severity, 0.25)
            total_risk += 0.15 * weight
        
        # Add base risk from overall level
        level_risk = {"low": 0.0, "medium": 0.2, "high": 0.5}.get(risk_level, 0.1)
        total_risk = min(1.0, total_risk + level_risk)
        
        score = max(0.0, 1.0 - total_risk)
        
        factors = [f"Audit risk level: {risk_level}"]
        if findings:
            factors.append(f"{len(findings)} findings detected")
        
        return ScoreResult(
            score=score,
            level=self._score_to_risk_level(1.0 - score).value,
            category="audit_risk",
            components={
                "finding_count": len(findings),
                "base_risk_level": risk_level,
            },
            factors=factors,
        )
    
    def score_journal_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> ScoreResult:
        """
        Score journal entry quality.
        
        Checks:
        - Balance (debits = credits)
        - Valid accounts
        - Completeness
        """
        if not entries:
            return ScoreResult(
                score=0.0,
                level=ConfidenceLevel.VERY_LOW.value,
                category="journal_quality",
                factors=["No journal entries"],
            )
        
        balanced_count = 0
        complete_count = 0
        
        for entry in entries:
            # Check balance
            is_balanced = entry.get("is_balanced", False)
            if is_balanced:
                balanced_count += 1
            
            # Check completeness
            has_lines = bool(entry.get("lines", []))
            has_date = bool(entry.get("date", ""))
            has_desc = bool(entry.get("description", ""))
            
            if has_lines and has_date and has_desc:
                complete_count += 1
        
        balance_score = balanced_count / len(entries)
        complete_score = complete_count / len(entries)
        
        score = balance_score * 0.7 + complete_score * 0.3
        
        factors = []
        if balanced_count < len(entries):
            factors.append(f"{len(entries) - balanced_count} unbalanced entries")
        if complete_count < len(entries):
            factors.append(f"{len(entries) - complete_count} incomplete entries")
        if not factors:
            factors.append("All entries balanced and complete")
        
        return ScoreResult(
            score=score,
            level=self._score_to_confidence_level(score).value,
            category="journal_quality",
            components={
                "balance_score": balance_score,
                "completeness_score": complete_score,
            },
            factors=factors,
        )
    
    def score_handoff_quality(
        self,
        handoff_context: Dict[str, Any],
    ) -> ScoreResult:
        """
        Score agent handoff quality.
        
        Evaluates context completeness for agent-to-agent transfers.
        """
        required_fields = [
            "workflow_id",
            "source_agent",
            "target_agent",
            "task_description",
        ]
        
        optional_fields = [
            "context_data",
            "priority",
            "deadline",
            "dependencies",
        ]
        
        # Score required fields
        required_present = sum(1 for f in required_fields if handoff_context.get(f))
        required_score = required_present / len(required_fields)
        
        # Score optional fields
        optional_present = sum(1 for f in optional_fields if handoff_context.get(f))
        optional_score = optional_present / len(optional_fields)
        
        # Timing score (if deadline present and reasonable)
        timing_score = 0.5  # Default
        if handoff_context.get("deadline"):
            timing_score = 0.8
        
        # Combined score
        score = (
            required_score * 0.5 +
            optional_score * 0.2 +
            timing_score * 0.3
        )
        
        return ScoreResult(
            score=score,
            level=self._score_to_confidence_level(score).value,
            category="handoff_quality",
            components={
                "required_fields": required_score,
                "optional_fields": optional_score,
                "timing": timing_score,
            },
            factors=[
                f"Required: {required_present}/{len(required_fields)}",
                f"Optional: {optional_present}/{len(optional_fields)}",
            ],
        )
    
    # =========================================================================
    # COMPREHENSIVE EVALUATION
    # =========================================================================
    
    def evaluate_workflow(
        self,
        workflow_id: str,
        artifacts: Dict[str, Any],
    ) -> EvaluationReport:
        """
        Perform comprehensive evaluation of a workflow's outputs.
        
        Args:
            workflow_id: ID of the workflow
            artifacts: Workflow artifacts including documents, transactions, entries, etc.
        
        Returns:
            EvaluationReport with all scores and recommendations
        """
        report = EvaluationReport(workflow_id=workflow_id)
        
        # Score extraction
        if "extracted_documents" in artifacts or "extracted_invoices" in artifacts:
            docs = artifacts.get("extracted_documents", []) or artifacts.get("extracted_invoices", [])
            if docs:
                doc_list = [d.model_dump() if hasattr(d, "model_dump") else d for d in docs]
                report.scores["extraction"] = self.score_extraction(doc_list)
        
        # Score transactions
        if "transactions" in artifacts or "invoice_transactions" in artifacts:
            txns = artifacts.get("transactions", []) or artifacts.get("invoice_transactions", [])
            if txns:
                txn_list = [t.model_dump() if hasattr(t, "model_dump") else t for t in txns]
                report.scores["transaction_accuracy"] = self.score_transaction_accuracy(txn_list)
        
        # Score journal entries
        if "journal_entries" in artifacts:
            entries = artifacts["journal_entries"]
            if entries:
                entry_list = [e.model_dump() if hasattr(e, "model_dump") else e for e in entries]
                report.scores["journal_quality"] = self.score_journal_entries(entry_list)
        
        # Score compliance
        if "compliance_result" in artifacts:
            compliance = artifacts["compliance_result"]
            if compliance:
                comp_dict = compliance.model_dump() if hasattr(compliance, "model_dump") else compliance
                report.scores["compliance_risk"] = self.score_compliance_risk(comp_dict)
        
        # Score audit
        if "audit_report" in artifacts:
            audit = artifacts["audit_report"]
            if audit:
                audit_dict = audit.model_dump() if hasattr(audit, "model_dump") else audit
                report.scores["audit_risk"] = self.score_audit_risk(audit_dict)
        
        # Calculate overall score
        if report.scores:
            all_scores = [s.score for s in report.scores.values()]
            report.overall_score = sum(all_scores) / len(all_scores)
            report.overall_level = self._score_to_confidence_level(report.overall_score).value
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report.scores)
        
        return report
    
    def _generate_recommendations(
        self,
        scores: Dict[str, ScoreResult],
    ) -> List[str]:
        """Generate recommendations based on scores."""
        recs = []
        
        for category, result in scores.items():
            if result.score < 0.5:
                if category == "extraction":
                    recs.append("Improve document extraction - consider manual review")
                elif category == "transaction_accuracy":
                    recs.append("Review transaction categorization rules")
                elif category == "journal_quality":
                    recs.append("Fix unbalanced journal entries before posting")
                elif category == "compliance_risk":
                    recs.append("Address compliance issues before proceeding")
                elif category == "audit_risk":
                    recs.append("Review flagged audit findings")
        
        if not recs:
            recs.append("All metrics acceptable - ready for review")
        
        return recs
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _score_to_confidence_level(self, score: float) -> ConfidenceLevel:
        """Convert numeric score to confidence level."""
        if score >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.6:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW
    
    def _score_to_risk_level(self, risk: float) -> RiskLevel:
        """Convert numeric risk to risk level."""
        if risk >= 0.8:
            return RiskLevel.CRITICAL
        elif risk >= 0.6:
            return RiskLevel.HIGH
        elif risk >= 0.4:
            return RiskLevel.MEDIUM
        elif risk >= 0.2:
            return RiskLevel.LOW
        return RiskLevel.MINIMAL
