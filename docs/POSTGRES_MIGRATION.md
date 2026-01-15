# PostgreSQL Migration Guide

This guide explains how to migrate the Server Scanner Dashboard from file-based storage (PVC) to PostgreSQL.

## Overview

The application now supports two storage backends for maintenance data:

1. **File-based storage** (legacy): JSON files on a PersistentVolumeClaim
2. **PostgreSQL** (recommended): PostgreSQL database with connection pooling

## Benefits of PostgreSQL

- **Reliability**: ACID transactions, automatic crash recovery
- **Scalability**: Connection pooling, better performance under load
- **Queries**: SQL queries for analytics and reporting
- **Backups**: Standard database backup tools
- **Multi-pod**: Multiple application pods can share the same database

## Architecture Changes

### Before (File-based)
```
┌─────────────────────┐
│   Application Pod   │
│                     │
│  maintenance.json   │◄──── PVC (ReadWriteMany)
└─────────────────────┘
```

### After (PostgreSQL)
```
┌─────────────────────┐         ┌──────────────────┐
│   Application Pod   │────────►│   PostgreSQL     │
│                     │         │   StatefulSet    │
│  (asyncpg client)   │         │                  │
└─────────────────────┘         │  PVC (RWO)       │
                                └──────────────────┘
```

## Deployment Steps

### 1. Update Helm Values

Edit `deploy/helm/server-scanner-dashboard/values.yaml`:

```yaml
# Disable old file-based storage
persistence:
  enabled: false

# Enable PostgreSQL
postgres:
  enabled: true
  auth:
    username: scanner
    password: "YOUR_SECURE_PASSWORD"  # CHANGE THIS!
    database: server_scanner
  persistence:
    enabled: true
    size: 5Gi

# Update config to use PostgreSQL
config:
  storageBackend: "postgres"
```

### 2. Deploy PostgreSQL

Deploy the updated Helm chart:

```bash
# Update Helm chart
helm upgrade server-scanner-dashboard ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner \
  --set postgres.auth.password=YOUR_SECURE_PASSWORD

# Verify PostgreSQL pod is running
kubectl get pods -n server-scanner -l app.kubernetes.io/component=database

# Check PostgreSQL logs
kubectl logs -n server-scanner -l app.kubernetes.io/component=database
```

### 3. Verify Database Initialization

The application automatically creates the schema on startup. Verify:

```bash
# Get PostgreSQL pod name
PGPOD=$(kubectl get pods -n server-scanner -l app.kubernetes.io/component=database -o jsonpath='{.items[0].metadata.name}')

# Connect to database
kubectl exec -it $PGPOD -n server-scanner -- psql -U scanner -d server_scanner

# Check table exists
\dt

# Check table structure
\d server_maintenance

# Exit psql
\q
```

Expected table structure:
```sql
                                  Table "public.server_maintenance"
   Column    |           Type           | Collation | Nullable |      Default
-------------+--------------------------+-----------+----------+-------------------
 server_name | character varying(255)   |           | not null |
 reason      | text                     |           | not null |
 severity    | character varying(20)    |           | not null |
 timestamp   | timestamp with time zone |           | not null |
 created_by  | character varying(255)   |           |          |
 updated_at  | timestamp with time zone |           |          | CURRENT_TIMESTAMP
Indexes:
    "server_maintenance_pkey" PRIMARY KEY, btree (server_name)
    "idx_server_maintenance_severity" btree (severity)
    "idx_server_maintenance_timestamp" btree ("timestamp")
```

### 4. Migrate Existing Data

If you have existing maintenance data in JSON files, migrate it:

#### Option A: Migrate from local JSON file

```bash
# Set PostgreSQL credentials
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=server_scanner
export POSTGRES_USER=scanner
export POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Port-forward to PostgreSQL
kubectl port-forward -n server-scanner svc/server-scanner-dashboard-postgres 5432:5432 &

# Run migration
python scripts/migrate-json-to-postgres.py --json-file /path/to/maintenance.json

# Stop port-forward
kill %1
```

#### Option B: Migrate from Kubernetes PVC

