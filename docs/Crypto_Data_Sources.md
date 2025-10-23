
# Crypto & Blockchain Data Sources

This document lists possible data sources for crypto / blockchain analytics, grouped by type, with API types, data offered, use-cases, and short notes on cost/access.

## Scope assumptions

- Include market data, exchange data, on-chain data, indexers, NFTs, derivatives, social sentiment, AML/compliance, and archival datasets.
- Focus on major chains (Ethereum, Bitcoin, Solana, BSC, Polygon, Avalanche, Tron, Cosmos, Near) but include cross-chain sources.

---

## 1) Market data & aggregators (price, market cap, historical OHLC, tick data)

- CoinGecko — REST (free tier), token metadata, OHLC, market cap, exchange tickers, contract-level lookup.
- CoinMarketCap — REST (API keys, free tier), market data, listings, metrics.
- LiveCoinWatch — REST (API), price and market metrics.
- Messari — REST (paid tiers), deep metadata, on-chain metrics.
- Nomics — REST (paid), normalized market data and exchange tickers.
- Kaiko — REST/Websocket (paid), high-fidelity tick data.
- CryptoCompare — REST/Websocket (paid tiers), market data, social metrics.
- IntoTheBlock — REST (paid), ML-derived token indicators.
- CoinAPI — tick-level trade & normalized market data (paid).

Use-cases: price feeds, historical backtesting, arbitrage detection, VWAP, correlation analysis.

---

## 2) Centralized Exchanges (CEX)

- Binance — REST & Websocket (spot, futures, margin), Kline/candles, depth, trades, account endpoints.
- Coinbase Pro — REST & Websocket; trades, orderbook, fills.
- Kraken — REST & Websocket.
- Bitstamp, Huobi, OKX, Bybit, Deribit.

Use-cases: real-time orderbook monitoring, trade execution, funding/future spreads.

---

## 3) Derivatives & Options data

- Deribit — REST & Websocket for options and perpetuals.
- CME Crypto Futures via data vendors.
- Skew / other analytics vendors.

Use-cases: implied volatility surface, options greeks, hedging strategies.

---

## 4) On-chain data providers / node-access

- Infura — Ethereum RPC (HTTPS/Websocket), IPFS gateway.
- Alchemy — RPC + enhanced APIs (webhooks, NFT APIs).
- QuickNode — multi-chain RPC endpoints.
- Ankr, Blockdaemon, Chainstack, GetBlock — managed nodes.
- Self-hosted: Geth, Erigon, Bitcoin Core.

Use-cases: raw transactions, logs, state queries, contract calls.

---

## 5) Blockchain indexers & analytical query layers

- The Graph — GraphQL subgraphs for protocol events.
- Covalent — unified REST API (balances, txs, token holders).
- Bitquery — GraphQL/REST for cross-chain blockchain data.
- Amberdata — on-chain + market data.
- Etherscan / BscScan family — explorer APIs.
- Dune Analytics — SQL queries over indexed data.
- Flipside Crypto — free SQL analytics and datasets.
- Nansen — wallet labeling, flows (paid).
- Arkham / Chainalysis — intelligence (paid).

Use-cases: token flows, holders, DEX volumes, wallet labeling.

---

## 6) DeFi & protocol datasets

- DeFiLlama — TVL dataset (open-source).
- CoinMetrics — network & market fundamentals.
- Token Terminal — protocol revenue metrics.
- Zapper / Zerion / DeBank — portfolio & DeFi position APIs.

Use-cases: TVL trends, protocol revenue, wallet positions.

---

## 7) NFT marketplaces and metadata

- OpenSea — REST & events (rate-limited).
- Blur, Rarible, LooksRare, MagicEden — marketplace APIs.
- IPFS / Arweave — metadata/media storage.
- NFTPort — unified NFT API.
- Alchemy NFT API, Moralis NFT API.

Use-cases: floor prices, mint tracking, ownership history.

---

## 8) Oracles & price feeds

- Chainlink — on-chain price feeds.
- Band Protocol, Tellor, API3.
- On-chain TWAPs (Uniswap v3, oracles).

Use-cases: on-chain price references, DeFi safety checks.

---

## 9) Real-time streaming & websockets

- Exchange websockets (Binance, Coinbase, Kraken).
- Node web sockets (newHeads, logs).
- Alchemy/Infura websockets and notify APIs.
- Webhook providers: Alchemy Notify, QuickNode Notify.
- High-throughput: Kafka / RabbitMQ via partners.

Use-cases: real-time alerts, trading bots, arbitrage, liquidations.

---

## 10) BigQuery / public cloud datasets & data dumps

- Google BigQuery public datasets: Ethereum, Bitcoin, Polygon, BSC.
- AWS open data / S3 and Parquet exports (various providers).
- Kaggle curated datasets.
- Etherscan / Blockchair CSV exports.

Use-cases: batch analytics, ML training, backtesting.

---

## 11) Social, sentiment & web data

- X/Twitter API — tweets and mentions.
- Reddit API — subreddit posts and comments.
- Telegram / Discord scrapers (respect ToS).
- Google Trends.
- Santiment, LunarCrush — social metrics (paid).
- GitHub API — repo activity.
- News APIs: CryptoPanic, NewsAPI, GDELT.

Use-cases: sentiment, narrative detection, event-driven signals.

---

## 12) Custodial, compliance, intelligence

- Chainalysis, Elliptic, TRM Labs, CipherTrace — wallet risk scoring, tracing.
- Arkham — wallet intelligence.

Use-cases: sanctions screening, AML, forensic tracing.

---

## 13) Payments & fiat rails

- Transak, MoonPay, Wyre — fiat onramps/offramps APIs.
- Bank APIs / payment processors for fiat flow correlation.

Use-cases: linking fiat flows to on-chain inflows, AML.

---

## 14) Wallet, portfolio & MEV

- Zapper, DeBank, Zerion — portfolio APIs.
- Flashbots — MEV bundles and relay data.
- Blocknative — mempool notifications.

Use-cases: wallet analytics, MEV and mempool monitoring.

---

## 15) Governance & DAO

- Snapshot — off-chain governance APIs.
- Tally, Boardroom — governance data.

Use-cases: voting analytics, governance participation.

---

## 16) Misc & developer tooling

- Web3 libraries: ethers.js, web3.py, web3.js, Alchemy SDK, Moralis SDK.
- IPFS gateways, Arweave gateways.

---

## 17) Suggested starter shortlist

- CoinGecko (market data)
- Binance REST & WS (liquidity)
- Alchemy or Infura (Ethereum RPC)
- The Graph (subgraphs)
- Google BigQuery public datasets (historical)
- Etherscan APIs (explorer data)
- DeFiLlama (TVL)
- Glassnode / CoinMetrics (on-chain fundamentals; paid)

---

## Integration notes

- Track API type (REST/WS/GraphQL/RPC/BigQuery) and rate limits.
- Normalize symbols and token addresses (use contract addresses for EVM tokens).
- Consider caching and backfilling for historical data.
- Validate licensing and commercial terms before redistribution.

---

## Next steps

- Produce CSV/JSON export of this inventory.
- Create connector templates for top 6 sources (Python): CoinGecko, Binance WS, Alchemy, The Graph, BigQuery, Etherscan.
- Prioritize sources by features required (real-time vs historical vs on-chain enrichment).

Prepared on October 12, 2025.
