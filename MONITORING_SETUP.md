# 🚀 Central-Books Monitoring Agent & CI/CD Setup Guide

## ✅ What's Been Installed

### Monitoring Agent
- ✅ `core/metrics.py` - Collects metrics across 7 business domains
- ✅ `core/management/commands/run_monitoring_agent.py` - OpenAI-powered monitoring reports
- ✅ Updated `requirements.txt` with OpenAI SDK and requests
- ✅ `.env.example` template for environment variables

### CI/CD Pipeline
- ✅ `.github/workflows/ci.yml` - Automated testing on every PR and push
- ✅ `.github/workflows/cd.yml` - Automated deployment to Render on main branch merges

---

## 📋 Prerequisites

Before you can use the monitoring agent and CI/CD pipeline, you need to set up several external services and obtain API keys/webhooks.

---

## 🔐 Part 1: Obtain API Keys & Webhooks

### 1.1 OpenAI API Key (REQUIRED)

**Purpose:** Powers the AI-driven monitoring reports

**Steps:**
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click "Create new secret key"
4. Name it "Central-Books Monitoring"
5. Copy the key (starts with `sk-proj-...`) - you won't see it again!
6. Save it securely - you'll add it to GitHub Secrets and Render later

**Estimated Cost:** ~$0.001-0.01 per report with gpt-5.1-mini

---

### 1.2 Slack Webhook (OPTIONAL)

**Purpose:** Receive monitoring reports in Slack

