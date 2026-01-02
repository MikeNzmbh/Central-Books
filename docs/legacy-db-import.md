# Legacy Database Import Guide

This guide explains how to migrate data from the legacy Django SQLite database to the new FastAPI/SQLAlchemy database.

## Prerequisites

- Python 3.11+ with FastAPI dependencies installed
- Legacy `db.sqlite3` file from Django installation
- New FastAPI database initialized (`alembic upgrade head`)

## Legacy Database Location

The legacy database is not committed to git. Place your backup at:

```
legacy/db/db.sqlite3
```

## Quick Start

```bash
cd backend

# 1. Dry run - see what will be imported (safe, read-only)
PYTHONPATH=. python tools/import_legacy_sqlite.py \
  --legacy-db ../legacy/db/db.sqlite3 \
  --mode dry-run

# 2. Import data
PYTHONPATH=. python tools/import_legacy_sqlite.py \
  --legacy-db ../legacy/db/db.sqlite3 \
  --mode import

# 3. Verify import
PYTHONPATH=. python tools/import_legacy_sqlite.py \
  --legacy-db ../legacy/db/db.sqlite3 \
  --mode verify
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--legacy-db` | Path to legacy db.sqlite3 (required) |
| `--target-db` | Target DATABASE_URL (default: from env or SQLite) |
| `--mode` | `dry-run`, `import`, or `verify` |
| `--report-dir` | Directory for JSON reports (default: `reports/`) |

## What Gets Migrated

| Legacy Table | New Table | Notes |
|--------------|-----------|-------|
| auth_user | users | Password reset required |
| core_business | businesses | Primary tenant |
| core_customer | customers | — |
| core_supplier | suppliers | — |
| core_account | accounts | Chart of Accounts |
| core_category | categories | — |
| core_invoice | invoices | — |

See [legacy-db-import-map.md](legacy-db-import-map.md) for field mappings.

## Safety Features

1. **Idempotent**: Uses `import_map` table to track what was imported. Re-running is safe.
2. **Dry-run first**: Always run `--mode dry-run` first to review.
3. **FK integrity**: Imports in dependency order (users → businesses → customers → invoices).
4. **Password reset**: All migrated users have `needs_password_reset=true`.

## Rollback Strategy

Import to a fresh database (recommended):

```bash
# Backup current DB
cp cloverbooks.db cloverbooks.db.backup

# Delete and recreate
rm cloverbooks.db
alembic upgrade head

# Run import
python tools/import_legacy_sqlite.py --legacy-db ../legacy/db/db.sqlite3 --mode import
```

To rollback: restore backup.

## Reports

Reports are saved to `backend/reports/` as JSON:
- `legacy_import_dry-run_YYYYMMDD_HHMMSS.json`
- `legacy_import_import_YYYYMMDD_HHMMSS.json`
- `legacy_import_verify_YYYYMMDD_HHMMSS.json`