```bash
# Set PostgreSQL credentials
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=server_scanner
export POSTGRES_USER=scanner
export POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Port-forward to PostgreSQL
kubectl port-forward -n server-scanner svc/server-scanner-dashboard-postgres 5432:5432 &

# Run migration from Kubernetes
python scripts/migrate-json-to-postgres.py \
  --from-k8s \
  --namespace server-scanner \
  --pvc-name scanner-data-pvc

# Stop port-forward
kill %1
```

#### Dry Run

Test migration without making changes:

```bash
python scripts/migrate-json-to-postgres.py \
  --json-file maintenance.json \
  --dry-run
```

### 5. Verify Migration

```bash
# Check record count
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c "SELECT COUNT(*) FROM server_maintenance;"

# View all records
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c "SELECT * FROM server_maintenance;"

# Check severity distribution
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c "SELECT severity, COUNT(*) FROM server_maintenance GROUP BY severity;"
```

### 6. Update Application

Redeploy application with PostgreSQL enabled:

```bash
# If not already done, update deployment
kubectl rollout restart deployment/server-scanner-dashboard -n server-scanner

# Check application logs
kubectl logs -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard --tail=50

# Verify it's using PostgreSQL
kubectl logs -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard | grep "PostgreSQL"
```

Expected log output:
```
INFO - Initializing PostgreSQL maintenance storage
INFO - PostgreSQL connection pool created (min=1, max=10)
INFO - Database schema verified
```

### 7. Test Functionality

```bash
# Get application URL
ROUTE=$(kubectl get route server-scanner-dashboard -n server-scanner -o jsonpath='{.spec.host}')

# Test maintenance API
curl -X PUT https://$ROUTE/api/servers/test-server/maintenance \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Testing PostgreSQL migration",
    "severity": "low",
    "timestamp": "'$(date -Iseconds)'",
    "created_by": "migration-test"
  }'

# Verify in database
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c "SELECT * FROM server_maintenance WHERE server_name = 'test-server';"

# Clean up test
curl -X DELETE https://$ROUTE/api/servers/test-server/maintenance
```

## Rollback Plan

If you need to rollback to file-based storage:

### 1. Export data from PostgreSQL

```bash
# Export to JSON
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -t -c \
  "SELECT json_object_agg(server_name, json_build_object('reason', reason, 'severity', severity, 'timestamp', timestamp, 'created_by', created_by)) FROM server_maintenance;" \
  > maintenance_backup.json
```

### 2. Update Helm values

```yaml
# Disable PostgreSQL
postgres:
  enabled: false

# Enable file-based storage
persistence:
  enabled: true

# Update config
config:
  storageBackend: "file"
```

### 3. Redeploy

```bash
helm upgrade server-scanner-dashboard ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner

# Copy backup to PVC
kubectl cp maintenance_backup.json server-scanner/POD_NAME:/app/data/maintenance.json
```

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `STORAGE_BACKEND` | Storage backend (`file` or `postgres`) | `postgres` |
| `POSTGRES_HOST` | PostgreSQL host | `server-scanner-dashboard-postgres` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `server_scanner` |
| `POSTGRES_USER` | Database user | (from secret) |
| `POSTGRES_PASSWORD` | Database password | (from secret) |
| `POSTGRES_MIN_POOL_SIZE` | Min connection pool size | `1` |
| `POSTGRES_MAX_POOL_SIZE` | Max connection pool size | `10` |

### Helm Values

```yaml
postgres:
  enabled: true                    # Enable PostgreSQL deployment
  image:
    repository: postgres
    tag: "15-alpine"
    pullPolicy: IfNotPresent
  auth:
    username: scanner              # Database user
    password: ""                   # REQUIRED: Set in production
    database: server_scanner       # Database name
  persistence:
    enabled: true                  # Enable persistent storage
    storageClass: ""               # Storage class (default if empty)
    accessMode: ReadWriteOnce      # Access mode for StatefulSet
    size: 5Gi                      # Volume size
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi
  initScript: true                 # Enable schema initialization
```

## Troubleshooting

### PostgreSQL pod not starting

