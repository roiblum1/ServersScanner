/**
 * Server Scanner Dashboard - JavaScript
 * Handles data loading, rendering, and user interactions
 */

// ============================================================================
// Configuration
// ============================================================================
const CONFIG = {
    AUTO_REFRESH_INTERVAL: 30000, // 30 seconds
    ANIMATION_DELAY: 50, // Stagger animation delay
};

// ============================================================================
// State Management
// ============================================================================
const state = {
    currentData: null,
    autoRefreshTimer: null,
    isLoading: false,
};

// ============================================================================
// Initialization
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    loadData();
    startAutoRefresh();
}

function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadData());
    }

    // Clear filter button
    const clearBtn = document.getElementById('clearBtn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearFilter);
    }

    // Zone filter input - Enter key
    const zoneFilterInput = document.getElementById('zoneFilter');
    if (zoneFilterInput) {
        zoneFilterInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                loadData();
            }
        });
    }
}

// ============================================================================
// Data Loading
// ============================================================================
async function loadData() {
    if (state.isLoading) return;

    const zoneFilter = document.getElementById('zoneFilter').value.trim();
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const zonesDiv = document.getElementById('zones');
    const clustersDiv = document.getElementById('clusters');
    const clusterPanel = document.getElementById('clusterPanel');

    state.isLoading = true;
    showElement(loading);
    hideElement(error);
    zonesDiv.innerHTML = '';
    clustersDiv.innerHTML = '';

    try {
        const url = zoneFilter
            ? `/api/servers?zone_filter=${encodeURIComponent(zoneFilter)}`
            : '/api/servers';

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        state.currentData = data;

        // Update UI
        updateSummary(data.summary);
        updateCacheInfo(data.cache_info);
        renderZones(data.zones);
        renderClusters(data.clusters);

        showElement(clusterPanel);
        hideElement(loading);
    } catch (err) {
        hideElement(loading);
        showElement(error);
        error.textContent = `⚠️ Error loading data: ${err.message}`;
        console.error('Error:', err);
    } finally {
        state.isLoading = false;
    }
}

// ============================================================================
// Summary Update
// ============================================================================
function updateSummary(summary) {
    animateNumber('availableCount', summary.total_available);
    animateNumber('installedCount', summary.total_installed);
    animateNumber('clusterCount', summary.total_clusters);
    animateNumber('zoneCount', summary.total_zones);
}

function updateCacheInfo(cacheInfo) {
    // Update cache status in header meta chips
    const headerMeta = document.querySelector('.header-meta');
    if (!headerMeta) return;

    // Remove existing cache chip if any
    const existingChip = document.getElementById('cacheChip');
    if (existingChip) existingChip.remove();

    // Create cache chip
    const cacheChip = document.createElement('span');
    cacheChip.id = 'cacheChip';
    cacheChip.className = 'meta-chip';

    if (cacheInfo.cached) {
        const minutes = Math.floor(cacheInfo.age_seconds / 60);
        const nextMinutes = Math.floor(cacheInfo.next_refresh_seconds / 60);
        cacheChip.innerHTML = `🔄 Cached ${minutes}m ago (refresh in ${nextMinutes}m)`;
        cacheChip.title = `Data from cache. Next auto-refresh in ${nextMinutes} minutes`;
    } else {
        cacheChip.innerHTML = `✨ Fresh scan`;
        cacheChip.className = 'meta-chip accent';
        cacheChip.title = 'Data from live scan (just now)';
    }

    headerMeta.appendChild(cacheChip);
}

function animateNumber(elementId, targetValue) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const currentValue = parseInt(element.textContent) || 0;
    const duration = 1000; // 1 second
    const steps = 30;
    const increment = (targetValue - currentValue) / steps;
    let step = 0;

    const timer = setInterval(() => {
        step++;
        if (step >= steps) {
            element.textContent = targetValue;
            clearInterval(timer);
        } else {
            element.textContent = Math.round(currentValue + increment * step);
        }
    }, duration / steps);
}

// ============================================================================
// Zone Rendering
// ============================================================================
function renderZones(zones) {
    const zonesDiv = document.getElementById('zones');

    zones.forEach((zone, index) => {
        const zoneDiv = createZoneElement(zone);

        // Stagger animation
        zoneDiv.style.animationDelay = `${index * CONFIG.ANIMATION_DELAY}ms`;

        zonesDiv.appendChild(zoneDiv);
    });
}

function createZoneElement(zone) {
    const zoneDiv = document.createElement('div');
    zoneDiv.className = 'zone-container';

    // Calculate statistics
    const stats = calculateZoneStats(zone);

    // Create header
    const header = createZoneHeader(zone, stats);
    zoneDiv.appendChild(header);

    // Create vendor sections
    Object.keys(zone.vendors).sort().forEach(vendor => {
        const servers = zone.vendors[vendor];
        if (servers.length === 0) return;

        const vendorSection = createVendorSection(vendor, servers);
        zoneDiv.appendChild(vendorSection);
    });

    return zoneDiv;
}

