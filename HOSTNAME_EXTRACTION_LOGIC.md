# Agent Hostname Extraction Logic

## Overview

This document explains how server names are extracted from Kubernetes Agent CRD resources.

## Priority Order

### 1. Extract Fields from Agent CRD

```
Agent CRD
├── spec
│   ├── hostname            → Priority 1
│   └── requestedHostname   → Priority 1
└── status
    ├── inventory
    │   └── hostname        → Priority 2 (fallback)
    └── requestedHostname   → Priority 2 (fallback)
```

**Code**:
```python
# Primary source: spec fields
hostname = spec.get("hostname") or inventory.get("hostname")
requested_hostname = spec.get("requestedHostname") or status.get("requestedHostname")
```

### 2. MAC Address Detection and Selection

The `HostnameParser` then decides which field to use:

```
┌─────────────────────────────────────────┐
│  hostname = "00:1a:2b:3c:4d:5e"        │  ← MAC address detected
│  requestedHostname = "ocp4-hypershift-1"│
└─────────────────────────────────────────┘
              ↓
    ┌─────────────────────┐
    │ Is hostname a MAC?  │
    └─────────────────────┘
              ↓
         ┌────┴────┐
         │   YES   │
         └────┬────┘
              ↓
    Use requestedHostname
         "ocp4-hypershift-1"  ✅
```

```
┌─────────────────────────────────────────┐
│  hostname = "ocp4-hypershift-worker-01" │  ← Valid hostname
│  requestedHostname = "something-else"   │
└─────────────────────────────────────────┘
              ↓
    ┌─────────────────────┐
    │ Is hostname a MAC?  │
    └─────────────────────┘
              ↓
         ┌────┴────┐
         │   NO    │
         └────┬────┘
              ↓
       Use hostname
    "ocp4-hypershift-worker-01"  ✅
```

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Extract from Agent CRD                              │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Check spec.hostname first                                    │
│   - If exists → use it                                       │
│   - If not → fallback to status.inventory.hostname           │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Check spec.requestedHostname first                           │
│   - If exists → use it                                       │
│   - If not → fallback to status.requestedHostname            │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Pass to HostnameParser                               │
└──────────────────────────────────────────────────────────────┘
                           ↓
                  ┌────────────────┐
                  │ Is hostname    │
                  │ a MAC address? │
                  └────────────────┘
                           ↓
                    ┌──────┴──────┐
                    │             │
                   YES            NO
                    │             │
                    ↓             ↓
         ┌──────────────────┐  ┌──────────────────┐
         │ Use requested    │  │ Use hostname     │
         │ Hostname         │  │                  │
         └──────────────────┘  └──────────────────┘
                    │             │
                    └──────┬──────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 3: Validate Pattern                                     │
│   - Must contain "ocp4-hypershift"                           │
│   - If doesn't match → return None                           │
│   - If matches → return server name                          │
└──────────────────────────────────────────────────────────────┘
```

## Examples

### Example 1: Normal Hostname in spec

```yaml
apiVersion: agent-install.openshift.io/v1beta1
kind: Agent
spec:
  hostname: "ocp4-hypershift-worker-01"
  requestedHostname: null
status:
  inventory:
    hostname: "00:1a:2b:3c:4d:5e"
  requestedHostname: null
```

**Result**:
- Extracted hostname: `"ocp4-hypershift-worker-01"` (from spec.hostname)
- Extracted requestedHostname: `null`
- MAC check: NO (valid hostname)
- **Final**: `"ocp4-hypershift-worker-01"` ✅

### Example 2: MAC Address in spec.hostname

```yaml
apiVersion: agent-install.openshift.io/v1beta1
kind: Agent
spec:
  hostname: "00:1a:2b:3c:4d:5e"
  requestedHostname: "ocp4-hypershift-worker-02"
status:
  inventory:
    hostname: "00:1a:2b:3c:4d:5e"
  requestedHostname: null
```

**Result**:
- Extracted hostname: `"00:1a:2b:3c:4d:5e"` (from spec.hostname)
- Extracted requestedHostname: `"ocp4-hypershift-worker-02"` (from spec.requestedHostname)
- MAC check: YES (hostname is MAC)
- **Final**: `"ocp4-hypershift-worker-02"` ✅

### Example 3: Fallback to status fields

```yaml
apiVersion: agent-install.openshift.io/v1beta1
kind: Agent
spec:
  hostname: null
  requestedHostname: null
