# Demo Instructions

*Quick setup guide for busy reviewers*

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

---

## 1. Clone & Setup

```bash
# Clone repository
git clone <REPO_URL>
cd <project>

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

---

## 2. Run Backend

```bash
# Apply database migrations
python manage.py migrate

# Start Django server
python manage.py runserver
```

Server runs at: `http://localhost:8000`

---

## 3. Run Frontend (Optional for Web Demo)

Open a **new terminal** window:

```bash
cd frontend
npm run dev
```

Vite server runs at: `http://localhost:5173`

---

## 4. Quick Test: CLI Demo

Without starting any servers:

```bash
python -m agentic.workflows.cli_receipts_demo
```

You should see:

```
============================================================
Agentic Accounting OS - Receipts Workflow Demo
============================================================

Status: SUCCESS
Steps: ✓ ingest ✓ extract ✓ normalize ✓ generate_entries ✓ compliance ✓ audit

Journal Entries:
  Office Depot: 6100 DR $89.99 / 1000 CR $89.99 ✓

Compliance Check: YES ✓
Audit Report: LOW risk
```

---

## 5. Web Demo

With both servers running, open:

```
http://localhost:8000/agentic/demo/receipts/
```

### What to Try

1. **Use sample data**: The page may have pre-populated receipts

2. **Add custom documents**:
   - Filename: `office_supplies.pdf`
   - Content: `Office Depot - $89.99 - office supplies`

3. **Click "Run Workflow"**

4. **Observe results**:
   - **Steps tab**: Timeline with status badges
   - **Journal Entries tab**: Balanced double-entry lines
   - **Compliance & Audit tab**: Issue/finding cards
   - **Raw JSON tab**: Full API response

---

## 6. API Test (cURL)

```bash
curl -X POST http://localhost:8000/agentic/demo/receipts-run/ \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"filename": "coffee.pdf", "content": "Starbucks $15.50"},
      {"filename": "software.pdf", "content": "GitHub $49"}
    ]
  }'
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Activate virtualenv: `source .venv/bin/activate` |
| Port 8000 in use | Kill process: `lsof -i :8000` → `kill <PID>` |
| Frontend not loading | Ensure Vite is running: `cd frontend && npm run dev` |
| CORS errors | Add `localhost:5173` to Django CORS settings |

---

## Without Running Anything

To understand the system without setup:

1. Read [proposal_draft.md](./proposal_draft.md) for the narrative
2. Read [technical_overview.md](./technical_overview.md) for architecture
3. Inspect [sample_output.json](./sample_output.json) for API response format

---

*5-minute setup • 2-minute demo*
