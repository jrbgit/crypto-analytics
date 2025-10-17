# Crypto Analytics with ML and LLM Integration

A comprehensive system for collecting, processing, storing, and analyzing cryptocurrency data from multiple sources using machine learning and large language models.

## Project Overview

This system is designed to:
- Collect data from various crypto data sources (starting with LiveCoinWatch)
- Process and store data with change tracking
- Use ML and LLM to analyze data and generate insights
- Provide a web interface for report-style data visualization
- Parse and analyze project websites, whitepapers, and social media

## Architecture

```
crypto-analytics/
├── src/
│   ├── collectors/     # Data collection modules (LiveCoinWatch, etc.)
│   ├── models/         # Database models and data structures
│   ├── analyzers/      # ML and LLM analysis modules
│   └── web/           # Web interface components
├── data/              # Raw and processed data storage
├── config/            # Configuration files
├── tests/             # Unit and integration tests
└── docs/              # Project documentation
```

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables (see config/.env.example)
3. Initialize database: `python src/models/init_db.py`
4. Start data collection: `python src/collectors/livecoinwatch.py`

## Data Sources

### Phase 1: LiveCoinWatch
- 10,000 API credits per day
- Comprehensive crypto project data including links and metadata
- Real-time price and market data

### Future Phases
- CoinGecko, CoinMarketCap
- On-chain data providers
- Social media and sentiment data
- DEX and DeFi protocols

## Features

- **Modular Data Collection**: Easily extensible to new data sources
- **Change Tracking**: Historical tracking of all data changes
- **LLM Integration**: Automated analysis of project websites and whitepapers  
- **ML Analytics**: Pattern detection and trend analysis
- **Web Dashboard**: Interactive reporting interface

## License

MIT License