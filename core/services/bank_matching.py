"""
Bank Reconciliation Matching Engine

Implements 3-tier automatic matching for bank transactions:
- Tier 1: Deterministic ID match (confidence 1.00)
- Tier 2: Invoice reference in description/remittance (confidence 0.95)
- Tier 3: Amount + date heuristic (confidence 0.80, or 0.50 if ambiguous)

Configuration:
Adjust MatchingConfig class constants to tune matching behavior.
"""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from core.models import (
    BankTransaction,
    Invoice,
    Expense,
    JournalEntry,
)


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

class MatchingConfig:
    """
    Configuration for bank transaction matching engine.
    
    Adjust these values to tune matching behavior:
    - DATE_LOOKBACK_DAYS: How many days BEFORE the bank transaction to search (stale payments)
    - DATE_LOOKAHEAD_DAYS: How many days AFTER the bank transaction to search (date entry errors)
    - CONFIDENCE_TIER1: Confidence for deterministic ID matches (should be 1.00)
    - CONFIDENCE_TIER2: Confidence for invoice/expense reference parsing
    - CONFIDENCE_TIER3_SINGLE: Confidence for single amount+date match
    - CONFIDENCE_TIER3_AMBIGUOUS: Confidence when multiple candidates found (requires manual selection)
    - DEFAULT_MAX_CANDIDATES: Maximum number of match candidates to return
    - AMOUNT_TOLERANCE: Tolerance for amount matching (in currency units, e.g., 0.01 = 1 cent)
    
    QBO-style asymmetric window: Bank transactions often represent stale payments 
    (e.g., invoice from 2 months ago paid today), so lookback is longer than lookahead.
    """
    
    # Date matching window (asymmetric, QBO-style)
    DATE_LOOKBACK_DAYS: int = 90   # Look back 90 days for stale invoices/expenses
    DATE_LOOKAHEAD_DAYS: int = 20  # Look ahead 20 days for date entry errors
    
    # Legacy compatibility (used by some tests)
    DATE_TOLERANCE_DAYS: int = 90  # Default to lookback for backward compat
    
    # Confidence scores (0.00 to 1.00)
    CONFIDENCE_TIER1: Decimal = Decimal("1.00")  # Deterministic ID match
    CONFIDENCE_TIER2: Decimal = Decimal("0.95")  # Reference parsing
    CONFIDENCE_TIER3_SINGLE: Decimal = Decimal("0.80")  # Single amount+date match
    CONFIDENCE_TIER3_AMBIGUOUS: Decimal = Decimal("0.50")  # Multiple candidates
    
    # Result limits
    DEFAULT_MAX_CANDIDATES: int = 5
    
    # Amount matching tolerance
    AMOUNT_TOLERANCE: Decimal = Decimal("0.01")  # 1 cent


