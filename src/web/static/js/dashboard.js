// Insight-Alpha Dashboard — Auto-refresh, approval workflow, and auto-sell monitoring

const POLL_INTERVAL = 5000; // 5 seconds

// ---- Clock ----
function updateClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'Asia/Kolkata', hour12: false
    });
    document.getElementById('clock').textContent = `IST ${time}`;
}
setInterval(updateClock, 1000);
updateClock();

// ---- Status Polling ----
async function pollStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        updateStatusUI(data);
    } catch (e) {
        console.error('Status poll failed:', e);
    }
}

function updateStatusUI(data) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const badge = document.getElementById('mode-badge');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    // Mode badge
    badge.textContent = data.mode.toUpperCase();
    if (data.mode === 'live') {
        badge.classList.add('live');
    }

    // Status indicator
    if (data.is_running) {
        dot.className = 'status-dot running';
        text.textContent = 'Engine Running';
        if (btnStart) btnStart.style.display = 'none';
        if (btnStop) btnStop.style.display = 'inline-flex';
    } else if (data.is_authenticated) {
        dot.className = 'status-dot authenticated';
        text.textContent = 'Authenticated';
        if (btnStart) btnStart.style.display = 'inline-flex';
        if (btnStop) btnStop.style.display = 'none';
    } else {
        dot.className = 'status-dot';
        text.textContent = 'Not Connected';
    }

    // Stats
    document.getElementById('stat-cycles').textContent = data.total_cycles || 0;

    // Pending signals badge in header
    const pendingBadge = document.getElementById('pending-count-badge');
    const pendingText = document.getElementById('pending-count-text');
    if (data.pending_signals > 0) {
        pendingBadge.style.display = 'inline-flex';
        pendingText.textContent = data.pending_signals;
    } else {
        pendingBadge.style.display = 'none';
    }

    // Auto-sell badge in header
    const autoSellBadge = document.getElementById('auto-sell-badge');
    const autoSellText = document.getElementById('auto-sell-count-text');
    if (data.auto_sell_active > 0) {
        autoSellBadge.style.display = 'inline-flex';
        autoSellText.textContent = data.auto_sell_active;
    } else {
        autoSellBadge.style.display = 'none';
    }
}

// ---- Portfolio Polling ----
async function pollPortfolio() {
    try {
        const res = await fetch('/api/portfolio');
        const data = await res.json();

        // Stats
        document.getElementById('stat-positions').textContent = data.open_count || 0;

        const pnlEl = document.getElementById('stat-pnl');
        const pnl = data.realized_pnl || 0;
        pnlEl.textContent = `\u20B9${pnl.toFixed(2)}`;
        pnlEl.className = `stat-value ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : ''}`;

        const deployed = data.deployed_capital || 0;
        document.getElementById('stat-deployed').textContent = `\u20B9${deployed.toFixed(2)}`;

        // Positions table
        const tbody = document.getElementById('positions-body');
        if (data.positions && data.positions.length > 0) {
            tbody.innerHTML = data.positions.map(p => {
                const autoSellTag = p.auto_sell
                    ? '<span class="tag-auto-sell" title="AI managing exit">\u1F916 Auto</span>'
                    : '<span class="tag-manual">Manual</span>';
                return `
                <tr>
                    <td><strong>${p.symbol}</strong></td>
                    <td><span class="tag-${p.direction.toLowerCase()}">${p.direction}</span></td>
                    <td>${p.quantity}</td>
                    <td>\u20B9${p.entry_price.toFixed(2)}</td>
                    <td>\u20B9${p.current_price.toFixed(2)}</td>
                    <td class="${p.pnl >= 0 ? 'positive' : 'negative'}">\u20B9${p.pnl.toFixed(2)}</td>
                    <td>${p.strategy}</td>
                    <td>${autoSellTag}</td>
                </tr>
            `}).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="8" class="empty">No open positions</td></tr>';
        }
    } catch (e) {
        console.error('Portfolio poll failed:', e);
    }
}

