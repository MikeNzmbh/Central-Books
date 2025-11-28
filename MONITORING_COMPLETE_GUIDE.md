# 🎯 Central-Books Monitoring System - Complete Setup Checklist

## ✅ What Has Been Installed

The **7-Domain AI Monitoring System** is now fully operational. Here's what you have:

### Core Components
- ✅ **`core/metrics.py`** - Comprehensive metrics collection across 7 domains
- ✅ **`core/management/commands/run_monitoring_agent.py`** - CLI command for monitoring reports
- ✅ **`core/views_monitoring.py`** - Slack slash command endpoint (`/cb-report`)
- ✅ **Updated `core/urls.py`** - Added `/slack/monitoring/report/` route
- ✅ **Updated `requirements.txt`** - Added OpenAI SDK (>= 1.46.0)
- ✅ **`.env.example`** - Template for all required environment variables

---

## 📊 7 Monitoring Domains Implemented

### 1. **Meta Data**
- Timestamp, environment, window tracking
- Business list and primary business info

### 2. **Product & Engineering**
- Feature usage tracking (invoices, expenses, reconciliations)
- On Boarding completion metrics
- Deployment tracking (placeholder for future)

### 3. **Ledger & Accounting**  
- Journal entries (total, unbalanced, future-dated)
- Account types breakdown (ASSET, LIABILITY, EQUITY, INCOME, EXPENSE)
- Key account balances (Cash, AR, AP)
- Unlinked bank transactions

### 4. **Banking & Reconciliation**
- Per-bank-account reconciliation status
- Bank feed vs ledger balance differences
- Unmatched and unreconciled transaction counts
- Age analysis (30/60/90 days)
- Last reconciliation timestamps

### 5. **Tax & FX**
- Active tax rates by code
- Invoice line validation (net + tax = total checks)
- Tax rate set but zero amount detection
- Multi-currency status

### 6. **Business & Revenue**
- MRR approximation (based on invoice data)
- Customer metrics (total, new, active)
- Payment success tracking

### 7. **Marketing & Traffic** (Placeholder)
- Website visits, conversions (ready for Google Analytics / Plausible integration)

### 8. **Support & Feedback** (Placeholder)  
- Tickets, NPS (ready for Zendesk / Intercom integration)

---

## 🔐 PART 1: Required Environment Variables

### Local Development (`.env` file)

Create or update your `.env` file:

```bash
# === MONITORING AGENT ===
OPENAI_API_KEY=sk-proj-xxxxx  # GET THIS from https://platform.openai.com/api-keys
MONITORING_MODEL=gpt-5.1-mini
MONITORING_ENV=local

# === SLACK/DISCORD (Optional) ===
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # See Part 2
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...  # See Part 2

# === SLACK SLASH COMMAND (Optional) ===
SLACK_VERIFICATION_TOKEN=your-slack-verification-token  # See Part 3
```

### Production (Render Environment Variables)

Go to your Render service → Environment tab and add:

| Variable | Value | Notes |
|----------|-------|-------|
| `OPENAI_API_KEY` | `sk-proj-xxxxx` | **REQUIRED** - From OpenAI |
| `MONITORING_MODEL` | `gpt-5.1-mini` | Recommended for cost |
| `MONITORING_ENV` | `production` | Environment identifier |
| `SLACK_WEBHOOK_URL` | Your webhook URL | Optional - for reports |
| `DISCORD_WEBHOOK_URL` | Your webhook URL | Optional - for reports |
| `SLACK_VERIFICATION_TOKEN` | Your Slack token | Optional - for slash command |

---

## 🎫 PART 2: Get OpenAI APindex Key

**Required for monitoring to work!**

1. Go to: https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Name it: "Central-Books Monitoring"
4. Copy the key (starts with `sk-proj-...`)
5. **Save it immediately** - you won't see it again!
6. Add to `.env` locally AND Render environment variables

**Expected Cost:** ~$0.001-0.01 per report with gpt-5.1-mini (about $1-2/month for 3 reports/day)

> **Important:** You must create the OpenAI API key yourself in the OpenAI dashboard and paste it into `.env` locally and Render environment variables. The API key is never stored in the repository for security reasons.

---

## 📢 PART 3: Slack Webhook Setup (Optional)

**To enable Slack monitoring reports:**

### Create Incoming Webhook

1. Go to: https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: **"Central-Books Monitor"**
4. Select your workspace
5. In sidebar: click "Incoming Webhooks"
6. Toggle "Activate Incoming Webhooks" to **ON**
7. Click "Add New Webhook to Workspace"
8. Select channel (e.g., `#monitoring`)
9. Click "Allow"
10. **Copy the webhook URL** (starts with `https://hooks.slack.com/services/...`)

### Configure Webhook

**Local Development:**
Add to `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T08PCBC5598/B09V4UYF0BH/xxxxx
```

**Render Production:**
1. Go to: Render Service → Environment tab
2. Add environment variable:
   - **Key:** `SLACK_WEBHOOK_URL`
   - **Value:** `https://hooks.slack.com/services/...` (your webhook URL)
