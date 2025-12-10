# Central Books

**AI-powered accounting OS with an intelligent Companion Control Tower.**

---

## Overview

Central Books (CERN Books) is a modern accounting platform built for small businesses, freelancers, and agencies. Unlike traditional bookkeeping software that simply records transactions, Central Books features an **AI Companion** that proactively monitors your financial health, surfaces issues, and guides you through month-end close.

The system combines **deterministic accounting rules** with **AI-powered insights** from DeepSeek and OpenAI. The AI never auto-posts transactions or moves money—it analyzes, suggests, and explains, while you remain in control. This "human-in-the-loop" design ensures accuracy and compliance while dramatically reducing the cognitive load of managing business finances.

Central Books is designed to be the **"control tower"** for your books: one dashboard that shows you what needs attention, what's working, and what to do next.

---

## Demo

📹 **Demo Video**: [Watch on Loom](https://www.loom.com/share/924456e287574d8bbae68cd16ddaab2a)

### Screenshots

Key screens (see demo video for full walkthrough):

| Feature | Description |
|---------|-------------|
| **Dashboard** | Main dashboard with Companion banner showing today's focus |
| **AI Companion** | Control Tower with Radar, Coverage, Playbook, and Story |
| **Receipts AI** | Upload and OCR extraction with suggested classification |
| **Books Review** | Ledger audit with Deterministic Findings + Neural Analysis |
| **Banking** | Bank transaction feed with reconciliation |

---

## Feature Highlights

### 📄 Receipts AI
- Upload receipts (photos, PDFs, scans)
- GPT-4o-mini extracts vendor, amount, date, and line items
- DeepSeek suggests journal entry classification
- One-click approval to post to ledger

### 📋 Invoices AI
- Create and track invoices with status management
- AI risk scoring for overdue/at-risk invoices
- Companion strip shows contextual insights

### 🏦 Banking Workspace
- Connect bank accounts manually or via import
- Transaction feed with categorization
- Reconciliation engine matches bank lines to ledger entries

### 📊 Books Review
- Ledger-wide audit across all journal entries
- Deterministic checks (duplicates, outliers, large entries)
- Neural Analysis insights from DeepSeek
- Risk scoring and actionable recommendations

### 🔍 Bank Review
- Per-account reconciliation analysis
- Unmatched transaction detection
- AI-powered insights for discrepancies

### 🎛️ AI Companion Control Tower
- **Radar**: 4-axis stability scores (cash, revenue, expenses, tax)
- **Coverage**: Percentage of transactions reviewed by AI
- **Close-Readiness**: Month-end checklist status
- **Playbook**: Prioritized action items
- **Story**: Weekly narrative summary of business health
- **Issues**: Aggregated findings from all surfaces

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                 │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    REACT FRONTEND                            │
│         (Vite + TypeScript + Tailwind CSS)                  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    DJANGO API                                │
│              (REST endpoints + views)                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Models    │  │   Agentic   │  │   Companion/LLM     │  │
│  │  (Django)   │  │  Workflows  │  │    Integration      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              DATABASE + LLM PROVIDERS                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  PostgreSQL │  │  DeepSeek   │  │  OpenAI GPT-4o-mini │  │
│  │  (SQLite    │  │  (Reasoner  │  │  (Vision/OCR)       │  │
│  │   locally)  │  │   + Chat)   │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Technology |
|-------|------------|
| **Backend** | Django 5.x, Django REST Framework, PostgreSQL |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **LLM (Text)** | DeepSeek Chat (deepseek-chat) for structured JSON output |
| **LLM (Vision)** | OpenAI GPT-4o-mini for receipt OCR/extraction |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/MikeNzmbh/Central-Books.git
cd Central-Books

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Or build for production
npm run build
```

### Access the Application

- **Django Admin**: http://localhost:8000/admin/
- **Main App**: http://localhost:8000/
- **AI Companion**: http://localhost:8000/ai-companion/

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

### Key Variables

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key (change in production) |
| `DATABASE_URL` | PostgreSQL connection string (prod) |
| `COMPANION_LLM_ENABLED` | Enable AI Companion (`true`/`false`) |
| `COMPANION_LLM_API_BASE` | DeepSeek API base URL (`https://api.deepseek.com/v1`) |
| `COMPANION_LLM_API_KEY` | Your DeepSeek API key |
| `COMPANION_LLM_MODEL` | Model name (`deepseek-chat`) |
| `COMPANION_LLM_TIMEOUT_SECONDS` | Request timeout (default: 60) |
| `COMPANION_LLM_MAX_TOKENS` | Max tokens per response (default: 2048) |
| `OPENAI_API_KEY` | OpenAI API key for vision/OCR tasks |

> ⚠️ **Security**: Never commit secrets to the repository. All sensitive values are set via environment variables.

See [`.env.example`](.env.example) for the complete list.

---

## AI / Safety Design

Central Books follows a **"deterministic-first, LLM-optional"** architecture:

1. **Deterministic engine always runs first** – Rule-based checks (duplicates, outliers, balance validation) execute before any LLM call.

2. **LLM is best-effort, suggest-only** – If the LLM times out or fails, the system gracefully falls back to deterministic results.

3. **No auto-posting of transactions** – AI can suggest journal entries, but humans must approve before posting to the ledger.

4. **Structured JSON validation** – All LLM outputs go through Pydantic validation to prevent malformed or hallucinated data.

5. **Human-in-the-loop** – Critical actions (posting, deletion, status changes) require explicit user action.

6. **Separate providers for separate tasks**:
   - DeepSeek Chat: Text reasoning, insights, narratives
   - OpenAI GPT-4o-mini: Vision/OCR for receipt extraction

7. **Timeout and fallback handling** – Every LLM call has a timeout; failures never crash the application.

8. **Audit trail** – All runs, findings, and AI suggestions are logged with timestamps and trace IDs.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [System Architecture](docs/CentralBooks_Residency_System_Architecture.md) | Detailed technical architecture |
| [Product Brief](docs/PRODUCT_BRIEF.md) | Non-technical product overview |
| [AI Companion Brief](docs/AI_COMPANION_BRIEF.md) | AI stack and safety design |
| [Demo Script](docs/RESIDENCY_DEMO_SCRIPT.md) | Step-by-step demo walkthrough |
| [Demo Data Notes](docs/DEMO_DATA_NOTES.md) | How demo data is set up |
| [Runbook](docs/RESIDENCY_RUNBOOK.md) | Testing and deployment notes |

---

## Residency Snapshot

This repository snapshot corresponds to the **AI Residency application** (December 2024).

- **Suggested tag**: `v0.1-residency`
- **Core features**: Receipts AI, Invoices, Banking, Books Review, Bank Review, AI Companion
- **AI stack**: DeepSeek Chat + OpenAI GPT-4o-mini
- **Safety architecture**: Deterministic-first, human-in-the-loop

To create the snapshot tag:
```bash
git tag -a v0.1-residency -m "AI Residency submission snapshot"
git push origin v0.1-residency
```

---

## License

Proprietary – All rights reserved.

---

*Built with ❤️ for small businesses everywhere.*
