# Legacy Database Import Mapping

This document maps legacy Django SQLite tables to the new FastAPI SQLAlchemy models.

## MVP Migration Scope

| Status | Legacy Table | Legacy Model | New Table | New Model | Migration Notes |
|--------|--------------|-------------|-----------|-----------|-----------------|
| MIGRATE | `auth_user` | Django User | `users` | User | Force password reset |
| MIGRATE | `core_business` | Business | `businesses` | Business | Primary tenant entity |
| MIGRATE | `core_customer` | Customer | `customers` | Customer | FK to business |
| MIGRATE | `core_supplier` | Supplier | `suppliers` | Supplier | FK to business |
| MIGRATE | `core_account` | Account | `accounts` | Account | FK to business, Chart of Accounts |
| MIGRATE | `core_category` | Category | `categories` | Category | FK to business, account |
| MIGRATE | `core_invoice` | Invoice | `invoices` | Invoice | FK to business, customer |
| DEFER | `core_invoiceline` | InvoiceLine | — | — | Complex, phase 2 |
| DEFER | `core_expense` | Expense | — | — | Phase 2 |
| DEFER | `core_bankaccount` | BankAccount | — | — | Phase 2 |
| DEFER | `core_banktransaction` | BankTransaction | — | — | Phase 2 |
| SKIP | `companion_*` | Companion | — | — | AI-generated, not migrated |
| SKIP | `core_*_audit` | Audit logs | — | — | Can be regenerated |

## Key Field Mappings

### auth_user → users

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK generated |
| email | email | Direct copy |
| first_name + last_name | name | Concatenate |
| password | password_hash | Store original, set needs_reset=true |
| is_superuser | is_admin | Direct copy |
| is_active | is_active | Direct copy |

### core_business → businesses

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK, tracked in import_map |
| name | name | Direct copy |
| currency | currency | Direct copy |
| owner_user_id | owner_user_id | Lookup new user ID |
| plan | plan | Direct copy |
| status | status | Direct copy |
| ai_companion_enabled | ai_enabled | Direct copy |

### core_customer → customers

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK |
| business_id | business_id | Lookup new business ID |
| name | name | Direct copy |
| email | email | Direct copy |
| phone | phone | Direct copy |

### core_supplier → suppliers

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK |
| business_id | business_id | Lookup new business ID |
| name | name | Direct copy |
| email | email | Direct copy |
| phone | phone | Direct copy |

### core_account → accounts

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK |
| business_id | business_id | Lookup new business ID |
| code | code | Direct copy |
| name | name | Direct copy |
| type | type | Direct copy (ASSET/LIABILITY/EQUITY/INCOME/EXPENSE) |
| parent_id | parent_id | Lookup new parent account ID |
| is_active | is_active | Direct copy |

### core_invoice → invoices

| Legacy Field | New Field | Transform |
|-------------|-----------|-----------|
| id | — | New PK |
| business_id | business_id | Lookup new business ID |
| customer_id | customer_id | Lookup new customer ID |
| invoice_number | invoice_number | Direct copy |
| issue_date | issue_date | Direct copy |
| due_date | due_date | Direct copy |
| status | status | Direct copy |
| total_amount | total_amount | Direct copy |
| net_total | net_total | Direct copy |
| tax_total | tax_total | Direct copy |

## Import Order

1. Users (Django auth_user)
2. Businesses (core_business)
3. Customers (core_customer)
4. Suppliers (core_supplier)
5. Accounts (core_account) — parents first
6. Categories (core_category)
7. Invoices (core_invoice)

## Idempotency Strategy

Use `import_map` table to track:
```
import_map:
  - legacy_table: VARCHAR(100)
  - legacy_pk: INTEGER
  - new_table: VARCHAR(100)
  - new_pk: INTEGER
  - imported_at: TIMESTAMP
  - PRIMARY KEY (legacy_table, legacy_pk)
```

Before inserting any record, check if it exists in import_map. If found, skip or update.

## Password Handling

Legacy Django passwords use PBKDF2 or bcrypt hashing with a specific format.
We will NOT verify these at runtime. Instead:
1. Store original hash in `password_hash` field
2. Add `needs_password_reset: bool = True` to User model
3. Force all migrated users to reset password on first login