3. Click "Save Changes"

**Render Cron Jobs:**
- Add the same `SLACK_WEBHOOK_URL` to each cron job's environment variables
- This ensures scheduled reports are sent to Slack

> **Quick Setup:** See `SLACK_SETUP_GUIDE.md` for step-by-step instructions with your actual webhook URL.

---

## 💬 PART 4: Discord Webhook Setup (Optional)

1. Open your Discord server
2. Server Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Name: **"Central-Books Monitor"**
5. Select channel
6. **Copy Webhook URL** (starts with `https://discord.com/api/webhooks/...`)
7. Add to `.env` and Render as `DISCORD_WEBHOOK_URL`

---

## ⚡ PART 5: Slack Slash Command Setup (Optional - For `/cb-report`)

### Create Slack App Command

1. Go to your Slack App: https://api.slack.com/apps
2. Select "Central-Books Monitor" (or create new app)
3. In sidebar: click "Slash Commands"
4. Click "Create New Command"
5. Fill in:
   - **Command:** `/cb-report`
   - **Request URL:** `https://central-books-web.onrender.com/slack/monitoring/report/`
   - **Short Description:** "Generate Central-Books monitoring report"
   - **Usage Hint:** (leave blank)
6. Click "Save"
7. **Reinstall app to workspace** (Slack will prompt you)

### Get Verification Token (Optional but recommended)

1. In your Slack App settings
2. Go to "Basic Information"
3. Scroll to "App Credentials"
4. Copy "Verification Token"
5. Add to `.env` and Render as `SLACK_VERIFICATION_TOKEN`


---

## ⏰ PART 6: Schedule Monitoring Agent

You have **two options** for scheduling automated monitoring reports:

### Option A: GitHub Actions (Recommended - Every 2 Hours)

**Advantages:**
- ✅ Runs every 2 hours automatically
- ✅ No additional Render services needed
- ✅ Uses production database directly
- ✅ Centralized in your GitHub repository

**Setup:**

1. **Add GitHub Secrets**
   - Go to: GitHub Repository → Settings → Secrets and variables → Actions
   - Click "New repository secret" for each:

   | Secret Name | Value | Purpose |
   |-------------|-------|---------|
   | `OPENAI_API_KEY` | Your OpenAI API key | AI report generation |
   | `SLACK_WEBHOOK_URL` | Your Slack webhook URL | Report delivery |
   | `DATABASE_URL` | `postgresql://central_books_db_user:...` | Production database |
   | `DJANGO_SECRET_KEY` | Your Django secret key | Django settings |
   | `MONITORING_MODEL` | `gpt-4o-mini` | OpenAI model |
   | `MONITORING_ENV` | `production` | Environment identifier |

2. **Workflow File**
   - ✅ Already created: `.github/workflows/monitoring.yml`
   - Schedule: Every 2 hours (`0 */2 * * *`)
   - Manual trigger: Available via "Run workflow" button

3. **Verify Workflow**
   - Go to: GitHub Repository → Actions tab
   - Look for "Monitoring Agent (Every 2 Hours)"
   - Click "Run workflow" to test manually
   - Check your Slack channel for the report

**Schedule:**
- Runs every 2 hours: 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00 UTC
- **12 reports per day** (more frequent than Render cron jobs)

---

### Option B: Render Cron Jobs (Alternative - 3× Per Day)

The agent should run **3× per day** to generate status reports.

### Create Render Cron Job

Since Render requires separate cron jobs for each schedule:

**Create 3 Cron Jobs:**

1. **Morning Report (09:00 UTC)**
   - Service type: Cron Job
   - Name: `central-books-monitoring-morning`
   - Environment: Python
   - GitHub repo: (your repo)
   - Branch: `main`
   - Command: `python manage.py run_monitoring_agent`
   - Schedule: `0 9 * * *`

2. **Afternoon Report (15:00 UTC)**
   - Name: `central-books-monitoring-afternoon`
   - Command: `python manage.py run_monitoring_agent`
   - Schedule: `0 15 * * *`

3. **Evening Report (21:00 UTC)**
   - Name: `central-books-monitoring-evening`
   - Command: `python manage.py run_monitoring_agent`
   - Schedule: `0 21 * * *`

**For each cron job, set the same environment variables as your web service:**
- `OPENAI_API_KEY`
- `MONITORING_MODEL=gpt-5.1-mini`
- `MONITORING_ENV=production`
- `SLACK_WEBHOOK_URL` (if using)
- `DISCORD_WEBHOOK_URL` (if using)
- `DATABASE_URL` (auto-set by Render)
- `DJANGO_SECRET_KEY` (same as web service)

---

## 🧪 PART 7: Local Testing

### Test 1: Dry Run (No API Calls)

```bash
python manage.py run_monitoring_agent --dry-run
```

**Expected Output:**
- ✅ Metrics collected successfully
- ✅ JSON structure with all 7 domains
- ⚠️ Skips OpenAI call if no API key

