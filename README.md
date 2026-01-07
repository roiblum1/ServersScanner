# Server Scanner

Multi-vendor server profile scanner for HP OneView, Dell OME, and Cisco UCS Central.

Uses the **Strategy Pattern** to cleanly separate vendor-specific logic into modular, maintainable components.

## Project Structure

```
Scan_Servers/
├── scan_servers.py                 # Main CLI entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Example environment configuration
└── src/
    ├── __init__.py                 # Package initialization
    ├── server_strategy.py          # Abstract base class & factory
    ├── hp_server_strategy.py       # HP OneView implementation
    ├── dell_server_strategy.py     # Dell OME implementation
    ├── cisco_server_strategy.py    # Cisco UCS implementation
    ├── kubernetes_bmh_filter.py    # Kubernetes BMH filter (optional)
    └── scanner_client.py           # Unified scanner client
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# For Cisco UCS support (optional)
pip install ucscsdk ucsmsdk

# Configure credentials
cp .env.example .env
# Edit .env with your credentials

# Run the scanner (default: simple list)
python scan_servers.py
```

## Usage

### Basic Usage

```bash
# Scan all vendors for ocp4-hypershift-* servers (default: list format)
python scan_servers.py

# Custom pattern
python scan_servers.py --pattern "ocp4-.*"

# Scan specific vendor only
python scan_servers.py --vendor HP
python scan_servers.py --vendor DELL
python scan_servers.py --vendor CISCO

# Scan multiple vendors
python scan_servers.py --vendor HP --vendor DELL
```

### Output Formats

```bash
# Simple list (DEFAULT) - Just server names
python scan_servers.py
python scan_servers.py --format list

# Detailed table - Names + MAC + BMC IP + Domain
python scan_servers.py --format table

# JSON output - Full structured data
python scan_servers.py --format json
python scan_servers.py --json  # shortcut
```

### Kubernetes BMH Filtering (Optional)

The scanner can automatically filter out servers that are already installed (exist as BareMetalHost resources in Kubernetes):

```bash
# Default: Show only AVAILABLE servers (filters out installed ones)
python scan_servers.py

# Show ALL servers including installed ones
python scan_servers.py --show-all
```

**How it works:**

1. Queries all configured Kubernetes clusters for BareMetalHost (BMH) resources
2. Filters out servers whose names match existing BMH resources
3. Shows only available (not installed) servers

**Configuration** (add to `.env`):
```bash
K8S_CLUSTER_NAMES=cluster1,cluster2,cluster3
K8S_DOMAIN_NAME=example.com
K8S_USERNAME=admin
K8S_PASSWORD=your-password
# OR use token authentication:
# K8S_TOKEN=your-token
K8S_NAMESPACE=inventory
```

**API Server Format:** `https://api.<cluster_name>.<domain_name>:6443`

**Example workflow:**

```bash
# Step 1: Scan without K8S filter (shows all servers)
python scan_servers.py --show-all
# Output: TOTAL: 20 servers (all vendor profiles)

# Step 2: Configure K8S filter in .env, then scan (default behavior)
python scan_servers.py
# Output: TOTAL: 12 servers (only available, 8 already installed)

# With verbose logging to see filtering details
python scan_servers.py --verbose
# Shows: "DELL: Filtered out 3 installed servers, 5 available"
```

### Advanced Options

```bash
# Check for duplicate names across vendors
python scan_servers.py --check-duplicates

# Use specific .env file
python scan_servers.py --env-file /path/to/.env

# Enable verbose logging
python scan_servers.py --verbose

# Combine options
python scan_servers.py --pattern "ocp4-tlv-.*" --vendor HP --format table
```

## Example Outputs

### List Format (Default)

```
🔍 Scanning for servers matching: ^ocp4-hypershift-.*

================================================================================
SERVER PROFILES
================================================================================

CISCO:
  - ocp4-hypershift-ucs-001
  - ocp4-hypershift-ucs-002
  - ocp4-hypershift-ucs-003

DELL:
  - ocp4-hypershift-server01
  - ocp4-hypershift-server02
  - ocp4-hypershift-server03
  - ocp4-hypershift-server04
  - ocp4-hypershift-server05
  - ocp4-hypershift-server06
  - ocp4-hypershift-server07
  - ocp4-hypershift-server08

HP:
  - ocp4-hypershift-rf-001
  - ocp4-hypershift-rf-002
  - ocp4-hypershift-rf-003
  - ocp4-hypershift-rf-004
  - ocp4-hypershift-rf-005

================================================================================

Summary:
  CISCO: 3 servers
  DELL: 8 servers
  HP: 5 servers
  TOTAL: 16 servers
```

