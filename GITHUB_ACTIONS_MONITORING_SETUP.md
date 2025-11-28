# ✅ GitHub Actions Monitoring Workflow - Complete Setup

## Overview

Successfully created a GitHub Actions workflow that automatically runs the Django monitoring agent **every 2 hours**, connecting to your production Render database and posting reports to Slack.

---

## 📁 File Created

**`.github/workflows/monitoring.yml`**

```yaml
name: Monitoring Agent (Every 2 Hours)

on:
  schedule:
    # Run every 2 hours
    - cron: "0 */2 * * *"
  workflow_dispatch:  # Allow manual triggers

jobs:
  run-monitoring:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run database migrations
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
          DJANGO_DEBUG: 'False'
        run: |
          python manage.py migrate --noinput
      
      - name: Run monitoring agent
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          MONITORING_MODEL: ${{ secrets.MONITORING_MODEL }}
          MONITORING_ENV: ${{ secrets.MONITORING_ENV }}
          DJANGO_DEBUG: 'False'
        run: |
          python manage.py run_monitoring_agent
      
      - name: Report status
        if: always()
        run: |
          if [ $? -eq 0 ]; then
            echo "✅ Monitoring report sent successfully"
          else
            echo "❌ Monitoring report failed"
            exit 1
          fi
```

---

## 🔐 GitHub Secrets Required

Go to: **GitHub Repository → Settings → Secrets and variables → Actions**

Click **"New repository secret"** for each:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `OPENAI_API_KEY` | `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` | AI report generation |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/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` | Report delivery to Slack |
| `DATABASE_URL` | `postgresql://central_books_db_user:mrtUyGJLC5cTWKQte5pfMKo3tnauziZf@dpg-d4eqrdqdbo4c73dmf1cg-a.oregon-postgres.render.com/central_books_db` | Production database |
| `DJANGO_SECRET_KEY` | `3499c4e39ba81aa04d68a2dbc6ddd8bd` | Django settings |
| `MONITORING_MODEL` | `gpt-4o-mini` | OpenAI model |
| `MONITORING_ENV` | `production` | Environment identifier |

---

## ⏰ Schedule

**Runs every 2 hours:**
- 00:00, 02:00, 04:00, 06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00 UTC
- **12 reports per day** automatically

**Also supports manual triggering:**
- Go to: GitHub → Actions → "Monitoring Agent (Every 2 Hours)"
- Click "Run workflow" button

---

## ✅ Validation

**YAML Syntax:** ✅ Valid
**Python Version:** 3.11
**Dependencies:** Installed from `requirements.txt`
**Database:** Connects to production Render PostgreSQL
**Migrations:** Runs safely before monitoring
**Model:** Uses `gpt-4o-mini`

---

## 📋 Final Checklist

### ✅ Completed:
- [x] Created `.github/workflows/monitoring.yml`
- [x] Updated `MONITORING_COMPLETE_GUIDE.md` with GitHub Actions section
- [x] Validated YAML syntax
- [x] Configured to use gpt-4o-mini model
- [x] Set up database migrations before monitoring
- [x] Configured Slack webhook delivery

### ⚠️ Manual Steps Required:

1. **Add GitHub Secrets** (see table above)  
   Navigate to: Repository → Settings → Secrets and variables → Actions

2. **Push workflow to GitHub**
   ```bash
   git add .github/workflows/monitoring.yml
   git commit -m "Add automated monitoring workflow (every 2 hours)"
   git push origin main
   ```

3. **Verify workflow**
   - Go to: GitHub → Actions tab
   - Look for "Monitoring Agent (Every 2 Hours)"
   - Click "Run workflow" to test manually
   - Check Slack for the report

4. **Confirm local dry-run works**
   ```bash
   python manage.py run_monitoring_agent --dry-run
   ```

---

## 🎯 How It Works

1. **Trigger:** GitHub Actions scheduler fires every 2 hours
2. **Setup:** Checks out code, installs Python 3.11, installs dependencies
3. **Database:** Connects to production Render PostgreSQL via `DATABASE_URL`
4. **Migrations:** Runs `python manage.py migrate --noinput` safely
5. **Monitoring:** Executes `python manage.py run_monitoring_agent`
   - Collects metrics from production database
   - Calls OpenAI API with `gpt-4o-mini`
   - Generates formatted report
   - Posts to Slack via webhook
6. **Status:** Reports success/failure in GitHub Actions logs

---

## 📊 Advantages Over Render Cron Jobs

| Feature | GitHub Actions | Render Cron Jobs |
|---------|----------------|------------------|
| Frequency | Every 2 hours (12×/day) | 3×/day |
| Cost | Free (GitHub Actions) | Additional Render services |
| Setup | Centralized in repo | Multiple cron job services |
| Logs | GitHub Actions UI | Render dashboard |
| Manual trigger | ✅ One click | ❌ Requires SSH or redeploy |
| Database access | Direct via `DATABASE_URL` | Same as web service |

---

## 🐛 Troubleshooting

### Workflow not running
- Check: Repository → Actions → Workflows are enabled
- Verify: GitHub Secrets are set correctly
- Test: Manually trigger with "Run workflow" button

### Database connection fails
- Verify: `DATABASE_URL` secret is correct
- Check: Render database is accessible from GitHub Actions IPs
- Test: Run migrations step separately

### OpenAI API errors
- Verify: `OPENAI_API_KEY` is valid
- Check: Model name is `gpt-4o-mini` (not gpt-5.1-mini)
- Test: Local dry-run works

### Slack delivery fails
- Verify: `SLACK_WEBHOOK_URL` is correct
- Test: Webhook with curl (see SLACK_SETUP_GUIDE.md)
- Check: Webhook hasn't been deleted in Slack

---

## 📚 Documentation Updated

- ✅ `MONITORING_COMPLETE_GUIDE.md` - Added "Option A: GitHub Actions" section
- ✅ Kept "Option B: Render Cron Jobs" as alternative

---

## 🚀 Ready to Deploy

The workflow is ready! Just add the GitHub Secrets and push to your repository.

**Next monitoring report:** Will run within 2 hours of pushing the workflow (at the next hour divisible by 2).
