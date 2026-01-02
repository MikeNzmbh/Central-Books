# Clover Books — Residency Runbook

*Developer guide for testing, deployment, and common tasks*

---

## Running Tests

### Full Test Suite

```bash
python manage.py test
```

### Specific App Tests

```bash
# Core app tests
python manage.py test core.tests

# Companion tests
python manage.py test companion.tests

# Agentic tests
python manage.py test agentic.tests
```

### Verbose Output

```bash
python manage.py test --verbosity=2
```

### Test Notes

- Some tests mock external LLM calls
- Set `COMPANION_LLM_ENABLED=false` for deterministic-only testing
- Tests use SQLite in-memory database by default

---

## Running Locally

### Backend

```bash
# Activate virtual environment
source .venv/bin/activate

# Run migrations (if needed)
python manage.py migrate

# Start server
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Access Points

| URL | Description |
|-----|-------------|
| `http://localhost:8000/` | Main application |
| `http://localhost:8000/admin/` | Django admin |
| `http://localhost:8000/ai-companion/` | AI Companion |
| `http://localhost:8000/books-review/` | Books Review |

---

## Git Tag for Residency

### Suggested Tag

```bash
git tag -a v0.1-residency -m "AI Residency submission snapshot - December 2024"
```

### Pushing Tag

```bash
git push origin v0.1-residency
```

### Checking Out Tag

```bash
git checkout v0.1-residency
```

---

## Troubleshooting

### LLM Not Working

1. **Check env vars**:
   ```bash
   grep COMPANION_LLM .env
   ```

2. **Verify API base**:
   - Must be `https://api.deepseek.com/v1` (not `/chat/completions`)

3. **Check logs** for timeout/error messages

### Neural Analysis Shows "Could Not Generate"

- Usually a timeout or JSON parsing issue
- Check Django console for detailed error
- Ensure `deepseek-chat` model is being used (not `deepseek-reasoner`)

### PDF Download Fails

- WeasyPrint requires system libraries (libgobject, etc.)
- Current implementation uses `reportlab` (pure Python) as fallback

### Database Reset

```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

---

## Deployment (Render.com)

### Configuration

See `render.yaml` for service configuration.

### Environment Variables

Set in Render dashboard:
- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (auto-set by Render)
- `COMPANION_LLM_*` variables
- `OPENAI_API_KEY`

### Deployment Trigger

Push to `main` branch triggers automatic deployment via GitHub Actions.

---

*December 2024*
