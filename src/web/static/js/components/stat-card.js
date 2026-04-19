// Reusable Stat Card Component

/**
 * Render a grid of stat cards.
 * @param {Array<{id, label, value, accent, delta?}>} stats
 * @returns {string} HTML string
 */
export function renderStatCards(stats) {
    return `<div class="grid-stats">${stats.map(s => `
        <div class="card stat-card ${s.accent ? 'accent-' + s.accent : ''}">
            <div class="stat-label">${s.label}</div>
            <div class="stat-value ${s.className || ''}" id="${s.id || ''}">${s.value}</div>
            ${s.delta != null ? `<div class="stat-delta ${s.deltaDir || ''}">${s.delta}</div>` : ''}
        </div>
    `).join('')}</div>`;
}

/**
 * Update a single stat card value by id.
 */
export function updateStat(id, value, className = '') {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    if (className) el.className = `stat-value ${className}`;
}
