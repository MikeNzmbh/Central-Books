# Central Books — Demo Data Notes

*How demo data is set up for testing and demonstrations*

---

## Overview

Central Books uses SQLite locally (`db.sqlite3`) with sample data for development and demos.

---

## Current Demo Data

The local database includes:

| Entity | Count | Notes |
|--------|-------|-------|
| Business | 1 | "CERN Books" (user's active business) |
| Users | 1 | Mike Nzamurambaho (mbahomike123@gmail.com) |
| Accounts | ~20+ | Standard chart of accounts |
| Expense Categories | 5 | Rent, Software, Travel, Marketing, Utilities |
| Invoices | ~5-10 | Mix of PAID, SENT, OVERDUE |
| Expenses | ~10-15 | Sample expenses with receipts |
| Journal Entries | ~35+ | Generated from invoices/expenses |
| Bank Accounts | 1+ | For Banking Workspace demos |
| Bank Transactions | ~20+ | Imported transactions |

---

## Seeding Demo Data

### Option 1: Django Shell (Manual)

```bash
python manage.py shell
```

```python
from core.models import Business, ExpenseCategory

business = Business.objects.get(name="My Business")

# Add expense categories
categories = ["Rent/Office", "Software", "Travel", "Marketing", "Utilities"]
for name in categories:
    ExpenseCategory.objects.get_or_create(business=business, name=name)
```

### Option 2: Fixtures (Not Currently Implemented)

*TODO: Create `fixtures/demo_data.json` for automated seeding.*

```bash
# Future implementation
python manage.py loaddata demo_data
```

### Option 3: Admin Interface

1. Go to `http://localhost:8000/admin/`
2. Log in as superuser
3. Add entities manually

---

## Creating Fresh Demo Environment

1. **Reset database** (if needed):
   ```bash
   rm db.sqlite3
   python manage.py migrate
   python manage.py createsuperuser
   ```

2. **Create business**:
   - Log in to the app
   - Complete business setup flow

3. **Add sample data**:
   - Create 5+ invoices (mix of statuses)
   - Create 10+ expenses with categories
   - Import bank transactions (CSV upload or manual)

4. **Run Books Review**:
   - Navigate to Books Review
   - Scan a date range to generate findings

---

## Demo Data Gotchas

1. **Expense Categories**: Must be added per-business. New businesses start empty.
2. **Bank Accounts**: Required for Bank Review demos—create at least one.
3. **Invoice Numbers**: Auto-generated if left blank (e.g., INV-00001).
4. **AI Companion**: Requires `COMPANION_LLM_ENABLED=true` and valid API keys.

---

*December 2024*
