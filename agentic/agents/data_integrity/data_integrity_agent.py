"""
Data Integrity Agent - AI Employee for Data Quality

Handles:
- Schema drift detection
- Suspicious transaction flagging
- Data validation
- Reconciliation analysis
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal

from agentic_core.agents.base_agent import BaseAgent
from agentic.agents.shared.profile import AgentProfile


class DataIntegrityAgent(BaseAgent):
    """
    AI Employee for data quality and integrity.

    Capabilities:
    - Scan for schema drift
    - Flag suspicious transactions
    - Validate data consistency
    - Analyze reconciliation discrepancies

    This agent has HIGH risk level as it identifies
    potential data issues that could affect financials.
    """

    agent_name = "data_integrity_agent"
    agent_version = "0.1.0"

    profile = AgentProfile(
        name="Data Integrity Agent",
        role="data_integrity",
        description=(
            "AI employee responsible for data quality and integrity monitoring. "
            "Scans for schema drift, flags suspicious transactions, validates "
            "data consistency, and analyzes reconciliation discrepancies."
        ),
        capabilities=[
            "scan_for_schema_drift",
            "flag_suspicious_transactions",
            "validate_ledger_consistency",
            "analyze_reconciliation_gaps",
            "detect_duplicate_entries",
            "verify_audit_trail",
        ],
        max_parallel_tasks=2,
        risk_level="high",
        llm_model="gpt-4.1-mini",
        system_prompt=(
            "You are a Data Integrity AI analyst. Your role is to protect the "
            "accuracy and reliability of financial data. Be thorough, flag any "
            "anomalies with clear evidence, and never assume data is clean. "
            "Financial accuracy is paramount."
        ),
        tools=[
            "schema_comparator",
            "transaction_analyzer",
            "audit_log_checker",
            "reconciliation_matcher",
        ],
        owner_team="data_platform",
    )

    def __init__(self, llm_client: Optional[Any] = None, **kwargs: Any):
        """Initialize the Data Integrity Agent."""
        super().__init__(llm_client=llm_client, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Default run method - delegates to specific capability methods."""
        self.log_step("DataIntegrityAgent.run() called - use specific methods instead")
        return {"status": "use_specific_methods"}

    async def scan_for_schema_drift(
        self,
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Scan events for schema drift.

        Args:
            events: List of event dictionaries to analyze.

        Returns:
            Schema drift analysis with findings.
        """
        self.log_step(f"Scanning {len(events)} events for schema drift")

        # Build prompt spec
        prompt_spec = {
            "task": "detect_schema_drift",
            "event_count": len(events),
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        if not events:
            return {
                "drift_detected": False,
                "findings": [],
                "recommendations": ["No events to analyze"],
            }

        # Analyze field presence across events
        field_presence: Dict[str, int] = {}
        field_types: Dict[str, set] = {}

        for event in events:
            for key, value in event.items():
                field_presence[key] = field_presence.get(key, 0) + 1
                if key not in field_types:
                    field_types[key] = set()
                field_types[key].add(type(value).__name__)

        findings = []
        total_events = len(events)

        # Check for inconsistent field presence
        for field, count in field_presence.items():
            presence_rate = count / total_events
            if 0.1 < presence_rate < 0.9:
                findings.append({
                    "type": "inconsistent_field",
                    "field": field,
                    "presence_rate": f"{presence_rate:.1%}",
                    "severity": "medium",
                    "message": f"Field '{field}' present in only {presence_rate:.1%} of events",
                })

        # Check for type inconsistencies
        for field, types in field_types.items():
            if len(types) > 1:
                findings.append({
                    "type": "type_mismatch",
                    "field": field,
                    "types_found": list(types),
                    "severity": "high",
                    "message": f"Field '{field}' has multiple types: {types}",
                })

        recommendations = []
        if findings:
            recommendations.append("Review event producers for schema consistency")
            recommendations.append("Consider adding schema validation middleware")
            if any(f["severity"] == "high" for f in findings):
                recommendations.append("URGENT: Fix type mismatches to prevent data corruption")

        return {
            "drift_detected": len(findings) > 0,
            "finding_count": len(findings),
            "findings": findings,
            "fields_analyzed": len(field_presence),
            "recommendations": recommendations,
        }

    async def flag_suspicious_transactions(
        self,
        transactions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Flag potentially suspicious transactions.

        Args:
            transactions: List of transaction dictionaries.

        Returns:
            List of flagged transactions with reasons.
        """
        self.log_step(f"Analyzing {len(transactions)} transactions for anomalies")

        # Build prompt spec
        prompt_spec = {
            "task": "flag_suspicious",
            "transaction_count": len(transactions),
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        flagged = []

        # Calculate statistics for anomaly detection
        amounts = []
        for txn in transactions:
            amount = txn.get("amount", 0)
            if isinstance(amount, (int, float, Decimal)):
                amounts.append(float(amount))

        if amounts:
            avg_amount = sum(amounts) / len(amounts)
            # Simple stddev approximation
            variance = sum((x - avg_amount) ** 2 for x in amounts) / len(amounts)
            std_dev = variance ** 0.5
        else:
            avg_amount = 0
            std_dev = 0

        for txn in transactions:
            flags = []
            risk_score = 0

            amount = float(txn.get("amount", 0))
            description = txn.get("description", "").lower()

            # Large transaction check
            if std_dev > 0 and abs(amount - avg_amount) > 3 * std_dev:
                flags.append("Unusually large deviation from average")
                risk_score += 30

            # Round number check
            if amount > 100 and amount == int(amount) and amount % 1000 == 0:
                flags.append("Suspiciously round amount")
                risk_score += 10

            # Description anomalies
            suspicious_keywords = ["cash", "personal", "loan", "transfer out", "adjustment"]
            for keyword in suspicious_keywords:
                if keyword in description:
                    flags.append(f"Contains suspicious keyword: '{keyword}'")
                    risk_score += 15

            # Missing fields
            if not txn.get("vendor") and not txn.get("payee"):
                flags.append("Missing vendor/payee information")
                risk_score += 20

            # Weekend/holiday transactions (simplified)
            if txn.get("is_weekend") or txn.get("is_holiday"):
                flags.append("Transaction on weekend/holiday")
                risk_score += 10

            # Duplicate detection (simplified)
            if txn.get("potential_duplicate"):
                flags.append("Potential duplicate transaction")
                risk_score += 25

            if flags:
                flagged.append({
                    "transaction_id": txn.get("id", "unknown"),
                    "amount": amount,
                    "description": txn.get("description", ""),
                    "flags": flags,
                    "risk_score": min(risk_score, 100),
                    "recommended_action": "review" if risk_score < 50 else "investigate",
                })

        return flagged

    async def validate_ledger_consistency(
        self,
        ledger_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate ledger consistency.

        Args:
            ledger_summary: Summary of ledger balances and totals.

        Returns:
            Validation result with any inconsistencies found.
        """
        self.log_step("Validating ledger consistency")

        issues = []

        # Check assets = liabilities + equity
        total_assets = float(ledger_summary.get("total_assets", 0))
        total_liabilities = float(ledger_summary.get("total_liabilities", 0))
        total_equity = float(ledger_summary.get("total_equity", 0))

        accounting_equation = total_assets - (total_liabilities + total_equity)
        if abs(accounting_equation) > 0.01:  # Allow penny rounding
            issues.append({
                "type": "accounting_equation_imbalance",
                "severity": "critical",
                "message": f"Assets ({total_assets}) ≠ Liabilities ({total_liabilities}) + Equity ({total_equity})",
                "difference": accounting_equation,
            })

        # Check debits = credits
        total_debits = float(ledger_summary.get("total_debits", 0))
        total_credits = float(ledger_summary.get("total_credits", 0))

        debit_credit_diff = abs(total_debits - total_credits)
        if debit_credit_diff > 0.01:
            issues.append({
                "type": "debit_credit_imbalance",
                "severity": "critical",
                "message": f"Total debits ({total_debits}) ≠ Total credits ({total_credits})",
                "difference": debit_credit_diff,
            })

        # Check for negative balances where not expected
        for account in ledger_summary.get("accounts", []):
            if account.get("type") == "asset" and account.get("balance", 0) < 0:
                issues.append({
                    "type": "unexpected_negative_balance",
                    "severity": "warning",
                    "message": f"Asset account '{account.get('name')}' has negative balance",
                    "balance": account.get("balance"),
                })

        return {
            "is_consistent": len(issues) == 0,
            "issues": issues,
            "critical_issues": sum(1 for i in issues if i["severity"] == "critical"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        }
