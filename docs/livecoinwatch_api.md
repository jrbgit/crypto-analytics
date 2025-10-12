# LiveCoinWatch API Analysis

## API Overview

LiveCoinWatch provides a comprehensive cryptocurrency API with the following key features:
- 10,000 free credits per day
- Real-time price and market data
- Historical data
- Comprehensive project metadata including social links

## API Base URL
```
https://api.livecoinwatch.com
```

## Authentication
- API Key required in headers: `x-api-key: YOUR_API_KEY`

## Key Endpoints

### 1. Coins List
- **Endpoint**: `/coins/list`
- **Method**: POST
- **Credits**: Variable based on data requested
- **Purpose**: Get comprehensive list of all cryptocurrencies
- **Sample Response**: See Avalanche example in project_spec.md

### 2. Single Coin Data  
- **Endpoint**: `/coins/single`
- **Method**: POST
- **Purpose**: Get detailed data for a specific coin

### 3. Coins Map
- **Endpoint**: `/coins/map`
- **Method**: POST
- **Purpose**: Get mapping of coins (useful for initial discovery)

### 4. Historical Data
- **Endpoint**: `/coins/single/history`
- **Method**: POST
- **Purpose**: Get historical price data

## Credit Management Strategy

With 10,000 daily credits, we need to optimize our usage:

### Phase 1: Initial Data Collection
1. Get complete coins list (estimate: 500-1000 credits)
2. Focus on top 200-500 coins by market cap
3. Collect basic data first, then expand

### Phase 2: Detailed Collection
1. Get detailed data for priority coins
2. Extract and process all link URLs
3. Schedule regular updates for active projects

### Phase 3: Historical Data
1. Collect historical data for trend analysis
2. Focus on coins with significant activity

## Data Processing Priority

Based on the Avalanche example, key data points include:
- **Basic Info**: name, rank, code, age, color
- **Market Data**: rate, volume, cap, delta (price changes)
- **Supply Data**: circulatingSupply, totalSupply, maxSupply
- **Exchange Data**: exchanges, markets, pairs
- **Categories**: project classification
- **Links**: All social and official links for LLM analysis

## Rate Limiting
- Track credit usage per request
- Implement exponential backoff
- Cache responses to minimize repeat requests
- Schedule data collection during low-usage periods

## API Request Examples

### Get Top 100 Coins
```json
{
  "currency": "USD",
  "sort": "rank",
  "order": "ascending",
  "offset": 0,
  "limit": 100,
  "meta": true
}
```

### Get Specific Coin
```json
{
  "currency": "USD",
  "code": "BTC",
  "meta": true
}
```

## Error Handling
- 429: Rate limit exceeded - implement retry with backoff
- 401: Authentication failed - check API key
- 500: Server error - retry with exponential backoff

## Credit Optimization Tips
1. Use limit parameter to control response size
2. Only request meta data when needed
3. Cache responses for frequently accessed data
4. Batch requests when possible
5. Use offset for pagination instead of multiple full requests