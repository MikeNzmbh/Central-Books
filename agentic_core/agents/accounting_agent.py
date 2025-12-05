"""
Accounting Agent

A specialized agent for generating double-entry journal entries from
normalized transactions. Uses deterministic LLM prompting with strict
accounting rules to ensure balanced, correct journal entries.

The agent:
1. Receives normalized transactions
2. Applies chart of accounts mapping
3. Uses LLM for complex categorization decisions
4. Generates balanced journal entry proposals
5. Validates double-entry rules

Example usage:
    agent = AccountingAgent(llm_client=openai_client)
    result, trace = await agent.execute(
        transactions=normalized_transactions,
        chart_of_accounts=coa_data,
    )
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from agentic_core.agents.base_agent import BaseAgent
from agentic_core.models.ledger import (
    JournalEntryProposal,
    JournalEntryStatus,
    JournalLineProposal,
    NormalizedTransaction,
    TransactionType,
)


# Deterministic system prompt for accounting decisions
ACCOUNTING_SYSTEM_PROMPT = """You are an expert double-entry bookkeeper.

CORE RULES:
1. Every journal entry MUST balance: total debits = total credits
2. Follow GAAP/IFRS principles for account classification
3. Use the chart of accounts provided - do not invent account codes
4. Always separate tax amounts into appropriate tax liability/asset accounts
5. Be conservative - when uncertain, use suspense accounts for review

DEBIT/CREDIT RULES:
- Assets: Debit to increase, Credit to decrease
- Liabilities: Credit to increase, Debit to decrease  
- Equity: Credit to increase, Debit to decrease
- Revenue/Income: Credit to increase, Debit to decrease
- Expenses: Debit to increase, Credit to decrease

RESPONSE FORMAT:
Return ONLY valid JSON matching this schema:
{
  "entries": [
    {
      "description": "Journal entry description",
      "lines": [
        {
          "account_code": "1000",
          "account_name": "Cash",
          "debit": 100.00,
          "credit": 0.00,
          "reasoning": "Why this account was chosen"
        }
      ],
      "confidence": 0.95,
      "reasoning": "Overall reasoning for this entry"
    }
  ]
}

