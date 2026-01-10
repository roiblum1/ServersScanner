# Architecture Documentation

## Overview

This project has been refactored using industry-standard **Design Patterns** to create a maintainable, scalable, and testable codebase.

### Key Features

1. **Zone-based Filtering and Grouping** - Automatically extract zones from server names and filter/group results
2. **Kubernetes Agent Integration** - Filter out already-installed servers using K8S Agent CRD
3. **Multi-vendor Support** - HP OneView, Dell OME, Cisco UCS Central
4. **Clean Architecture** - Separation of concerns, no code duplication, high cohesion

## Design Patterns Used

### 1. Strategy Pattern
**Location**: `src/strategies/`

Each vendor (HP, Dell, Cisco) implements the `VendorStrategy` interface with vendor-specific logic for querying servers.

```python
class VendorStrategy(ABC):
    @abstractmethod
    def get_server_profiles(self, pattern: str) -> List[ServerProfile]:
        pass
```

**Benefits**:
- Easy to add new vendors
- Each vendor's logic is isolated
- Swappable implementations

### 2. Factory Pattern
**Location**: `src/repositories/strategy_factory.py`

Creates vendor strategy instances based on vendor type.

```python
strategy = StrategyFactory.create_strategy(VendorType.HP, credentials)
```

**Benefits**:
- Centralized object creation
- Decouples creation from usage
- Easy to extend with new strategies

### 3. Facade Pattern
**Location**: `src/services/scanner_service.py`

`ScannerService` provides a simple interface to the complex subsystems (vendor strategies, filters, parsers).

```python
scanner = ScannerService(...)
results = scanner.scan(pattern="ocp4-*")
```

**Benefits**:
- Simplified API for clients
- Hides complexity
- Single entry point

### 4. Value Object Pattern
**Location**: `src/models/`

Immutable data structures (`ServerProfile`, `ZoneConfig`) that represent domain concepts.

```python
@dataclass(frozen=True)
class ServerProfile:
    name: str
    vendor: str
    zone: Optional[str] = None
```

**Benefits**:
- Immutability prevents bugs
- Clear domain model
- Type safety

## Project Structure

```
src/
├── models/              # Domain models (Value Objects)
│   ├── server_profile.py
│   └── zone_config.py
│
├── strategies/          # Strategy Pattern - Vendor implementations
│   ├── base_strategy.py     # Abstract base class
│   ├── hp_strategy.py
│   ├── dell_strategy.py
│   └── cisco_strategy.py
│
├── filters/             # Filtering components
│   └── agent_filter.py      # K8S Agent CRD filter
│
├── parsers/             # Parsing utilities
│   ├── hostname_parser.py   # Extract hostname from Agent
│   └── zone_parser.py       # Extract zone from server name
│
├── repositories/        # Factory Pattern
│   └── strategy_factory.py # Creates vendor strategies
│
├── services/            # Business logic (Facade Pattern)
│   └── scanner_service.py   # Main orchestrator
│
└── formatters/          # Output formatting (Strategy Pattern)
    ├── base_formatter.py
    └── zone_vendor_formatter.py
```

## Data Flow

```
scan_servers.py (CLI)
    ↓
ScannerService (Facade)
    ↓
┌─────────────────────────────────────┐
│  1. Create vendor strategies        │
│     (via StrategyFactory)            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  2. Query each vendor for profiles  │
│     (HP, Dell, Cisco strategies)     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  3. Extract zones from server names │
│     (ZoneParser)                     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  4. Filter by configured zones      │
│     (ZoneConfig)                     │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  5. Query K8S Agent resources       │
│     (AgentFilter)                    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  6. Filter out installed servers    │
│     (HostnameParser)                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  7. Group results by zone + vendor  │
│     (ScanResults)                    │
└─────────────────────────────────────┘
    ↓
ZoneVendorFormatter
    ↓
Output (list/table/json)
```

## Key Components

### HostnameParser
**Purpose**: Extract server names from Kubernetes Agent resources

**Logic**:
1. Try `hostname` field first
2. If `hostname` is a MAC address, use `requestedHostname`
3. Only accept names matching `ocp4-hypershift-*`

### ZoneParser
**Purpose**: Extract zone names from server profile names

**Patterns**:
- `ocp4-hypershift-<zone>-01` → `zone`
- `ocp4-hypershift-data<zone>-01` → `zone`
- `ocp4-hypershift-<zone>-l4-01` → `zone`

### AgentFilter
**Purpose**: Query Kubernetes Agent CRD to find installed servers

**API**: Uses `oc get agent -A -o wide`

**Authentication**: Per-cluster tokens (supports multiple clusters)

### ScanResults
**Purpose**: Encapsulate scan results with zone/vendor grouping

