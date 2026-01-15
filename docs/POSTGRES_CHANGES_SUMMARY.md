# PostgreSQL Migration - Changes Summary

This document summarizes all changes made to migrate from file-based storage to PostgreSQL.

## Overview

Successfully migrated the Server Scanner Dashboard maintenance storage from file-based JSON on PVC to PostgreSQL database with connection pooling and async support.

## Files Created

### 1. PostgreSQL Storage Implementation
**File**: `src/storage/maintenance_store_postgres.py` (335 lines)

**Purpose**: Async PostgreSQL storage backend for maintenance data

**Key Features**:
- Connection pooling using `asyncpg`
- Automatic schema creation with constraints
- Full CRUD operations (get, set, remove, get_all)
- Statistics methods (count, by_severity, recent)
- Proper error handling and logging

**Database Schema**:
```sql
CREATE TABLE server_maintenance (
    server_name VARCHAR(255) PRIMARY KEY,
    reason TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_server_maintenance_severity ON server_maintenance(severity);
CREATE INDEX idx_server_maintenance_timestamp ON server_maintenance(timestamp);
```

### 2. Helm Chart Resources

#### PostgreSQL StatefulSet
**File**: `deploy/helm/server-scanner-dashboard/templates/postgres-statefulset.yaml` (107 lines)

**Purpose**: Deploy PostgreSQL as a StatefulSet in Kubernetes

**Features**:
- PostgreSQL 15 Alpine image
- Persistent storage via volumeClaimTemplates
- Health checks (liveness + readiness probes)
- Security context (non-root user)
- Optional init script for schema creation

#### PostgreSQL Services
**File**: `deploy/helm/server-scanner-dashboard/templates/postgres-service.yaml` (40 lines)

**Purpose**: Expose PostgreSQL within the cluster

**Services Created**:
1. Headless service (`-postgres-headless`) for StatefulSet
2. Regular ClusterIP service (`-postgres`) for application access

#### PostgreSQL Secret
**File**: `deploy/helm/server-scanner-dashboard/templates/postgres-secret.yaml` (13 lines)

**Purpose**: Store PostgreSQL credentials securely

**Contains**:
- `username`: Database user
- `password`: Database password

#### PostgreSQL Init ConfigMap
**File**: `deploy/helm/server-scanner-dashboard/templates/postgres-init-configmap.yaml` (31 lines)

**Purpose**: Optional database initialization script

**Contains**:
- Table creation SQL
- Index creation
- Permission grants

### 3. Migration Script
**File**: `scripts/migrate-json-to-postgres.py` (425 lines)

**Purpose**: Migrate existing JSON data to PostgreSQL

**Features**:
- Load from local JSON file or Kubernetes PVC
- Dry-run mode for testing
- Record validation and normalization
- Progress tracking and error reporting
- Statistics summary

**Usage**:
```bash
# From local file
python scripts/migrate-json-to-postgres.py --json-file maintenance.json

# From Kubernetes PVC
python scripts/migrate-json-to-postgres.py --from-k8s --namespace server-scanner

# Dry run
python scripts/migrate-json-to-postgres.py --json-file maintenance.json --dry-run
```

### 4. Documentation
**File**: `docs/POSTGRES_MIGRATION.md` (500+ lines)

**Purpose**: Complete migration guide

**Sections**:
- Architecture overview
- Deployment steps
- Data migration procedures
- Verification and testing
- Rollback plan
- Troubleshooting
- Performance tuning
- Backup and recovery

## Files Modified

### 1. Configuration
**File**: `src/config.py`

**Changes**:
- Added `DatabaseConfig` class with PostgreSQL settings
- Environment variables for database connection
- Storage backend selection (`file` vs `postgres`)
- Connection pool configuration

**New Environment Variables**:
```python
STORAGE_BACKEND = "postgres"  # or "file"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_DB = "server_scanner"
POSTGRES_USER = "scanner"
POSTGRES_PASSWORD = "***"
POSTGRES_MIN_POOL_SIZE = "1"
POSTGRES_MAX_POOL_SIZE = "10"
```

### 2. Dependencies Initialization
**File**: `src/api/dependencies.py`

**Changes**:
- Conditional initialization based on `STORAGE_BACKEND`
- Support for both `MaintenanceStore` (file) and `MaintenanceStorePostgres`
- Proper error handling for both backends

