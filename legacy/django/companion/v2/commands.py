from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


HumanStatus = Literal["auto_applied", "proposed", "accepted", "rejected"]


class HumanInTheLoop(BaseModel):
    tier: int = Field(ge=0, le=3)
    status: HumanStatus
    circuit_breaker_check: Optional[str] = None


class ExplainabilityMetadata(BaseModel):
    actor: str = "system_companion_v2"
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    logic_trace_id: Optional[str] = None
    rationale: Optional[str] = None
    business_profile_constraint: Optional[str] = None
    human_in_the_loop: HumanInTheLoop

    # Allow future extension without breaking.
    model_config = {"extra": "allow"}


class CommandBase(BaseModel):
    command_id: UUID = Field(default_factory=uuid4)
    workspace_id: int
    metadata: ExplainabilityMetadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}


class ProposeCategorizationCommand(CommandBase):
    """
    Propose categorizing a bank transaction by creating a split/categorized journal entry.
    """

    type: Literal["ProposeCategorizationCommand"] = "ProposeCategorizationCommand"
    bank_transaction_id: int
    proposed_splits: list[dict[str, Any]]
    # Each split: {account_id: int, amount: Decimal|str|number, description?: str}


class ApplyCategorizationCommand(CommandBase):
    type: Literal["ApplyCategorizationCommand"] = "ApplyCategorizationCommand"
    shadow_event_id: UUID
    # Optional override (e.g., user changed split amounts/accounts in UI before apply)
    override_splits: Optional[list[dict[str, Any]]] = None


class ProposeBankMatchCommand(CommandBase):
    type: Literal["ProposeBankMatchCommand"] = "ProposeBankMatchCommand"
    bank_transaction_id: int
    journal_entry_id: int
    match_confidence: Decimal = Decimal("1.00")


class ApplyBankMatchCommand(CommandBase):
    type: Literal["ApplyBankMatchCommand"] = "ApplyBankMatchCommand"
    shadow_event_id: UUID


class ProposeJournalAdjustmentCommand(CommandBase):
    type: Literal["ProposeJournalAdjustmentCommand"] = "ProposeJournalAdjustmentCommand"
    # Placeholder for v2 expansion.
    journal_entry_payload: dict[str, Any]


class ApplyJournalAdjustmentCommand(CommandBase):
    type: Literal["ApplyJournalAdjustmentCommand"] = "ApplyJournalAdjustmentCommand"
    shadow_event_id: UUID


CompanionCommand = (
    ProposeCategorizationCommand
    | ApplyCategorizationCommand
    | ProposeBankMatchCommand
    | ApplyBankMatchCommand
    | ProposeJournalAdjustmentCommand
    | ApplyJournalAdjustmentCommand
)