```bash
# Check pod status
kubectl describe pod -n server-scanner -l app.kubernetes.io/component=database

# Check logs
kubectl logs -n server-scanner -l app.kubernetes.io/component=database

# Common issues:
# - PVC not bound: Check storage class availability
# - Password not set: Update values.yaml with postgres.auth.password
# - Resource limits: Check node resources
```

### Application can't connect to PostgreSQL

```bash
# Check service
kubectl get svc -n server-scanner | grep postgres

# Check connectivity from app pod
kubectl exec -it POD_NAME -n server-scanner -- \
  nc -zv server-scanner-dashboard-postgres 5432

# Check credentials in secret
kubectl get secret server-scanner-dashboard-postgres -n server-scanner -o yaml

# Check application logs
kubectl logs -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard | grep -i postgres
```

### Migration script fails

```bash
# Verify credentials
export POSTGRES_PASSWORD=YOUR_PASSWORD
psql -h localhost -p 5432 -U scanner -d server_scanner -c "\dt"

# Check JSON file format
python -m json.tool maintenance.json

# Run with verbose logging
python scripts/migrate-json-to-postgres.py --json-file maintenance.json --verbose
```

## Performance Tuning

### Connection Pool Settings

For high-traffic deployments, adjust connection pool size:

```python
# In src/config.py
POSTGRES_MIN_POOL_SIZE = int(os.getenv("POSTGRES_MIN_POOL_SIZE", "5"))
POSTGRES_MAX_POOL_SIZE = int(os.getenv("POSTGRES_MAX_POOL_SIZE", "20"))
```

```yaml
# In deployment
env:
  - name: POSTGRES_MIN_POOL_SIZE
    value: "5"
  - name: POSTGRES_MAX_POOL_SIZE
    value: "20"
```

### Database Indexing

The schema includes indexes on `severity` and `timestamp` for faster queries. Monitor query performance:

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'server_maintenance';

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM server_maintenance WHERE severity = 'critical';
```

## Backup and Recovery

### Backup

```bash
# Dump database
kubectl exec -it $PGPOD -n server-scanner -- \
  pg_dump -U scanner server_scanner > backup_$(date +%Y%m%d).sql

# Backup to PVC (recommended)
kubectl exec -it $PGPOD -n server-scanner -- \
  pg_dump -U scanner server_scanner -f /var/lib/postgresql/data/backup_$(date +%Y%m%d).sql
```

### Restore

```bash
# From local file
cat backup.sql | kubectl exec -i $PGPOD -n server-scanner -- \
  psql -U scanner server_scanner

# From PVC
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner server_scanner -f /var/lib/postgresql/data/backup.sql
```

## Security Considerations

1. **Password Management**: Store PostgreSQL password in a secret management system (Vault, Sealed Secrets)
2. **Network Policies**: Restrict access to PostgreSQL service to only application pods
3. **Encryption**: Enable SSL/TLS for PostgreSQL connections in production
4. **RBAC**: Limit database user permissions to only required operations (SELECT, INSERT, UPDATE, DELETE)
5. **Backups**: Implement automated backup strategy with encryption

## Monitoring

### Health Checks

```bash
# Check PostgreSQL health
kubectl exec -it $PGPOD -n server-scanner -- pg_isready -U scanner

# Check database size
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c \
  "SELECT pg_size_pretty(pg_database_size('server_scanner'));"

# Check connection count
kubectl exec -it $PGPOD -n server-scanner -- \
  psql -U scanner -d server_scanner -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'server_scanner';"
```

### Prometheus Metrics

Enable postgres_exporter for metrics collection:

```yaml
# Add to postgres deployment
- name: postgres-exporter
  image: prometheuscommunity/postgres-exporter
  env:
    - name: DATA_SOURCE_NAME
      value: "postgresql://scanner:$(POSTGRES_PASSWORD)@localhost:5432/server_scanner?sslmode=disable"
  ports:
    - containerPort: 9187
```

## Support

For issues or questions:
- Check logs: `kubectl logs -n server-scanner POD_NAME`
- Review documentation: `/docs/POSTGRES_MIGRATION.md`
- Open issue: GitHub repository