**Code**:
```python
def initialize_dependencies():
    global _maintenance_store, _cache_repo, ...

    if DatabaseConfig.use_postgres():
        logger.info("Initializing PostgreSQL maintenance storage")
        _maintenance_store = MaintenanceStorePostgres(
            host=DatabaseConfig.POSTGRES_HOST,
            port=DatabaseConfig.POSTGRES_PORT,
            database=DatabaseConfig.POSTGRES_DB,
            user=DatabaseConfig.POSTGRES_USER,
            password=DatabaseConfig.POSTGRES_PASSWORD
        )
    else:
        logger.info("Initializing file-based maintenance storage")
        _maintenance_store = MaintenanceStore(data_dir=Path(DatabaseConfig.DATA_DIR))
```

### 3. Python Dependencies
**File**: `requirements.txt`

**Added**:
```
# Database (optional - for PostgreSQL storage)
asyncpg>=0.29.0

# Already present but now required
pydantic>=2.0.0
```

### 4. Docker Image
**File**: `Dockerfile`

**Changes**:
- Added `libpq-dev` to build stage (PostgreSQL client headers)
- Added `libpq5` to runtime stage (PostgreSQL client library)

**Build Stage**:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Runtime Stage**:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*
```

### 5. Helm Values
**File**: `deploy/helm/server-scanner-dashboard/values.yaml`

**Changes**:
- Deprecated file-based `persistence` (set `enabled: false`)
- Added `postgres` section with full configuration
- Updated `config.storageBackend` to `"postgres"`
- Added `config.dataDir` for backward compatibility

**PostgreSQL Configuration**:
```yaml
postgres:
  enabled: true
  image:
    repository: postgres
    tag: "15-alpine"
  auth:
    username: scanner
    password: ""  # REQUIRED in production
    database: server_scanner
  persistence:
    enabled: true
    size: 5Gi
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 100m
      memory: 256Mi
  initScript: true
```

### 6. ConfigMap Template
**File**: `deploy/helm/server-scanner-dashboard/templates/configmap.yaml`

**Changes**:
- Added `STORAGE_BACKEND` environment variable
- Added `DATA_DIR` environment variable
- Added PostgreSQL connection variables (when `postgres.enabled`)

**Added Variables**:
```yaml
# Storage backend configuration
STORAGE_BACKEND: {{ .Values.config.storageBackend | quote }}
DATA_DIR: {{ .Values.config.dataDir | quote }}

{{- if .Values.postgres.enabled }}
# PostgreSQL configuration
POSTGRES_HOST: {{ include "server-scanner-dashboard.fullname" . }}-postgres
POSTGRES_PORT: "5432"
POSTGRES_DB: {{ .Values.postgres.database | quote }}
{{- end }}
```

### 7. Deployment Template
**File**: `deploy/helm/server-scanner-dashboard/templates/deployment.yaml`

**Changes**:
- Added PostgreSQL credentials from secret as environment variables

**Added Environment Variables**:
```yaml
{{- if .Values.postgres.enabled }}
env:
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: {{ include "server-scanner-dashboard.fullname" . }}-postgres
        key: username
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: {{ include "server-scanner-dashboard.fullname" . }}-postgres
        key: password
{{- end }}
```

## Architecture Comparison

### Before (File-based Storage)

```
┌────────────────────────────────┐
│     Application Pod            │
│                                │
│  ┌──────────────────────────┐  │
│  │  MaintenanceStore        │  │
│  │  (file-based)            │  │
│  │                          │  │
│  │  - Reads/writes JSON     │  │
│  │  - File locking          │  │
│  │  - No connection pool    │  │
│  └──────────────────────────┘  │
│              │                 │
└──────────────┼─────────────────┘
               │
               ▼
    ┌─────────────────────┐
    │   PVC (ReadWriteMany)│
    │                     │
    │  maintenance.json   │
    └─────────────────────┘
```

**Limitations**:
- File locking issues with multiple pods
- No ACID guarantees
- Manual backup/restore
- Limited query capabilities
- No connection pooling

### After (PostgreSQL)

```
┌────────────────────────────────┐         ┌──────────────────────────┐
│     Application Pod(s)         │         │   PostgreSQL StatefulSet │
│                                │         │                          │
│  ┌──────────────────────────┐  │         │  ┌────────────────────┐  │
│  │  MaintenanceStorePostgres│  │◄────────┼─►│  PostgreSQL 15     │  │
│  │  (async PostgreSQL)      │  │         │  │                    │  │
│  │                          │  │         │  │  - ACID compliance │  │
│  │  - Connection pool       │  │         │  │  - Indexes         │  │
│  │  - Async operations      │  │         │  │  - Constraints     │  │
│  │  - Auto-reconnect        │  │         │  │  - Crash recovery  │  │
│  └──────────────────────────┘  │         │  └────────────────────┘  │
└────────────────────────────────┘         │            │             │
                                           └────────────┼─────────────┘
                                                        │
                                                        ▼
                                             ┌─────────────────────┐
                                             │ PVC (ReadWriteOnce) │
                                             │                     │
                                             │  PostgreSQL data    │
                                             └─────────────────────┘
