// Insight-Alpha — Utility Functions

/** Format number as INR currency */
export function formatCurrency(value) {
    if (value == null || isNaN(value)) return '\u20B90.00';
    const abs = Math.abs(value);
    return `${value < 0 ? '-' : ''}\u20B9${abs.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

/** Format as percentage */
export function formatPct(value, decimals = 1) {
    if (value == null || isNaN(value)) return '0.0%';
    return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
}

/** Format confidence score (0-1) as display string */
export function formatScore(value) {
    if (value == null || isNaN(value)) return '-';
    return value.toFixed(2);
}

/** Format timestamp string to HH:MM:SS */
export function formatTime(ts) {
    if (!ts) return '-';
    if (typeof ts === 'string' && ts.length <= 8) return ts;
    const d = new Date(ts);
    return d.toLocaleTimeString('en-IN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'Asia/Kolkata', hour12: false,
    });
}

/** Format date string to DD MMM YYYY */
export function formatDate(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return d.toLocaleDateString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
        timeZone: 'Asia/Kolkata',
    });
}

/** Format duration in seconds to human-readable */
export function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '-';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/** Get PnL CSS class */
export function pnlClass(value) {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return '';
}

/** Get direction tag class */
export function directionTag(direction) {
    const d = (direction || '').toLowerCase();
    if (d === 'buy' || d === 'long') return 'tag-buy';
    if (d === 'sell' || d === 'short') return 'tag-sell';
    return 'tag-neutral';
}

/** Create DOM element with optional class and children */
export function el(tag, attrs = {}, children = []) {
    const elem = document.createElement(tag);
    for (const [key, val] of Object.entries(attrs)) {
        if (key === 'class') elem.className = val;
        else if (key === 'text') elem.textContent = val;
        else if (key === 'html') elem.innerHTML = val;
        else if (key === 'style' && typeof val === 'object') {
            Object.assign(elem.style, val);
        } else if (key.startsWith('on')) {
            elem.addEventListener(key.slice(2).toLowerCase(), val);
        } else {
            elem.setAttribute(key, val);
        }
    }
    for (const child of children) {
        if (typeof child === 'string') {
            elem.appendChild(document.createTextNode(child));
        } else if (child) {
            elem.appendChild(child);
        }
    }
    return elem;
}

/** Show a toast notification */
export function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = el('div', { class: `toast ${type}` }, [message]);
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/** Debounce function */
export function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

/** Get progress bar color based on utilization percentage */
export function utilizationColor(pct) {
    if (pct >= 90) return 'red';
    if (pct >= 70) return 'yellow';
    return 'green';
}