**Steps:**
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "Central-Books Monitor", select your workspace
4. In the left sidebar, click "Incoming Webhooks"
5. Toggle "Activate Incoming Webhooks" to ON
6. Click "Add New Webhook to Workspace"
7. Select the channel you want reports in (e.g., #monitoring)
8. Click "Allow"
9. Copy the Webhook URL (starts with `https://hooks.slack.com/services/...`)

---

### 1.3 Discord Webhook (OPTIONAL)

**Purpose:** Receive monitoring reports in Discord

**Steps:**
1. Open your Discord server
2. Go to Server Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Name: "Central-Books Monitor"
5. Select the channel you want reports in
6. Copy the Webhook URL (starts with `https://discord.com/api/webhooks/...`)

---

### 1.4 Render API Key (REQUIRED for automated deploys)

**Purpose:** Allows GitHub Actions to trigger Render deployments

**Steps:**
1. Go to https://dashboard.render.com/account/settings
2. Scroll to "API Keys"
3. Click "Create API Key"
4. Name: "GitHub Actions CI/CD"
5. Copy the API key (starts with `rnd_...`)

---

### 1.5 Render Service IDs (REQUIRED for automated deploys)

**Purpose:** Identifies which Render service to deploy

**Steps:**
1. Go to your Render dashboard: https://dashboard.render.com/
2. Click on your "central-books-web" service
3. Look at the URL - it contains your service ID
   - Example: `https://dashboard.render.com/web/srv-abc123xyz456`
   - Your service ID is: `srv-abc123xyz456`
4. Copy this ID

---

## 🔧 Part 2: Configure GitHub Secrets

GitHub Secrets allow your CI/CD workflows to access sensitive credentials securely.

**Steps:**
1. Go to your GitHub repository
2. Click "Settings" tab
3. In the left sidebar, click "Secrets and variables" → "Actions"
4. Click "New repository secret" for each of the following:

### Required Secrets

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Powers monitoring reports |
| `RENDER_API_KEY` | Your Render API key | Triggers deployments |
| `RENDER_SERVICE_ID` | Your Render service ID | Identifies backend service |

### Optional Secrets

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL | Delivers reports to Slack |
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL | Delivers reports to Discord |

**Screenshot Guide:**
```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

---

## ⚙️ Part 3: Configure Render Environment Variables

Environment variables tell your production app how to connect to external services.

**Steps:**
1. Go to https://dashboard.render.com/
2. Click on your "central-books-web" service
3. Click "Environment" in the left sidebar
4. Add the following environment variables:

### Required Variables

| Variable Name | Value | Notes |
|---------------|-------|-------|
| `OPENAI_API_KEY` | Your OpenAI API key | Same as GitHub Secret |
| `MONITORING_MODEL` | `gpt-5.1-mini` | Recommended for cost efficiency |
| `MONITORING_ENV` | `production` | Identifies environment |

### Optional Variables

| Variable Name | Value | Notes |
|---------------|-------|-------|
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL | Leave blank to disable |
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL | Leave blank to disable |

**After adding variables:**
1. Click "Save Changes"
2. Render will automatically redeploy your service

---

## ⏰ Part 4: Set Up Render Cron Job

The monitoring agent should run 3× per day to generate status reports.

### Option A: Using Render Cron Jobs (Recommended)

**Steps:**
1. Go to your Render dashboard
2. Click "New +" → "Cron Job"
3. Configure:
   - **Name:** `central-books-monitoring`
   - **Environment:** Python
   - **GitHub Repo:** Select your repo
   - **Branch:** `main`
   - **Command:** `python manage.py run_monitoring_agent`
   - **Schedule:** Custom (see below)
4. Add the schedule expressions:
   - `0 9 * * *` (09:00 UTC daily)
   - `0 15 * * *` (15:00 UTC daily)
   - `0 21 * * *` (21:00 UTC daily)

5. Set environment variables (same as Part 3)
6. Click "Create Cron Job"

**Note:** You'll need to create 3 separate cron jobs in Render since it doesn't support multiple schedules in one job.

### Option B: External Cron Service (Alternative)

If Render cron jobs don't work for you:

1. Use a service like GitHub Actions scheduled workflows
2. Or use a dedicated cron service like cron-job.org
3. Make HTTP requests to a Django endpoint that triggers the monitoring agent

---

## 🧪 Part 5: Test Everything

### Test Monitoring Agent Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables in .env
cat > .env << EOF
OPENAI_API_KEY=your-key-here
MONITORING_MODEL=gpt-5.1-mini
SLACK_WEBHOOK_URL=your-slack-webhook
DISCORD_WEBHOOK_URL=your-discord-webhook
EOF

# 3. Test with dry-run (no webhooks)
python manage.py run_monitoring_agent --dry-run

# 4. Test with actual delivery
python manage.py run_monitoring_agent
```

### Test CI Pipeline

```bash
# 1. Create a test branch
git checkout -b test-ci

# 2. Make a small change
echo "# CI Test" >> README.md

# 3. Commit and push
git add .
git commit -m "Test CI pipeline"
git push origin test-ci

# 4. Create a Pull Request on GitHub
# - Go to your repo
# - Click "Pull requests" → "New pull request"
# - Select your test-ci branch
# - Watch the CI checks run!
```

### Test CD Pipeline

```bash
# 1. After CI passes, merge your PR to main
# 2. Go to Actions tab on GitHub
# 3. Watch the "Central-Books CD" workflow run
# 4. Verify deployment on Render dashboard
```

---

## 📊 Part 6: Understanding the Monitoring Report

When the monitoring agent runs, it will generate a report like this:

```
📊 CENTRAL-BOOKS MONITORING REPORT
Generated: 2025-11-27T09:32:21+00:00
Environment: production

=== OVERVIEW ===
System healthy with 2 accounts in chart. No recent revenue or
banking activity. Reconciliation clean.

=== 🛠️ Product & Engineering ===
⚠️ No deployment or feature tracking currently configured.
Uptime: 99.9%

=== 📒 Ledger & Accounting ===
2 accounts configured. 0 journal entries last 30d.
Chart of accounts: healthy (0 unbalanced entries)

=== 🏦 Banking & Reconciliation ===
0 bank accounts. 0 transactions last 30d.
Reconciliation health: healthy

=== 💰 Tax & FX ===
0 active tax rates configured.
Multi-currency enabled (CAD). No FX conversions tracked.

=== 📈 Business & Revenue ===
Revenue last 30d: $0.00
Expenses last 30d: $0.00
Profit: $0.00
0 active customers, 0 suppliers

=== 📢 Marketing & Traffic ===
No data available

=== 💬 Support & Feedback ===
No data available
```

---

## 🔄 Part 7: Rollback Procedures

### Rollback a Bad Deployment

**Option 1: Via Render Dashboard**
1. Go to your service → "Events" tab
2. Find the last successful deployment
3. Click "Redeploy"

**Option 2: Via Git Revert**
```bash
# Revert the last commit
git revert HEAD
git push origin main

# CD pipeline will automatically deploy the reverted version
```

### Pause Auto-Deployments

**GitHub Actions:**
```bash
# Disable cd.yml workflow
# Go to: Repository → Actions → Workflows → Central-Books CD
# Click "..." → "Disable workflow"
```

**Render:**
```bash
# Go to: Service → Settings → Auto-Deploy
# Set to "No" and save
```

---

## 🐛 Troubleshooting

### Monitoring Agent Fails with "OpenAI API Error"

**Symptom:** Command exits with OpenAI-related error

**Solutions:**
1. Check API key is valid: https://platform.openai.com/api-keys
2. Verify you have available credits
3. Check the model name is correct (`gpt-5.1-mini`)

### Webhook Delivery Fails

**Symptom:** Report generated but not delivered to Slack/Discord

**Solutions:**
1. Test webhook URL with curl:
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d '{"text":"Test message"}'
   ```
2. Regenerate the webhook if it's invalid
3. Check webhook hasn't been deleted in Slack/Discord

### CI Tests Fail

**Symptom:** GitHub Actions shows red X

**Solutions:**
1. Click into the failed job to see detailed logs
2. Run tests locally: `python manage.py test`
3. Fix the failing test and push again

### CD Deployment Hangs

**Symptom:** Deployment workflow runs forever

**Solutions:**
1. Check Render dashboard for build errors
2. Verify `RENDER_API_KEY` and `RENDER_SERVICE_ID` are correct
3. Check Render service logs for startup errors

---

## 📚 Additional Resources

- **OpenAI API Docs:** https://platform.openai.com/docs
- **Render Cron Jobs:** https://docs.render.com/cronjobs
- **GitHub Actions:** https://docs.github.com/en/actions
- **Slack Webhooks:** https://api.slack.com/messaging/webhooks
- **Discord Webhooks:** https://discord.com/developers/docs/resources/webhook

---

## 🎉 You're Done!

Once you've completed all 7 parts:
- ✅ Monitoring agent will run 3× daily
- ✅ Every PR triggers automated tests
- ✅ Every merge to main deploys automatically
- ✅ Reports delivered to Slack/Discord

**Next Steps:**
1. Customize metrics in `core/metrics.py` as your business grows
2. Add more TODO integrations (analytics, support tickets, etc.)
3. Configure Slack slash command for on-demand reports (advanced)
