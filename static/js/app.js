/**
 * Server Scanner Dashboard — JavaScript
 * Features:
 *  - Hardware details on every server card
 *  - Inline maintenance button per card
 *  - Live name search (client-side, no API call)
 *  - Status filter pills (All / Available / Installed / Maintenance)
 *  - Zone filter (API-level)
 *  - Unified server detail + maintenance modal
 */

// ============================================================================
// State
// ============================================================================
const state = {
    currentData: null,
    isLoading: false,
    theme: localStorage.getItem('theme') || 'dark',
    statusFilter: 'all',   // 'all' | 'available' | 'installed' | 'maintenance'
    searchQuery: '',
    allZones: [],          // full zone list from unfiltered load
    page: 1,
    pageSize: 500,
};

// ============================================================================
// Theme
// ============================================================================
function initializeTheme() {
    const isLight = state.theme === 'light';
    document.body.classList.toggle('light-mode', isLight);
    document.getElementById('themeIcon').textContent = isLight ? '🌙' : '☀️';
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', state.theme);
    initializeTheme();
}

// ============================================================================
// Init
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    setupEventListeners();
    loadData();
});

function setupEventListeners() {
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
    document.getElementById('refreshBtn').addEventListener('click', () => loadData());
    document.getElementById('clearBtn').addEventListener('click', clearFilters);

    // Zone dropdown — reload data on selection change (reset to page 1)
    document.getElementById('zoneFilter').addEventListener('change', () => {
        state.page = 1;
        loadData();
    });

    // Server name search — live client-side filter
    document.getElementById('serverSearch').addEventListener('input', e => {
        state.searchQuery = e.target.value.trim().toLowerCase();
        applyClientFilters();
    });

    // Status pills
    document.getElementById('statusPills').addEventListener('click', e => {
        const btn = e.target.closest('[data-status]');
        if (!btn) return;
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        state.statusFilter = btn.dataset.status;
        applyClientFilters();
    });

    // Modal ESC
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeServerModal();
    });

    // Char counter
    document.getElementById('maintenanceReason').addEventListener('input', e => {
        document.getElementById('reasonCharCount').textContent = e.target.value.length;
    });
}

