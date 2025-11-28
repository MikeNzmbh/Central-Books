# 🚀 Quick Reference: Central-Books Monitoring & CI/CD

## What's Installed

✅ Monitoring Agent (`core/metrics.py` + `run_monitoring_agent` command)
✅ CI Pipeline (`.github/workflows/ci.yml`)
✅ CD Pipeline (`.github/workflows/cd.yml`)
✅ Comprehensive documentation (`MONITORING_SETUP.md`)

---

## Quick Commands

```bash
# Test monitoring agent locally (no API calls)
python manage.py run_monitoring_agent --dry-run

# Run monitoring agent (requires OPENAI_API_KEY)
python manage.py run_monitoring_agent

# Django health check
python manage.py check

# Run tests
python manage.py test
```

---

## Required Setup (⚠️ STOP - Manual Steps Required)

### 1. Get OpenAI API Key
- Visit: https://platform.openai.com/api-keys
- Copy API key (starts with `sk-proj-...`)

### 2. Add to GitHub Secrets
- Repo → Settings → Secrets and variables → Actions
- Add:
  - `OPENAI_API_KEY` = Your OpenAI key
  - `RENDER_API_KEY` = From dashboard.render.com/account/settings
  - `RENDER_SERVICE_ID` = From your service URL (`srv-xxxxx`)

### 3. Add to Render Environment Variables
- Service → Environment → Add variables:
  - `OPENAI_API_KEY` = Your OpenAI key
  - `MONITORING_MODEL` = `gpt-5.1-mini`
  - `MONITORING_ENV` = `production`

### 4. Set Up Render Cron Jobs
- New + → Cron Job
- Create 3 jobs:
  - Schedule: `0 9 * * *` (09:00 UTC)
  - Schedule: `0 15 * * *` (15:00 UTC)
  - Schedule: `0 21 * * *` (21:00 UTC)
- Command (all 3): `python manage.py run_monitoring_agent`
- Add same environment variables as web service

---

## Optional: Slack/Discord Webhooks

### Slack
1. https://api.slack.com/apps → Create app → Incoming Webhooks
2. Copy webhook URL
3. Add to GitHub Secrets as `SLACK_WEBHOOK_URL`
4. Add to Render env vars as `SLACK_WEBHOOK_URL`

### Discord
1. Server Settings → Integrations → Webhooks → New
2. Copy webhook URL
3. Add to GitHub Secrets as `DISCORD_WEBHOOK_URL`
4. Add to Render env vars as `DISCORD_WEBHOOK_URL`

---

## CI/CD Workflow

```
Developer pushes code → GitHub
                       ↓
               CI Tests Run (auto)
                       ↓
              ✅ Tests Pass?
                       ↓
           Merge PR to main
                       ↓
           CD Pipeline Triggered
                       ↓
         Deploy to Render (auto)
                       ↓
       Migrations Run (auto)
                       ↓
         Health Check ✅
```

---

## Metrics Collected

1. **Meta** - Environment, timestamp, business info
2. **Product & Engineering** - Features, bugs, uptime
3. **Ledger & Accounting** - Journal entries, accounts
4. **Banking** - Transactions, reconciliation status
5. **Tax & FX** - Tax rates, currency
6. **Revenue** - Income, expenses, profit
7. **Marketing** - Signups, traffic (placeholder)
8. **Support** - Tickets, satisfaction (placeholder)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "OPENAI_API_KEY is required" | Add to `.env` or Render env vars |
| Webhook 404 | Regenerate webhook in Slack/Discord |
| CI tests fail | Run `python manage.py test` locally |
| Deploy hangs | Check Render dashboard for errors |

---

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ⚠️ Configure GitHub Secrets (see Required Setup)
3. ⚠️ Configure Render Environment Variables
4. ⚠️ Set up Render Cron Jobs
5. ✅ Test locally: `python manage.py run_monitoring_agent --dry-run`
6. 🚀 Push to GitHub and watch CI/CD magic happen!

---

## Full Documentation

📖 **Complete Setup Guide:** `MONITORING_SETUP.md`
📊 **Implementation Details:** `walkthrough.md` artifact

---

## Cost Estimate

- **OpenAI API:** ~$0.09-0.90/month (3 reports/day with gpt-5.1-mini)
- **Render:** Free tier or existing plan
- **Total:** ~$1-2/month additional cost

---

## Support

Questions? Check `MONITORING_SETUP.md` for detailed instructions and troubleshooting.

Happy monitoring! 🎉
