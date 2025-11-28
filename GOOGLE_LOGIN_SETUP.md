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

### 3. Usage

Users can now click **"Continue with Google"** on the login page (`/login/`) to authenticate using their Google account.

## Security Notes

- ⚠️ **Never commit** your `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` to version control
- ⚠️ Keep OAuth credentials in `.env` (gitignored) or environment variables
- ⚠️ Use different OAuth credentials for development and production

## Troubleshooting

### Redirect URI Mismatch Error
Make sure the redirect URI in Google Cloud Console exactly matches:
- Development: `http://127.0.0.1:8000/accounts/google/login/callback/`
- Production: `https://your-domain.com/accounts/google/login/callback/`

### Google Login Button Not Appearing
1. Verify `django-allauth` is installed: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Check that GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set

### Email Already Exists Error
If a user already has an account with the same email, allauth will attempt to link the accounts. Configure `ACCOUNT_EMAIL_VERIFICATION` in `settings.py` to control this behavior.