// ============================================================================
// Data Loading
// ============================================================================
async function loadData(forceRefresh = false) {
    if (state.isLoading) return;
    state.isLoading = true;

    const zoneFilter = document.getElementById('zoneFilter').value.trim();
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const zonesDiv = document.getElementById('zones');

    loading.style.display = 'block';
    error.style.display = 'none';
    zonesDiv.innerHTML = '';

    try {
        const params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
        if (zoneFilter) params.set('zone_filter', zoneFilter);
        if (forceRefresh) params.set('force_refresh', 'true');
        const url = `/api/servers?${params}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        state.currentData = data;

        updateSummary(data.summary);
        updateCacheInfo(data.cache_info);
        renderZoneDashboard(data.zones);
        renderZones(data.zones);
        renderClusters(data.clusters);
        renderPagination(data.pagination);

        // Only update the full zone list when loading unfiltered (all zones)
        const selectedZone = document.getElementById('zoneFilter').value;
        if (!selectedZone) state.allZones = data.zones;
        populateZoneDropdown(state.allZones);

        document.getElementById('clusterPanel').style.display = 'block';
        document.getElementById('zoneDashboard').style.display = 'block';
        loading.style.display = 'none';

        // Re-apply any active client-side filters
        applyClientFilters();

    } catch (err) {
        loading.style.display = 'none';
        error.style.display = 'block';
        error.textContent = `⚠️ Error loading data: ${err.message}`;
    } finally {
        state.isLoading = false;
    }
}

// ============================================================================
// Client-side filtering (search + status pill)
// ============================================================================
function applyClientFilters() {
    const cards = document.querySelectorAll('.server-card');
    let visible = 0;

    cards.forEach(card => {
        const name = (card.dataset.name || '').toLowerCase();
        const status = card.dataset.status || '';

        const matchesSearch = !state.searchQuery || name.includes(state.searchQuery);
        const matchesStatus = state.statusFilter === 'all' || status === state.statusFilter;

        const show = matchesSearch && matchesStatus;
        card.style.display = show ? '' : 'none';
        if (show) visible++;
    });

    // Show match count when filtering
    const matchEl = document.getElementById('matchCount');
    if (state.searchQuery || state.statusFilter !== 'all') {
        matchEl.style.display = 'block';
        matchEl.textContent = `${visible} server${visible !== 1 ? 's' : ''} match`;
    } else {
        matchEl.style.display = 'none';
    }

    // Hide vendor sections that have no visible cards
    document.querySelectorAll('.vendor-section').forEach(sec => {
        const anyVisible = [...sec.querySelectorAll('.server-card')]
            .some(c => c.style.display !== 'none');
        sec.style.display = anyVisible ? '' : 'none';
    });

    // Hide zone containers that have no visible cards
    document.querySelectorAll('.zone-container').forEach(zone => {
        const anyVisible = [...zone.querySelectorAll('.server-card')]
            .some(c => c.style.display !== 'none');
        zone.style.display = anyVisible ? '' : 'none';
    });
}

// ============================================================================
// Pagination
// ============================================================================
function renderPagination(pagination) {
    const el = document.getElementById('pagination');
    if (!pagination || pagination.total_pages <= 1) {
        el.style.display = 'none';
        return;
    }

    const { page, total_pages, total, page_size } = pagination;
    const from = (page - 1) * page_size + 1;
    const to = Math.min(page * page_size, total);

    el.innerHTML = '';
    el.style.display = 'flex';

    const prevBtn = document.createElement('button');
    prevBtn.textContent = '← Prev';
    prevBtn.disabled = page <= 1;
    prevBtn.addEventListener('click', () => { state.page = page - 1; loadData(); });

    const info = document.createElement('span');
    info.className = 'page-info';
    info.textContent = `${from}–${to} of ${total}`;

    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Next →';
    nextBtn.disabled = page >= total_pages;
    nextBtn.addEventListener('click', () => { state.page = page + 1; loadData(); });

    el.appendChild(prevBtn);
    el.appendChild(info);
    el.appendChild(nextBtn);
}

function clearFilters() {
    document.getElementById('serverSearch').value = '';
    document.getElementById('zoneFilter').value = '';
    state.searchQuery = '';
    state.statusFilter = 'all';
    state.page = 1;
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    document.querySelector('.pill[data-status="all"]').classList.add('active');
    loadData();
}

// ============================================================================
// Zone dropdown — populated from API data
// ============================================================================
function populateZoneDropdown(zones) {
    const select = document.getElementById('zoneFilter');
    const current = select.value;

    // Keep the "All zones" placeholder, replace zone options
    while (select.options.length > 1) select.remove(1);

    zones.forEach(z => {
        const opt = document.createElement('option');
        opt.value = z.zone;
        opt.textContent = `📍 ${z.zone}`;
        select.appendChild(opt);
    });

    // Restore previous selection if still valid
    if (current && [...select.options].some(o => o.value === current)) {
        select.value = current;
    }
}

// ============================================================================
// Summary
// ============================================================================
function updateSummary(summary) {
    animateNumber('availableCount', summary.total_available);
    animateNumber('installedCount', summary.total_installed);
    animateNumber('clusterCount', summary.total_clusters);
    animateNumber('zoneCount', summary.total_zones);
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    const from = parseInt(el.textContent) || 0;
    const steps = 30;
    let step = 0;
    const timer = setInterval(() => {
        step++;
        el.textContent = step >= steps ? target : Math.round(from + (target - from) * step / steps);
        if (step >= steps) clearInterval(timer);
    }, 1000 / steps);
}

function updateCacheInfo(info) {
    const el = document.getElementById('cacheStatus');
    if (!el) return;
    if (info.cached) {
        el.innerHTML = `<span class="status-dot"></span> Cached ${Math.floor(info.age_seconds / 60)}m ago`;
        el.classList.remove('accent');
    } else {
        el.innerHTML = `<span class="status-dot pulse"></span> Live Scan`;
        el.classList.add('accent');
    }
}

// ============================================================================
// Zone rendering
// ============================================================================
function renderZones(zones) {
    const container = document.getElementById('zones');
    const frag = document.createDocumentFragment();
    zones.forEach(zone => frag.appendChild(createZoneElement(zone)));
    container.appendChild(frag);
}

function createZoneElement(zone) {
    const div = document.createElement('div');
    div.className = 'zone-container';

    const stats = calcZoneStats(zone);
    div.appendChild(createZoneHeader(zone, stats));

    const content = document.createElement('div');
    content.className = 'zone-content';

    Object.keys(zone.vendors).sort().forEach(vendor => {
        const servers = zone.vendors[vendor];
        if (servers.length) content.appendChild(createVendorSection(vendor, servers));
    });

    div.appendChild(content);

    div.querySelector('.zone-header').addEventListener('click', () => {
        div.classList.toggle('collapsed');
        const states = JSON.parse(localStorage.getItem('zoneCollapseStates') || '{}');
        states[zone.zone] = div.classList.contains('collapsed');
        localStorage.setItem('zoneCollapseStates', JSON.stringify(states));
    });

    const states = JSON.parse(localStorage.getItem('zoneCollapseStates') || '{}');
    if (states[zone.zone]) div.classList.add('collapsed');

    return div;
}

function createZoneHeader(zone, stats) {
    const h = document.createElement('div');
    h.className = 'zone-header';
    h.innerHTML = `
        <div class="zone-title"><span class="collapse-icon">▼</span> 📍 ${zone.zone}</div>
        <div class="zone-stats">
            <span style="color:var(--success)"><strong>${stats.available}</strong> available</span>
            <span style="color:var(--danger)"><strong>${stats.installed}</strong> installed</span>
            ${stats.maintenance ? `<span style="color:var(--color-maintenance)"><strong>${stats.maintenance}</strong> maintenance</span>` : ''}
        </div>`;
    return h;
}

function calcZoneStats(zone) {
    let available = 0, installed = 0, maintenance = 0;
    Object.values(zone.vendors).flat().forEach(s => {
        if (s.status === 'available') available++;
        else if (s.status === 'installed') installed++;
        else if (s.status === 'maintenance') maintenance++;
    });
    return { available, installed, maintenance };
}

function createVendorSection(vendor, servers) {
    const sec = document.createElement('div');
    sec.className = 'vendor-section';
    sec.innerHTML = `<div class="vendor-title">${getVendorIcon(vendor)} ${vendor}</div>`;

    const grid = document.createElement('div');
    grid.className = 'server-grid';
    const frag = document.createDocumentFragment();
    servers.forEach(s => frag.appendChild(createServerCard(s)));
    grid.appendChild(frag);
    sec.appendChild(grid);
    return sec;
}

// ============================================================================
// Server Card — compact: name, model/serial, cluster info
// ============================================================================
function createServerCard(server) {
    const card = document.createElement('div');
    card.className = `server-card ${server.status}`;
    card.dataset.name = server.name.toLowerCase();
    card.dataset.status = server.status;

    const dot = document.createElement('div');
    dot.className = `status-indicator ${server.status}`;

    const info = document.createElement('div');
    info.className = 'server-info';

    // Server name
    const nameRow = document.createElement('div');
    nameRow.className = 'server-name';
    nameRow.textContent = server.name;
    info.appendChild(nameRow);

    // Model · S/N  (only hardware shown on card)
    if (server.model || server.serial) {
        const modelRow = document.createElement('div');
        modelRow.className = 'server-hw-row';
        modelRow.textContent = [
            server.model,
            server.serial ? `S/N: ${server.serial}` : '',
        ].filter(Boolean).join('  ·  ');
        info.appendChild(modelRow);
    }

    // Installed: management cluster + hosted cluster
    if (server.cluster) {
        const clusterRow = document.createElement('div');
        clusterRow.className = 'server-cluster';
        clusterRow.innerHTML = `📦 ${server.cluster}`;
        info.appendChild(clusterRow);
    }
    if (server.deployment_cluster) {
        const depRow = document.createElement('div');
        depRow.className = 'server-deployment';
        depRow.innerHTML = `🚀 ${server.deployment_cluster}`;
        info.appendChild(depRow);
    }

    // Maintenance badge on card
    if (server.maintenance) {
        const maintBanner = document.createElement('div');
        maintBanner.className = 'card-maint-banner';
        maintBanner.innerHTML = `<span class="severity-badge ${server.maintenance.severity}">${server.maintenance.severity.toUpperCase()}</span> ${server.maintenance.reason}`;
        info.appendChild(maintBanner);
    }

    card.appendChild(dot);
    card.appendChild(info);

    // Maintenance quick-action button
    const maintBtn = document.createElement('button');
    maintBtn.className = `card-maint-btn ${server.status === 'maintenance' ? 'is-maint' : ''}`;
    maintBtn.title = server.status === 'maintenance' ? 'View / remove maintenance' : 'Set maintenance';
    maintBtn.innerHTML = server.status === 'maintenance' ? '⚠️' : '🔧';
    maintBtn.addEventListener('click', e => {
        e.stopPropagation();
        openServerModal(server, true);
    });
    card.appendChild(maintBtn);

    // Click → full detail modal
    card.addEventListener('click', () => openServerModal(server, false));

    return card;
}

function formatDiskSize(total_disk_gb) {
    if (!total_disk_gb) return null;
    if (total_disk_gb >= 1024) return `${(total_disk_gb / 1024).toFixed(1)} TB`;
    return `${total_disk_gb} GB`;
}

function getVendorIcon(v) {
    return { HP: '🔷', DELL: '🔶', CISCO: '🔹' }[v.toUpperCase()] || '📦';
}

// ============================================================================
// Zone Dashboard
// ============================================================================
function renderZoneDashboard(zones) {
    const container = document.getElementById('zoneCards');
    container.innerHTML = '';
    zones.forEach((zone, i) => {
        const card = createZoneDashboardCard(zone);
        card.style.animationDelay = `${i * 50}ms`;
        container.appendChild(card);
    });
}

function createZoneDashboardCard(zone) {
    const card = document.createElement('div');
    card.className = 'zone-stat-card';
    card.style.animation = 'fadeInUp 0.5s ease';

    const stats = calcZoneStats(zone);
    const total = stats.available + stats.installed + stats.maintenance;

    card.innerHTML = `
        <div class="zone-stat-header">
            <div class="zone-stat-name">📍 ${zone.zone}</div>
            <div class="zone-stat-total">${total}</div>
        </div>
        <div class="zone-stat-grid">
            <div class="zone-stat-item available"><div class="zone-stat-label">Available</div><div class="zone-stat-value">${stats.available}</div></div>
            <div class="zone-stat-item installed"><div class="zone-stat-label">Installed</div><div class="zone-stat-value">${stats.installed}</div></div>
            ${stats.maintenance ? `<div class="zone-stat-item maint"><div class="zone-stat-label">Maintenance</div><div class="zone-stat-value">${stats.maintenance}</div></div>` : ''}
        </div>`;

    const vendors = {};
    Object.keys(zone.vendors).forEach(v => { vendors[v] = zone.vendors[v].length; });
    if (Object.keys(vendors).length) {
        const vHtml = Object.keys(vendors).sort().map(v => {
            const pct = total ? (vendors[v] / total * 100) : 0;
            return `<div class="zone-vendor-bar">
                <div class="zone-vendor-name">${v}</div>
                <div class="zone-vendor-progress"><div class="zone-vendor-fill ${v.toLowerCase()}" style="width:${pct}%"></div></div>
                <div class="zone-vendor-count">${vendors[v]}</div>
            </div>`;
        }).join('');
        card.innerHTML += `<div class="zone-vendors"><div class="zone-vendor-title">Vendor Distribution</div><div class="zone-vendor-bars">${vHtml}</div></div>`;
    }

    return card;
}

// ============================================================================
// Clusters
// ============================================================================
function renderClusters(clusters) {
    const container = document.getElementById('clusters');
    container.innerHTML = '';
    if (!clusters.length) {
        container.innerHTML = '<p style="text-align:center;color:var(--text-muted)">No clusters configured</p>';
        return;
    }
    clusters.forEach((c, i) => {
        const div = document.createElement('div');
        div.className = 'cluster-item';
        div.style.animationDelay = `${i * 50}ms`;
        div.innerHTML = `<div class="cluster-name">${c.cluster_name}</div><div class="cluster-count"><strong>${c.installed_count}</strong> servers</div>`;
        container.appendChild(div);
    });
}

// ============================================================================
// Server Detail + Maintenance Modal
// ============================================================================
let currentServer = null;

function openServerModal(server, focusMaintenance) {
    currentServer = server;

    document.getElementById('modalTitle').textContent = server.name;
    document.getElementById('modalVendorBadge').textContent =
        `${getVendorIcon(server.vendor)} ${server.vendor}  ·  ${server.zone || 'Unknown zone'}`;

    // Build hardware grid
    const hw = [
        ['Model', server.model],
        ['Serial', server.serial],
        ['CPU', formatCPU(server)],
        ['Memory', server.memory_gb ? `${server.memory_gb} GB` : null],
        ['Storage', formatDiskSize(server.total_disk_gb)],
    ].filter(([, v]) => v);

    const hwGrid = document.getElementById('hwGrid');
    hwGrid.innerHTML = hw.length
        ? hw.map(([l, v]) => `<div class="hw-item"><div class="hw-label">${l}</div><div class="hw-value">${v}</div></div>`).join('')
        : '<div class="hw-empty">No hardware details available yet — run the daily sync to populate.</div>';

    // Network grid
    const net = [
        ['BMC Address', server.bmc_address],
        ['MAC Address', server.mac_address],
        ['Cluster', server.cluster],
        ['Deployed to', server.deployment_cluster],
    ].filter(([, v]) => v);

    const netSection = document.getElementById('netSection');
    const netGrid = document.getElementById('netGrid');
    if (net.length) {
        netGrid.innerHTML = net.map(([l, v]) => `<div class="hw-item"><div class="hw-label">${l}</div><div class="hw-value mono">${v}</div></div>`).join('');
        netSection.style.display = '';
    } else {
        netSection.style.display = 'none';
    }

    // Maintenance section
    const form = document.getElementById('maintenanceForm');
    const view = document.getElementById('maintenanceView');

    if (server.maintenance) {
        view.style.display = 'block';
        form.style.display = 'none';
        document.getElementById('viewReason').textContent = server.maintenance.reason;
        const badge = document.getElementById('viewSeverity');
        badge.textContent = server.maintenance.severity.toUpperCase();
        badge.className = `severity-badge ${server.maintenance.severity}`;
        document.getElementById('viewTimestamp').textContent =
            new Date(server.maintenance.timestamp).toLocaleString();
        document.getElementById('viewCreatedBy').textContent =
            server.maintenance.created_by ? `by ${server.maintenance.created_by}` : '';
    } else {
        view.style.display = 'none';
        form.style.display = 'block';
        document.getElementById('maintenanceReason').value = '';
        document.getElementById('maintenanceSeverity').value = 'medium';
        document.getElementById('reasonCharCount').textContent = '0';
    }

    const modal = document.getElementById('serverModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    if (focusMaintenance) {
        setTimeout(() => {
            const maintSection = modal.querySelector('.modal-section:last-child');
            if (maintSection) maintSection.scrollIntoView({ behavior: 'smooth' });
        }, 100);
    }
}

function formatCPU(s) {
    if (!s.cpu_model && !s.cpu_count) return null;
    const parts = [];
    if (s.cpu_count) parts.push(`${s.cpu_count}×`);
    if (s.cpu_model) parts.push(s.cpu_model);
    if (s.cpu_cores) parts.push(`(${s.cpu_cores} cores/socket)`);
    return parts.join(' ') || null;
}

function closeServerModal() {
    document.getElementById('serverModal').style.display = 'none';
    document.body.style.overflow = '';
    currentServer = null;
}

function updateCardInPlace(server) {
    const card = document.querySelector(`.server-card[data-name="${server.name.toLowerCase()}"]`);
    if (!card) return;

    // Update classes and data attributes
    card.className = `server-card ${server.status}`;
    card.dataset.status = server.status;

    // Update status dot
    const dot = card.querySelector('.status-indicator');
    if (dot) dot.className = `status-indicator ${server.status}`;

    const info = card.querySelector('.server-info');

    // Rebuild cluster rows (remove stale, add if installed/maintenance+installed)
    info.querySelectorAll('.server-cluster, .server-deployment').forEach(el => el.remove());
    if (server.cluster) {
        const clusterRow = document.createElement('div');
        clusterRow.className = 'server-cluster';
        clusterRow.innerHTML = `📦 ${server.cluster}`;
        const banner = info.querySelector('.card-maint-banner');
        banner ? info.insertBefore(clusterRow, banner) : info.appendChild(clusterRow);
    }
    if (server.deployment_cluster) {
        const depRow = document.createElement('div');
        depRow.className = 'server-deployment';
        depRow.innerHTML = `🚀 ${server.deployment_cluster}`;
        const banner = info.querySelector('.card-maint-banner');
        banner ? info.insertBefore(depRow, banner) : info.appendChild(depRow);
    }

    // Update or remove maintenance banner
    const existing = info.querySelector('.card-maint-banner');
    if (existing) existing.remove();
    if (server.maintenance) {
        const banner = document.createElement('div');
        banner.className = 'card-maint-banner';
        banner.innerHTML = `<span class="severity-badge ${server.maintenance.severity}">${server.maintenance.severity.toUpperCase()}</span> ${server.maintenance.reason}`;
        info.appendChild(banner);
    }

    // Update maintenance button
    const btn = card.querySelector('.card-maint-btn');
    if (btn) {
        btn.className = `card-maint-btn ${server.status === 'maintenance' ? 'is-maint' : ''}`;
        btn.title = server.status === 'maintenance' ? 'View / remove maintenance' : 'Set maintenance';
        btn.innerHTML = server.status === 'maintenance' ? '⚠️' : '🔧';
    }

    // Re-apply client filters so status pill filter stays correct
    applyClientFilters();
}

async function submitMaintenance() {
    const reason = document.getElementById('maintenanceReason').value.trim();
    if (!reason) {
        document.getElementById('maintenanceReason').focus();
        return;
    }
    const severity = document.getElementById('maintenanceSeverity').value;

    try {
        const res = await fetch(`/api/servers/${encodeURIComponent(currentServer.name)}/maintenance`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason, severity, timestamp: new Date().toISOString(), created_by: null }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`);
        // Save pre-maintenance state so removal can restore it correctly
        const card = document.querySelector(`.server-card[data-name="${currentServer.name.toLowerCase()}"]`);
        if (card) {
            card.dataset.preStatus = currentServer.status;
            card.dataset.preCluster = currentServer.cluster || '';
            card.dataset.preDeployment = currentServer.deployment_cluster || '';
        }
        currentServer.maintenance = { reason, severity, timestamp: new Date().toISOString(), created_by: null };
        currentServer.status = 'maintenance';
        updateCardInPlace(currentServer);
        closeServerModal();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function removeMaintenance() {
    if (!confirm(`Remove maintenance from ${currentServer.name}?`)) return;
    try {
        const res = await fetch(`/api/servers/${encodeURIComponent(currentServer.name)}/maintenance`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // Restore pre-maintenance status (could be 'installed' or 'available')
        const card = document.querySelector(`.server-card[data-name="${currentServer.name.toLowerCase()}"]`);
        currentServer.maintenance = null;
        currentServer.status = card?.dataset.preStatus || 'available';
        currentServer.cluster = card?.dataset.preCluster || null;
        currentServer.deployment_cluster = card?.dataset.preDeployment || null;
        updateCardInPlace(currentServer);
        closeServerModal();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}
