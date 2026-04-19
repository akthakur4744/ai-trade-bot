// Insight-Alpha — Centralized API Client

const BASE = '';

async function request(url, options = {}) {
    try {
        const res = await fetch(BASE + url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ message: res.statusText }));
            throw new Error(err.message || res.statusText);
        }
        return await res.json();
    } catch (e) {
        console.error(`API ${url}:`, e);
        throw e;
    }
}

// --- Engine Status ---

export function fetchStatus() {
    return request('/api/status');
}

// --- Portfolio ---

export function fetchPortfolio() {
    return request('/api/portfolio');
}

// --- Alerts ---

export function fetchAlerts() {
    return request('/api/alerts');
}

// --- Signals ---

export function fetchSignals() {
    return request('/api/signals');
}

export function fetchSignalHistory(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/signals/history${qs ? '?' + qs : ''}`);
}

// --- Trades ---

export function fetchTrades() {
    return request('/api/trades');
}

export function fetchTradeHistory(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/trades/history${qs ? '?' + qs : ''}`);
}

// --- Analytics ---

export function fetchPerformance(period = 'all') {
    return request(`/api/analytics/performance?period=${period}`);
}

export function fetchStrategyStats(period = 'all') {
    return request(`/api/analytics/strategy?period=${period}`);
}

// --- Pipeline ---

export function fetchPipelineStatus() {
    return request('/api/pipeline/status');
}

// --- Watchlist ---

export function fetchWatchlist() {
    return request('/api/watchlist');
}

export function addWatchlistSymbol(symbol) {
    return request('/api/watchlist', {
        method: 'POST',
        body: JSON.stringify({ action: 'add', symbol }),
    });
}

export function removeWatchlistSymbol(symbol) {
    return request('/api/watchlist', {
        method: 'POST',
        body: JSON.stringify({ action: 'remove', symbol }),
    });
}

// --- Config ---

export function fetchConfig() {
    return request('/api/config');
}

export function updateConfig(data) {
    return request('/api/config', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// --- Position Management ---

export function exitPosition(symbol) {
    return request(`/api/positions/${encodeURIComponent(symbol)}/exit`, {
        method: 'POST',
    });
}

// --- Engine Control ---

export function startEngine() {
    return request('/engine/start', { method: 'POST' });
}

export function stopEngine() {
    return request('/engine/stop', { method: 'POST' });
}

export function runCycle() {
    return request('/engine/cycle', { method: 'POST' });
}
