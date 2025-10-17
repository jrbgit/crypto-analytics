# YouTube Data API Setup Guide

This guide explains how to set up YouTube Data API credentials for the crypto analytics platform.

## Overview

The YouTube scraper uses the YouTube Data API v3 to:
- Fetch channel information (subscriber count, video count, etc.)
- Retrieve recent videos with metadata (titles, descriptions, view counts, etc.)
- Extract engagement metrics (likes, comments, views)
- Analyze content patterns and upload frequency

## API Quota Information

- **Daily Quota**: 10,000 units (free tier)
- **Channel info request**: ~3-5 units
- **Video list request**: ~1-3 units per video
- **Typical channel analysis**: 20-50 units (depending on number of videos)

This allows for **200-500 channel analyses per day** on the free tier.

## Setup Instructions

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID for reference

### 2. Enable YouTube Data API v3

1. In the Cloud Console, go to **APIs & Services** → **Library**
2. Search for "YouTube Data API v3"
3. Click on it and press **ENABLE**

### 3. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** user type
   - Fill in required fields (App name, User support email, Developer email)
   - Add your email to test users
   - Save and continue through the scopes (no scopes needed) and test users sections
4. Back in Credentials, create OAuth client ID:
   - Choose **Desktop application** as the application type
   - Give it a name (e.g., "Crypto Analytics YouTube Scraper")
5. Copy the **Client ID** and **Client Secret**

### 4. Configure the Application

1. Copy `config/.env.example` to `config/.env`
2. Set the YouTube OAuth credentials:
   ```
   YOUTUBE_CLIENT_ID=your_actual_client_id_here
   YOUTUBE_CLIENT_SECRET=your_actual_client_secret_here
   ```

**Important**: The first time you run the scraper, it will:
1. Open your web browser for OAuth authorization
2. Ask you to sign in to Google and grant permissions
3. Save the credentials locally for future use
4. You only need to do this once unless you revoke the app's permissions

## Testing Your Setup

Run this test to verify your API key works:

```python
from src.scrapers.youtube_scraper import YouTubeScraper

scraper = YouTubeScraper()

# Test with Ethereum's official channel
result = scraper.scrape_youtube_channel("https://www.youtube.com/@ethereum")

if result.scrape_success:
    print(f"✅ YouTube API working! Found {result.total_videos} videos")
    if result.channel_info:
        print(f"Channel: {result.channel_info.title}")
        print(f"Subscribers: {result.channel_info.subscriber_count:,}")
else:
    print(f"❌ Error: {result.error_message}")
```

## Common YouTube URL Formats Supported

The scraper supports these YouTube channel URL formats:

```
https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxx  # Direct channel ID
https://www.youtube.com/@username                        # Handle format
https://www.youtube.com/c/channelname                   # Custom URL
https://www.youtube.com/user/username                   # Legacy format
https://youtube.com/@username                           # Without www
```

## Quota Management Tips

1. **Monitor usage**: Check quota usage in Google Cloud Console
2. **Optimize requests**: The scraper is designed to minimize API calls
3. **Rate limiting**: Built-in delays prevent quota exhaustion
4. **Upgrade if needed**: Consider paid plans for high-volume analysis

## Error Handling

The scraper handles common API errors:

- **403 Quota Exceeded**: Automatically logged with helpful message
- **404 Channel Not Found**: Graceful handling with clear error message
- **401 Invalid API Key**: Clear instructions for fixing credentials
- **Network Issues**: Automatic retry with exponential backoff

## Security Best Practices

1. **Restrict API Key**: Always set API restrictions in Google Cloud Console
2. **Environment Variables**: Never commit API keys to version control
3. **IP Restrictions**: Optionally restrict by server IP address
4. **Regular Rotation**: Consider rotating API keys periodically

## Integration with Analysis Pipeline

Once configured, YouTube analysis is automatically available for any project with a `youtube` link_type in the database. The system will:

1. **Scrape**: Fetch channel info and recent videos
2. **Analyze**: Use LLM or metadata analysis for insights
3. **Store**: Save results to database for reporting
4. **Report**: Include YouTube metrics in project analysis

## Troubleshooting

### API Key Issues
```
❌ YouTube API quota exceeded or API key invalid
```
- **Solution**: Check API key in Google Cloud Console, verify it's enabled for YouTube Data API v3

### Channel Not Found
```
❌ YouTube channel not found
```
- **Solution**: Verify the channel URL format, ensure channel exists and is public

### Quota Exceeded
```
❌ YouTube API quota exceeded
```
- **Solution**: Wait for quota reset (daily) or upgrade to paid plan

### Import Errors
```
ImportError: No module named 'googleapiclient'
```
- **Solution**: Install required packages: `pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2`

### OAuth Authorization Issues
```
OAuth flow failed: [Errno 10061] Connection refused
```
- **Solution**: Make sure port 8080 is available and you have a web browser on the same machine
- **Alternative**: Run the scraper on a machine with GUI access for the initial OAuth setup

For additional help, check the [YouTube Data API documentation](https://developers.google.com/youtube/v3).