function createZoneHeader(zone, stats) {
    const header = document.createElement('div');
    header.className = 'zone-header';

    const title = document.createElement('div');
    title.className = 'zone-title';
    title.innerHTML = `📍 ${zone.zone}`;

    const statsDiv = document.createElement('div');
    statsDiv.className = 'zone-stats';
    statsDiv.innerHTML = `
        <span style="color: var(--color-available);">
            <strong>${stats.available}</strong> available
        </span>
        <span style="color: var(--color-installed);">
            <strong>${stats.installed}</strong> installed
        </span>
    `;

    header.appendChild(title);
    header.appendChild(statsDiv);

    return header;
}

function calculateZoneStats(zone) {
    let availableCount = 0;
    let installedCount = 0;

    Object.values(zone.vendors).forEach(servers => {
        servers.forEach(server => {
            if (server.status === 'available') {
                availableCount++;
            } else {
                installedCount++;
            }
        });
    });

    return { available: availableCount, installed: installedCount };
}

function createVendorSection(vendor, servers) {
    const section = document.createElement('div');
    section.className = 'vendor-section';

    const title = document.createElement('div');
    title.className = 'vendor-title';
    title.innerHTML = `${getVendorIcon(vendor)} ${vendor}`;

    const grid = document.createElement('div');
    grid.className = 'server-grid';

    servers.forEach((server, index) => {
        const card = createServerCard(server);
        card.style.animationDelay = `${index * 30}ms`;
        grid.appendChild(card);
    });

    section.appendChild(title);
    section.appendChild(grid);

    return section;
}

function createServerCard(server) {
    const card = document.createElement('div');
    card.className = `server-card ${server.status}`;
    card.title = `${server.name} - ${server.status}`;

    const indicator = document.createElement('div');
    indicator.className = `status-indicator ${server.status}`;

    const info = document.createElement('div');
    info.className = 'server-info';

    const name = document.createElement('div');
    name.className = 'server-name';
    name.textContent = server.name;

    info.appendChild(name);

    if (server.cluster) {
        const cluster = document.createElement('div');
        cluster.className = 'server-cluster';
        cluster.innerHTML = `📦 ${server.cluster}`;
        info.appendChild(cluster);
    }

    card.appendChild(indicator);
    card.appendChild(info);

    // Add click interaction
    card.addEventListener('click', () => showServerDetails(server));

    return card;
}

// ============================================================================
// Cluster Rendering
// ============================================================================
function renderClusters(clusters) {
    const clustersDiv = document.getElementById('clusters');

    if (clusters.length === 0) {
        clustersDiv.innerHTML = '<p style="text-align: center; color: var(--text-muted);">No clusters configured</p>';
        return;
    }

    clusters.forEach((cluster, index) => {
        const clusterDiv = createClusterElement(cluster);
        clusterDiv.style.animationDelay = `${index * CONFIG.ANIMATION_DELAY}ms`;
        clustersDiv.appendChild(clusterDiv);
    });
}

function createClusterElement(cluster) {
    const div = document.createElement('div');
    div.className = 'cluster-item';

    const name = document.createElement('div');
    name.className = 'cluster-name';
    name.textContent = cluster.cluster_name;

    const count = document.createElement('div');
    count.className = 'cluster-count';
    count.innerHTML = `<strong>${cluster.installed_count}</strong> servers installed`;

    div.appendChild(name);
    div.appendChild(count);

    if (cluster.servers.length > 0) {
        const serversDiv = document.createElement('div');
        serversDiv.className = 'cluster-servers';

        cluster.servers.forEach(serverName => {
            const serverItem = document.createElement('div');
            serverItem.textContent = `• ${serverName}`;
            serversDiv.appendChild(serverItem);
        });

        div.appendChild(serversDiv);
    }

    return div;
}

// ============================================================================
// Utility Functions
// ============================================================================
function getVendorIcon(vendor) {
    const icons = {
        'HP': '🔷',
        'DELL': '🔶',
        'CISCO': '🔹',
    };
    return icons[vendor.toUpperCase()] || '📦';
}

function clearFilter() {
    document.getElementById('zoneFilter').value = '';
    loadData();
}

function showElement(element) {
    if (element) element.style.display = 'block';
}

function hideElement(element) {
    if (element) element.style.display = 'none';
}

function showServerDetails(server) {
    // Could open a modal with more details in the future
    console.log('Server details:', server);

    // For now, show a simple alert
    const statusEmoji = server.status === 'available' ? '✅' : '❌';
    const clusterInfo = server.cluster ? `\nCluster: ${server.cluster}` : '';

    alert(`${statusEmoji} ${server.name}\n\nVendor: ${server.vendor}\nZone: ${server.zone}\nStatus: ${server.status}${clusterInfo}`);
}

// ============================================================================
// Auto Refresh
// ============================================================================
function startAutoRefresh() {
    stopAutoRefresh(); // Clear any existing timer

    state.autoRefreshTimer = setInterval(() => {
        console.log('Auto-refreshing data...');
        loadData();
    }, CONFIG.AUTO_REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (state.autoRefreshTimer) {
        clearInterval(state.autoRefreshTimer);
        state.autoRefreshTimer = null;
    }
}

// Stop auto-refresh when page is hidden (battery/performance optimization)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
        loadData(); // Refresh immediately when page becomes visible
    }
});

// ============================================================================
// Export for testing
// ============================================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        loadData,
        updateSummary,
        renderZones,
        renderClusters,
        clearFilter,
    };
}
