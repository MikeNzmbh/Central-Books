# Architectural Blueprint – Central Books Tax Engine v1 (Canada + US)

## Executive Summary

The Central Books Tax Engine v1 implements a **split-brain design** for tax calculation and compliance:

| Layer | Role | Technology |
|-------|------|------------|
| **Deterministic Core** | All tax math, reporting, and filing-grade outputs | PostgreSQL, Django models, pure `Decimal` arithmetic |
| **Probabilistic Observer** | Anomaly detection explanations, period summaries, nudges | DeepSeek LLM (strictly advisory, never authoritative for amounts) |

### Key Design Principles

1. **LLM is an Observer, Not a Calculator** – The LLM layer ("Tax Guardian") may explain, summarize, and nudge, but **never** computes payable amounts without deterministic validation.
2. **Option B Infrastructure** – Heavy operations (snapshots, anomaly passes, narratives) run via Django management commands + cron, not Celery.
3. **Extensible Schema** – v1 supports Canada (all provinces/territories) and US (state + local) structurally. Implementation is phased, but the schema handles full complexity from day one.
4. **Country Lock** – Once a business selects its tax country, it **cannot be changed**. This is a hard constraint.

---

## Scope & Non-Scope

### In Scope v1

#### Canada
- GST/HST/PST/QST support for all provinces/territories
- Place-of-supply logic (TPP vs IPP/services) at design level
- Quebec as a distinct regime (QST + GST, historically compounded)
- Line mapping to official returns:
  - CRA GST34 (federal GST/HST)
  - Revenu Québec VDZ-471.1 (QST)

