/**
 * Server Scanner Dashboard - JavaScript
 * Handles data loading, rendering, and user interactions
 */

// ============================================================================
// Configuration
// ============================================================================
const CONFIG = {
    AUTO_REFRESH_INTERVAL: 300000, // 5 minutes (servers don't change frequently)
    ANIMATION_DELAY: 50, // Stagger animation delay
};

// ============================================================================
// State Management
// ============================================================================
const state = {
    currentData: null,
    autoRefreshTimer: null,
    isLoading: false,
    theme: localStorage.getItem('theme') || 'dark',
};

// ============================================================================
// Theme Management
// ============================================================================
function initializeTheme() {
    if (state.theme === 'light') {
        document.body.classList.add('light-mode');
        document.getElementById('themeIcon').textContent = '🌙';
    } else {
        document.body.classList.remove('light-mode');
        document.getElementById('themeIcon').textContent = '☀️';
    }
}

function toggleTheme() {
    if (state.theme === 'dark') {
        state.theme = 'light';
        document.body.classList.add('light-mode');
        document.getElementById('themeIcon').textContent = '🌙';
    } else {
        state.theme = 'dark';
        document.body.classList.remove('light-mode');
        document.getElementById('themeIcon').textContent = '☀️';
    }
    localStorage.setItem('theme', state.theme);
}

// ============================================================================
// Initialization
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    initializeTheme();
    setupEventListeners();
    loadData();
    startAutoRefresh();
}

function setupEventListeners() {
    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

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
        renderZoneDashboard(data.zones);
        renderZones(data.zones);
        renderClusters(data.clusters);

        showElement(clusterPanel);
        showElement(document.getElementById('zoneDashboard'));
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
    // Update the cache status chip
    const cacheStatus = document.getElementById('cacheStatus');
    if (!cacheStatus) return;

    if (cacheInfo.cached) {
        const minutes = Math.floor(cacheInfo.age_seconds / 60);
        const nextMinutes = Math.floor(cacheInfo.next_refresh_seconds / 60);

        const statusHtml = `
            <span class="status-dot"></span>
            Cached ${minutes}m ago
        `;
        cacheStatus.innerHTML = statusHtml;
        cacheStatus.title = `Data from cache. Next auto-refresh in ${nextMinutes} minutes`;
        cacheStatus.classList.remove('accent');
    } else {
        const statusHtml = `
            <span class="status-dot pulse"></span>
            Live Scan
        `;
        cacheStatus.innerHTML = statusHtml;
        cacheStatus.title = 'Fresh data from live scan';
        cacheStatus.classList.add('accent');
    }
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

    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();

    zones.forEach((zone) => {
        const zoneDiv = createZoneElement(zone);
        fragment.appendChild(zoneDiv);
    });

    // Single DOM update instead of multiple
    zonesDiv.appendChild(fragment);
}

function createZoneElement(zone) {
    const zoneDiv = document.createElement('div');
    zoneDiv.className = 'zone-container';

    // Calculate statistics
    const stats = calculateZoneStats(zone);

    // Create header
    const header = createZoneHeader(zone, stats);
    zoneDiv.appendChild(header);

    // Create content wrapper for collapse functionality
    const contentDiv = document.createElement('div');
    contentDiv.className = 'zone-content';

    // Create vendor sections
    Object.keys(zone.vendors).sort().forEach(vendor => {
        const servers = zone.vendors[vendor];
        if (servers.length === 0) return;

        const vendorSection = createVendorSection(vendor, servers);
        contentDiv.appendChild(vendorSection);
    });

    zoneDiv.appendChild(contentDiv);

    // Add collapse functionality
    header.addEventListener('click', () => {
        zoneDiv.classList.toggle('collapsed');
        // Save collapse state to localStorage
        const collapseStates = JSON.parse(localStorage.getItem('zoneCollapseStates') || '{}');
        collapseStates[zone.zone] = zoneDiv.classList.contains('collapsed');
        localStorage.setItem('zoneCollapseStates', JSON.stringify(collapseStates));
    });

    // Restore collapse state from localStorage
    const collapseStates = JSON.parse(localStorage.getItem('zoneCollapseStates') || '{}');
    if (collapseStates[zone.zone]) {
        zoneDiv.classList.add('collapsed');
    }

    return zoneDiv;
}