### Test 2: Full Run with OpenAI (Requires API Key)

```bash
# First, set your API key in .env
export OPENAI_API_KEY=sk-proj-xxxxx

# Then run
python manage.py run_monitoring_agent
```

**Expected Output:**
- ✅ Metrics collected
- ✅ OpenAI API called
- ✅ Report generated
- ✅ Delivered to Slack/Discord (if webhook configured)

### Test 3: Slack Slash Command (Requires Slack App Setup)

1. In Slack, type: `/cb-report`
2. Press Enter
3. Wait 5-10 seconds
4. Report should appear in channel

---

## 📚 PART 8: Usage Guide

### Command-Line Usage

```bash
# Dry run (print metrics without AI analysis)
python manage.py run_monitoring_agent --dry-run

# Normal run (sends to webhooks)
python manage.py run_monitoring_agent

# Use different OpenAI model
python manage.py run_monitoring_agent --model gpt-4o
```

### Slack Slash Command

Once configured:
- Type `/cb-report` in any Slack channel
- Report generated on-demand
- Visible to everyone in channel

### On-Demand via cURL (for testing)

```bash
# Trigger Slack endpoint directly
curl -X POST https://central-books-web.onrender.com/slack/monitoring/report/ \
  -d "token=your-verification-token"
```

---

## 🐛 Troubleshooting

### Issue: "OPENAI_API_KEY is required"
**Solution:** Add API key to `.env` locally or Render environment variables

### Issue: Slack webhook returns 404
**Solution:** Regenerate webhook in Slack app settings

### Issue: Slash command doesn't work
**Solutions:**
1. Verify Request URL is correct in Slack App settings
2. Check Render logs for errors (`render logs`)
3. Ensure CSRF exemption is working (`@csrf_exempt` decorator)

### Issue: Metrics show zeros
**Solutions:**
1. Check if business has data (invoices, expenses, bank transactions)
2. Verify date ranges in metrics collection
3. Look for Django ORM query errors in logs

### Issue: Report takes too long
**Solutions:**
1. Use async Slack response (built-in for slash commands)
2. Reduce metrics collection query complexity
3. Add database indexes on frequently queried fields

---

## 📈 What Gets Reported

Sample monitoring report structure:

```
📊 CENTRAL-BOOKS MONITORING REPORT
Generated: 2025-11-27T09:51:47+00:00
Environment: production

=== OVERVIEW ===
System healthy. 3 businesses active. Recent activity: 5 expenses created.
Ledger balanced with 9 accounts. No bank reconciliation issues.

=== 🛠️ Product & Engineering ===
3 businesses onboarded. 5 expenses created in last 24h.
No reconciliations started. TODO: Track deployments.

=== 📒 Ledger & Accounting ===
9 accounts (4 ASSET, 3 LIABILITY, 1 INCOME, 1 EXPENSE).
5 journal entries, all balanced. Cash at Bank: -$693.48

=== 🏦 Banking & Reconciliation ===
0 bank accounts configured. No transactions to reconcile.

=== 💰 Tax & FX ===
0 active tax rates. Multi-currency enabled (CAD).
Invoice validation: 200 lines checked, 0 mismatches.

=== 📈 Business & Revenue ===
0 customers. 0 payments in window. TODO: Track MRR.

=== 📢 Marketing & Traffic ===
No data available (TODO: Integrate Google Analytics)

=== 💬 Support & Feedback ===
No data available (TODO: Integrate ticketing system)
```

---

## 🚀 Next Steps

1. ✅ Test locally with `--dry-run`
2. ⚠️ Add `OPENAI_API_KEY` to `.env`
3. ⚠️ Add `OPENAI_API_KEY` to Render
4. ⚠️ Set up Slack/Discord webhooks (optional)
5. ⚠️ Create Render cron jobs (3× daily)
6. ⚠️ Set up Slack slash command (optional)
7. ✅ Monitor reports in Slack/Discord
8. 📝 Customize metrics as business grows

---

## 💡 Future Enhancements (TODOs in Code)

- [ ] Request logging for `product_engineering.requests`
- [ ] Deployment tracking (Git commits or Render API)
- [ ] Page view tracking (`dashboard_views`)
- [ ] Bank feed import tracking
- [ ] Google Analytics / Plausible integration for `marketing_traffic`
- [ ] Zendesk / Intercom integration for `support_feedback`
- [ ] Subscription/MRR tracking for `business_revenue.mrr`
- [ ] Payment failure tracking
- [ ] FX document totals validation

---

## 📞 Support

**Files to reference:**
- `core/metrics.py` - Metrics collection logic
- `core/management/commands/run_monitoring_agent.py` - CLI command
- `core/views_monitoring.py` - Slack endpoint
- `.env.example` - Environment variable template

**Need help?** Check the TODO comments in `core/metrics.py` for integration points.

---

**Status:** ✅ Ready for production! Just add your API keys and webhooks.