class BankMatchingEngine:
    """
    Three-tier automatic matching for bank reconciliation.
    
    This engine attempts to match bank transactions to existing journal entries
    using three progressively less certain matching strategies:
    
    1. Tier 1 (Deterministic): Match by external_id (100% confidence)
    2. Tier 2 (High Confidence): Parse invoice/expense references from description (95% confidence)
    3. Tier 3 (Heuristic): Match by amount + date proximity (80% or 50% confidence)
    
    Usage:
        matches = BankMatchingEngine.find_matches(bank_transaction)
        for match in matches:
            print(f"Confidence: {match['confidence']}, Reason: {match['reason']}")
    """

    @staticmethod
    def apply_suggestions(bank_transaction: BankTransaction) -> None:
        """
        Run matching engine and update bank_transaction suggestion fields.
        """
        matches = BankMatchingEngine.find_matches(bank_transaction, limit=1)
        if matches:
            best = matches[0]
            bank_transaction.suggestion_confidence = int(best["confidence"] * 100)
            bank_transaction.suggestion_reason = best["reason"]
            bank_transaction.status = BankTransaction.TransactionStatus.SUGGESTED
            bank_transaction.save(update_fields=["suggestion_confidence", "suggestion_reason", "status"])
        else:
            # No matches found
            if bank_transaction.status == BankTransaction.TransactionStatus.NEW:
                # Keep as NEW if no suggestions
                pass

    @staticmethod
    def find_matches(
        bank_transaction: BankTransaction,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find potential matches (Rules or Journal Entries).
        """
        if limit is None:
            limit = MatchingConfig.DEFAULT_MAX_CANDIDATES
            
        business = bank_transaction.bank_account.business
        candidates: List[Dict[str, Any]] = []

        # Tier 0: Bank Rules (Highest priority)
        tier0 = BankMatchingEngine._tier0_rule_match(bank_transaction, business)
        if tier0:
            candidates.extend(tier0)
            # Rules are definitive suggestions
            return candidates[:limit]

        # Tier 1: Deterministic ID match
        tier1 = BankMatchingEngine._tier1_id_match(bank_transaction, business)
        if tier1:
            candidates.extend(tier1)
            return candidates[:limit]

        # Tier 2: Invoice/expense reference in description
        tier2 = BankMatchingEngine._tier2_reference_match(bank_transaction, business)
        candidates.extend(tier2)

        # Tier 2.5: Cross-account transfer detection
        tier_transfer = BankMatchingEngine._tier_transfer_detection(bank_transaction, business)
        candidates.extend(tier_transfer)

        # Tier 3: Amount + date heuristic
        tier3 = BankMatchingEngine._tier3_amount_date_match(bank_transaction, business)
        candidates.extend(tier3)

        # Deduplicate and sort
        seen = set()
        unique_candidates = []
        for candidate in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
            # Use a unique key for deduplication
            if "rule" in candidate:
                key = f"rule_{candidate['rule'].id}"
            else:
                key = f"je_{candidate['journal_entry'].id}"
                
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)

        return unique_candidates[:limit]

    @staticmethod
    def _tier0_rule_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 0: Match against BankRules.
        
        QBO-style matching priority:
        1. bank_text_pattern against raw bank text (highest confidence)
        2. description_pattern against cleansed description
        3. Legacy pattern field (backward compatible)
        4. Merchant name substring match (fallback)
        """
        from core.models import BankRule
        
        candidates = []
        rules = BankRule.objects.filter(business=business)
        
        # Get raw bank text if available (some imports include it)
        raw_bank_text = getattr(tx, 'raw_bank_text', tx.description) or tx.description
        
        for rule in rules:
            # Priority 1: bank_text_pattern match (raw bank data)
            if rule.bank_text_pattern and re.search(rule.bank_text_pattern, raw_bank_text, re.IGNORECASE):
                candidates.append({
                    "rule": rule,
                    "confidence": Decimal("1.00"),
                    "match_type": "RULE",
                    "reason": f"Rule: {rule.merchant_name} (Bank text match)",
                    "auto_confirm": rule.auto_confirm,
                })
                continue  # Found best match, skip other checks
            
            # Priority 2: description_pattern match (user-friendly description)
            if rule.description_pattern and re.search(rule.description_pattern, tx.description, re.IGNORECASE):
                candidates.append({
                    "rule": rule,
                    "confidence": Decimal("0.98"),
                    "match_type": "RULE",
                    "reason": f"Rule: {rule.merchant_name} (Description match)",
                    "auto_confirm": rule.auto_confirm,
                })
                continue
            
            # Priority 3: Legacy pattern field (backward compatible)
            if rule.pattern and re.search(rule.pattern, tx.description, re.IGNORECASE):
                candidates.append({
                    "rule": rule,
                    "confidence": Decimal("1.00"),
                    "match_type": "RULE",
                    "reason": f"Rule: {rule.merchant_name}",
                    "auto_confirm": rule.auto_confirm,
                })
                continue
            
            # Priority 4: Merchant name substring match (fallback)
            if rule.merchant_name.lower() in tx.description.lower():
                candidates.append({
                    "rule": rule,
                    "confidence": Decimal("0.90"),
                    "match_type": "RULE",
                    "reason": f"Rule: {rule.merchant_name} (Name match)",
                    "auto_confirm": rule.auto_confirm,
                })
                
        return candidates

    @staticmethod
    def _tier1_id_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 1: Match by external_id or check number.
        """
        if not tx.external_id:
            return []

        candidates = []

        # Try matching to invoices by invoice_number
        invoice = (
            Invoice.objects.filter(
                business=business,
                invoice_number=tx.external_id,
            )
            .first()
        )

        if invoice:
            # Explicitly query JournalEntry
            ct = ContentType.objects.get_for_model(Invoice)
            journal_entry = JournalEntry.objects.filter(
                source_content_type=ct,
                source_object_id=invoice.id,
            ).first()
            
            if journal_entry:
                candidates.append(
                    {
                        "journal_entry": journal_entry,
                        "confidence": MatchingConfig.CONFIDENCE_TIER1,
                        "match_type": "ONE_TO_ONE",
                        "reason": f"Matched invoice #{invoice.invoice_number} by external_id",
                    }
                )
                return candidates  # Return immediately for deterministic match

        # Try matching to expenses by ID or reference
        if tx.external_id and tx.external_id.isdigit():
            expense = (
                Expense.objects.filter(
                    business=business,
                    id=int(tx.external_id),
                )
                .first()
            )

            if expense:
                # Explicitly query JournalEntry
                ct = ContentType.objects.get_for_model(Expense)
                journal_entry = JournalEntry.objects.filter(
                    source_content_type=ct,
                    source_object_id=expense.id,
                ).first()

                if journal_entry:
                    candidates.append(
                        {
                            "journal_entry": journal_entry,
                            "confidence": MatchingConfig.CONFIDENCE_TIER1,
                            "match_type": "ONE_TO_ONE",
                            "reason": f"Matched expense #{expense.id} by external_id",
                        }
                    )

        return candidates

    @staticmethod
    def _tier2_reference_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 2: Parse description for invoice/expense references.
        """
        candidates = []

        # Look for patterns like INV-1234, #INV1234, Invoice 1234
        invoice_patterns = [
            r"INV[- ]?(\d+)",
            r"#INV(\d+)",
            r"[Ii]nvoice[#\s-]*(\d+)",
        ]

        for pattern in invoice_patterns:
            match = re.search(pattern, tx.description, re.IGNORECASE)
            if match:
                invoice_num = match.group(1)

                # Find invoice(s) that match this number
                invoices = Invoice.objects.filter(
                    business=business, invoice_number__icontains=invoice_num
                )

                invoice_ct = ContentType.objects.get_for_model(Invoice)
                for invoice in invoices:
                    # Explicitly query JournalEntry to avoid GenericRelation issues
                    journal_entry = JournalEntry.objects.filter(
                        source_content_type=invoice_ct,
                        source_object_id=invoice.id,
                    ).first()
                    
                    if journal_entry:
                        candidates.append(
                            {
                                "journal_entry": journal_entry,
                                "confidence": MatchingConfig.CONFIDENCE_TIER2,
                                "match_type": "ONE_TO_ONE",
                                "reason": f"Invoice {invoice.invoice_number} referenced in description",
                            }
                        )

        # Look for expense patterns
        expense_patterns = [
            r"EXP[- ]?(\d+)",
            r"#EXP(\d+)",
            r"[Ee]xpense[#\s-]*(\d+)",
        ]

        for pattern in expense_patterns:
            match = re.search(pattern, tx.description, re.IGNORECASE)
            if match:
                expense_id_str = match.group(1)
                if expense_id_str.isdigit():
                    expense_id = int(expense_id_str)
                    expenses = Expense.objects.filter(
                        business=business, id=expense_id
                    )

                    expense_ct = ContentType.objects.get_for_model(Expense)
                    for expense in expenses:
                        journal_entry = JournalEntry.objects.filter(
                            source_content_type=expense_ct,
                            source_object_id=expense.id,
                        ).first()
                        
                        if journal_entry:
                            candidates.append(
                                {
                                    "journal_entry": journal_entry,
                                    "confidence": MatchingConfig.CONFIDENCE_TIER2,
                                    "match_type": "ONE_TO_ONE",
                                    "reason": f"Expense #{expense.id} referenced in description",
                                }
                            )

        return candidates

    @staticmethod
    def _tier3_amount_date_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 3: Match by amount + date proximity.
        
        Uses asymmetric date window (QBO-style):
        - Lookback 90 days for stale invoices/expenses that were paid late
        - Lookahead 20 days for minor date entry errors
        """
        amount_abs = abs(tx.amount)

        # Find journal entries with matching amount within asymmetric date window
        date_start = tx.date - timedelta(days=MatchingConfig.DATE_LOOKBACK_DAYS)
        date_end = tx.date + timedelta(days=MatchingConfig.DATE_LOOKAHEAD_DAYS)

        # Get all journal entries in the date range
        journal_entries = JournalEntry.objects.filter(
            business=business,
            date__gte=date_start,
            date__lte=date_end,
        ).prefetch_related("lines")

        candidate_entries = []
        for je in journal_entries:
            # Calculate total debit amount of the journal entry
            je_total = sum(line.debit for line in je.lines.all())

            # Check if amounts match (within tolerance)
            if abs(je_total - amount_abs) < MatchingConfig.AMOUNT_TOLERANCE:
                candidate_entries.append(je)

        # Build candidates list
        candidates = []
        if len(candidate_entries) == 1:
            # Single clear match: high confidence
            candidates.append(
                {
                    "journal_entry": candidate_entries[0],
                    "confidence": MatchingConfig.CONFIDENCE_TIER3_SINGLE,
                    "match_type": "ONE_TO_ONE",
                    "reason": f"Amount {amount_abs} matches (lookback: {MatchingConfig.DATE_LOOKBACK_DAYS}d, lookahead: {MatchingConfig.DATE_LOOKAHEAD_DAYS}d)",
                }
            )
        elif len(candidate_entries) > 1:
            # Multiple matches: low confidence, requires manual selection
            for je in candidate_entries:
                candidates.append(
                    {
                        "journal_entry": je,
                        "confidence": MatchingConfig.CONFIDENCE_TIER3_AMBIGUOUS,
                        "match_type": "ONE_TO_ONE",
                        "reason": f"Amount match (ambiguous: {len(candidate_entries)} candidates)",
                    }
                )

        return candidates

    @staticmethod
    def _tier_transfer_detection(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 2.5: Cross-account transfer detection.
        
        Looks for matching opposite transactions in other bank accounts:
        - If tx is a withdrawal (-$1000), look for deposits (+$1000) in other accounts
        - If tx is a deposit (+$1000), look for withdrawals (-$1000) in other accounts
        
        This helps identify internal transfers between accounts owned by the same business.
        """
        candidates = []
        
        tx_amount = Decimal(str(tx.amount))
        tx_date = tx.date
        current_account_id = tx.bank_account_id
        
        # Only look for transfers within a tight date window (3 days)
        date_tolerance = timedelta(days=3)
        date_start = tx_date - date_tolerance
        date_end = tx_date + date_tolerance
        
        # Look for opposite amount in OTHER bank accounts of the same business
        opposite_amount = -tx_amount
        
        # Get all other bank accounts for this business
        from core.models import BankAccount
        other_accounts = BankAccount.objects.filter(
            business=business
        ).exclude(id=current_account_id)
        
        for other_account in other_accounts:
            # Find transactions with opposite amount in this account
            matching_txs = BankTransaction.objects.filter(
                bank_account=other_account,
                date__gte=date_start,
                date__lte=date_end,
            ).exclude(
                status__in=['EXCLUDED', 'RECONCILED', 'MATCHED_SINGLE', 'MATCHED_MULTI']
            )
            
            for other_tx in matching_txs:
                other_amount = Decimal(str(other_tx.amount))
                
                # Check if amounts are opposite (with small tolerance for fees)
                if abs(other_amount - opposite_amount) < MatchingConfig.AMOUNT_TOLERANCE:
                    # This looks like a transfer! Create a special transfer suggestion
                    candidates.append({
                        "transfer_match": other_tx,
                        "transfer_from_account": tx.bank_account.name if tx_amount < 0 else other_account.name,
                        "transfer_to_account": other_account.name if tx_amount < 0 else tx.bank_account.name,
                        "confidence": Decimal("0.85"),  # High but not definitive
                        "match_type": "TRANSFER",
                        "reason": f"Likely transfer between {tx.bank_account.name} and {other_account.name} (matching opposite amounts within {date_tolerance.days} days)",
                    })
        
        return candidates