```

**Benefits**:
- Multi-pod support (connection pooling)
- ACID transactions
- Standard PostgreSQL tools
- SQL queries for analytics
- Automatic schema management

## Data Model

### File-based (JSON)
```json
{
  "server01.example.com": {
    "reason": "Hardware replacement scheduled",
    "severity": "high",
    "timestamp": "2026-01-15T10:30:00Z",
    "created_by": "admin"
  }
}
```

### PostgreSQL (Table)
```sql
 server_name         | reason                          | severity | timestamp              | created_by | updated_at
--------------------+---------------------------------+----------+------------------------+------------+------------
 server01.example.com| Hardware replacement scheduled  | high     | 2026-01-15 10:30:00+00 | admin      | 2026-01-15 10:30:00+00
```

**Normalization**: Server names are normalized (lowercase, trimmed) for consistency.

## Deployment Workflow

### 1. Prerequisites
- Kubernetes cluster with storage provisioner
- kubectl access to cluster
- Python 3.8+ with asyncpg installed (for migration)

### 2. Deployment Steps

```bash
# 1. Update values.yaml with PostgreSQL password
vim deploy/helm/server-scanner-dashboard/values.yaml

# 2. Deploy with Helm
helm upgrade --install server-scanner-dashboard \
  ./deploy/helm/server-scanner-dashboard \
  --namespace server-scanner \
  --create-namespace

# 3. Verify PostgreSQL deployment
kubectl get pods -n server-scanner -l app.kubernetes.io/component=database

# 4. Verify schema creation
kubectl logs -n server-scanner -l app.kubernetes.io/component=database

# 5. Migrate existing data (if any)
export POSTGRES_PASSWORD="your-password"
kubectl port-forward -n server-scanner svc/server-scanner-dashboard-postgres 5432:5432 &
python scripts/migrate-json-to-postgres.py --from-k8s --namespace server-scanner

# 6. Verify application
kubectl logs -n server-scanner -l app.kubernetes.io/name=server-scanner-dashboard | grep PostgreSQL
```

### 3. Verification

```bash
# Test maintenance API
curl -X PUT https://YOUR_ROUTE/api/servers/test-server/maintenance \
  -H "Content-Type: application/json" \
  -d '{"reason": "Test", "severity": "low", "timestamp": "2026-01-15T12:00:00Z"}'

# Verify in database
kubectl exec -it POSTGRES_POD -n server-scanner -- \
  psql -U scanner -d server_scanner -c "SELECT * FROM server_maintenance;"

# Clean up
curl -X DELETE https://YOUR_ROUTE/api/servers/test-server/maintenance
```

## Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `STORAGE_BACKEND` | Storage backend type | `postgres` | No |
| `DATA_DIR` | Data directory for file storage | `/data` | No (only for file backend) |
| `POSTGRES_HOST` | PostgreSQL hostname | `postgres` | Yes (for postgres backend) |
| `POSTGRES_PORT` | PostgreSQL port | `5432` | No |
| `POSTGRES_DB` | Database name | `server_scanner` | No |
| `POSTGRES_USER` | Database username | (from secret) | Yes (for postgres backend) |
| `POSTGRES_PASSWORD` | Database password | (from secret) | Yes (for postgres backend) |
| `POSTGRES_MIN_POOL_SIZE` | Min connections in pool | `1` | No |
| `POSTGRES_MAX_POOL_SIZE` | Max connections in pool | `10` | No |

## Backward Compatibility

The application maintains backward compatibility with file-based storage:

1. **Config Selection**: Use `STORAGE_BACKEND=file` to use old storage
2. **Dual Support**: Both `MaintenanceStore` and `MaintenanceStorePostgres` implement the same interface
3. **Automatic Detection**: `dependencies.py` automatically selects the correct backend
4. **No Code Changes**: Application code remains unchanged

## Testing Checklist

- [x] PostgreSQL pod starts successfully
- [x] Database schema created automatically
- [x] Application connects to PostgreSQL
- [x] Maintenance API works (PUT, DELETE, GET)
- [x] Data persists across pod restarts
- [x] Migration script works (JSON → PostgreSQL)
- [ ] Performance testing under load
- [ ] Multi-pod deployment testing
- [ ] Backup and restore procedures
- [ ] Monitoring and alerting setup

## Performance Considerations

### Connection Pooling

**Default Settings**:
- Min pool size: 1
- Max pool size: 10

**Tuning for High Traffic**:
```yaml
env:
  - name: POSTGRES_MIN_POOL_SIZE
    value: "5"
  - name: POSTGRES_MAX_POOL_SIZE
    value: "20"