Do not include any text outside the JSON object.
"""


class AccountingAgent(BaseAgent):
    """
    Agent for generating journal entries from transactions.

    This agent uses LLM-powered reasoning to:
    - Map transactions to appropriate accounts
    - Handle complex categorization decisions
    - Generate balanced double-entry proposals
    - Provide reasoning for audit trails

    Attributes:
        agent_name: "accounting_agent"
        default_expense_account: Fallback expense account code.
        default_income_account: Fallback income account code.
        default_asset_account: Fallback asset (cash) account code.
        suspense_account: Account for uncertain transactions.
    """

    agent_name = "accounting_agent"
    agent_version = "0.1.0"

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        default_model: str = "gpt-4",
        default_expense_account: str = "6000",
        default_income_account: str = "4000",
        default_asset_account: str = "1000",
        suspense_account: str = "9999",
        **kwargs: Any,
    ):
        """
        Initialize the accounting agent.

        Args:
            llm_client: OpenAI-compatible LLM client.
            default_model: Model to use for LLM calls.
            default_expense_account: Default expense account code.
            default_income_account: Default income account code.
            default_asset_account: Default asset (cash) account code.
            suspense_account: Account for uncertain transactions.
        """
        super().__init__(llm_client=llm_client, default_model=default_model, **kwargs)
        self.default_expense_account = default_expense_account
        self.default_income_account = default_income_account
        self.default_asset_account = default_asset_account
        self.suspense_account = suspense_account

    async def run(
        self,
        transactions: list[NormalizedTransaction],
        chart_of_accounts: Optional[list[dict[str, Any]]] = None,
        business_context: Optional[str] = None,
    ) -> list[JournalEntryProposal]:
        """
        Generate journal entry proposals from normalized transactions.

        Args:
            transactions: List of normalized transactions to process.
            chart_of_accounts: Optional list of available accounts.
            business_context: Optional context about the business.

        Returns:
            List of journal entry proposals.
        """
        self.log_step(f"Processing {len(transactions)} transactions")

        proposals: list[JournalEntryProposal] = []

        for txn in transactions:
            self.log_step(f"Processing transaction: {txn.description}")

            try:
                # Try LLM-based entry generation
                entry = await self._generate_entry_with_llm(
                    txn, chart_of_accounts, business_context
                )
            except Exception as e:
                self.log_step(f"LLM generation failed: {e}, using fallback")
                # Fallback to deterministic rules
                entry = self._generate_entry_fallback(txn)

            # Validate the entry
            is_valid, error = entry.validate_balance()
            if not is_valid:
                self.log_step(f"Entry validation failed: {error}")
                entry.status = JournalEntryStatus.PENDING_REVIEW
                entry.review_notes = f"Auto-validation failed: {error}"

            proposals.append(entry)

        self.log_step(f"Generated {len(proposals)} journal entry proposals")
        return proposals

    async def _generate_entry_with_llm(
        self,
        transaction: NormalizedTransaction,
        chart_of_accounts: Optional[list[dict[str, Any]]],
        business_context: Optional[str],
    ) -> JournalEntryProposal:
        """Generate a journal entry using LLM reasoning."""
        # Build the prompt
        prompt = self._build_entry_prompt(
            transaction, chart_of_accounts, business_context
        )

        # Call LLM
        response = await self.call_llm(
            prompt=prompt,
            system_prompt=ACCOUNTING_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic
        )

        # Parse the response
        return self._parse_entry_response(response, transaction)

    def _build_entry_prompt(
        self,
        transaction: NormalizedTransaction,
        chart_of_accounts: Optional[list[dict[str, Any]]],
        business_context: Optional[str],
    ) -> str:
        """Build the prompt for LLM entry generation."""
        prompt_parts = [
            "Generate a journal entry for the following transaction:",
            "",
            f"Transaction ID: {transaction.transaction_id}",
            f"Date: {transaction.transaction_date}",
            f"Type: {transaction.transaction_type.value}",
            f"Amount: {transaction.amount} {transaction.currency}",
            f"Description: {transaction.description}",
        ]

        if transaction.payee_name:
            prompt_parts.append(f"Payee/Vendor: {transaction.payee_name}")
        if transaction.category_hint:
            prompt_parts.append(f"Category Hint: {transaction.category_hint}")
        if transaction.account_code_hint:
            prompt_parts.append(f"Account Hint: {transaction.account_code_hint}")
        if transaction.tax_amount:
            prompt_parts.append(f"Tax Amount: {transaction.tax_amount}")
        if transaction.tax_code:
            prompt_parts.append(f"Tax Code: {transaction.tax_code}")

        if chart_of_accounts:
            prompt_parts.extend([
                "",
                "Available Chart of Accounts:",
                json.dumps(chart_of_accounts[:50], indent=2),  # Limit for context
            ])

        if business_context:
            prompt_parts.extend([
                "",
                f"Business Context: {business_context}",
            ])

        prompt_parts.extend([
            "",
            "Generate a balanced journal entry following double-entry rules.",
        ])

        return "\n".join(prompt_parts)

    def _parse_entry_response(
        self,
        response: str,
        transaction: NormalizedTransaction,
    ) -> JournalEntryProposal:
        """Parse LLM response into a JournalEntryProposal."""
        try:
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```"):
                # Remove markdown code blocks
                lines = response.split("\n")
                response = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                )

            data = json.loads(response)
            entries = data.get("entries", [])

            if not entries:
                raise ValueError("No entries in response")

            entry_data = entries[0]  # Take first entry

            # Build the proposal
            proposal = JournalEntryProposal(
                source_transaction_id=transaction.transaction_id,
                entry_date=transaction.transaction_date,
                description=entry_data.get("description", transaction.description),
                currency=transaction.currency,
                agent_name=self.agent_name,
                agent_confidence=entry_data.get("confidence", 0.8),
                reasoning=entry_data.get("reasoning"),
                status=JournalEntryStatus.PENDING_REVIEW,
            )

            # Add lines
            for line_data in entry_data.get("lines", []):
                debit = Decimal(str(line_data.get("debit", 0)))
                credit = Decimal(str(line_data.get("credit", 0)))

                # Skip zero lines
                if debit == 0 and credit == 0:
                    continue

                line = JournalLineProposal(
                    account_code=line_data.get("account_code", self.suspense_account),
                    account_name=line_data.get("account_name"),
                    debit=debit,
                    credit=credit,
                    reasoning=line_data.get("reasoning"),
                )
                proposal.lines.append(line)

            return proposal

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.log_step(f"Failed to parse LLM response: {e}")
            # Return fallback entry
            return self._generate_entry_fallback(transaction)

    def _generate_entry_fallback(
        self,
        transaction: NormalizedTransaction,
    ) -> JournalEntryProposal:
        """Generate a simple fallback entry using deterministic rules."""
        proposal = JournalEntryProposal(
            source_transaction_id=transaction.transaction_id,
            entry_date=transaction.transaction_date,
            description=transaction.description,
            currency=transaction.currency,
            agent_name=self.agent_name,
            agent_confidence=0.5,  # Lower confidence for fallback
            reasoning="Generated using fallback rules (LLM unavailable or failed)",
            status=JournalEntryStatus.PENDING_REVIEW,
        )

        amount = transaction.amount

        if transaction.transaction_type == TransactionType.EXPENSE:
            # Expense: Debit expense account, Credit cash/bank
            expense_account = (
                transaction.account_code_hint or self.default_expense_account
            )
            proposal.add_debit(
                account_code=expense_account,
                amount=amount,
                description=transaction.description,
                reasoning="Expense transaction - debit expense account",
            )
            proposal.add_credit(
                account_code=self.default_asset_account,
                amount=amount,
                account_name="Cash/Bank",
                description=transaction.description,
                reasoning="Expense paid from cash/bank",
            )

        elif transaction.transaction_type == TransactionType.INCOME:
            # Income: Debit cash/bank, Credit income account
            income_account = (
                transaction.account_code_hint or self.default_income_account
            )
            proposal.add_debit(
                account_code=self.default_asset_account,
                amount=amount,
                account_name="Cash/Bank",
                description=transaction.description,
                reasoning="Income received to cash/bank",
            )
            proposal.add_credit(
                account_code=income_account,
                amount=amount,
                description=transaction.description,
                reasoning="Income transaction - credit income account",
            )

        elif transaction.transaction_type == TransactionType.TRANSFER:
            # Transfer: Debit one bank, Credit another bank
            proposal.add_debit(
                account_code=transaction.account_code_hint or "1010",
                amount=amount,
                account_name="Bank Account (To)",
                description=transaction.description,
                reasoning="Transfer destination account",
            )
            proposal.add_credit(
                account_code=self.default_asset_account,
                amount=amount,
                account_name="Bank Account (From)",
                description=transaction.description,
                reasoning="Transfer source account",
            )

        else:
            # Unknown - use suspense account
            proposal.add_debit(
                account_code=self.suspense_account,
                amount=amount,
                account_name="Suspense",
                description=transaction.description,
                reasoning="Unknown transaction type - requires manual review",
            )
            proposal.add_credit(
                account_code=self.default_asset_account,
                amount=amount,
                account_name="Cash/Bank",
                description=transaction.description,
                reasoning="Offset for suspense entry",
            )

        return proposal

    def validate_proposals(
        self,
        proposals: list[JournalEntryProposal],
    ) -> tuple[list[JournalEntryProposal], list[str]]:
        """
        Validate a list of proposals and return valid ones with errors.

        Args:
            proposals: List of proposals to validate.

        Returns:
            Tuple of (valid_proposals, error_messages).
        """
        valid = []
        errors = []

        for proposal in proposals:
            is_valid, error = proposal.validate_balance()
            if is_valid:
                valid.append(proposal)
            else:
                errors.append(f"Entry {proposal.entry_id}: {error}")

        return valid, errors
