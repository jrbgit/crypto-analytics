# Docker Infrastructure Setup

This document describes the Docker infrastructure for the crypto analytics project.

## Services

### Core Services (Always Running)

#### PostgreSQL (Port 5432)
- **Image**: `postgres:16-alpine`
- **Container**: `crypto_analytics_db`
- **Database**: `crypto_analytics`
- **User**: `crypto_user`
- **Optimizations**: Configured for analytical workloads with parallel queries

**Performance Tuning:**
- `max_connections=300` - Supports high concurrent loads
- `shared_buffers=512MB` - Doubled memory cache for better performance
- `effective_cache_size=2GB` - Increased for query optimization
- `work_mem=16MB` - Doubled per-query memory for complex operations
- `maintenance_work_mem=256MB` - Faster index creation and maintenance
- `wal_buffers=32MB` - Improved write-ahead log performance
- `max_parallel_workers=12` - More parallel query execution
- `max_parallel_workers_per_gather=6` - More parallel workers per query
- `max_parallel_maintenance_workers=4` - Parallel index builds
- `log_statement=ddl` - Only log schema changes (reduced logging overhead)

#### Redis (Port 6379)
- **Image**: `redis:7-alpine`
- **Container**: `crypto_analytics_cache`
- **Config**: `config/redis.conf`
- **Max Memory**: 512MB with LRU eviction
- **Persistence**: AOF enabled for durability

**Configuration Highlights:**
- Memory limit with automatic eviction
- Append-only file for data durability
- Optimized for read-heavy workloads
- Dangerous commands disabled for security

### Admin Services (Profile: `admin`)

Start with: `docker-compose --profile admin up -d`

#### Adminer (Port 8080)
- **Image**: `adminer:4.8.1`
- **Container**: `crypto_analytics_admin`
- Lightweight database admin interface
- Auto-connects to PostgreSQL

#### pgAdmin (Port 5050)
- **Image**: `dpage/pgadmin4:latest`
- **Container**: `crypto_analytics_pgadmin`
- Full-featured PostgreSQL management
- Pre-configured with server connection (see `config/pgadmin_servers.json`)

**Default Credentials:**
- Email: `admin@example.com` (override with `PGADMIN_EMAIL`)
- Password: `admin_secure_password_2024` (override with `PGADMIN_PASSWORD`)

### Backup Service (Profile: `backup`)

Start with: `docker-compose --profile backup up -d`

#### postgres_backup
- **Container**: `crypto_analytics_backup`
- **Schedule**: Daily at midnight
- **Retention**: 7 days
- **Location**: `./backups/` directory
- **Format**: SQL dumps with timestamp

**Backup Files:**
```
backups/
├── crypto_analytics_20251023_000000.sql
├── crypto_analytics_20251024_000000.sql
└── ...
```

## Configuration Files

### Redis Configuration
**Location**: `config/redis.conf`

Key settings:
- Memory limit: 512MB
- Eviction policy: LRU (Least Recently Used)
- Persistence: AOF + RDB snapshots
- Security: Dangerous commands disabled

### pgAdmin Server Configuration
**Location**: `config/pgadmin_servers.json`

Pre-configures connection to the PostgreSQL container.

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DB_PASSWORD=your_secure_password

# pgAdmin
PGADMIN_EMAIL=your-email@example.com
PGADMIN_PASSWORD=your_admin_password

# Redis (optional)
REDIS_PASSWORD=your_redis_password
```

## Docker Commands

### Start Core Services
```bash
docker-compose up -d
```

### Start with Admin Tools
```bash
docker-compose --profile admin up -d
```

### Start with Backup Service
```bash
docker-compose --profile backup up -d
```

### Start Everything
```bash
docker-compose --profile admin --profile backup up -d
```

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove Volumes (⚠️ Deletes All Data)
```bash
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Check Service Health
```bash
docker-compose ps
```

## Data Persistence

All data is stored in named Docker volumes:

- `postgres_data` - PostgreSQL database files
- `redis_data` - Redis persistence files
- `pgadmin_data` - pgAdmin configuration

These volumes persist even when containers are stopped or removed.

## Backup and Restore

### Manual Backup
```bash
docker exec crypto_analytics_db pg_dump -U crypto_user crypto_analytics > backup.sql
```

### Restore from Backup
```bash
docker exec -i crypto_analytics_db psql -U crypto_user crypto_analytics < backup.sql
```

### Access Automated Backups
```bash
ls backups/
```

## Network

All services run on a custom network: `crypto_analytics_network`

Services can communicate using container names:
- `postgres` - PostgreSQL database
- `redis` - Redis cache
- `adminer` - Admin interface
- `pgadmin` - Admin interface

## Troubleshooting

### PostgreSQL won't start
```bash
# Check logs
docker-compose logs postgres

# Common issues:
# - Port 5432 already in use
# - Insufficient memory
# - Corrupted data volume (requires volume reset)
```

### Redis connection issues
```bash
# Test connection
docker exec crypto_analytics_cache redis-cli ping
# Should return: PONG
```

### Cannot access admin interfaces
```bash
# Check if services are running
docker-compose ps

# Restart admin services
docker-compose --profile admin restart
```

### Backup service not creating backups
```bash
# Check logs
docker-compose logs postgres_backup

# Verify directory permissions
ls -la backups/
```

## Security Recommendations

1. **Change default passwords** in `.env` file
2. **Enable Redis authentication** (uncomment `requirepass` in `config/redis.conf`)
3. **Restrict network access** - Don't expose ports to public internet
4. **Use SSL/TLS** for production deployments
5. **Regular backups** - Enable the backup service profile
6. **Monitor logs** - Check for suspicious activity

## Resource Usage

### Resource Limits Summary

| Service | CPU Limit | CPU Reserved | Memory Limit | Memory Reserved |
|---------|-----------|--------------|--------------|------------------|
| PostgreSQL | 4 cores | 2 cores | 4GB | 2GB |
| Redis | 1 core | 0.5 cores | 1GB | 512MB |
| Adminer | 0.5 cores | 0.25 cores | 512MB | 256MB |
| pgAdmin | 1 core | 0.25 cores | 1GB | 256MB |
| Backup | 2 cores | 0.5 cores | 2GB | 512MB |

### System Requirements

**Minimum (Core services only):**
- **CPU**: 4 cores
- **RAM**: 6GB
- **Storage**: 20GB

**Recommended (All services):**
- **CPU**: 8+ cores
- **RAM**: 10GB+
- **Storage**: 50GB+

**Production:**
- **CPU**: 12+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ (SSD recommended)

## Future Enhancements

### PostgreSQL Read Replica (Commented Out)
- Uncomment `postgres_replica` service in `docker-compose.yml`
- Configure streaming replication
- Use for read-heavy analytics queries

### Monitoring Stack
Consider adding:
- Prometheus for metrics
- Grafana for dashboards
- AlertManager for notifications

### Production Deployment
For production:
- Add resource limits to all services
- Implement SSL/TLS
- Use managed database services
- Set up automated off-site backups
- Configure log aggregation