```

**PostgreSQL Configuration** (for very high traffic):
```ini
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
```

### Indexing Strategy

Current indexes:
1. **Primary Key** on `server_name` (unique, hash-based lookups)
2. **B-tree Index** on `severity` (filtering by severity level)
3. **B-tree Index** on `timestamp` (time-based queries)

**Query Performance**:
- Lookup by server name: O(1) - hash index
- Filter by severity: O(log n) - B-tree index
- Recent maintenance: O(log n) - timestamp index

## Security Considerations

### Current Implementation

1. **Credentials**: Stored in Kubernetes Secret
2. **Network**: ClusterIP service (internal only)
3. **User Permissions**: Application user has SELECT, INSERT, UPDATE, DELETE only
4. **Connection**: No SSL/TLS (cluster-internal traffic)

### Production Recommendations

1. **Secret Management**: Use Vault or Sealed Secrets for password management
2. **SSL/TLS**: Enable SSL for PostgreSQL connections
3. **Network Policies**: Restrict database access to application pods only
4. **Audit Logging**: Enable PostgreSQL audit log
5. **Backup Encryption**: Encrypt database backups

## Cost Implications

### Storage

**Before** (File-based):
- PVC: 1Gi ReadWriteMany (expensive in cloud environments)
- No indexes, no optimizations

**After** (PostgreSQL):
- PVC: 5Gi ReadWriteOnce (cheaper than RWX)
- Indexes for performance (minimal overhead)
- Better data compression

### Compute

**Before**:
- File I/O overhead
- No connection pooling
- Limited concurrency

**After**:
- Connection pooling (efficient resource use)
- PostgreSQL resource limits: 500m CPU, 512Mi memory
- Better multi-pod scaling

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Database Health**
   - Connection pool utilization
   - Query latency
   - Error rate

2. **Storage**
   - Database size growth
   - PVC usage
   - I/O operations

3. **Application**
   - Maintenance record count
   - API response times
   - Failed database operations

### Recommended Alerts

```yaml
alerts:
  - name: PostgreSQLDown
    expr: up{job="postgres"} == 0
    duration: 1m
    severity: critical

  - name: HighDatabaseConnections
    expr: pg_stat_database_numbackends > 80
    duration: 5m
    severity: warning

  - name: SlowQueries
    expr: rate(pg_stat_statements_mean_time[5m]) > 1000
    duration: 5m
    severity: warning
```

## Migration Statistics

**Total Files Created**: 8
- Storage implementation: 1
- Helm templates: 4
- Migration script: 1
- Documentation: 2

**Total Files Modified**: 7
- Configuration: 1
- Dependencies: 1
- Requirements: 1
- Dockerfile: 1
- Helm values: 1
- Helm templates: 2

**Total Lines Added**: ~1,500
**Total Lines Modified**: ~100

## Next Steps

1. **Deploy to Staging**: Test full deployment in staging environment
2. **Performance Testing**: Load testing with realistic data volumes
3. **Backup Strategy**: Implement automated PostgreSQL backups
4. **Monitoring**: Set up Prometheus monitoring with postgres_exporter
5. **Documentation**: Add runbooks for common operations
6. **Training**: Train ops team on PostgreSQL management

## Rollback Plan

If issues arise:

1. **Immediate**: Switch `STORAGE_BACKEND=file` and restart pods
2. **Data Export**: Use migration script to export PostgreSQL → JSON
3. **Helm Rollback**: `helm rollback server-scanner-dashboard`
4. **PVC Restore**: Restore from PVC backup if needed

## Success Criteria

- ✅ PostgreSQL deploys successfully in Kubernetes
- ✅ Application connects and creates schema automatically
- ✅ All CRUD operations work correctly
- ✅ Migration script successfully transfers existing data
- ✅ Data persists across pod restarts
- ✅ Documentation complete and accurate
- ⏳ Performance meets or exceeds file-based storage
- ⏳ Multi-pod deployment validated
- ⏳ Backup and restore procedures tested

## Contact

For questions or issues:
- Check logs: `kubectl logs -n server-scanner POD_NAME`
- Review docs: `/docs/POSTGRES_MIGRATION.md`
- Migration guide: `/docs/POSTGRES_CHANGES_SUMMARY.md`
