# Google OAuth Login Setup

Central-Books now supports Google OAuth login using `django-allauth`.

## Configuration

### 1. Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth 2.0 Client ID**
5. Configure the OAuth consent screen if prompted
6. Select **Web application** as the application type
7. Add authorized redirect URIs:
   - For local development: `http://127.0.0.1:8000/accounts/google/login/callback/`
   - For production: `https://your-domain.com/accounts/google/login/callback/`
8. Click **Create** and copy the **Client ID** and **Client Secret**

### 2. Set Environment Variables

Add the following environment variables:

**Local Development (.env file):**
```bash
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
```

**Production (Render/GitHub Actions):**
Add these as environment variables or secrets in your deployment platform:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SITE_DOMAIN` (optional override; defaults to Render hostname or the first non-local ALLOWED_HOST)

### 3. Run Setup Command

After setting environment variables, run the setup command to configure the database:

```bash
python manage.py setup_google_oauth
```

This command will:
- Verify your environment variables are set
- Update the site domain configuration
- Create/update the Google SocialApp in the database
- Display the redirect URI you need to configure in Google Cloud Console

### 4. Usage

Users can now click **"Continue with Google"** on the login page (`/login/`) to authenticate using their Google account.

## Security Notes

- ⚠️ **Never commit** your `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` to version control
- ⚠️ Keep OAuth credentials in `.env` (gitignored) or environment variables
- ⚠️ Use different OAuth credentials for development and production

## Troubleshooting

### Error 400: invalid_request (flowName=GeneralOAuthFlow)
This error occurs when the Google OAuth credentials are not properly configured in the database.

**Solution:**
1. Make sure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in your environment
2. Run `python manage.py setup_google_oauth` to configure the database
3. Verify the SocialApp was created: `python manage.py shell -c "from allauth.socialaccount.models import SocialApp; print(SocialApp.objects.filter(provider='google').values())"`

### Redirect URI Mismatch Error
Make sure the redirect URI in Google Cloud Console exactly matches:
- Development: `http://127.0.0.1:8000/accounts/google/login/callback/`
- Production: `https://your-domain.com/accounts/google/login/callback/`

**Tip:** The `setup_google_oauth` command displays the exact redirect URI you need to use.

### Google Login Button Not Appearing
1. Verify `django-allauth` is installed: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Check that GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set
4. Run `python manage.py setup_google_oauth`

### Email Already Exists Error
If a user already has an account with the same email, allauth will attempt to link the accounts. Configure `ACCOUNT_EMAIL_VERIFICATION` in `settings.py` to control this behavior.
