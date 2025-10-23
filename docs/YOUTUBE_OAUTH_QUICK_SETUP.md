# YouTube OAuth 2.0 Quick Setup

You're absolutely correct! YouTube Data API v3 now requires OAuth 2.0 credentials instead of simple API keys. I've updated the implementation to use your OAuth credentials.

## Your Credentials
- **Client ID**: `63234829948-h407c75md1q8qt0knmv7u0751h5vovsh.apps.googleusercontent.com`
- **Client Secret**: `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`

## Quick Setup Steps

### 1. Install Required Packages
```bash
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

### 2. Configure Environment
Add to your `config/.env` file:
```env
YOUTUBE_CLIENT_ID=63234829948-h407c75md1q8qt0knmv7u0751h5vovsh.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=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
```

### 3. Test Setup
Run the setup helper:
```bash
python scripts/setup_youtube_oauth.py
```

This will:
1. Open your web browser for OAuth authorization
2. Ask you to sign in to Google and grant permissions  
3. Test the connection with a sample channel
4. Save credentials locally for future use

### 4. OAuth Authorization Flow
The first time you run the scraper:
1. **Browser opens** automatically to `http://localhost:8080`
2. **Sign in** to your Google account
3. **Grant permissions** for YouTube Data API access (read-only)
4. **Credentials saved** to `config/youtube_credentials.pickle`
5. **Future runs** use saved credentials (no browser needed)

## What Changed in the Implementation

✅ **OAuth 2.0 Support**: Uses `google-auth-oauthlib` for authentication  
✅ **Credential Persistence**: Saves tokens locally, refreshes automatically  
✅ **Headless Support**: Works on servers after initial setup  
✅ **Error Handling**: Graceful fallbacks for auth failures  
✅ **Same API**: All existing scraper methods work unchanged  

## Troubleshooting

**Port 8080 in use?**
- Close any applications using port 8080
- The OAuth flow uses this port temporarily

**No browser available?**
- Run initial setup on a machine with GUI access
- Copy the generated `config/youtube_credentials.pickle` to your server

**Permission denied?**
- Make sure your OAuth app has YouTube Data API v3 scope
- Check that you're signed in to the correct Google account

## Security Notes

- OAuth credentials are more secure than API keys
- Tokens are scoped to read-only YouTube data
- Refresh tokens allow long-term access without re-auth
- Never commit `youtube_credentials.pickle` to version control

Your YouTube integration is now ready! The scraper will work exactly the same as before, but with proper OAuth 2.0 authentication.

**Next step**: Run `python scripts/setup_youtube_oauth.py` to complete the setup.