# Twitter Integration Guide

## Overview

This guide provides comprehensive documentation for the Twitter integration in the Crypto Analytics project, including API limitations, prioritization strategies, and implementation details.

## Table of Contents

- [API Overview & Limitations](#api-overview--limitations)
- [Setup & Authentication](#setup--authentication)
- [Prioritization Strategy](#prioritization-strategy)
- [Usage Guide](#usage-guide)
- [Analysis Metrics](#analysis-metrics)
- [Database Integration](#database-integration)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Best Practices](#best-practices)

## API Overview & Limitations

### Twitter API v2 Free Tier

- **Monthly Limit**: 100 tweet retrievals + 500 writes per month
- **Rate Limiting**: 100 requests per 24-hour period (managed by our system)
- **Data Access**: User profiles, public metrics, basic tweet data
- **Cost**: Free (with strict limitations)

### Upgrade Options

- **Basic ($100/month)**: 10,000 tweets per month
- **Pro ($5,000/month)**: 1M tweets per month

### Key Constraints

⚠️ **Critical**: Our implementation is designed for the FREE tier - every API call counts!

- Only 100 calls per month = ~3 calls per day
- No real-time data streaming
- Limited to public account data
- Cannot access tweet content in detail due to quota constraints

## Setup & Authentication

### 1. Twitter Developer Account Setup

1. Visit [developer.twitter.com](https://developer.twitter.com)
2. Apply for developer access
3. Create a new App in the Developer Portal
4. Generate Bearer Token (API v2)

### 2. Environment Configuration

Add to your `.env` file:

```bash
# Twitter API Configuration
TWITTER_BEARER_TOKEN=your_bearer_token_here
```

### 3. Installation

All required dependencies are already included in `requirements.txt`:
- `requests` (HTTP client)
- `python-dotenv` (environment management)

## Prioritization Strategy

### Why Prioritization is Critical

With only 100 API calls per month, we must carefully select which Twitter accounts to analyze for maximum value.

### 4-Tier Priority System

#### Tier 1 (40 calls): Top Market Cap Projects
- Projects with $1B+ market cap
- Top 100 ranked cryptocurrencies
- **Rationale**: Highest impact, most user interest

#### Tier 2 (25 calls): High-Quality Mid-Tier Projects
- Projects with excellent website analysis scores (7.0+/10)
- Ranks 101-500 with good fundamentals
- **Rationale**: Hidden gems, promising projects

#### Tier 3 (20 calls): Emerging Projects
- Smaller projects with decent overall scores (5.0+/10)
- **Rationale**: Early identification of rising stars

#### Tier 4 (15 calls): Buffer & Re-analysis
- Reserved for re-analyzing changed accounts
- New high-priority projects
- **Rationale**: Flexibility and updates

### Automated Prioritization

Run the prioritization script to generate target lists:

```bash
python scripts/analysis/twitter_prioritization_strategy.py
```

This creates a prioritized JSON file with exactly 100 accounts to analyze per month.

## Usage Guide

### Single Account Analysis

```python
from src.analyzers.twitter_analyzer import TwitterContentAnalyzer
from src.models.database import DatabaseManager

# Initialize
db_manager = DatabaseManager(database_url)
analyzer = TwitterContentAnalyzer(db_manager)

# Analyze single account
success = analyzer.analyze_and_store(
    link_id=123,
    twitter_url="https://twitter.com/bitcoin",
    project_name="Bitcoin"
)
```

### Batch Analysis (Recommended)

```bash
# Analyze up to 10 accounts in batch
python src/analyzers/twitter_analyzer.py batch 10
```

Or programmatically:

```python
from src.analyzers.twitter_analyzer import analyze_twitter_link_batch

results = analyze_twitter_link_batch(database_url, limit=10)
print(f"Analyzed: {results['analyzed']}, Failed: {results['failed']}")
```

### Check API Usage

```python
analyzer = TwitterContentAnalyzer(db_manager)
stats = analyzer.get_usage_stats()

print(f"Monthly usage: {stats['monthly_usage']}/{stats['monthly_limit']}")
print(f"Remaining: {stats['monthly_remaining']} calls")
```

### Progress Monitoring

```bash
python scripts/analysis/monitor_progress.py
```

This shows Twitter-specific metrics including API quota usage.

## Analysis Metrics

### 5-Category Scoring System (0-10 each)

#### 1. Authenticity Score (30% weight)
- **Purpose**: Detect fake or suspicious accounts
- **Factors**:
  - Account age (6+ months preferred)
  - Verification status
  - Follower/following ratios
  - Profile completeness

#### 2. Professional Score (25% weight)
- **Purpose**: Assess professional appearance
- **Factors**:
  - Complete profile (bio, website, image)
  - Bio quality and length
  - Professional username patterns
  - Website link presence

#### 3. Community Score (20% weight)
- **Purpose**: Measure community building success
- **Factors**:
  - Follower count (1K+ for credibility)
  - Listed count (community value indicator)
  - Healthy follower/following ratio

#### 4. Activity Score (15% weight)
- **Purpose**: Evaluate account activity patterns
- **Factors**:
  - Tweet count vs account age
  - Posting frequency (0.5-3 tweets/day optimal)
  - Consistent activity over time

#### 5. Engagement Quality Score (10% weight)
- **Purpose**: Assess genuine vs artificial engagement
- **Factors**:
  - Listed/follower ratio (1% excellent)
  - Balanced following approach
  - Reasonable activity levels

### Health Status Classification

- **Excellent (8.5+/10)**: High-quality, trusted accounts
- **Good (7.0-8.4/10)**: Solid accounts with minor issues
- **Average (5.0-6.9/10)**: Decent but some concerns
- **Poor (3.0-4.9/10)**: Multiple red flags present
- **Suspicious (<3.0/10)**: Likely fake or scam accounts

### Red Flags Detection

Automatically identifies concerning patterns:
- Very new accounts (< 90 days)
- Suspicious follower patterns
- No profile completeness
- Financial advice language in bio
- Excessive posting frequency
- Protected accounts (unusual for crypto projects)

### Positive Indicators

Recognizes quality signals:
- Verification badges (legacy or blue)
- Mature accounts (1+ years)
- Large, engaged communities
- Professional profiles with websites
- Consistent, balanced posting

## Database Integration

### Data Storage

Twitter analysis results are stored in the existing `link_content_analysis` table with creative field mapping:

- **Raw Data**: Complete analysis stored as JSON in `raw_content`
- **Scores**: 
  - `technical_depth_score` → Authenticity Score
  - `content_quality_score` → Professional Score
  - `confidence_score` → Analysis Confidence
- **Metadata**: 
  - `development_stage` → Health Status
  - `red_flags` → Identified concerns
  - `core_features` → Positive indicators

### Query Examples

```sql
-- Get Twitter analyses with scores
SELECT 
    cp.name,
    lca.technical_depth_score as authenticity,
    lca.content_quality_score as professional,
    lca.development_stage as health_status,
    lca.confidence_score
FROM link_content_analysis lca
JOIN project_links pl ON lca.link_id = pl.id
JOIN crypto_projects cp ON pl.project_id = cp.id
WHERE pl.link_type = 'twitter'
ORDER BY lca.technical_depth_score DESC;

-- Find high-quality Twitter accounts
SELECT cp.name, pl.url
FROM link_content_analysis lca
JOIN project_links pl ON lca.link_id = pl.id  
JOIN crypto_projects cp ON pl.project_id = cp.id
WHERE pl.link_type = 'twitter'
    AND lca.technical_depth_score >= 8.0
    AND lca.content_quality_score >= 8.0;
```

## Monitoring & Troubleshooting

### Progress Monitoring

The enhanced progress monitor provides Twitter-specific insights:

```bash
python scripts/analysis/monitor_progress.py
```

**Twitter Section Includes**:
- Analysis completion progress
- API usage tracking (calls used/remaining)
- Average quality scores
- High-priority accounts analyzed
- Usage recommendations

### Common Issues & Solutions

#### "No API calls remaining"
- **Cause**: Monthly quota exhausted
- **Solution**: Wait for monthly reset or upgrade plan
- **Prevention**: Monitor usage with progress monitor

#### "Rate limit exceeded" 
- **Cause**: Daily allocation exceeded (4 calls/day)
- **Solution**: Wait 24 hours or run analysis spread over time
- **Prevention**: Use batch analysis with proper spacing

#### "Authentication failed"
- **Cause**: Invalid or missing bearer token
- **Solution**: Check TWITTER_BEARER_TOKEN in .env file
- **Verification**: Re-generate token in Twitter Developer Portal

#### Low analysis confidence scores
- **Cause**: Incomplete profile data or API limitations
- **Solution**: Normal for free tier limitations
- **Action**: Focus on accounts with higher data completeness

### Testing Integration

Run comprehensive tests:

```bash
python scripts/analysis/test_twitter_integration.py
```

Tests include:
- Prerequisites validation
- API client functionality  
- Analysis metrics accuracy
- Real account analysis (quota-conscious)

## Best Practices

### API Quota Management

#### DO:
- ✅ Run batch analysis monthly, not daily
- ✅ Use prioritization strategy to maximize value
- ✅ Monitor usage with progress monitor
- ✅ Test with small batches first
- ✅ Keep 10-15 calls as buffer for urgent analyses

#### DON'T:
- ❌ Run analysis on low-value accounts
- ❌ Waste calls on testing in production
- ❌ Ignore rate limiting warnings
- ❌ Analyze accounts already processed
- ❌ Run without checking available quota

### Analysis Strategy

#### Monthly Workflow:
1. **Week 1**: Generate prioritization list
2. **Week 2**: Run batch analysis (40-50 calls)
3. **Week 3**: Analyze remaining tier 1 & 2 (30-40 calls)  
4. **Week 4**: Complete tier 3 & 4, save buffer (20-30 calls)

#### Quality Focus:
- Prioritize market cap and fundamentals over quantity
- Focus on accounts likely to provide valuable signals
- Re-analyze accounts only when significant changes expected
- Use website analysis scores to guide Twitter prioritization

### Production Deployment

#### Pre-deployment Checklist:
- [ ] Twitter Developer Account approved
- [ ] Bearer Token generated and tested
- [ ] Environment variables configured
- [ ] Database tables exist and accessible
- [ ] Test suite passes completely
- [ ] Prioritization list generated
- [ ] Monitoring setup validated

#### Deployment Steps:
1. Set up environment variables
2. Run integration tests
3. Generate initial prioritization list
4. Start with small batch (5-10 accounts)
5. Monitor results and API usage
6. Scale to full monthly allocation

#### Monitoring in Production:
- Daily: Check API quota usage
- Weekly: Review analysis quality metrics
- Monthly: Generate new prioritization list
- Monthly: Assess ROI and adjust strategy

### Performance Optimization

#### API Efficiency:
- Use single API call per account (profile lookup only)
- Batch database operations
- Implement proper error handling and retries
- Cache results to avoid re-analysis

#### Database Optimization:
- Index on link_type for fast Twitter queries
- Regular cleanup of old analysis data
- Monitor query performance
- Use appropriate data types for JSON storage

## Support & Updates

### Getting Help

1. **Check Logs**: Review detailed logging output
2. **Run Tests**: Use integration test suite for diagnosis  
3. **Monitor API**: Check quota and rate limiting status
4. **Review Documentation**: This guide and API research docs

### Future Enhancements

When upgrading to paid tiers:
- **Basic Tier ($100/month)**: 10,000 calls enables analysis of all major projects
- **Pro Tier ($5,000/month)**: 1M calls enables comprehensive analysis with tweet content
- **Enhanced Metrics**: Add tweet sentiment analysis, engagement patterns
- **Real-time Updates**: Monitor account changes and anomalies
- **Advanced Prioritization**: Dynamic prioritization based on market conditions

### Version History

- **v1.0**: Initial implementation with free tier support
- **API**: Twitter API v2 with Bearer Token authentication
- **Features**: Complete analysis pipeline with 5-category scoring
- **Database**: Integrated with existing schema
- **Monitoring**: Enhanced progress tracking with Twitter insights

---

## Quick Reference

### Key Files
- **API Client**: `src/collectors/twitter_api.py`
- **Analysis Metrics**: `src/analyzers/twitter_analysis_metrics.py`
- **Main Analyzer**: `src/analyzers/twitter_analyzer.py`  
- **Prioritization**: `scripts/analysis/twitter_prioritization_strategy.py`
- **Testing**: `scripts/analysis/test_twitter_integration.py`
- **Monitoring**: `scripts/analysis/monitor_progress.py`

### Key Commands
```bash
# Generate priority list
python scripts/analysis/twitter_prioritization_strategy.py

# Run batch analysis  
python src/analyzers/twitter_analyzer.py batch 10

# Check progress
python scripts/analysis/monitor_progress.py

# Run tests
python scripts/analysis/test_twitter_integration.py
```

### Environment Variables
```bash
TWITTER_BEARER_TOKEN=your_bearer_token_here
DATABASE_URL=your_database_url_here
```

For detailed technical information, see the API research documentation: `docs/twitter_api_research.md`