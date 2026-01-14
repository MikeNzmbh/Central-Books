# Tax Engine v1 – Blueprint Status

Source of truth: `docs/tax_engine_v1_blueprint.md`.

## Implemented (Deterministic Core + Option B)

- Deterministic data model in `taxes/`:
  - `TaxJurisdiction` (hierarchy + sourcing_rule)
  - `TaxProductRule` (taxability rules per jurisdiction + date)
  - `TaxPeriodSnapshot` (period snapshots + line mappings + workflow status + `filed_at`)
  - `TaxAnomaly` (severity/status workflow + linked source objects)
  - `TaxComponent` linked to `TaxJurisdiction`
  - `TransactionLineTaxDetail` includes `jurisdiction_code` + `transaction_date`
- Calculation semantics:
  - Banker's rounding (`ROUND_HALF_EVEN`) and 1¢ dust-sweeper reconciliation
  - Tax-inclusive (`TaxGroup.tax_treatment = INCLUDED`) and exclusive (`ON_TOP`) modes
  - Simple vs compound (`TaxGroup.calculation_method`)
- Period pipeline (Option B infra):
  - `tax_refresh_period`, `tax_watchdog_period` (deterministic)
  - `tax_nudge_notifications` (deterministic nudges → `CompanionInsight` in `tax_fx`)
  - `tax_llm_enrich_period` (LLM observer; advisory only)
- Filing-grade line mappings:
  - Canada GST/HST (GST34-style) in `line_mappings["CA"]` (federal + HST provinces; excludes PST/QST)
  - Quebec QST (VDZ-471-style) in `line_mappings["CA_QC"]`
  - US SER-style summary in `line_mappings["US"]` (taxable sales avoids double counting stacked locals)
- Anomaly catalog (deterministic):
  - `T1_RATE_MISMATCH`, `T2_POSSIBLE_OVERCHARGE`, `T3_MISSING_TAX`, `T3_MISSING_COMPONENT`
  - `T4_ROUNDING_ANOMALY`, `T5_EXEMPT_TAXED`, `T6_NEGATIVE_BALANCE`, `T7_LATE_FILING`
- Place-of-supply & sourcing (province/state level):
  - Invoice-level inputs: ship-from/ship-to/customer-location jurisdiction codes + `place_of_supply_hint`
  - Canada: TPP vs services/IPP → province/territory jurisdiction (e.g., `CA-NS`, `CA-QC`)
  - US: origin/destination sourcing by `TaxJurisdiction.sourcing_rule`; California `HYBRID` at state level
  - US local stacks (sample pattern):
    - Seeded example county/city/district jurisdictions under states
    - Deterministic mapping of stacked TaxGroup components to state + local jurisdiction codes
    - California HYBRID: state at `US-CA`, locals sourced from destination (ship-to/customer location)
- Companion + Tax Guardian integration:
  - Tax axis in radar, close-readiness blockers, playbook mapping
  - Tax Guardian console (periods, snapshot detail, anomalies, exports, workflow controls, drilldown links)
  - Filing calendar risk flags (`due_date`, `is_due_soon`, `is_overdue`)
  - Tax Settings v1 + Product Rules console (deterministic CRUD)
  - Optional AI observer summary:
    - CLI: `tax_llm_enrich_period`
    - API: `POST /api/tax/periods/<period_key>/llm-enrich/` (throttled)

## Deferred by Design (Blueprint Explicitly Defers)

- Full jurisdiction/rate catalog seeding (beyond the canonical seed subset)
- SSUTA alignment (US product category mapping)
- Full nationwide county/city/district catalogs (we seed only a small deterministic subset in v1)
- Explicit FOB shipping-point nuance (v1 defaults to delivery/ship-to when present)
- E-file integrations
- Full LLM observer layer (expanded narratives + advanced nudges) — remains advisory and opt-in
