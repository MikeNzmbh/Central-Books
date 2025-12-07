# Receipts AI Companion – Ops Notes

This guide explains what happens when receipts are uploaded, how the AI Companion toggle changes behaviour, and where to look when debugging.

## End-to-end flow

1. **Upload**: Files hit `api/agentic/receipts/run`, which creates a `ReceiptRun` and `ReceiptDocument` rows and stores files.
2. **Workflow**: `run_receipts_workflow` is invoked with business defaults and the `ai_companion_enabled` flag.
3. **Processing steps**:
   - Extraction (deterministic stub today)
   - Normalization to internal transaction shape
   - Journal proposal generation
   - Audit/anomaly checks
4. **Persistence**: Each `ReceiptDocument` gets:
   - `extracted_payload`
   - `proposed_journal_payload`
   - `audit_flags` (list of `{code, severity, message}`)
   - `audit_score` (0–100)
   - `audit_explanations` (human-readable reasons)
   - `status` (ok/warning/error)
5. **Metrics & trace**:
   - `ReceiptRun.metrics` includes totals, warnings, errors, high-risk counts, and `agent_retries`.
   - `ReceiptRun.trace_id` ties the run to the agent console; trace events are emitted during processing.

## AI Companion toggle

- **OFF (`ai_companion_enabled=False`)**: Conservative, deterministic rules (basic extraction/validation, simple audit thresholds, no reflection retries).
- **ON (`ai_companion_enabled=True`)**: Richer agentic behaviour (extra audit heuristics, reflection pass when flags are present, higher `agent_retries` where applicable).

## Risk and audit representation

- `audit_flags`: structured findings (severity + message).
- `audit_score`: numeric risk indicator; higher means riskier.
- `audit_explanations`: short plain-language reasons.
- `risk_level` (derived in UI): low/medium/high based on score/flags/status.

## Where to debug

- **API responses**: `/api/agentic/receipts/run/<id>` returns documents with audit/risk data and the run `trace_id`.
- **Console trace**: Use the `trace_id` in the agent console (e.g., `/agentic/console?trace=<trace_id>`) to inspect workflow events, retries, and failures.

This is the canonical path: files → `ReceiptRun` + `ReceiptDocument` → `run_receipts_workflow` (extract/normalize/propose/audit) → persist → metrics + trace for observability. Enable the companion when you want deeper reasoning and audit coverage; leave it off for lighter-weight ingestion.