function createZoneHeader(zone, stats) {
    const header = document.createElement('div');
    header.className = 'zone-header';

    const title = document.createElement('div');
    title.className = 'zone-title';
    title.innerHTML = `<span class="collapse-icon">▼</span> 📍 ${zone.zone}`;

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

    // Use DocumentFragment for batch DOM updates
    const fragment = document.createDocumentFragment();
    servers.forEach((server) => {
        const card = createServerCard(server);
        fragment.appendChild(card);
    });
    grid.appendChild(fragment);

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
    count.innerHTML = `<strong>${cluster.installed_count}</strong> servers`;

    div.appendChild(name);
    div.appendChild(count);

    // Don't show individual server names - just the total count
    // This keeps the UI clean when there are 400+ servers

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
// Zone Dashboard
// ============================================================================
function renderZoneDashboard(zones) {
    const zoneCardsDiv = document.getElementById('zoneCards');
    zoneCardsDiv.innerHTML = '';

    zones.forEach((zone, index) => {
        const card = createZoneDashboardCard(zone);
        card.style.animationDelay = `${index * 50}ms`;
        zoneCardsDiv.appendChild(card);
    });
}

function createZoneDashboardCard(zone) {
    const card = document.createElement('div');
    card.className = 'zone-stat-card';
    card.style.animation = 'fadeInUp 0.5s ease';

    // Calculate statistics
    const stats = calculateZoneDetailedStats(zone);

    // Header
    const header = document.createElement('div');
    header.className = 'zone-stat-header';
    header.innerHTML = `
        <div class="zone-stat-name">📍 ${zone.zone}</div>
        <div class="zone-stat-total">${stats.total}</div>
    `;
    card.appendChild(header);

    // Stats Grid
    const statsGrid = document.createElement('div');
    statsGrid.className = 'zone-stat-grid';
    statsGrid.innerHTML = `
        <div class="zone-stat-item available">
            <div class="zone-stat-label">Available</div>
            <div class="zone-stat-value">${stats.available}</div>
        </div>
        <div class="zone-stat-item installed">
            <div class="zone-stat-label">Installed</div>
            <div class="zone-stat-value">${stats.installed}</div>
        </div>
    `;
    card.appendChild(statsGrid);

    // Vendor breakdown
    if (Object.keys(stats.vendors).length > 0) {
        const vendorsSection = document.createElement('div');
        vendorsSection.className = 'zone-vendors';
        vendorsSection.innerHTML = '<div class="zone-vendor-title">Vendor Distribution</div>';

        const vendorBars = document.createElement('div');
        vendorBars.className = 'zone-vendor-bars';

        Object.keys(stats.vendors).sort().forEach(vendor => {
            const count = stats.vendors[vendor];
            const percentage = stats.total > 0 ? (count / stats.total * 100) : 0;

            const bar = document.createElement('div');
            bar.className = 'zone-vendor-bar';
            bar.innerHTML = `
                <div class="zone-vendor-name">${vendor}</div>
                <div class="zone-vendor-progress">
                    <div class="zone-vendor-fill ${vendor.toLowerCase()}" style="width: ${percentage}%"></div>
                </div>
                <div class="zone-vendor-count">${count}</div>
            `;
            vendorBars.appendChild(bar);
        });

        vendorsSection.appendChild(vendorBars);
        card.appendChild(vendorsSection);
    }

    return card;
}

function calculateZoneDetailedStats(zone) {
    let available = 0;
    let installed = 0;
    const vendors = {};

    Object.keys(zone.vendors).forEach(vendor => {
        const servers = zone.vendors[vendor];
        let vendorCount = 0;

        servers.forEach(server => {
            vendorCount++;
            if (server.status === 'available') {
                available++;
            } else {
                installed++;
            }
        });

        if (vendorCount > 0) {
            vendors[vendor] = vendorCount;
        }
    });

    return {
        total: available + installed,
        available,
        installed,
        vendors
    };
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
