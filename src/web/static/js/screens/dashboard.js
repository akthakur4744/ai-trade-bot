// Dashboard Overview Screen

import * as api from '../api.js';
import { formatCurrency, pnlClass } from '../utils.js';
import { renderStatCards, updateStat } from '../components/stat-card.js';

let pollTimer = null;

export function init(container) {
    container.innerHTML = `<div class="screen">
        ${renderStatCards([
            { id: 'ds-cycles', label: 'Scan Cycles', value: '0', accent: 'blue' },
            { id: 'ds-positions', label: 'Open Positions', value: '0', accent: 'purple' },
            { id: 'ds-pnl', label: "Today's PnL", value: '\u20B90.00', accent: 'green' },
            { id: 'ds-deployed', label: 'Capital Deployed', value: '\u20B90.00', accent: 'cyan' },
            { id: 'ds-unrealized', label: 'Unrealized PnL', value: '\u20B90.00', accent: 'yellow' },
            { id: 'ds-winrate', label: 'Win Rate', value: '-', accent: 'purple' },
        ])}

        <div class="grid-2col">
            <!-- Positions Summary -->
            <div class="card">
                <div class="section-header">
                    <h3 class="card-title"><span class="icon">&#9635;</span> Open Positions</h3>
                    <a href="#/positions" class="btn btn-ghost btn-sm">View All &#8594;</a>
                </div>
                <div class="table-wrap">
                    <table class="data-table" id="ds-positions-table">
                        <thead><tr>
                            <th>Symbol</th>
                            <th>Dir</th>
                            <th>Qty</th>
                            <th class="cell-right">Entry</th>
                            <th class="cell-right">Current</th>
                            <th class="cell-right">PnL</th>
                            <th>Strategy</th>
                        </tr></thead>
                        <tbody id="ds-positions-body">
                            <tr class="empty-row"><td colspan="7">No open positions</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Activity Log -->
            <div class="card">
                <div class="section-header">
                    <h3 class="card-title"><span class="icon">&#9783;</span> Activity Log</h3>
                </div>
                <div class="log-container dashboard-activity" id="ds-activity-log">
                    <div class="log-entry log-info">
                        <span class="log-msg">Waiting for activity...</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Signals -->
        <div class="card">
            <div class="section-header">
                <h3 class="card-title"><span class="icon">&#9783;</span> Recent Signals</h3>
                <a href="#/signals" class="btn btn-ghost btn-sm">Pipeline &#8594;</a>
            </div>
            <div class="table-wrap">
                <table class="data-table">
                    <thead><tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Direction</th>
                        <th>Strategy</th>
                        <th class="cell-right">Confidence</th>
                        <th class="cell-right">Score</th>
                        <th class="cell-right">Entry</th>
                        <th class="cell-right">Stop</th>
                        <th class="cell-right">Target</th>
                    </tr></thead>
                    <tbody id="ds-signals-body">
                        <tr class="empty-row"><td colspan="9">No signals yet</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>`;
}

export function activate() {
    poll();
    pollTimer = setInterval(poll, 5000);
}

export function deactivate() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function poll() {
    try {
        const [status, portfolio, alerts, signals] = await Promise.all([
            api.fetchStatus(),
            api.fetchPortfolio(),
            api.fetchAlerts(),
            api.fetchSignals(),
        ]);

        // Stats
        updateStat('ds-cycles', status.total_cycles || 0);
        updateStat('ds-positions', portfolio.open_count || 0);

        const pnl = portfolio.realized_pnl || 0;
        updateStat('ds-pnl', formatCurrency(pnl), pnlClass(pnl));

        const deployed = portfolio.deployed_capital || 0;
        updateStat('ds-deployed', formatCurrency(deployed));

        const unrealized = portfolio.unrealized_pnl || 0;
        updateStat('ds-unrealized', formatCurrency(unrealized), pnlClass(unrealized));

        if (status.win_rate != null) {
            updateStat('ds-winrate', `${(status.win_rate * 100).toFixed(0)}%`);
        }

        // Positions table
        renderPositions(portfolio.positions || []);

        // Activity log
        renderAlerts(alerts || []);

        // Signals table
        renderSignals(signals || []);
    } catch (e) {
        // silent
    }
}

function renderPositions(positions) {
    const tbody = document.getElementById('ds-positions-body');
    if (!tbody) return;

    if (positions.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No open positions</td></tr>';
        return;
    }

    tbody.innerHTML = positions.slice(0, 5).map(p => {
        const dir = (p.direction || '').toLowerCase();
        const tagClass = dir === 'buy' || dir === 'long' ? 'tag-buy' : 'tag-sell';
        const pnl = p.pnl || 0;
        return `<tr>
            <td><strong>${p.symbol}</strong></td>
            <td><span class="tag ${tagClass}">${p.direction}</span></td>
            <td class="cell-mono">${p.quantity}</td>
            <td class="cell-mono cell-right">${formatCurrency(p.entry_price)}</td>
            <td class="cell-mono cell-right">${formatCurrency(p.current_price)}</td>
            <td class="cell-mono cell-right ${pnlClass(pnl)}">${formatCurrency(pnl)}</td>
            <td><span class="tag tag-neutral">${p.strategy}</span></td>
        </tr>`;
    }).join('');
}

function renderAlerts(alerts) {
    const container = document.getElementById('ds-activity-log');
    if (!container) return;

    if (alerts.length === 0) {
        container.innerHTML = '<div class="log-entry log-info"><span class="log-msg">Waiting for activity...</span></div>';
        return;
    }

    container.innerHTML = alerts.map(a => `
        <div class="log-entry log-${a.level}">
            <span class="log-time">${a.time}</span>
            <span class="log-msg">${a.message}</span>
        </div>
    `).join('');
}

function renderSignals(signals) {
    const tbody = document.getElementById('ds-signals-body');
    if (!tbody) return;

    if (signals.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="9">No signals yet</td></tr>';
        return;
    }

    tbody.innerHTML = signals.slice(0, 10).map(s => {
        const dir = (s.direction || '').toLowerCase();
        const tagClass = dir === 'buy' || dir === 'long' ? 'tag-buy' : 'tag-sell';
        return `<tr>
            <td class="cell-mono">${s.time || '-'}</td>
            <td><strong>${s.symbol}</strong></td>
            <td><span class="tag ${tagClass}">${s.direction}</span></td>
            <td><span class="tag tag-neutral">${s.strategy}</span></td>
            <td class="cell-mono cell-right">${(s.confidence || 0).toFixed(2)}</td>
            <td class="cell-mono cell-right">${(s.score || 0).toFixed(2)}</td>
            <td class="cell-mono cell-right">${formatCurrency(s.entry)}</td>
            <td class="cell-mono cell-right">${formatCurrency(s.stop)}</td>
            <td class="cell-mono cell-right">${formatCurrency(s.target)}</td>
        </tr>`;
    }).join('');
}
