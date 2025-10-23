# Crypto Analytics with ML and LLM Integration

A comprehensive system for collecting, processing, storing, and analyzing cryptocurrency data from multiple sources using machine learning and large language models. This project automates the collection of crypto project data, scrapes and analyzes web content, social media, and whitepapers to provide deep insights into cryptocurrency projects.

## 🚀 Features

### Data Collection
- **LiveCoinWatch Integration**: Automated collection of 52,000+ crypto projects with market data, links, and metadata
- **Multi-source Scraping**: Websites, whitepapers, Reddit, Twitter, Telegram, Medium, and YouTube
- **Rate Limiting & Error Handling**: Robust API client with retry logic and rate limit management
- **Change Tracking**: Historical tracking of all data changes with timestamp and source attribution

### Content Analysis
- **LLM-Powered Analysis**: Automated analysis using Ollama (local LLM inference)
- **Website Analysis**: Extract technology stack, use cases, competitive advantages
- **Whitepaper Analysis**: Parse and analyze project whitepapers (PDF and web formats)
- **Social Media Intelligence**: Reddit sentiment, Twitter activity, Telegram engagement
- **Medium & YouTube**: Content analysis from project blogs and video channels

### Data Infrastructure
- **PostgreSQL Database**: Production-ready with optimized schema for crypto data
- **Docker Compose Setup**: Full infrastructure including PostgreSQL, Redis, and admin tools
- **Migration System**: Alembic-based database migrations with rollback support
- **Status Tracking**: Comprehensive logging for website, whitepaper, and Reddit scraping

## 📁 Project Structure

