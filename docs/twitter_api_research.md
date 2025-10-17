# Twitter API v2 Free Tier Research

## API Overview
- **Service**: Twitter API v2 (X API)
- **Free Tier Limit**: 100 posts retrieval + 500 writes per month
- **Rate Limiting**: 100 requests per 24-hour period

## Authentication
- **Required**: Bearer Token (OAuth 2.0)
- **Setup Process**:
  1. Create Twitter Developer Account
  2. Create a new App in Developer Portal
  3. Generate Bearer Token
  4. Store token in `.env` as `TWITTER_BEARER_TOKEN`

## Available Endpoints (Free Tier)
### User Lookup
- `GET /2/users/by/username/{username}` - Get user by username
- `GET /2/users/{id}` - Get user by ID
- **Fields Available**: 
  - `id`, `name`, `username`, `created_at`, `description`
  - `location`, `pinned_tweet_id`, `profile_image_url`
  - `protected`, `public_metrics`, `url`, `verified`, `verified_type`

### Tweets Lookup
- `GET /2/tweets/{id}` - Get tweet by ID
- `GET /2/users/{id}/tweets` - Get user's recent tweets (limited)
- **Fields Available**:
  - `id`, `text`, `created_at`, `author_id`
  - `public_metrics` (retweet_count, like_count, reply_count, quote_count)
  - `context_annotations`, `entities`, `lang`

## Key Metrics for Crypto Analysis
### User Profile Metrics
- **Account Age**: `created_at` - older accounts more trustworthy
- **Follower Count**: `public_metrics.followers_count`
- **Following Count**: `public_metrics.following_count`
- **Tweet Count**: `public_metrics.tweet_count`
- **Listed Count**: `public_metrics.listed_count`
- **Verification Status**: `verified` (legacy) or `verified_type` (new system)

### Content Quality Indicators
- **Bio Quality**: Analysis of `description` field
- **Profile Completeness**: presence of `url`, `location`, `profile_image_url`
- **Recent Activity**: Tweet frequency and engagement patterns

### Engagement Metrics (per tweet)
- **Like Count**: `public_metrics.like_count`
- **Retweet Count**: `public_metrics.retweet_count`
- **Reply Count**: `public_metrics.reply_count`
- **Quote Count**: `public_metrics.quote_count`

## Rate Limiting Strategy
Given 100 API calls/month constraint:

### Priority Scoring System
1. **Market Cap Tier 1 (Top 100)**: Priority 1 - ~40 calls
2. **Market Cap Tier 2 (101-500)**: Priority 2 - ~30 calls
3. **High-Quality Projects**: Priority 3 - ~20 calls
4. **Buffer for Re-analysis**: ~10 calls

### API Call Optimization
- Use single user lookup call per account
- Batch multiple field requests in one call
- Avoid tweet timeline calls unless critical
- Store results for monthly reuse

## Data Quality Considerations
### Red Flags for Crypto Projects
- **New Account** (< 6 months old)
- **Low Follower/Following Ratio** (< 0.1 or > 100)
- **No Profile Picture** or generic image
- **Empty Bio** or copy-paste descriptions
- **Low Engagement** relative to follower count
- **Unverified** for major projects

### Quality Indicators
- **Verified Badge** (blue checkmark)
- **Consistent Branding** (profile matches website)
- **Regular Activity** (tweets within last 30 days)
- **Community Interaction** (replies to users)
- **Professional Bio** with clear project description

## Implementation Requirements
### Python Libraries
- `requests` (already in requirements.txt)
- `python-dotenv` (already in requirements.txt)

### Environment Variables
```bash
TWITTER_BEARER_TOKEN=your_bearer_token_here
```

### Database Schema Extensions
Need to add Twitter-specific fields to `link_content_analysis` table or create `twitter_analysis` table:
- `follower_count`
- `following_count`
- `tweet_count`
- `account_age_days`
- `verified_status`
- `engagement_rate`
- `profile_completeness_score`

## API Response Example
```json
{
  "data": {
    "id": "783214",
    "name": "Bitcoin",
    "username": "bitcoin",
    "created_at": "2007-02-20T14:35:54.000Z",
    "description": "Bitcoin is a decentralized digital currency...",
    "location": "Worldwide",
    "public_metrics": {
      "followers_count": 5500000,
      "following_count": 1,
      "tweet_count": 400,
      "listed_count": 100000
    },
    "verified": true,
    "verified_type": "blue",
    "profile_image_url": "https://pbs.twimg.com/profile_images/...",
    "url": "https://bitcoin.org"
  }
}
```

## Cost Considerations
- **Free Tier**: $0/month, 100 calls
- **Basic Tier**: $100/month, 10,000 calls
- **Pro Tier**: $5,000/month, 1M calls

Given our current 100-call limit, we need to be extremely selective about which accounts to analyze. Focus on highest-value targets with clear prioritization system.

## Next Steps
1. Set up Twitter Developer account
2. Implement authentication and basic client
3. Create prioritization algorithm for account selection
4. Design analysis metrics specific to crypto projects
5. Implement batch processing with careful rate limiting