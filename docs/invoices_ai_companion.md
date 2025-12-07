# Invoices AI Companion – Ops Notes

How the invoice companion works end-to-end, how the toggle changes behaviour, and where to debug.

## Flow

1. **Upload**: POST `/api/agentic/invoices/run` creates an `InvoiceRun` plus `InvoiceDocument` rows and stores uploaded files.
2. **Workflow**: `run_invoices_workflow` executes with business defaults and `ai_companion_enabled`.
3. **Processing**:
   - Extraction (vendor, invoice number, dates, totals, tax)
   - Normalization to internal invoice transaction shape
   - Journal proposal generation
   - Audit/anomaly checks
4. **Persistence per document**:
   - `extracted_payload`
   - `proposed_journal_payload`
   - `audit_flags` (`{code, severity, message}`)
   - `audit_score` (0–100) and `audit_explanations`
   - `status` (`PROCESSED`, `ERROR`, etc.)
5. **Run observability**:
   - `InvoiceRun.metrics` stores totals, warnings/errors, high-risk count, and `agent_retries`
   - `InvoiceRun.trace_id` ties the run to the agent console; trace events emitted during processing

## AI Companion toggle

- **OFF**: Conservative path; deterministic extraction/validation, basic audit rules, no reflection retries.
- **ON**: Richer agentic checks; extra heuristics (duplicate patterns, unusual amounts, date sanity), reflection pass on flagged docs, higher `agent_retries`.

## Risk/audit fields

- `audit_flags`: structured findings with severity.
- `audit_score`: numeric risk indicator; higher = riskier.
- `audit_explanations`: short natural-language context.
- `risk_level`: derived in UI from score/flags/status.

## Debugging

- **API**: `/api/agentic/invoices/run/<id>` returns documents with audit/risk and the run `trace_id`.
- **Console**: Open `/agentic/console?trace=<trace_id>` to follow the agent trace, retries, and failures.

Canonical path: files → `InvoiceRun`/`InvoiceDocument` → `run_invoices_workflow` (extract/normalize/propose/audit) → persist → metrics + trace. Use the companion toggle to choose between lightweight ingestion (OFF) and fuller agentic scrutiny (ON).
