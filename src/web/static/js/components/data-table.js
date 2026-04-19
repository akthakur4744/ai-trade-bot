// Reusable Data Table Component

/**
 * Render a data table with optional sorting.
 * @param {Object} config
 * @param {Array<{key, label, align?, sortable?, render?}>} config.columns
 * @param {Array<Object>} config.rows
 * @param {string} config.emptyText
 * @param {string} config.id
 * @param {string} config.sortKey - current sort column key
 * @param {string} config.sortDir - 'asc' or 'desc'
 * @param {Function} config.onSort - callback(key)
 * @param {Function} config.onRowClick - callback(row)
 * @returns {string} HTML string
 */
export function renderDataTable(config) {
    const {
        columns, rows, emptyText = 'No data', id = '',
        sortKey = null, sortDir = 'asc', onSort = null, onRowClick = null,
    } = config;

    const thead = columns.map(col => {
        let cls = '';
        if (col.align === 'right') cls += ' cell-right';
        if (col.align === 'center') cls += ' cell-center';
        if (col.sortable) {
            cls += ' sortable';
            if (sortKey === col.key) cls += ` sorted-${sortDir}`;
        }
        return `<th class="${cls}" data-col="${col.key}">${col.label}</th>`;
    }).join('');

    let tbody;
    if (!rows || rows.length === 0) {
        tbody = `<tr class="empty-row"><td colspan="${columns.length}">${emptyText}</td></tr>`;
    } else {
        tbody = rows.map((row, idx) => {
            const cells = columns.map(col => {
                const val = row[col.key];
                const rendered = col.render ? col.render(val, row) : (val ?? '-');
                let cls = '';
                if (col.align === 'right') cls += ' cell-right';
                if (col.align === 'center') cls += ' cell-center';
                if (col.mono) cls += ' cell-mono';
                return `<td class="${cls}">${rendered}</td>`;
            }).join('');
            return `<tr data-row-index="${idx}">${cells}</tr>`;
        }).join('');
    }

    return `<div class="table-wrap">
        <table class="data-table" ${id ? `id="${id}"` : ''}>
            <thead><tr>${thead}</tr></thead>
            <tbody>${tbody}</tbody>
        </table>
    </div>`;
}

/**
 * Attach sort click handlers to a rendered data-table.
 * Call after rendering the table HTML into DOM.
 */
export function attachTableHandlers(tableId, onSort, onRowClick) {
    const table = document.getElementById(tableId);
    if (!table) return;

    if (onSort) {
        table.querySelectorAll('th.sortable').forEach(th => {
            th.addEventListener('click', () => onSort(th.dataset.col));
        });
    }

    if (onRowClick) {
        table.querySelectorAll('tbody tr[data-row-index]').forEach(tr => {
            tr.style.cursor = 'pointer';
            tr.addEventListener('click', () => onRowClick(parseInt(tr.dataset.rowIndex)));
        });
    }
}

/**
 * Render pagination controls.
 * @param {Object} opts
 * @param {number} opts.page - current page (1-based)
 * @param {number} opts.totalPages
 * @param {number} opts.total - total item count
 * @param {Function} opts.onPage - callback(pageNumber)
 * @returns {string} HTML string
 */
export function renderPagination(opts) {
    const { page, totalPages, total, onPage } = opts;
    if (totalPages <= 1) return '';

    const pages = [];
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || Math.abs(i - page) <= 2) {
            pages.push(i);
        } else if (pages[pages.length - 1] !== '...') {
            pages.push('...');
        }
    }

    return `<div class="pagination" id="pagination">
        <button class="page-btn" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>&laquo;</button>
        ${pages.map(p => p === '...'
            ? '<span class="page-info">...</span>'
            : `<button class="page-btn ${p === page ? 'active' : ''}" data-page="${p}">${p}</button>`
        ).join('')}
        <button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''}>&raquo;</button>
        <span class="page-info">${total} total</span>
    </div>`;
}

/**
 * Attach pagination click handlers.
 */
export function attachPaginationHandlers(onPage) {
    const container = document.getElementById('pagination');
    if (!container) return;
    container.querySelectorAll('.page-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (!btn.disabled) onPage(parseInt(btn.dataset.page));
        });
    });
}
