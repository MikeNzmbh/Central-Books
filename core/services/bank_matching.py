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
    - DATE_TOLERANCE_DAYS: How many days before/after to search for matching journal entries
    - CONFIDENCE_TIER1: Confidence for deterministic ID matches (should be 1.00)
    - CONFIDENCE_TIER2: Confidence for invoice/expense reference parsing
    - CONFIDENCE_TIER3_SINGLE: Confidence for single amount+date match
    - CONFIDENCE_TIER3_AMBIGUOUS: Confidence when multiple candidates found (requires manual selection)
    - DEFAULT_MAX_CANDIDATES: Maximum number of match candidates to return
    - AMOUNT_TOLERANCE: Tolerance for amount matching (in currency units, e.g., 0.01 = 1 cent)
    """
    
    # Date matching window
    DATE_TOLERANCE_DAYS: int = 3
    
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
    def find_matches(
        bank_transaction: BankTransaction,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find potential journal entry matches for a bank transaction.

        Returns list of candidate matches ordered by confidence (highest first).
        
        Args:
            bank_transaction: The bank transaction to match
            limit: Maximum number of candidates to return (defaults to MatchingConfig.DEFAULT_MAX_CANDIDATES)

        Returns:
            List of dicts with keys:
                - journal_entry: JournalEntry instance
                - confidence: Decimal (0.00 to 1.00)
                - match_type: str ("ONE_TO_ONE", etc.)
                - reason: str (human-readable explanation)
                
        Example:
            >>> tx = BankTransaction.objects.get(id=123)
            >>> matches = BankMatchingEngine.find_matches(tx, limit=3)
            >>> if matches:
            ...     best_match = matches[0]
            ...     print(f"Best match: {best_match['journal_entry']} ({best_match['confidence']*100}%)")
        """
        if limit is None:
            limit = MatchingConfig.DEFAULT_MAX_CANDIDATES
            
        business = bank_transaction.bank_account.business
        candidates: List[Dict[str, Any]] = []

        # Tier 1: Deterministic ID match
        tier1 = BankMatchingEngine._tier1_id_match(bank_transaction, business)
        if tier1:
            candidates.extend(tier1)
            # If we found a deterministic match, return immediately
            return candidates[:limit]

        # Tier 2: Invoice/expense reference in description
        tier2 = BankMatchingEngine._tier2_reference_match(bank_transaction, business)
        candidates.extend(tier2)

        # Tier 3: Amount + date heuristic
        tier3 = BankMatchingEngine._tier3_amount_date_match(bank_transaction, business)
        candidates.extend(tier3)

        # Deduplicate by journal_entry.id and sort by confidence
        seen = set()
        unique_candidates = []
        for candidate in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
            je_id = candidate["journal_entry"].id
            if je_id not in seen:
                seen.add(je_id)
                unique_candidates.append(candidate)

        return unique_candidates[:limit]

    @staticmethod
    def _tier1_id_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 1: Match by external_id or check number.
        
        Looks for exact match between bank_transaction.external_id and:
        - Invoice.invoice_number
        - Expense.expense_number
        
        Args:
            tx: Bank transaction to match
            business: Business to search within
            
        Returns:
            List with single candidate if found, empty list otherwise
            Confidence: MatchingConfig.CONFIDENCE_TIER1 (1.00)
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

        # Try matching to expenses by expense_number or reference
        expense = (
            Expense.objects.filter(
                business=business,
                expense_number=tx.external_id,
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
                        "reason": f"Matched expense #{expense.expense_number} by external_id",
                    }
                )

        return candidates

    @staticmethod
    def _tier2_reference_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 2: Parse description for invoice/expense references.
        
        Uses regex patterns to find invoice/expense numbers in the transaction description:
        - INV-1234, #INV1234, Invoice 1234
        - EXP-1234, #EXP1234, Expense 1234
        
        Args:
            tx: Bank transaction to match
            business: Business to search within
            
        Returns:
            List of candidates (may be multiple if multiple references found)
            Confidence: MatchingConfig.CONFIDENCE_TIER2 (0.95)
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
                expense_num = match.group(1)

                expenses = Expense.objects.filter(
                    business=business, expense_number__icontains=expense_num
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
                                "reason": f"Expense {expense.expense_number} referenced in description",
                            }
                        )

        return candidates

    @staticmethod
    def _tier3_amount_date_match(tx: BankTransaction, business) -> List[Dict[str, Any]]:
        """
        Tier 3: Match by amount + date proximity.
        
        Finds journal entries with:
        - Matching amount (within MatchingConfig.AMOUNT_TOLERANCE)
        - Date within ±MatchingConfig.DATE_TOLERANCE_DAYS
        
        Args:
            tx: Bank transaction to match
            business: Business to search within
            
        Returns:
            List of candidates
            Confidence:
                - Single match: MatchingConfig.CONFIDENCE_TIER3_SINGLE (0.80)
                - Multiple matches: MatchingConfig.CONFIDENCE_TIER3_AMBIGUOUS (0.50)
        """
        amount_abs = abs(tx.amount)

        # Find journal entries with matching amount within date window
        date_start = tx.date - timedelta(days=MatchingConfig.DATE_TOLERANCE_DAYS)
        date_end = tx.date + timedelta(days=MatchingConfig.DATE_TOLERANCE_DAYS)

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
                    "reason": f"Amount {amount_abs} matches within {MatchingConfig.DATE_TOLERANCE_DAYS} days",
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
