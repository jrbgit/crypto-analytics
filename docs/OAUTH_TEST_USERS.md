# Adding Test Users to OAuth Consent Screen

If you're getting an "app not verified" warning, you can add your Google account as a test user:

## Steps:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent)
2. Select your project
3. Click on **OAuth consent screen** in the left sidebar
4. Scroll down to **Test users** section
5. Click **+ ADD USERS**
6. Add your Gmail address (joanas@gmail.com)
7. Click **SAVE**

## What this does:
- Allows your account to bypass the "unverified app" warning
- Enables testing without going through Google's app verification process
- Only affects the specific Gmail accounts you add

## For production:
- You'll need to submit your app for Google's verification process
- Or keep it in testing mode if it's only for personal use