// ---- Alerts Polling ----
async function pollAlerts() {
    try {
        const res = await fetch('/api/alerts');
        const alerts = await res.json();
        const container = document.getElementById('activity-log');

        if (alerts && alerts.length > 0) {
            container.innerHTML = alerts.map(a => `
                <div class="log-entry log-${a.level}">
                    <span class="log-time">${a.time}</span>
                    <span class="log-msg">${a.message}</span>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('Alerts poll failed:', e);
    }
}

// ---- Signals Polling ----
async function pollSignals() {
    try {
        const res = await fetch('/api/signals');
        const signals = await res.json();
        const tbody = document.getElementById('signals-body');

        if (signals && signals.length > 0) {
            tbody.innerHTML = signals.map(s => `
                <tr>
                    <td>${s.time || '-'}</td>
                    <td><strong>${s.symbol}</strong></td>
                    <td><span class="tag-${(s.direction || '').toLowerCase()}">${s.direction}</span></td>
                    <td>${s.strategy}</td>
                    <td>${(s.confidence || 0).toFixed(2)}</td>
                    <td>${(s.score || 0).toFixed(2)}</td>
                    <td>\u20B9${(s.entry || 0).toFixed(2)}</td>
                    <td>\u20B9${(s.stop || 0).toFixed(2)}</td>
                    <td>\u20B9${(s.target || 0).toFixed(2)}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="9" class="empty">No signals yet</td></tr>';
        }
    } catch (e) {
        console.error('Signals poll failed:', e);
    }
}

// ---- Pending Signals Polling ----
async function pollPending() {
    try {
        const res = await fetch('/api/pending');
        const signals = await res.json();

        const panel = document.getElementById('pending-panel');
        const list = document.getElementById('pending-list');
        const badge = document.getElementById('pending-badge');

        const pending = signals.filter(s => s.status === 'pending');

        if (signals.length > 0) {
            panel.style.display = 'block';
            badge.textContent = pending.length;

            list.innerHTML = signals.map(s => {
                const isPending = s.status === 'pending';
                const dirClass = s.direction === 'BUY' ? 'tag-buy' : 'tag-sell';
                const sentClass = s.sentiment === 'BULLISH' ? 'sentiment-bullish' :
                                 s.sentiment === 'BEARISH' ? 'sentiment-bearish' : 'sentiment-neutral';

                const statusBadge = isPending
                    ? ''
                    : `<span class="pending-status pending-${s.status}">${s.status.toUpperCase()}</span>`;

                const buttons = isPending ? `
                    <div class="pending-actions">
                        <button class="btn btn-approve" onclick="signalAction('${s.signal_id}', 'approve')">
                            \u2705 Approve
                        </button>
                        <button class="btn btn-auto-sell" onclick="signalAction('${s.signal_id}', 'auto_sell')">
                            \u1F916 Auto-Sell
                        </button>
                        <button class="btn btn-ignore" onclick="signalAction('${s.signal_id}', 'ignore')">
                            \u274C Ignore
                        </button>
                    </div>
                ` : '';

                const drivers = (s.key_drivers || []).map(d =>
                    `<span class="driver-tag">\u1F511 ${d}</span>`
                ).join('');

                const risks = (s.risks || []).map(r =>
                    `<span class="risk-tag">\u26A0 ${r}</span>`
                ).join('');

                return `
                <div class="pending-signal ${isPending ? '' : 'pending-resolved'}" id="pending-${s.signal_id}">
                    <div class="pending-header">
                        <div class="pending-symbol">
                            <span class="${dirClass}">${s.direction}</span>
                            <strong>${s.symbol}</strong>
                            ${statusBadge}
                        </div>
                        <div class="pending-meta">
                            <span class="${sentClass}">${s.sentiment}</span>
                            <span class="pending-strength">${s.strength}</span>
                            <span class="pending-time">${s.created_at}</span>
                        </div>
                    </div>

                    <div class="pending-body">
                        <div class="pending-scores">
                            <span>Confidence: <strong>${(s.confidence * 100).toFixed(0)}%</strong></span>
                            <span>Score: <strong>${s.score.toFixed(2)}</strong></span>
                            <span>Strategy: <strong>${s.strategy}</strong></span>
                        </div>

                        <div class="pending-prices">
                            <span>Entry: <strong>\u20B9${s.entry.toFixed(2)}</strong></span>
                            <span>Stop: <strong>\u20B9${s.stop.toFixed(2)}</strong></span>
                            ${s.target > 0 ? `<span>Target: <strong>\u20B9${s.target.toFixed(2)}</strong></span>` : ''}
                        </div>

                        ${s.summary ? `<div class="pending-summary">${s.summary}</div>` : ''}

                        ${drivers ? `<div class="pending-drivers">${drivers}</div>` : ''}
                        ${risks ? `<div class="pending-risks">${risks}</div>` : ''}

                        <div class="pending-footer">
                            <span>Holding: ${s.time_horizon}</span>
                            <span>Regime: ${s.regime}</span>
                            <span>Expires in ${s.expiry_minutes} min</span>
                        </div>
                    </div>

                    ${buttons}
                </div>
                `;
            }).join('');
        } else {
            panel.style.display = 'none';
        }
    } catch (e) {
        console.error('Pending poll failed:', e);
    }
}

// ---- Signal Action (Approve / Auto-Sell / Ignore) ----
async function signalAction(signalId, action) {
    const el = document.getElementById(`pending-${signalId}`);
    if (el) {
        const buttons = el.querySelector('.pending-actions');
        if (buttons) buttons.innerHTML = '<span class="loading-text">Processing...</span>';
    }

    try {
        const res = await fetch(`/api/signals/${signalId}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
        });
        const data = await res.json();

        // Immediate refresh
        pollPending();
        pollPortfolio();
        pollAlerts();
        pollAutoSell();

        if (data.status === 'executed') {
            const autoTag = data.auto_sell ? ' (Auto-Sell enabled)' : '';
            showToast(`Trade executed: ${data.symbol} @ \u20B9${data.price.toFixed(2)}${autoTag}`, 'success');
        } else if (data.status === 'ignored') {
            showToast(`Signal ignored: ${data.symbol}`, 'info');
        } else if (data.status === 'error') {
            showToast(`Error: ${data.message}`, 'error');
        }
    } catch (e) {
        console.error('Signal action failed:', e);
        showToast('Action failed. Check console.', 'error');
    }
}

// ---- Auto-Sell Status Polling ----
async function pollAutoSell() {
    try {
        const res = await fetch('/api/auto-sell');
        const data = await res.json();

        const panel = document.getElementById('auto-sell-panel');
        const list = document.getElementById('auto-sell-list');

        if (data.triggers && data.triggers.length > 0) {
            panel.style.display = 'block';
            list.innerHTML = data.triggers.map(t => {
                const dirClass = t.direction === 'BUY' ? 'tag-buy' : 'tag-sell';
                return `
                <div class="auto-sell-item">
                    <div class="auto-sell-header">
                        <span class="${dirClass}">${t.direction}</span>
                        <strong>${t.symbol}</strong>
                        <span class="auto-sell-timer">${t.time_remaining_min} min remaining</span>
                    </div>
                    <div class="auto-sell-levels">
                        <span>Entry: \u20B9${t.entry.toFixed(2)}</span>
                        <span>Stop: <span class="negative">\u20B9${t.stop_loss.toFixed(2)}</span></span>
                        <span>Target: <span class="positive">\u20B9${t.target.toFixed(2)}</span></span>
                        <span>Trail: ${t.trailing_pct.toFixed(1)}%</span>
                    </div>
                    <div class="auto-sell-tracking">
                        <span>High: \u20B9${t.highest_price.toFixed(2)}</span>
                        <span>Conf Floor: ${(t.confidence_floor * 100).toFixed(0)}%</span>
                    </div>
                    ${t.exit_strategy ? `<div class="auto-sell-strategy">${t.exit_strategy.replace(/\\n/g, '<br>')}</div>` : ''}
                    ${t.invalidation ? `<div class="auto-sell-invalidation">\u26A0 ${t.invalidation}</div>` : ''}
                </div>
                `;
            }).join('');
        } else if (data.events && data.events.length > 0) {
            // Show recent auto-sell events even if no active triggers
            panel.style.display = 'block';
            list.innerHTML = '<div class="auto-sell-no-active">No active triggers</div>' +
                data.events.slice(0, 5).map(e => {
                    const isExit = e.action === 'executed';
                    return `
                    <div class="auto-sell-event ${isExit ? 'auto-sell-exit' : ''}">
                        <span class="auto-sell-event-time">${e.time}</span>
                        <span>${e.symbol} — ${e.action}${isExit ? `: ${e.reason}` : ''}</span>
                        ${isExit ? `<span class="${e.pnl >= 0 ? 'positive' : 'negative'}">\u20B9${e.pnl.toFixed(2)}</span>` : ''}
                    </div>
                    `;
                }).join('');
        } else {
            panel.style.display = 'none';
        }
    } catch (e) {
        console.error('Auto-sell poll failed:', e);
    }
}

// ---- Insights Polling ----
async function pollInsights() {
    try {
        const res = await fetch('/api/insights');
        const data = await res.json();
        if (data && Object.keys(data).length > 0) {
            renderInsights(data);
        }
    } catch (e) {
        console.error('Insights poll failed:', e);
    }
}

function renderInsights(insights) {
    const panel = document.getElementById('insights-panel');
    panel.style.display = 'block';

    // Macro
    if (insights.macro) {
        const m = insights.macro.data;
        const dirClass = m.direction === 'BULLISH' ? 'sentiment-bullish' :
                        m.direction === 'BEARISH' ? 'sentiment-bearish' : 'sentiment-neutral';
        document.getElementById('macro-content').innerHTML = `
            <div>Nifty: <strong>${m.nifty}</strong></div>
            <div>VIX: <strong>${m.vix}</strong></div>
            <div>Direction: <strong class="${dirClass}">${m.direction}</strong></div>
            <div>Regime: <strong>${m.regime}</strong></div>
            ${m.risk_off ? '<div style="color:var(--accent-red)">\u26A0 Risk-Off</div>' : ''}
        `;
        document.getElementById('insight-time').textContent = `Updated: ${insights.macro.updated_at}`;
    }

    // Sentiment from research
    if (insights.research) {
        const r = insights.research.data;
        const sentClass = r.sentiment === 'BULLISH' ? 'sentiment-bullish' :
                         r.sentiment === 'BEARISH' ? 'sentiment-bearish' : 'sentiment-neutral';
        document.getElementById('sentiment-content').innerHTML = `
            <div>Sentiment: <strong class="${sentClass}">${r.sentiment}</strong></div>
            <div>Strength: <strong>${(r.news_strength * 100).toFixed(0)}%</strong></div>
            <div>Urgency: <strong>${r.urgency}</strong></div>
            ${r.affected_sectors.length > 0 ? `<div>Sectors: ${r.affected_sectors.join(', ')}</div>` : ''}
        `;

        // Research summary
        const section = document.getElementById('research-section');
        section.style.display = 'block';
        document.getElementById('research-summary').textContent = r.summary || 'No analysis available';

        // Key drivers
        const driversEl = document.getElementById('research-drivers');
        driversEl.innerHTML = (r.key_drivers || []).map(d =>
            `<span class="driver-tag">\u1F511 ${d}</span>`
        ).join('');

        // Entities
        const entitiesEl = document.getElementById('research-entities');
        entitiesEl.innerHTML = (r.entities || []).map(e => {
            const cls = e.sentiment === 'BULLISH' ? 'entity-bullish' :
                       e.sentiment === 'BEARISH' ? 'entity-bearish' : 'entity-neutral';
            const emoji = e.sentiment === 'BULLISH' ? '\u1F7E2' :
                         e.sentiment === 'BEARISH' ? '\u1F534' : '\u26AA';
            return `<span class="entity-tag ${cls}">${emoji} ${e.symbol}</span>`;
        }).join('');
    }

    // Sentinel risk
    if (insights.sentinel) {
        const s = insights.sentinel.data;
        const riskColor = s.risk_penalty > 0.4 ? 'var(--accent-red)' :
                         s.risk_penalty > 0.2 ? 'var(--accent-yellow)' : 'var(--accent-green)';
        document.getElementById('risk-content').innerHTML = `
            <div>Risk Penalty: <strong style="color:${riskColor}">${(s.risk_penalty * 100).toFixed(0)}%</strong></div>
            <div>Recommendation: <strong>${s.recommendation}</strong></div>
            ${(s.counter_arguments || []).length > 0 ?
                `<div style="margin-top:4px;font-size:12px;color:var(--text-muted)">
                    \u26A0 ${s.counter_arguments[0]}
                </div>` : ''}
        `;
    }

    // News headlines
    if (insights.news) {
        const n = insights.news.data;
        const newsSection = document.getElementById('news-section');
        newsSection.style.display = 'block';
        document.getElementById('news-list').innerHTML = (n.headlines || []).map(h =>
            `<div class="news-item">
                <span class="news-source">${h.source}</span>
                <span>${h.title}</span>
            </div>`
        ).join('');
    }

    // Scored signals
    if (insights.scoring) {
        const sc = insights.scoring.data;
        if (sc.scored && sc.scored.length > 0) {
            const scoringSection = document.getElementById('scoring-section');
            scoringSection.style.display = 'block';
            document.getElementById('scoring-list').innerHTML = sc.scored.map(s => {
                const dirTag = s.direction === 'BUY' ? 'tag-buy' : 'tag-sell';
                return `<div class="scoring-item">
                    <span class="scoring-symbol">${s.symbol}</span>
                    <span class="${dirTag}">${s.direction}</span>
                    <span class="scoring-conf">Conf: ${(s.confidence * 100).toFixed(0)}%</span>
                    <span class="scoring-conf">Score: ${s.final_score.toFixed(2)}</span>
                    <span class="scoring-summary">${s.summary || s.strategy}</span>
                </div>`;
            }).join('');
        }
    }
}

// ---- Toast Notifications ----
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => toast.classList.add('toast-visible'));

    // Remove after 4 seconds
    setTimeout(() => {
        toast.classList.remove('toast-visible');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ---- Engine Controls ----
async function startEngine() {
    try {
        const res = await fetch('/engine/start', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started') {
            pollStatus();
            pollAlerts();
        }
    } catch (e) {
        console.error('Start failed:', e);
    }
}

async function stopEngine() {
    try {
        const res = await fetch('/engine/stop', { method: 'POST' });
        const data = await res.json();
        pollStatus();
        pollAlerts();
    } catch (e) {
        console.error('Stop failed:', e);
    }
}

async function runCycle() {
    try {
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '\u23F3 Running...';

        const res = await fetch('/engine/cycle', { method: 'POST' });
        const data = await res.json();

        btn.disabled = false;
        btn.textContent = '\u1F504 Run Single Cycle';
        pollStatus();
        pollAlerts();
        pollPortfolio();
        pollSignals();
        pollPending();
        pollAutoSell();
        pollInsights();
    } catch (e) {
        console.error('Cycle failed:', e);
    }
}

// ---- Polling Loop ----
function startPolling() {
    pollStatus();
    pollPortfolio();
    pollAlerts();
    pollSignals();
    pollInsights();
    pollPending();
    pollAutoSell();

    setInterval(() => {
        pollStatus();
        pollPortfolio();
        pollAlerts();
        pollSignals();
        pollInsights();
        pollPending();
        pollAutoSell();
    }, POLL_INTERVAL);
}

// Start on page load
startPolling();