### Table Format (Detailed)

```bash
python scan_servers.py --format table
```

```
====================================================================================================
SERVER NAME                              VENDOR   BMC IP           MAC ADDRESS        DOMAIN
====================================================================================================
ocp4-hypershift-server01                 DELL     10.1.1.101       AA:BB:CC:DD:EE:01  -
ocp4-hypershift-server02                 DELL     10.1.1.102       AA:BB:CC:DD:EE:02  -
ocp4-hypershift-rf-001                   HP       10.2.2.101       11:22:33:44:55:01  -
ocp4-hypershift-rf-002                   HP       10.2.2.102       11:22:33:44:55:02  -
ocp4-hypershift-ucs-001                  CISCO    10.3.3.101       66:77:88:99:AA:01  ucs-domain-1
====================================================================================================

Summary:
  CISCO: 3 servers
  DELL: 8 servers
  HP: 5 servers
  TOTAL: 16 servers
```

### JSON Format

```bash
python scan_servers.py --json
```

```json
{
  "timestamp": "2026-01-07T10:30:00Z",
  "servers": {
    "HP": [
      {
        "name": "ocp4-hypershift-rf-001",
        "vendor": "HP",
        "mac_address": "11:22:33:44:55:01",
        "bmc_ip": "10.2.2.101",
        "serial_number": "ABC123",
        "model": "ProLiant DL360 Gen10"
      }
    ],
    "DELL": [
      {
        "name": "ocp4-hypershift-server01",
        "vendor": "DELL",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "bmc_ip": "10.1.1.101",
        "serial_number": "DEF456",
        "model": "PowerEdge R640"
      }
    ],
    "CISCO": [
      {
        "name": "ocp4-hypershift-ucs-001",
        "vendor": "CISCO",
        "mac_address": "66:77:88:99:AA:01",
        "bmc_ip": "10.3.3.101",
        "domain": "ucs-domain-1"
      }
    ]
  }
}
```

### Duplicate Detection

```bash
python scan_servers.py --check-duplicates
```

```
⚠️  DUPLICATES FOUND across vendors:
   - ocp4-hypershift-server01 exists in: HP, DELL
```

## Environment Variables

Create a `.env` file with your credentials:

| Variable | Required | Description |
|----------|----------|-------------|
| `ONEVIEW_IP` | For HP | HP OneView IP address |
| `ONEVIEW_USERNAME` | For HP | HP OneView username (default: administrator) |
| `ONEVIEW_PASSWORD` | For HP | HP OneView password |
| `OME_IP` | For Dell | Dell OME IP address |
| `OME_USERNAME` | For Dell | Dell OME username (default: admin) |
| `OME_PASSWORD` | For Dell | Dell OME password |
| `UCS_CENTRAL_IP` | For Cisco | Cisco UCS Central IP |
| `UCS_CENTRAL_USERNAME` | For Cisco | UCS Central username (default: admin) |
| `UCS_CENTRAL_PASSWORD` | For Cisco | UCS Central password |
| `UCS_MANAGER_USERNAME` | For Cisco | UCS Manager username (default: admin) |
| `UCS_MANAGER_PASSWORD` | For Cisco | UCS Manager password |
| `K8S_CLUSTER_NAMES` | Optional | Comma-separated Kubernetes cluster names |
| `K8S_DOMAIN_NAME` | Optional | Kubernetes cluster domain name |
| `K8S_USERNAME` | Optional | Kubernetes username for authentication |
| `K8S_PASSWORD` | Optional | Kubernetes password for authentication |
| `K8S_TOKEN` | Optional | Kubernetes token (alternative to username/password) |
| `K8S_NAMESPACE` | Optional | Kubernetes namespace for BMH resources (default: inventory) |

### Kubernetes BMH Filter Prerequisites

If you want to use the Kubernetes BMH filtering feature:

1. **Install Python Kubernetes client**:
   ```bash
   pip install kubernetes
   ```

