// Inline Sparkline — canvas-based mini chart

/**
 * Draw a sparkline onto a canvas element.
 * @param {HTMLCanvasElement} canvas
 * @param {number[]} data - array of values
 * @param {Object} opts
 * @param {string} opts.color - line color
 * @param {string} opts.fillColor - fill under line
 * @param {number} opts.lineWidth
 */
export function drawSparkline(canvas, data, opts = {}) {
    if (!canvas || !data || data.length < 2) return;

    const {
        color = '#4a9eff',
        fillColor = 'rgba(74, 158, 255, 0.1)',
        lineWidth = 1.5,
    } = opts;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padY = 2;

    const points = data.map((val, i) => ({
        x: (i / (data.length - 1)) * w,
        y: padY + ((max - val) / range) * (h - padY * 2),
    }));

    // Determine color based on trend
    const trend = data[data.length - 1] >= data[0];
    const lineColor = opts.color || (trend ? '#00c853' : '#ff4757');
    const areaColor = opts.fillColor || (trend ? 'rgba(0, 200, 83, 0.1)' : 'rgba(255, 71, 87, 0.1)');

    // Fill
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = areaColor;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // End dot
    const last = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(last.x, last.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();
}

/**
 * Render a sparkline cell HTML.
 * @param {string} id - unique id for the canvas
 * @returns {string} HTML string
 */
export function sparklineCell(id) {
    return `<canvas id="${id}" class="sparkline-cell" width="80" height="30"></canvas>`;
}