status:
  inventory:
    hostname: "ocp4-hypershift-worker-03"
  requestedHostname: null
```

**Result**:
- Extracted hostname: `"ocp4-hypershift-worker-03"` (fallback to status.inventory.hostname)
- Extracted requestedHostname: `null`
- MAC check: NO (valid hostname)
- **Final**: `"ocp4-hypershift-worker-03"` ✅

### Example 4: MAC in status, requestedHostname in status

```yaml
apiVersion: agent-install.openshift.io/v1beta1
kind: Agent
spec:
  hostname: null
  requestedHostname: null
status:
  inventory:
    hostname: "001a2b3c4d5e"
  requestedHostname: "ocp4-hypershift-worker-04"
```

**Result**:
- Extracted hostname: `"001a2b3c4d5e"` (fallback to status.inventory.hostname)
- Extracted requestedHostname: `"ocp4-hypershift-worker-04"` (fallback to status.requestedHostname)
- MAC check: YES (hostname is MAC without separators)
- **Final**: `"ocp4-hypershift-worker-04"` ✅

## MAC Address Patterns

The hostname parser recognizes these MAC address formats:

```python
# With separators (colon or dash)
"00:1a:2b:3c:4d:5e"  ✅
"00-1a-2b-3c-4d-5e"  ✅

# Without separators
"001a2b3c4d5e"       ✅

# Not MAC addresses
"ocp4-hypershift-worker-01"  ❌ (valid hostname)
"localhost"                   ❌ (valid hostname)
```

## Pattern Validation

After selecting the hostname, it must match the pattern:

```python
SERVER_NAME_PATTERN = re.compile(r'ocp4-hypershift', re.IGNORECASE)
```

**Examples**:
- `"ocp4-hypershift-worker-01"` ✅ Matches
- `"ocp4-hypershift-master-a"` ✅ Matches
- `"random-hostname"` ❌ Rejected
- `"worker-01"` ❌ Rejected

## Code References

### Files

1. **[src/filters/agent_filter.py](src/filters/agent_filter.py#L185-L220)**
   - `_extract_agent_hostnames()` - Extracts hostname and requestedHostname from Agent CRD

2. **[src/parsers/hostname_parser.py](src/parsers/hostname_parser.py)**
   - `is_mac_address()` - Detects MAC addresses
   - `is_valid_server_name()` - Validates against pattern
   - `extract_hostname()` - Main logic for selecting hostname

### Key Methods

```python
# Agent Filter (src/filters/agent_filter.py)
def _extract_agent_hostnames(self, agent: dict) -> tuple[Optional[str], Optional[str]]:
    spec = agent.get("spec", {})
    status = agent.get("status", {})
    inventory = status.get("inventory", {})

    # Priority: spec → status
    hostname = spec.get("hostname") or inventory.get("hostname")
    requested_hostname = spec.get("requestedHostname") or status.get("requestedHostname")

    return hostname, requested_hostname
```

```python
# Hostname Parser (src/parsers/hostname_parser.py)
def extract_hostname(cls, hostname: Optional[str], requested_hostname: Optional[str]) -> Optional[str]:
    # If hostname is valid (not MAC), use it
    if hostname and not cls.is_mac_address(hostname):
        if cls.is_valid_server_name(hostname):
            return hostname

    # If hostname is MAC, try requestedHostname
    if hostname and cls.is_mac_address(hostname):
        if requested_hostname and cls.is_valid_server_name(requested_hostname):
            return requested_hostname

    # Fallback to requestedHostname
    if requested_hostname and cls.is_valid_server_name(requested_hostname):
        return requested_hostname

    return None
```

## Debugging

Enable debug logging to see hostname extraction:

```bash
python3 -m src.scan_servers --verbose
```

Look for log lines like:
```
DEBUG - Agent hostnames - hostname: 00:1a:2b:3c:4d:5e, requestedHostname: ocp4-hypershift-worker-01
DEBUG - Found Agent with server name: ocp4-hypershift-worker-01
```

## Summary

**The logic is simple**:
1. **Try spec fields first** (user's intent)
2. **Fall back to status fields** (observed state)
3. **If hostname is MAC** → use requestedHostname
4. **Otherwise** → use hostname
5. **Validate** against pattern (ocp4-hypershift)

This ensures we always get the most accurate server name from Agent CRDs.