2. **Cluster access**: Ensure your credentials (username/password or token) can access the clusters

3. **BareMetalHost CRD**: Clusters must have the BareMetalHost CustomResourceDefinition installed (from Metal3 or OpenShift)
   - The filter queries `baremetalhosts.metal3.io/v1alpha1` custom resources
   - If the CRD is not found in a cluster, it will be skipped with a warning

**Why Python Kubernetes client?**
- ✅ Pure Python - no external kubectl binary required
- ✅ Better error handling and type safety
- ✅ Faster - no subprocess overhead
- ✅ More flexible authentication options
- ✅ Better suited for development and testing

## Architecture

This project follows the **Strategy Pattern** for clean separation of vendor-specific logic:

- **`VendorStrategy`** - Abstract base class defining the interface
- **`HPServerStrategy`** - HP OneView implementation
- **`DellServerStrategy`** - Dell OME implementation
- **`CiscoServerStrategy`** - Cisco UCS Central implementation
- **`VendorStrategyFactory`** - Factory to create strategy instances
- **`ServerScanner`** - Unified client that orchestrates all strategies

### Benefits

- **Extensible**: Add new vendors by implementing `VendorStrategy`
- **Maintainable**: Vendor logic is isolated in separate files
- **Testable**: Each strategy can be tested independently
- **Clean**: Main script is simple and focused on CLI concerns

## Integration with BareMetalHostUCS

This project is designed to be compatible with the [BareMetalHostUCS](../BareMetalHostUCS) project. Both share the same:

- **Strategy Pattern architecture** - Same abstract base class structure
- **Method signatures** - `get_server_info(server_name)` returns `Tuple[Optional[str], Optional[str]]`
- **Type annotations** - Uses `Tuple` from `typing` module for Python 3.7+ compatibility
- **Vendor implementations** - HP, Dell, and Cisco strategies follow identical patterns

**Key difference:**
- **BareMetalHostUCS**: Uses `get_server_info()` for single-server detailed lookups
- **Scan_Servers**: Uses `get_server_profiles()` for bulk scanning with minimal API calls

Both methods are implemented in all vendor strategies, making the codebase reusable across projects.

## Notes

- Only configured vendors are scanned (missing credentials = skipped)
- SSL certificate verification is disabled for self-signed certificates
- Cisco UCS requires the `ucscsdk` and `ucsmsdk` packages
- The scanner connects to each vendor, queries profiles, and disconnects properly
- All vendor implementations follow the same pattern used in the BareMetalHostUCS project
- **READ-ONLY operations**: No data modifications, only queries (GET requests and kubectl get commands)

## Two Scanning Modes

This scanner supports **two distinct use cases**:

### 1. Bulk Scanning - `get_server_profiles(pattern)`
Used by the CLI scanner to **list many servers efficiently**:
- Returns ONLY server profile names (no MAC/BMC data)
- Minimal API calls - very fast
- Used for inventory and availability checking
- Default CLI behavior

### 2. Single Server Lookup - `get_server_info(server_name)`
Used by BareMetalHostUCS project for **detailed single server queries**:
- Returns MAC address + BMC IP for ONE specific server
- Makes necessary API calls to fetch hardware details
- Used when you need to provision/configure a specific server
- Compatible with BareMetalHostUCS interface

## Command Line Options

```
usage: scan_servers.py [-h] [--pattern PATTERN] [--vendor {HP,DELL,CISCO}]
                       [--format {list,table,json}] [--json]
                       [--env-file ENV_FILE] [--check-duplicates]
                       [--show-all] [--verbose]

options:
  -h, --help            show this help message and exit
  --pattern PATTERN, -p PATTERN
                        Regex pattern to match server names (default: ^ocp4-hypershift-.*)
  --vendor {HP,DELL,CISCO}, -v {HP,DELL,CISCO}
                        Scan specific vendor(s) only (can be repeated)
  --format {list,table,json}, -f {list,table,json}
                        Output format: list (default), table (detailed), or json
  --json, -j            Output as JSON (shortcut for --format json)
  --env-file ENV_FILE, -e ENV_FILE
                        Path to .env file with credentials
  --check-duplicates, -d
                        Check for duplicate profile names across vendors
  --show-all            Show all servers including installed ones (default: filter out
                        installed servers if K8S configured)
  --verbose             Enable verbose logging
```
