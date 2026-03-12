# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Multi-vendor server inventory dashboard that queries HP OneView, Dell OME, and Cisco UCS Central. A daily Kubernetes CronJob fetches full server hardware details (CPU, memory, model, serial, disks, BMC IP, MAC) and stores them in MongoDB. The web dashboard reads from MongoDB and overlays live Kubernetes installation status at request time. Maintenance records are embedded in MongoDB server documents.

## Running the Application

```bash
pip install -r requirements.txt
pip install ucscsdk ucsmsdk   # optional: Cisco UCS support

cp .env.example .env           # fill in MONGO_URI + vendor credentials

# Web dashboard (reads from MongoDB — no vendor credentials needed)
python -m src.web_ui
python -m src.web_ui --verbose --reload

# Daily sync (writes to MongoDB — requires vendor credentials)
python -m src.cli.sync_mongo

# Legacy CLI scanner (name-only, no MongoDB)
python -m src.scan_servers

# Seed fake data for local UI testing
python seed_test_data.py
```

There is no test suite or linting configuration.

## Configuration

`validate_web_config()` — called by web app — requires `MONGO_URI`.
`validate_sync_config()` — called by CronJob — requires `MONGO_URI` + at least one vendor.

Key env vars:

```
# MongoDB (required for both)
MONGO_URI=mongodb://user:pass@host:27017
MONGO_DB_NAME=server_scanner      # default: server_scanner

# TLS/SSL — one setting covers ALL systems (HP, Dell, Cisco, K8s, MongoDB)
TLS_VERIFY=false                  # false = skip cert verification (self-signed certs)

# Vendors (CronJob only)
ONEVIEW_IP, ONEVIEW_USERNAME, ONEVIEW_PASSWORD
OME_IP, OME_USERNAME, OME_PASSWORD
UCS_CENTRAL_IP, UCS_CENTRAL_USERNAME, UCS_CENTRAL_PASSWORD
UCS_MANAGER_USERNAME, UCS_MANAGER_PASSWORD

# Kubernetes (optional — live install status)
K8S_CLUSTER_NAMES, K8S_DOMAIN_NAME, K8S_TOKEN, K8S_NAMESPACE

# Sync rate-limit (Dell OME only — HP uses bulk calls)
SYNC_BATCH_SIZE=50
SYNC_BATCH_DELAY=1.0
```

## Architecture

```
CronJob (daily)                     Web Dashboard (always-on)
src/cli/sync_mongo.py               src/web_ui.py
        |                                   |
  SyncService                       DashboardService
        |                                   |         \
VendorStrategy                  ServerRepository  KubernetesRepository
.get_full_server_data()                    |       (live K8s queries)
        |                                  |
      MongoDB ----------------------------  +
```

**API Layer** (`src/api/`):
- `dashboard_routes.py` — `GET /api/servers`, cache management
- `maintenance_routes.py` — `PUT/DELETE /api/servers/{name}/maintenance`, `GET /api/servers/{name}`
- `dependencies.py` — FastAPI DI wiring (MongoDB singletons)

**Service Layer** (`src/services/`):
- `dashboard_service.py` — reads MongoDB, merges live K8s status, returns `DashboardData`
- `sync_service.py` — CronJob orchestrator: calls `strategy.get_full_server_data()`, upserts to MongoDB

**Storage** (`src/storage/database/`):
- `mongo_client.py` — `MongoDatabase` (Motor async client, lifecycle managed by web app startup/shutdown)
- `server_repository.py` — `ServerRepository` (all CRUD for `servers` collection, incl. maintenance ops)

**Strategy Layer** (`src/strategies/`):
- All inherit `base_strategy.py:VendorStrategy`
- `get_full_server_data(pattern, hardware_details, batch_size, batch_delay)` — CronJob path
- `get_server_profiles()` — name-only bulk scan (legacy CLI)
- HP: 2 bulk API calls regardless of server count (profiles + hardware cross-referenced by URI)
- Dell: 2 bulk + 4 per-server inventory calls, batched with `batch_delay` sleep
- Cisco: 1 Central session + 1 UCS Manager session per domain

**Models** (`src/models/`):
- `server_document.py` — `ServerDocument` Pydantic model (MongoDB contract)
- `api_responses.py` — `DashboardData`, `ServerInfo` (includes hardware fields), `MaintenanceInfo`

## MongoDB Schema

Collection: `servers`, `_id` = server profile name.

Upsert rule: `$set` hardware fields + `$setOnInsert` for `maintenance: null`. The CronJob never overwrites existing maintenance records.

## TLS Verification

`AppConfig.TLS_VERIFY` is the single source of truth, read from `TLS_VERIFY` env var. Propagates to:
- `VendorHTTPClient` (HP/Dell) via `requests.Session.verify`
- Cisco SDK: `UcscHandle(secure=TLS_VERIFY)` and `UcsHandle(secure=TLS_VERIFY)`
- Kubernetes client: `k8s_client.Configuration.verify_ssl`
- MongoDB Motor: `AsyncIOMotorClient(tlsAllowInvalidCertificates=not TLS_VERIFY)`
- urllib3 `InsecureRequestWarning` suppressed only when `TLS_VERIFY=false`

## Helm Deployment

`deploy/helm/server-scanner-dashboard/values.yaml` controls everything:
- `config.tlsVerify` — TLS verification (default: `"false"`)
- `secrets.mongoUri` — MongoDB connection string
- `cronjob.schedule` — daily sync schedule (default: `"0 6 * * *"`)
- `cronjob.enabled` — enable/disable the daily sync CronJob

## Adding a New Vendor

1. Create `src/strategies/<vendor>_strategy.py` inheriting from `VendorStrategy`
2. Implement `get_server_profiles()`, `get_server_info()`, and `get_full_server_data()`
3. Register in `src/repositories/strategy_factory.py`
4. Add config vars to `src/config.py` `VendorConfig` + `validate_sync_config()` + `.env.example`
5. Add credentials to `src/cli/sync_mongo.py:build_strategies()` and Helm `values.yaml`/`secret.yaml`
