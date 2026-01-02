# Safety & Governance

*Security, safety policies, and guardrails for the Agentic Accounting OS*

---

## Overview

The Agentic Accounting OS is designed with safety-first principles. LLMs assist with financial workflows but **never directly control money or approve transactions**.

---

## Core Safety Policies

### SAFETY-001: LLM Cannot Move Money
- **Category**: Financial
- **Severity**: Critical
- **Description**: The LLM cannot directly execute financial transactions, transfers, or payments.
- **Enforcement**: All transaction endpoints require human-approved session tokens. LLM can only propose transactions.

### SAFETY-002: LLM Cannot Approve Journal Entries
- **Category**: Approval
- **Severity**: Critical
- **Description**: The LLM cannot approve or post journal entries to the ledger.
- **Enforcement**: Entry posting requires human approval flag. LLM generates proposals only.

### SAFETY-003: LLM Cannot Fabricate Financial Data
- **Category**: Data
- **Severity**: Critical
- **Description**: The LLM cannot create fake transactions, invoices, or financial records.
- **Enforcement**: All financial data must trace to source documents. Audit trails required.

### SAFETY-004: Human Approval Required for Posting
- **Category**: Approval
- **Severity**: High
- **Description**: All journal entries must be approved by a human before posting to the ledger.
- **Enforcement**: Posting API requires approval token from authenticated user session.

### SAFETY-005: Tenant Isolation for Vector Memory
- **Category**: Isolation
- **Severity**: High
- **Description**: Vector memory and embeddings are isolated per tenant/business.
- **Enforcement**: All memory queries include tenant_id filter. Cross-tenant queries blocked.

### SAFETY-006: No PII Leakage
- **Category**: Privacy
- **Severity**: High
- **Description**: Personally identifiable information must not be exposed in logs, prompts, or outputs.
- **Enforcement**: PII detection in outputs. Masking in logs. Secure prompt handling.

### SAFETY-007: High-Value Transaction Review
- **Category**: Financial
- **Severity**: Medium
- **Description**: Transactions exceeding $10,000 require additional human review.
- **Enforcement**: Automatic flagging in compliance step. Supervisor escalation.

### SAFETY-008: Complete Audit Trail
- **Category**: Data
- **Severity**: Medium
- **Description**: All agent actions, decisions, and communications must be logged.
- **Enforcement**: Message bus logging. Workflow step recording. Supervisor daily logs.

---

## Guardrails

### Journal Entry Validation
```python
validate_journal_entry(entry)
# Checks: balanced, required fields, valid accounts
```

### LLM Output Validation
```python
validate_llm_output(output)
# Checks: no code injection, no PII, no unauthorized actions
```

### Cross-Tenant Validation
```python
validate_cross_tenant(source_tenant, target_tenant)
# Blocks: any cross-tenant data access
```

### Transaction Amount Validation
```python
validate_transaction_amount(amount)
# Flags: transactions > $10,000 for review
```

### Prompt Injection Detection
```python
validate_prompt_injection(prompt)
# Detects: injection attempts, jailbreak patterns
```

---

## Governance Model

### Human-in-the-Loop

```
Document Upload → LLM Extraction → Human Review → LLM Journal Entry → Human Approval → Post to Ledger
```

At two critical points, humans must approve:
1. **Review**: After extraction, before journal entry generation
2. **Approval**: Before posting entries to the ledger

### Supervisor Oversight

The Supervisor Agent monitors all workflows:
- Detects failures and anomalies
- Escalates high-risk decisions
- Produces daily logs for audit
- Enforces safety rules

### Audit Trail

Every action is logged:
- Workflow step results
- Agent messages
- Supervisor decisions
- Human approvals

---

## Implementation Files

| File | Purpose |
|------|---------|
| `agentic/safety/policies.py` | Policy definitions |
| `agentic/safety/guards.py` | Runtime guardrails |
| `agentic/agents/supervisor/` | Supervisor enforcement |
| `agentic/agents/messaging/` | Message logging |

---

## Compliance

This safety framework supports:
- SOX compliance (audit trails, separation of duties)
- GDPR (PII protection, data isolation)
- GAAP (accurate financial records)

---

*December 2024*
