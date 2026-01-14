# Companion Tasks Catalog

Canonical Companion tasks (single source of truth for playbook + close-readiness).

| Code | Surface  | Label                                  | Description                                                        | Tier     |
|------|----------|----------------------------------------|--------------------------------------------------------------------|----------|
| R1   | receipts | Review unprocessed receipts            | Manually review receipts that are unprocessed or flagged.          | basic    |
| R2   | receipts | Post approved receipts to ledger       | Post cleared receipts so expenses stay current.                    | basic    |
| I1   | invoices | Match payments to invoices             | Apply customer payments to open invoices and clear AR.             | basic    |
| I1B  | invoices | Chase overdue invoices                 | Follow up on overdue invoices across 30/60/90+ day buckets.       | basic    |
| I2   | invoices | Review revenue recognition anomalies   | Flag unusual timing/allocation for revenue recognition.           | premium  |
| B1   | bank     | Review unreconciled transactions       | Clear unreconciled bank lines and confirm matches.                | basic    |
| B2   | bank     | Confirm ending cash balance            | Confirm ending cash aligns to statements and ledger.              | basic    |
| G1   | books    | Resolve suspense account balance       | Investigate and clear suspense/clearing account balances.         | basic    |
| G2   | books    | Fix unbalanced entries                 | Identify and correct unbalanced journal entries.                  | basic    |
| G2B  | books    | Validate retained earnings rollforward | Confirm retained earnings movement matches prior NI + balance.    | basic    |
| G3   | books    | Review negative tax payable/receivable | Confirm negative tax balances are intentional.                    | basic    |
| G4   | books    | Run Books Review and confirm status    | Complete Books Review and resolve findings for the period.        | basic    |
| T1   | tax      | Review GST/HST / sales tax summary     | Validate sales tax balances and filings (CA/US focus).            | basic    |
| T2   | tax      | Confirm tax accrual for the period     | Ensure tax accruals are posted and reconciled before close.       | basic    |
| T3   | tax      | Tie tax reports to GL                  | Reconcile tax collected vs liability movement and report tie-out. | basic    |
| C1   | close    | Run final sanity checks                | Confirm critical issues and anomalies are cleared pre-close.      | basic    |
| C2   | close    | Lock this period                       | Lock the period once reconciliation and reviews are complete.     | basic    |

## Tax Guardian anomaly → task mapping (deterministic)

| Anomaly code        | Default task |
|---------------------|--------------|
| T1_RATE_MISMATCH    | T1 – Review GST/HST / sales tax summary |
| T3_MISSING_TAX      | T2 – Confirm tax accrual for the period |
| T4_ROUNDING_ANOMALY | T3 – Tie tax reports to GL |
| T5_EXEMPT_TAXED     | T1 – Review GST/HST / sales tax summary |
| T6_NEGATIVE_BALANCE | T2 – Confirm tax accrual for the period |