#### US
- State-level sales tax + structural support for local jurisdictions (county, city, district)
- Origin vs destination sourcing rules
- California hybrid model (state-level origin, district-level destination)
- SER-style line mapping (simplified seller's return)

#### Infrastructure
- Deterministic tax period snapshot + anomaly records
- Option B async pattern: management commands + cron
- Integration with Companion / Tax Guardian for surfacing issues
- Pixel-perfect line mapping architecture for filing

### Not in Scope v1 (Supported by Design)

| Item | Note |
|------|------|
| Full jurisdiction catalog pre-loaded | Seed subset in code; rest via manual entry / import |
| SSUTA implementation | Schema supports mapping; not implemented yet |
| Full LLM classification engine | Design stub provided; implementation deferred |
| E-file integrations | Data structures ready; external API calls deferred |
| Payroll taxes | Separate domain; not covered here |

---

## Deterministic Core – Data Model

### Existing Models (in `taxes/` app)

The following models **already exist** in `taxes/models.py` and will be **extended** as needed:

| Model | Purpose | Migration Notes |
|-------|---------|-----------------|
| `TaxComponent` | Atomic tax rate (e.g., GST 5%, QST 9.975%) | Add optional `jurisdiction` FK |
| `TaxRate` | Time-versioned rates with product category support | Already SCD2-like via `effective_from/to` |
| `TaxGroup` | User-facing bundles (e.g., "HST 13%") | Add `is_compound` calculation method |
| `TaxGroupComponent` | Through model preserving calculation order | No changes needed |
| `TransactionLineTaxDetail` | Component-level tax per invoice/expense line | Add `jurisdiction_code` field |

### New Models to Add

The following models are **new** and will be added to `taxes/models.py`:

#### `TaxJurisdiction`

Hierarchy-aware jurisdiction model supporting Canada, US, and nested local jurisdictions.

```python
class TaxJurisdiction(models.Model):
    """
    Canonical jurisdiction for tax purposes.
    Supports federal, provincial/state, and nested local (county, city, district).
    """
    class JurisdictionType(models.TextChoices):
        FEDERAL = "FEDERAL", "Federal"
        PROVINCIAL = "PROVINCIAL", "Provincial/Territory"
        STATE = "STATE", "State"
        COUNTY = "COUNTY", "County"
        CITY = "CITY", "City"
        DISTRICT = "DISTRICT", "District (e.g., CA special tax districts)"

    class SourcingRule(models.TextChoices):
        ORIGIN = "ORIGIN", "Origin-based"
        DESTINATION = "DESTINATION", "Destination-based"
        HYBRID = "HYBRID", "Hybrid (e.g., California)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)  # e.g., "CA", "CA-ON", "US-CA", "US-CA-LA"
    name = models.CharField(max_length=128)
    jurisdiction_type = models.CharField(max_length=20, choices=JurisdictionType.choices)
    country_code = models.CharField(max_length=2)  # ISO 3166-1 alpha-2
    region_code = models.CharField(max_length=10, blank=True)  # Province/State code
    sourcing_rule = models.CharField(
        max_length=20,
        choices=SourcingRule.choices,
        default=SourcingRule.DESTINATION,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)  # SSUTA alignment, special notes
```

**Jurisdiction Examples:**

| code | name | type | country | region | sourcing | parent |
|------|------|------|---------|--------|----------|--------|
| `CA` | Canada | FEDERAL | CA | | DESTINATION | NULL |
| `CA-ON` | Ontario | PROVINCIAL | CA | ON | DESTINATION | CA |
| `CA-QC` | Quebec | PROVINCIAL | CA | QC | DESTINATION | CA |
| `US` | United States | FEDERAL | US | | DESTINATION | NULL |
| `US-CA` | California | STATE | US | CA | HYBRID | US |
| `US-CA-LA` | Los Angeles County | COUNTY | US | CA | DESTINATION | US-CA |
| `US-TX` | Texas | STATE | US | TX | ORIGIN | US |

**California Hybrid Handling:**
- `sourcing_rule="HYBRID"` on `US-CA` signals special logic
- State-level component uses origin sourcing
- District-level components (children with `DISTRICT` type) use destination sourcing

#### `TaxProductRule`

Connects product/service categories with taxability rules per jurisdiction.

```python
class TaxProductRule(models.Model):
    """
    Taxability rule for a product category within a jurisdiction.
    """
    class RuleType(models.TextChoices):
        TAXABLE = "TAXABLE", "Taxable at standard rate"
        EXEMPT = "EXEMPT", "Exempt (no tax)"
        ZERO_RATED = "ZERO_RATED", "Zero-rated (0% but recoverable ITCs)"
        REDUCED = "REDUCED", "Reduced rate applies"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jurisdiction = models.ForeignKey(TaxJurisdiction, on_delete=models.CASCADE)
    product_code = models.CharField(max_length=32)  # e.g., "FOOD", "CLOTHING", "MEDICINE"
    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    special_rate = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Override rate for REDUCED type",
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
```

**Alignment:**
- Canadian categories: based on CRA/RQ guidance (basic groceries, medical devices, etc.)
- US categories: designed for future SSUTA alignment (food, clothing, medical, SaaS, digital goods)

#### `BusinessTaxProfile`

Per-business tax configuration (may be merged into `Business` model or separate).

> **Note:** The existing `Business` model already has `tax_country` (immutable after selection) and `tax_region` fields. We will extend rather than duplicate.

**Additions to `Business` model (or new `BusinessTaxProfile`):**

```python
# Fields to add to Business or create as a one-to-one profile:
gst_hst_number = models.CharField(max_length=15, blank=True)  # BN/RT e.g., 123456789RT0001
qst_number = models.CharField(max_length=16, blank=True)  # e.g., 1234567890TQ0001
us_sales_tax_id = models.CharField(max_length=32, blank=True)  # State-specific permit
default_nexus_jurisdictions = models.JSONField(default=list)  # ["US-CA", "US-NY"]
```

> **Constraint:** `tax_country` is immutable after first set. Changing it requires support intervention.

#### `TaxPeriodSnapshot`

Computed tax data for a specific business + period.

```python
class TaxPeriodSnapshot(models.Model):
    """
    Canonical snapshot of computed tax data for a filing period.
    Deterministic source of truth for Tax Reports and Companion surfaces.
    """
    class SnapshotStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft (pending changes)"
        COMPUTED = "COMPUTED", "Computed (ready for review)"
        REVIEWED = "REVIEWED", "Reviewed by user"
        FILED = "FILED", "Filed with authority"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE)
    period_key = models.CharField(max_length=16)  # e.g., "2025Q2", "2025-04"
    country = models.CharField(max_length=2)  # CA or US
    status = models.CharField(max_length=16, choices=SnapshotStatus.choices, default=SnapshotStatus.DRAFT)
    computed_at = models.DateTimeField(auto_now=True)

    # Aggregated data
    summary_by_jurisdiction = models.JSONField(default=dict)
    # Example:
    # {
    #   "CA-ON": {"taxable_sales": 10000, "tax_collected": 1300, "itcs": 200, "net": 1100},
    #   "CA-QC": {"taxable_sales": 5000, "qst_collected": 497.50, "gst_collected": 250, ...}
    # }

    line_mappings = models.JSONField(default=dict)
    # Example for GST34:
    # {
    #   "line_101": 10000.00,
    #   "line_105": 1300.00,
    #   "line_108": 200.00,
    #   "line_109": 1100.00
    # }

    # Optional LLM enrichment (nullable; populated by tax_llm_enrich_period command)
    llm_summary = models.TextField(blank=True)
    llm_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("business", "period_key")
        indexes = [models.Index(fields=["business", "period_key", "status"])]
```

#### `TaxAnomaly`

Tax-specific anomaly model aligned with the Companion anomaly pattern.

```python
class TaxAnomaly(models.Model):
    """
    Canonical tax anomaly record, surfaced through Tax Guardian.
    """
    class AnomalySeverity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class AnomalyStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        RESOLVED = "RESOLVED", "Resolved"
        IGNORED = "IGNORED", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey("core.Business", on_delete=models.CASCADE)
    period_key = models.CharField(max_length=16)  # e.g., "2025Q2"
    code = models.CharField(max_length=64)  # e.g., "T1_RATE_MISMATCH", "T2_OVERCHARGE"
    severity = models.CharField(max_length=10, choices=AnomalySeverity.choices)
    status = models.CharField(max_length=16, choices=AnomalyStatus.choices, default=AnomalyStatus.OPEN)
    description = models.TextField()
    
    # Links to source
    linked_transaction_ct = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    linked_transaction_id = models.PositiveIntegerField(null=True, blank=True)
    linked_transaction = GenericForeignKey("linked_transaction_ct", "linked_transaction_id")
    
    task_code = models.CharField(max_length=8, blank=True)  # e.g., "T2" from companion_tasks_catalog
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
```

**Anomaly Code Examples:**

| Code | Description |
|------|-------------|
| `T1_RATE_MISMATCH` | Applied rate differs from TaxRate for that date/jurisdiction |
| `T2_POSSIBLE_OVERCHARGE` | Tax collected exceeds expected by > threshold |
| `T3_MISSING_COMPONENT` | Invoice line missing expected tax component |
| `T4_ROUNDING_ANOMALY` | Sum of line taxes differs from computed subtotal × rate by > 2¢ |
| `T5_EXEMPT_TAXED` | Exempt product category was taxed |
| `T6_NEGATIVE_BALANCE` | Negative tax payable/receivable (from anomaly_detection.py) |

---

## Calculation Semantics (Inclusive/Exclusive + Rounding)

### Tax Calculation Modes

| Mode | Formula (Exclusive) | Formula (Inclusive) |
|------|---------------------|---------------------|
| Exclusive | `tax = base × rate` | N/A |
| Inclusive | `base = total / (1 + rate)` | `tax = total - base` |

**Example (13% HST):**
- Exclusive: $100.00 base → $13.00 tax → $113.00 total
- Inclusive: $113.00 total → $100.00 base → $13.00 tax

### Precision & Rounding

| Rule | Implementation |
|------|----------------|
| Internal precision | All calculations use Python `Decimal`, **never floats** |
| Rounding method | **Banker's rounding** (round half to even) |
| Rounding point | **Line-item level**, with document-level reconciliation |
| Tolerance | 1¢ discrepancy allowed between sum-of-lines and subtotal × rate |

### Dust Sweeper Pattern

When the sum of rounded line taxes differs from the expected total (subtotal × rate):

1. Calculate expected total tax at document level: `expected = subtotal × rate`
2. Calculate sum of line taxes: `actual = Σ(line_tax_i)`
3. If `abs(expected - actual) <= $0.01`, adjust final line to reconcile
4. If `> $0.01`, flag as `T4_ROUNDING_ANOMALY` for review

This ensures CRA/State acceptability while maintaining line-item auditability.

---

## Place-of-Supply and Sourcing Logic (Canada + US)

**v1 implementation status (implemented at province/state level, with sample US local stacks):**
- Inputs: `Invoice.ship_from_jurisdiction_code`, `Invoice.ship_to_jurisdiction_code`, `Invoice.customer_location_jurisdiction_code`, `Invoice.place_of_supply_hint` (AUTO/TPP/SERVICE/IPP).
- Canada: TPP vs services/IPP place-of-supply resolution to a province/territory code (e.g., `CA-NS`, `CA-QC`).
- US: origin vs destination sourcing by state using `TaxJurisdiction.sourcing_rule`, plus optional county/city/district stacks when invoices carry local jurisdiction codes (e.g., `US-CA-SF`) and tax groups include stacked components.
- Current limitations (still deterministic, deferred by design):
  - No explicit “FOB shipping point / buyer-arranged carrier” flag yet; v1 defaults to delivery/`ship_to` when present.
  - Local jurisdiction catalogs are **sample + extensible** (seeded examples, not a full nationwide catalog).
  - California HYBRID is implemented as: state-level jurisdiction at `US-CA`, with local/district components sourced from destination (ship-to/customer location); deeper county-origin nuances are deferred.

### Canada

#### Tangible Personal Property (TPP)

```
IF goods are delivered THEN
    tax_jurisdiction = delivery_location_province
ELSE IF FOB shipping point THEN
    tax_jurisdiction = ship_from_province
ELSE
    tax_jurisdiction = ship_to_province
```

#### Services & Intangible Personal Property (IPP)

```
tax_jurisdiction = customer_business_location_province
FALLBACK → customer_billing_address_province
```

#### Quebec Special Rules

- **Two components:** GST (federal, 5%) + QST (Quebec, 9.975%)
- **Historical compounding removed** (as of 2013), but schema supports `is_compound` for legacy data
- **Separate filing:** QST filed with Revenu Québec, GST filed with CRA

### US

#### Origin vs Destination States

| Sourcing Type | Rule | States |
|---------------|------|--------|
| Origin | Tax based on seller's location | TX, AZ, MO, IL, OH, PA, UT, VA |
| Destination | Tax based on buyer's location | Most states (CA*, NY, WA, FL, etc.) |

*California is hybrid – see below.

#### California Hybrid Model

```python
def california_tax(invoice, tax_group):
    """
    v1 deterministic pattern:
    - State-level jurisdiction is US-CA.
    - Local/district jurisdictions are destination-based (ship_to/customer location).
    - Each TaxGroupComponent maps deterministically to a jurisdiction code in order.
    """
    jurisdictions = resolve_us_jurisdictions_for_invoice(invoice)  # ["US-CA", "US-CA-SF", "US-CA-DIST-1", ...]
    # Component 1 -> jurisdictions[0] (state)
    # Component 2..n -> jurisdictions[1..] (locals), clamped to last local
    return jurisdictions
```

The `TaxJurisdiction.sourcing_rule = "HYBRID"` on `US-CA` signals this special handling.

#### Inter-State Sales

For sellers with nexus in the buyer's state:
1. Look up buyer's destination jurisdiction
2. Apply that state's rate stack (state + local)

For sellers without nexus: no tax collection obligation (buyer owes use tax).

---

## Option B Infra – Async Pattern via Management Commands

### Design Philosophy

- **No Celery/Redis** for v1
- Heavy operations run via Django management commands + cron or manual triggers
- Can upgrade to Celery later without schema changes

### Management Commands

#### `tax_refresh_period`

Computes and stores deterministic tax snapshot for a period.

```bash
python manage.py tax_refresh_period --business-id=UUID --period=2025Q2
```

**Behavior:**
1. Scan ledger for invoices, credit notes, expenses with tax for the business/period
2. Compute deterministic aggregates by jurisdiction/rate/product
3. Build line mappings (GST34 lines, US SER lines)
4. Create/update `TaxPeriodSnapshot`

**Inputs:**
- `business_id` (required)
- `period_key` (required, e.g., "2025Q2", "2025-04")

#### `tax_watchdog_period`

Runs deterministic anomaly checks and creates `TaxAnomaly` records.

```bash
python manage.py tax_watchdog_period --business-id=UUID --period=2025Q2
```

**Deterministic Checks:**
- Rate mismatch vs `TaxRate` for transaction date
- Inclusive/exclusive mismatch
- Misconfigured taxable/exempt products
- Rounding anomalies beyond tolerance
- Negative tax balances

**Outputs:**
- Creates/updates `TaxAnomaly` records
- No LLM involvement

#### `tax_nudge_notifications` (Design Stub)

Scans snapshots + anomalies to generate user notifications.

```bash
python manage.py tax_nudge_notifications
```

**Nudge Scenarios:**
- "Period ending soon, unresolved anomalies remain"
- "Filing deadline approaching (GST/HST due by month-end +1)"
- "Return may be overdue for Q1"

**Implementation:** Deferred; document the notification pipeline design for later.

#### `tax_llm_enrich_period` (Design Stub)

Optional LLM enrichment for period summaries.

```bash
python manage.py tax_llm_enrich_period --business-id=UUID --period=2025Q2
```

**Behavior:**
1. Fetch `TaxPeriodSnapshot` + top `TaxAnomaly` records
2. Call DeepSeek (HEAVY_REASONING or LIGHT_CHAT) for narrative
3. Write to `TaxPeriodSnapshot.llm_summary` and `llm_notes`

**Constraints:**
- **Opt-in only** – never called on normal page load
- Behind feature flag or separate CLI invocation
- Token-limited (max 3 anomalies, compact transaction representation)

---

## Integration with Tax Reports & Companion / Tax Guardian

### Tax Report Screens

Tax reports (existing `taxes/views.py` or new React pages) should:

1. **Read from `TaxPeriodSnapshot`** instead of recomputing on every request
2. Fall back to live computation if snapshot doesn't exist (with warning)
3. Display line mappings (GST34, VDZ-471, US SER) from snapshot

### AI Companion / Control Tower Integration

| Component | Tax Data Source | Notes |
|-----------|----------------|-------|
| Radar | `TaxAnomaly` count by severity | Tax axis in radar chart |
| Tax Guardian | `TaxAnomaly` list | Surfaces issues with task codes |
| Playbook | Tasks T1, T2, T3 from `companion_tasks_catalog.md` | Based on open anomalies |
| Close Readiness | Check for open `TaxAnomaly` with status=OPEN | Blocks close if critical |

**All amounts come from deterministic core.** LLM may explain/summarize but never override.

### User Story Example

> **Canadian SMB in Ontario, Q2 GST/HST Filing**
>
> 1. `tax_refresh_period --period=2025Q2` runs nightly via cron
> 2. `tax_watchdog_period --period=2025Q2` runs afterward
> 3. Companion Overview shows:
>    - **Tax Guardian:** 2 issues detected
>    - **Snapshot:** Net tax payable $1,234.56, mapped to line 109
> 4. User clicks Tax Guardian → sees:
>    - `T1_RATE_MISMATCH`: Invoice #1042 used 13% but NS rate is 15%
>    - `T6_NEGATIVE_BALANCE`: HST Payable is -$50 (overpayment?)
> 5. Playbook shows: "T2: Resolve tax anomalies before filing"
> 6. Close Readiness shows: "Tax issues unresolved" (blocks close)
> 7. User fixes issues, re-runs refresh, anomalies cleared
> 8. Close Readiness: ✅ "Tax: All clear"

---

## Token & Safety Strategy for LLM Use (Tax)

### LLM Role Definition

| ✅ LLM MAY | ❌ LLM MAY NOT |
|-----------|---------------|
| Explain anomalies in plain language | Compute payable amounts |
| Summarize a period's tax position | Override deterministic results |
| Suggest next actions | Create or modify tax records |
| Generate filing reminders | Make taxability decisions |

### Token Efficiency Strategy

| Strategy | Implementation |
|----------|----------------|
| Compact representation | Use TOON-like JSON: `{"id":"INV-1042","amt":500,"tax":65,"rate":0.13}` |
| Limit scope | Max 3 anomalies per LLM call |
| Pre-aggregate | Send jurisdiction totals, not line-by-line |
| Cache summaries | Store `llm_summary` in snapshot; don't regenerate unless data changes |

### Safety Guardrails

1. **Deterministic validation** – Any LLM-suggested amount is cross-checked against `TaxPeriodSnapshot`
2. **No auto-posting** – LLM cannot modify ledger or tax records
3. **Audit trail** – `explanation_source="ai"` flag distinguishes AI-generated content
4. **Graceful degradation** – If LLM unavailable, fall back to deterministic explanations

---

## Appendix: Line Mapping Reference

### CRA GST34 (Federal GST/HST)

| Line | Description | Source |
|------|-------------|--------|
| 101 | Sales and other revenue | Sum of invoice taxable amounts |
| 103 | Eligible ITCs | Sum of recoverable expense tax |
| 104 | Net tax (before adjustments) | Line 105 - Line 108 |
| 105 | GST/HST collected | Sum of invoice tax collected |
| 108 | ITCs claimed | Sum of expense ITCs |
| 109 | Net tax payable/refund | Line 105 - Line 108 ± adjustments |

### Revenu Québec VDZ-471.1 (QST)

| Line | Description | Source |
|------|-------------|--------|
| 205 | QST collected | Sum of QST from invoices |
| 206 | ITRs (Input Tax Refunds) | Sum of recoverable QST from expenses |
| 209 | Net QST payable/refund | Line 205 - Line 206 ± adjustments |

### US SER (Simplified Electronic Return)

| Field | Description |
|-------|-------------|
| Gross Sales | Total sales in jurisdiction |
| Exempt Sales | Sales of exempt products |
| Taxable Sales | Gross - Exempt |
| Tax Collected | Taxable × rate (by jurisdiction) |
| Discounts/Adjustments | Any vendor discounts |
| Net Tax Due | Tax Collected - Adjustments |

---

## References

- [Tax Guardian](./tax_guardian.md) – Lightweight deterministic tax checks
- [Anomaly Detection](./anomaly_detection.md) – Companion v3 anomaly pattern
- [Finance Companion](./finance_companion.md) – Finance snapshot design
- [Companion Tasks Catalog](./companion_tasks_catalog.md) – Canonical task codes
- [LLM Safety and Tokens](./llm_safety_and_tokens.md) – Token strategy

---

*Document version: v1.0 | Created: 2024-12-11 | Author: Central Books Tax Engine Team*
