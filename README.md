# Server Scanner Dashboard

Multi-vendor server inventory dashboard for HP OneView, Dell OME, and Cisco UCS Central.

A daily Kubernetes CronJob syncs all server hardware details into MongoDB. The web dashboard reads from MongoDB and overlays live Kubernetes installation status at request time. Maintenance records are stored directly in MongoDB server documents.

## Architecture

```
CronJob (daily)                     Web Dashboard (always-on)
src/cli/sync_mongo.py               src/web_ui.py
        │                                   │
  SyncService                       DashboardService
        │                                   │              \
VendorStrategy                   ServerRepository    KubernetesRepository
.get_full_server_data()                    │           (live K8s queries)
        │                                  │
      MongoDB ───────────────────────────── ┘
     (servers collection)
```

## Quick Start

```bash
pip install -r requirements.txt
pip install ucscsdk ucsmsdk   # optional: Cisco UCS support

cp .env.example .env          # fill in MONGO_URI + vendor credentials

# Web dashboard (reads from MongoDB)
python -m src.web_ui

# Daily sync (writes to MongoDB) — also runs as Kubernetes CronJob
python -m src.cli.sync_mongo
```

## Configuration

All configuration is via environment variables (`.env` or Kubernetes ConfigMap/Secret).

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_URI` | ✅ web + sync | — | MongoDB connection string |
| `MONGO_DB_NAME` | — | `server_scanner` | MongoDB database name |
| `TLS_VERIFY` | — | `false` | TLS cert verification (HP, Dell, Cisco, K8s, MongoDB) |
| `ONEVIEW_IP/USERNAME/PASSWORD` | ✅ sync | — | HP OneView credentials |
| `OME_IP/USERNAME/PASSWORD` | ✅ sync | — | Dell OME credentials |
| `UCS_CENTRAL_IP/USERNAME/PASSWORD` | ✅ sync | — | Cisco UCS Central credentials |
| `UCS_MANAGER_USERNAME/PASSWORD` | ✅ sync | — | Cisco UCS Manager credentials |
| `K8S_CLUSTER_NAMES` | optional | — | Comma-separated cluster names |
| `K8S_DOMAIN_NAME` | optional | — | Cluster API domain |
| `K8S_TOKEN` | optional | — | Per-cluster tokens (comma-separated) |
| `SYNC_BATCH_SIZE` | — | `50` | Dell OME: servers per batch |
| `SYNC_BATCH_DELAY` | — | `1.0` | Dell OME: seconds between batches |

## MongoDB Document Schema

Collection: `servers`

```json
{
  "_id": "ocp4-hypershift-zone-a-01",
  "vendor": "HP",
  "zone": "zone-a",
  "bmc_address": "10.0.0.1",
  "mac_address": "aa:bb:cc:dd:ee:ff",
  "cpu_model": "Intel Xeon Gold 6230R",
  "cpu_count": 2,
  "cpu_cores": 26,
  "memory_gb": 256,
  "model": "ProLiant DL380 Gen10",
  "serial": "MXQ12345",
  "disks": [{"size_gb": 960, "type": "SSD", "model": "..."}],
  "maintenance": null,
  "last_scanned": "2025-03-12T06:00:00Z"
}
```

Maintenance is embedded in the server document. The CronJob upserts hardware fields without touching the `maintenance` field, so maintenance records survive daily re-syncs.

## Sync Behaviour by Vendor

| Vendor | Bulk calls | Per-server calls | Notes |
|---|---|---|---|
| HP OneView | 2 (profiles + hardware) | 0 | Bulk hardware lookup, cross-referenced by URI |
| Dell OME | 2 (profiles + devices) | 4 per server | MAC, CPU, memory, storage inventory; batched with delay |
| Cisco UCS | 1 Central + 1 per domain | ~6 per server | Groups by UCS Manager domain to minimise connections |

## Web UI Features

- Server cards: name, model, serial — click for full hardware details
- Inline 🔧 maintenance button per card (no page scroll needed)
- Live name search (client-side, instant)
- Zone filter dropdown (populated from API, persists across zone switches)
- Status pills: All / Available / Installed / Maintenance
- Dark/light theme

## Helm Deployment

```bash
helm upgrade --install server-scanner \
  deploy/helm/server-scanner-dashboard/ \
  --set secrets.mongoUri="mongodb://..." \
  --set secrets.oneviewIp="10.0.0.1" \
  --set secrets.oneviewUsername="admin" \
  --set secrets.oneviewPassword="..." \
  --set config.tlsVerify="false"
```

The CronJob runs daily at 06:00 (`config.cronjob.schedule`). The web Deployment and CronJob share the same Secret, so vendor credentials only need to be set once.

## Local Development with Test Data

```bash
# Seed fake servers into MongoDB for UI testing
python seed_test_data.py

# Start the dashboard (no vendor credentials needed)
MONGO_URI="..." python -m src.web_ui
```
