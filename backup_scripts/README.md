# Backup Scripts

This directory is for custom backup scripts that can be mounted into the `postgres_backup` Docker container.

## Usage

The backup service in `docker-compose.yml` mounts this directory as `/scripts` inside the container.

## Default Backup Behavior

The default backup service runs daily and:
- Creates SQL dumps of the entire database
- Stores them in the `../backups/` directory
- Retains backups for 7 days
- Runs automatically at midnight

## Custom Scripts

Add custom backup scripts here if you need:
- Selective table backups
- Pre/post backup hooks
- Custom retention policies
- Backup to cloud storage (S3, etc.)

## Example: Selective Backup

```bash
#!/bin/sh
# backup_tables.sh
pg_dump -h postgres -U crypto_user -d crypto_analytics \
  -t crypto_projects -t project_links \
  > /backups/selective_$(date +%Y%m%d_%H%M%S).sql
```

## Example: S3 Upload

```bash
#!/bin/sh
# upload_to_s3.sh
aws s3 cp /backups/crypto_analytics_latest.sql \
  s3://your-bucket/backups/
```
