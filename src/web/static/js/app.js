// Insight-Alpha — App Router & Global Controller

import * as api from './api.js';
import { showToast } from './utils.js';

// --- Screen Registry ---
const screens = {};
let currentScreen = null;
let globalPollTimer = null;

const SCREEN_MODULES = {
    dashboard: './screens/dashboard.js',
    signals: './screens/signals.js',
    positions: './screens/positions.js',
    trades: './screens/trades.js',
    watchlist: './screens/watchlist.js',
    analytics: './screens/analytics.js',
    settings: './screens/settings.js',
};

const PAGE_TITLES = {
    dashboard: 'Dashboard',
    signals: 'Signal Pipeline',
    positions: 'Open Positions',
    trades: 'Trade History',
    watchlist: 'Market Watchlist',
    analytics: 'Performance Analytics',
    settings: 'System Settings',
};

// --- Router ---

function getRoute() {
    const hash = window.location.hash.replace('#/', '').replace('#', '');
    return hash || 'dashboard';
}

async function navigateTo(screenName) {
    const container = document.getElementById('screen-container');
    if (!container) return;

    // Deactivate current screen
    if (currentScreen && screens[currentScreen] && screens[currentScreen].deactivate) {
        screens[currentScreen].deactivate();
    }

    // Load screen module if not cached
    if (!screens[screenName]) {
        try {
            const mod = await import(SCREEN_MODULES[screenName]);
            screens[screenName] = mod;
        } catch (e) {
            console.error(`Failed to load screen: ${screenName}`, e);
            container.innerHTML = `<div class="empty-state">
                <div class="empty-icon">&#9888;</div>
                <div class="empty-text">Failed to load screen</div>
                <div class="empty-hint">${e.message}</div>
            </div>`;
            return;
        }
    }

    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.screen === screenName);
    });

    // Update page title
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = PAGE_TITLES[screenName] || screenName;

    // Render screen
    currentScreen = screenName;
    const mod = screens[screenName];
    if (mod.init) {
        mod.init(container);
    }
    if (mod.activate) {
        mod.activate();
    }

    // Close mobile menu
    document.getElementById('sidebar')?.classList.remove('open');
}

// --- Clock ---

function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'Asia/Kolkata', hour12: false,
    });
    const el = document.getElementById('clock');
    if (el) el.textContent = `IST ${time}`;
}

// --- Global Status Polling ---

async function pollGlobalStatus() {
    try {
        const data = await api.fetchStatus();
        updateGlobalStatusUI(data);
    } catch (e) {
        // silent
    }
}

function updateGlobalStatusUI(data) {
    // Mode badge
    const badge = document.getElementById('mode-badge');
    if (badge) {
        badge.textContent = (data.mode || 'paper').toUpperCase();
        badge.className = `badge badge-${data.mode === 'live' ? 'live' : 'paper'}`;
    }

    // Header status
    const headerDot = document.getElementById('header-status-dot');
    const headerText = document.getElementById('header-status-text');
    const sidebarDot = document.getElementById('sidebar-status-dot');
    const sidebarText = document.getElementById('sidebar-status-text');

    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    if (data.is_running) {
        if (headerDot) headerDot.className = 'status-dot running';
        if (headerText) headerText.textContent = 'Engine Running';
        if (sidebarDot) sidebarDot.className = 'status-dot running';
        if (sidebarText) sidebarText.textContent = 'Engine Running';
        if (btnStart) btnStart.style.display = 'none';
        if (btnStop) btnStop.style.display = 'inline-flex';
    } else if (data.is_authenticated) {
        if (headerDot) headerDot.className = 'status-dot authenticated';
        if (headerText) headerText.textContent = 'Authenticated';
        if (sidebarDot) sidebarDot.className = 'status-dot authenticated';
        if (sidebarText) sidebarText.textContent = 'Authenticated';
        if (btnStart) btnStart.style.display = 'inline-flex';
        if (btnStop) btnStop.style.display = 'none';
    } else {
        if (headerDot) headerDot.className = 'status-dot';
        if (headerText) headerText.textContent = 'Not Connected';
        if (sidebarDot) sidebarDot.className = 'status-dot';
        if (sidebarText) sidebarText.textContent = 'Disconnected';
    }

    // Update nav badge for positions
    const navBadge = document.getElementById('nav-positions-count');
    if (navBadge && data.open_positions != null) {
        navBadge.textContent = data.open_positions;
    }
}

// --- Engine Controls (global) ---

window.__engine = {
    async start() {
        try {
            const data = await api.startEngine();
            if (data.status === 'started') {
                showToast('Trading engine started', 'success');
                pollGlobalStatus();
            } else {
                showToast(data.status || 'Failed to start', 'warning');
            }
        } catch (e) {
            showToast(`Start failed: ${e.message}`, 'error');
        }
    },

    async stop() {
        try {
            await api.stopEngine();
            showToast('Trading engine stopped', 'warning');
            pollGlobalStatus();
        } catch (e) {
            showToast(`Stop failed: ${e.message}`, 'error');
        }
    },

    async cycle() {
        const btn = document.getElementById('btn-cycle');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '&#8987; Running...';
        }
        try {
            await api.runCycle();
            showToast('Scan cycle completed', 'success');
            pollGlobalStatus();
        } catch (e) {
            showToast(`Cycle failed: ${e.message}`, 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '&#8635; Cycle';
            }
        }
    },
};

// --- Mobile Menu ---

function setupMobileMenu() {
    const btn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    if (btn && sidebar) {
        btn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

// --- Init ---

function init() {
    // Clock
    updateClock();
    setInterval(updateClock, 1000);

    // Global status poll
    pollGlobalStatus();
    globalPollTimer = setInterval(pollGlobalStatus, 5000);

    // Mobile menu
    setupMobileMenu();

    // Route
    const route = getRoute();
    navigateTo(route);

    // Hash change listener
    window.addEventListener('hashchange', () => {
        navigateTo(getRoute());
    });
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
