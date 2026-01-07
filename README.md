# Server Scanner

Simple tool to scan HP OneView, Dell OME, and Cisco UCS Central for server profiles.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# For Cisco UCS support (optional)
pip install ucscsdk ucsmsdk

# Configure credentials
cp .env.example .env
# Edit .env with your credentials

# Run the scanner
python scan_servers.py
```

## Usage

```bash
# Scan all vendors for ocp4-hypershift-* servers (default)
python scan_servers.py

# Custom pattern
python scan_servers.py --pattern "ocp4-.*"

# Scan specific vendor only
python scan_servers.py --vendor HP
python scan_servers.py --vendor DELL
python scan_servers.py --vendor CISCO

# Scan multiple vendors
python scan_servers.py --vendor HP --vendor DELL

# Output as JSON
python scan_servers.py --json

# Check for duplicate names across vendors
python scan_servers.py --check-duplicates

# Use specific .env file
python scan_servers.py --env-file /path/to/.env

# Combine options
python scan_servers.py --pattern "ocp4-tlv-.*" --vendor HP --json
```

## Example Output

```
🔍 Scanning for servers matching: ^ocp4-hypershift-.*

  Connecting to HP OneView at 10.0.0.1...
  ✓ Connected to HP OneView
  ✓ Found 5 profiles in HP
  Connecting to Dell OME at 10.0.0.2...
  ✓ Connected to Dell OME
  ✓ Found 8 profiles in DELL
  Connecting to Cisco UCS Central at 10.0.0.3...
  ✓ Connected to Cisco UCS Central
  ✓ Found 3 profiles in CISCO

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

## JSON Output

```bash
python scan_servers.py --json
```

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "servers": {
    "HP": [
      {
        "name": "ocp4-hypershift-rf-001",
        "vendor": "HP",
        "mac_address": "11:22:33:44:55:01",
        "bmc_ip": "10.2.2.101",
        "model": "ProLiant DL360 Gen10"
      }
    ],
    "DELL": [...],
    "CISCO": [...]
  }
}
```

## Duplicate Detection

Find servers with the same name across different vendors:

```bash
python scan_servers.py --check-duplicates
```

```
⚠️  DUPLICATES FOUND across vendors:
   - ocp4-hypershift-server01 exists in: HP, DELL
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ONEVIEW_IP` | HP OneView IP address |
| `ONEVIEW_USERNAME` | HP OneView username |
| `ONEVIEW_PASSWORD` | HP OneView password |
| `OME_IP` | Dell OME IP address |
| `OME_USERNAME` | Dell OME username |
| `OME_PASSWORD` | Dell OME password |
| `UCS_CENTRAL_IP` | Cisco UCS Central IP |
| `UCS_CENTRAL_USERNAME` | UCS Central username |
| `UCS_CENTRAL_PASSWORD` | UCS Central password |
| `UCS_MANAGER_USERNAME` | UCS Manager username |
| `UCS_MANAGER_PASSWORD` | UCS Manager password |

## Notes

- Only configured vendors are scanned (missing credentials = skipped)
- SSL certificate verification is disabled for self-signed certs
- Cisco UCS requires the `ucscsdk` and `ucsmsdk` packages
- The script connects to each vendor, queries profiles, and disconnects
