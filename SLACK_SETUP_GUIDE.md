# 📢 Slack Webhook Setup Guide

## ✅ Your Slack Webhook URL
```
https://hooks.slack.com/services/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
```

---

## 🚀 Quick Setup Instructions

### 1. **Local Development (.env file)**

Add to `/Users/wherethefuckthefunction/Desktop/PROJECT BIBLE/.env`:

```bash
# Monitoring Agent
OPENAI_API_KEY=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
MONITORING_MODEL=gpt-5.1-mini
MONITORING_ENV=local

# Slack Webhook
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/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
```

### 2. **Render Web Service**

1. Go to: https://dashboard.render.com/
2. Click on **central-books-web** service
3. Navigate to **Environment** tab
4. Click **Add Environment Variable**
5. Add:
   - **Key:** `SLACK_WEBHOOK_URL`
   - **Value:** `https://hooks.slack.com/services/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`
6. Click **Save Changes**

### 3. **Render Cron Jobs** (if you created them)

For each cron job (`morning`, `afternoon`, `evening`):
1. Click on the cron job
2. Navigate to **Environment** tab
3. Add the same variables:
   - `OPENAI_API_KEY` = (your OpenAI key)
   - `MONITORING_MODEL` = `gpt-5.1-mini`
   - `SLACK_WEBHOOK_URL` = `https://hooks.slack.com/services/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`

---

## 🧪 Test Locally

### Dry Run (no Slack posting)
```bash
python manage.py run_monitoring_agent --dry-run
```

**Expected output:**
```
🔄 Collecting metrics...
📊 METRICS COLLECTED: {...}
⚠️  SLACK_WEBHOOK_URL not set - skipping Slack notification
⚠️  No webhook URLs configured...
```

### Full Run (posts to Slack)
```bash
python manage.py run_monitoring_agent
```

**Expected output:**
```
🔄 Collecting metrics...
🤖 Calling OpenAI (gpt-5.1-mini)...
📤 Sending to Slack...
✅ Report delivered successfully
```

**Check Slack:** You should see the monitoring report in your configured channel!

---

## 📊 What Gets Posted to Slack

Sample report:
```
📊 CENTRAL-BOOKS MONITORING REPORT
Generated: 2025-11-27T10:16:30+00:00
Environment: local

=== OVERVIEW ===
System healthy. 3 businesses active...

=== 🛠️ Product & Engineering ===
...

=== 📒 Ledger & Accounting ===
...
```

---

## 🔧 Troubleshooting

### Issue: "Invalid webhook URL" error
**Solution:** Verify the webhook URL is correct by testing with curl:
```bash
curl -X POST https://hooks.slack.com/services/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 \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test from Central-Books monitoring"}'
```

### Issue: "SLACK_WEBHOOK_URL not set" message
**Solution:** 
1. Verify `.env` file exists and contains the webhook URL
2. Check for typos in the variable name
3. Restart your terminal/IDE to reload environment variables

### Issue: No message appears in Slack
**Solutions:**
1. Check webhook hasn't been deleted in Slack
2. Verify the correct channel is configured
3. Check Slack app settings

---

## 🎯 Quick Command Reference

```bash
# Test dry-run (no Slack posting)
python manage.py run_monitoring_agent --dry-run

# Post to Slack
python manage.py run_monitoring_agent

# Use different model
python manage.py run_monitoring_agent --model gpt-4o
```

---

## ✅ Setup Complete Checklist

- [x] Slack webhook URL obtained
- [ ] Added to local `.env` file
- [ ] Added to Render web service environment
- [ ] Added to Render cron jobs (if created)
- [ ] Tested locally with `--dry-run`
- [ ] Tested actual posting to Slack
- [ ] Verified report appears in Slack channel

---

**Status:** Ready to use! Just update your `.env` and Render environment variables.