**Structure**:
```python
{
    "zone-a": {
        "HP": [ServerProfile(...), ...],
        "DELL": [ServerProfile(...), ...],
        "CISCO": [ServerProfile(...), ...]
    },
    "zone-b": {
        ...
    }
}
```

## SOLID Principles

### Single Responsibility Principle (SRP)
- Each class has ONE reason to change
- `HostnameParser` only parses hostnames
- `ZoneParser` only extracts zones
- `AgentFilter` only queries Kubernetes

### Open/Closed Principle (OCP)
- Open for extension, closed for modification
- Add new vendors by implementing `VendorStrategy`
- Add new output formats by implementing `OutputFormatter`

### Liskov Substitution Principle (LSP)
- Strategies are interchangeable
- Any `VendorStrategy` works in `ScannerService`

### Interface Segregation Principle (ISP)
- Small, focused interfaces
- `VendorStrategy` defines only essential methods

### Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- `ScannerService` depends on `VendorStrategy` interface, not concrete implementations

## Benefits of This Architecture

### Maintainability
- **Clear separation of concerns** - Each component has a single responsibility
- **No code duplication** - Shared logic extracted to utilities
- **Easy to debug** - Small, focused classes

### Scalability
- **Easy to add vendors** - Implement `VendorStrategy` interface
- **Easy to add filters** - Create new filter classes
- **Easy to add output formats** - Implement `OutputFormatter`

### Testability
- **Small units** - Each class can be tested independently
- **Dependency injection** - Easy to mock dependencies
- **Immutable data** - Predictable behavior

### Readability
- **Self-documenting code** - Clear class and method names
- **Type hints** - IDE support and early error detection
- **Design patterns** - Standard patterns developers recognize

## Configuration

### Environment Variables

```bash
# Vendor credentials
ONEVIEW_IP=10.0.0.1
OME_IP=10.0.0.2
UCS_CENTRAL_IP=10.0.0.3

# Zone filtering (optional)
ZONES=zone-a,zone-b,zone-c

# Kubernetes Agent filtering (optional)
K8S_CLUSTER_NAMES=cluster1,cluster2
K8S_DOMAIN_NAME=example.com
K8S_TOKEN=token1,token2  # Per-cluster tokens
K8S_NAMESPACE=assisted-installer
```

## Usage Examples

### Scan all servers in all zones
```bash
python scan_servers.py
```

### Scan specific zones only
```bash
python scan_servers.py --zones zone-a,zone-b
```

### Output as JSON
```bash
python scan_servers.py --format json
```

### Scan specific vendor
```bash
python scan_servers.py --vendor HP
```

### Include installed servers
```bash
python scan_servers.py --show-all
```

## Migration from Old Code

### What Changed

1. **BareMetalHost → Agent CRD**
   - Changed from `baremetalhosts.metal3.io` to `agents.agent-install.openshift.io`
   - Changed namespace from `inventory` to `assisted-installer`

2. **Hostname Logic**
   - Added MAC address detection
   - Falls back to `requestedHostname` when needed

3. **Zone-based Grouping**
   - Results now grouped by zone first, then vendor
   - Zone filtering support via `ZONES` env var

4. **Code Organization**
   - Moved to modular architecture
   - Separated concerns into layers

### Backwards Compatibility

The core functionality remains the same:
- ✅ Vendor strategies unchanged (HP, Dell, Cisco)
- ✅ Pattern matching works the same
- ✅ `.env` file mostly compatible (namespace changed)
- ✅ Command-line interface similar

## Testing Strategy

### Unit Tests (Recommended)

```python
# Test HostnameParser
def test_mac_address_detection():
    assert HostnameParser.is_mac_address("00:1A:2B:3C:4D:5E")
    assert not HostnameParser.is_mac_address("server-name")

# Test ZoneParser
def test_zone_extraction():
    assert ZoneParser.extract_zone("ocp4-hypershift-zone-a-01") == "zone-a"

# Test AgentFilter
def test_agent_filter(mock_k8s_client):
    filter = AgentFilter(config)
    servers = filter.get_installed_servers()
    assert len(servers) > 0
```

### Integration Tests

```bash
# Test with actual credentials
python scan_servers.py --verbose --zones zone-a

# Test Agent filter
python scan_servers.py --show-all  # Without filtering
python scan_servers.py             # With filtering (should show fewer servers)
```

## Future Enhancements

1. **Caching Layer** - Cache vendor API responses
2. **Async/Await** - Parallel vendor queries
3. **Metrics/Observability** - Prometheus metrics
4. **Web UI** - Dashboard for viewing results
5. **Database** - Store historical scan results
6. **Alerts** - Notify when new servers available

## Contributing

When adding new features:

1. Follow existing patterns (Strategy, Factory, etc.)
2. Keep classes small and focused (SRP)
3. Add type hints
4. Update tests
5. Document in this file