```
crypto-analytics/
├── src/
│   ├── collectors/        # Data collection modules
│   │   ├── livecoinwatch.py    # LiveCoinWatch API client
│   │   ├── twitter_api.py      # Twitter integration
│   │   └── telegram_api.py     # Telegram channel monitoring
│   ├── scrapers/         # Web scraping modules
│   │   ├── website_scraper.py  # General website scraping
│   │   ├── whitepaper_scraper.py
│   │   ├── reddit_scraper.py
│   │   ├── medium_scraper.py
│   │   └── youtube_scraper.py
│   ├── analyzers/        # LLM analysis modules
│   │   ├── website_analyzer.py
│   │   ├── whitepaper_analyzer.py
│   │   ├── reddit_analyzer.py
│   │   ├── twitter_analyzer.py
│   │   ├── telegram_analyzer.py
│   │   ├── medium_analyzer.py
│   │   └── youtube_analyzer.py
│   ├── pipelines/        # Analysis pipelines
│   │   ├── content_analysis_pipeline.py
│   │   └── website_analysis_pipeline.py
│   ├── models/           # Database models
│   │   ├── database.py         # SQLAlchemy models
│   │   └── init_db.py          # Database initialization
│   ├── services/         # Business logic services
│   │   ├── reddit_status_logger.py
│   │   ├── website_status_logger.py
│   │   └── whitepaper_status_logger.py
│   └── utils/            # Utility modules
│       ├── error_reporter.py
│       ├── logging_config.py
│       └── url_filter.py
├── scripts/              # Utility scripts
│   ├── analysis/         # Analysis runners
│   ├── migration/        # Database migrations
│   ├── dev/              # Development tools
│   └── utils/            # Helper scripts
├── config/               # Configuration files
├── data/                 # Data storage (gitignored)
├── logs/                 # Application logs (gitignored)
├── tests/                # Unit and integration tests
├── docs/                 # Comprehensive documentation
├── migrations/           # Alembic database migrations
└── docker-compose.yml    # Docker infrastructure setup
```

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (for database)
- Ollama installed and running locally
- API Keys for:
  - LiveCoinWatch
  - Twitter API (optional)
  - Reddit API (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/jrbgit/crypto-analytics.git
cd crypto-analytics
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
# Or for development
pip install -e .[dev]
```

3. **Set up environment variables**
```bash
cp config/.env.example config/.env
# Edit config/.env with your API keys
```

4. **Start the database**
```bash
docker-compose up -d postgres
# Optional: start admin interfaces
docker-compose --profile admin up -d
```

5. **Initialize the database**
```bash
python src/models/init_db.py
```

6. **Run migrations** (if needed)
```bash
alembic upgrade head
```

### Quick Start

**Collect crypto project data:**
```bash
python src/collectors/livecoinwatch.py
```

**Run website analysis:**
```bash
python scripts/analysis/run_website_analysis.py
```

**Run comprehensive analysis:**
```bash
python scripts/analysis/run_comprehensive_analysis.py
```

**Monitor progress:**
```bash
python scripts/analysis/monitor_progress.py
```

## 🗄️ Database Schema

The system uses PostgreSQL with the following main tables:

- **crypto_projects**: Core project data (price, market cap, supply, etc.)
- **project_links**: Social media and official links with status tracking
- **project_images**: Project logos and icons
- **project_changes**: Historical change tracking
- **link_content_analysis**: LLM analysis results for websites
- **website_status_log**: Website scraping status and error tracking
- **whitepaper_status_log**: Whitepaper analysis status
- **reddit_status_log**: Reddit scraping status
- **api_usage**: API usage tracking and rate limiting

See `docs/DATABASE_MIGRATION_GUIDE.md` for detailed schema information.

## 📊 Data Sources

### Primary Data
- **LiveCoinWatch**: Market data, rankings, supply metrics, project links
- Rate limit: 10,000 requests/day
- Coverage: 52,000+ crypto projects

### Content Sources
- **Project Websites**: Technology stack, features, use cases
- **Whitepapers**: Technical specifications, tokenomics, roadmaps
- **Reddit**: Community sentiment, discussion activity
- **Twitter**: Social engagement, announcements
- **Telegram**: Community size, activity levels
- **Medium**: Project blog posts, updates
- **YouTube**: Video content, tutorials, AMAs

## 🔧 Configuration

### Environment Variables

Create a `config/.env` file with:

```env
# Database
DATABASE_URL=postgresql://crypto_user:password@localhost:5432/crypto_analytics

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2  # or your preferred model

# API Keys
LIVECOINWATCH_API_KEY=your_api_key_here

# Optional: Social Media APIs
TWITTER_API_KEY=your_twitter_key
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
```

### Docker Services

The `docker-compose.yml` includes:
- **postgres**: Main database (port 5432)
- **redis**: Caching layer (port 6379)
- **adminer**: Database admin UI (port 8080)
- **pgadmin**: PostgreSQL admin (port 5050)
- **postgres_backup**: Automated daily backups

## 🧪 Development

### Running Tests
```bash
pytest tests/
# With coverage
pytest --cov=src tests/
```

### Code Quality
```bash
# Linting
flake8 src/

# Type checking
mypy src/

# Formatting
black src/
```

### Development Scripts
```bash
python scripts/dev/lint.py      # Run all linters
python scripts/dev/check_types.py  # Type checking
python scripts/dev/setup.py     # Development setup
```

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

### Project Overview
- `CryptoAnalyticsWithML_LLM.md`: Original project concept and vision
- `project_spec.md`: Complete project specification
- `Crypto_Data_Sources.md`: Comprehensive list of crypto data sources and APIs

### Technical Documentation
- `DATABASE_MIGRATION_GUIDE.md`: Database schema and migrations
- `PERFORMANCE_ANALYSIS.md`: Performance optimization guide
- `ANALYSIS_REPORT.md`: Analysis results and findings

### API Integration Guides
- `livecoinwatch_api.md`: LiveCoinWatch API documentation
- `REDDIT_API_NOTES.md`: Reddit integration guide
- `twitter_integration_guide.md`: Twitter API setup
- `YOUTUBE_API_SETUP.md`: YouTube OAuth configuration
- `GOOGLE_DRIVE_SUPPORT.md`: Google Drive whitepaper extraction

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite and linters
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Repository**: https://github.com/jrbgit/crypto-analytics
- **Issues**: https://github.com/jrbgit/crypto-analytics/issues

## 🙏 Acknowledgments

- LiveCoinWatch for comprehensive crypto market data
- Ollama for local LLM inference capabilities
- The cryptocurrency and open-source communities
