"""
Companion v2: Shadow Ledger + command-sourced, safety-governed accountant mode.

This package contains:
- Command schemas (pydantic)
- Guardrails (kill switch + circuit breakers)
- Deterministic command handlers that append to the Shadow Ledger and, when approved,
  apply changes to the canonical ledger with provenance links.
"""

