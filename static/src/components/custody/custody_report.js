/** @odoo-module **/
/**
 * Custodia de terceros — material vendido que sigue en mi almacén.
 *
 * Reporte de consulta rápida: KPIs + gráficas (por BODEGA, antigüedad
 * apilada por estado, reparto por estado, materiales y clientes) + tabla
 * por PLACA (lote, material, bodega, ubicación, días) con la orden como
 * dato más; vista alterna agrupada por orden. El cálculo pesado viene del
 * servidor (stock.quant.get_custody_report); aquí se filtra, ordena y dibuja.
 *
 * Gráficas con Chart.js (bundle nativo web.chartjs_lib, el mismo que usa
 * SOM Analytics): se dibujan en <canvas> después de cada render (onPatched)
 * y solo se reconstruyen cuando cambian los datos (firma por gráfica), así
 * ordenar la tabla o abrir una orden no re-anima nada.
 */
import { Component, useState, onWillStart, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

const STATUS_ORDER = ["paid_auth", "paid", "auth", "assigned"];
const STATUS_META = {
    paid_auth: { label: "Pagada + autorizada", color: "#0b57d0", hint: "Pagada al 100 % y con entrega autorizada: el cliente ya podría llevársela" },
    paid: { label: "Pagada", color: "#159957", hint: "Pagada al 100 %: el material es del cliente" },
    auth: { label: "Autorizada sin pago", color: "#f2b705", hint: "Entrega autorizada sin pago completo: se comprometió la salida" },
    assigned: { label: "Asignada", color: "#5cb9f2", hint: "Asignada a una orden confirmada, sin pago completo ni autorización" },
};
const AGING_COLORS = { ok: "#0b57d0", warn: "#f59e0b", hot: "#ea580c", crit: "#dc2626" };
const FONT = "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif";
const INK = "#0f172a";
const MUTED = "#64748b";

function fmtNum(v, d = 2) {
    return (v || 0).toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtTick(v) {
    const a = Math.abs(v || 0);
    if (a >= 1e6) return (v / 1e6).toFixed(1) + " M";
    if (a >= 1e3) return (v / 1e3).toFixed(a >= 1e5 ? 0 : 1) + " k";
    return fmtNum(v, 0);
}
function truncate(s, n = 34) {
    s = s || "";
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// Texto al centro de la dona (total de m²)
const ctyCenterText = {
    id: "ctyCenterText",
    afterDraw(chart) {
        const opts = chart.config.options.plugins?.ctyCenterText;
        if (!opts || !opts.text) return;
        const meta = chart.getDatasetMeta(0);
        if (!meta.data || !meta.data[0]) return;
        const { x, y } = meta.data[0];
        const ctx = chart.ctx;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.font = `800 20px ${FONT}`;
        ctx.fillStyle = INK;
        ctx.fillText(opts.text, x, y - 8);
        ctx.font = `600 11px ${FONT}`;
        ctx.fillStyle = MUTED;
        ctx.fillText(opts.sub || "", x, y + 12);
        ctx.restore();
    },
};

export class CustodyReport extends Component {
    static template = "inventory_visual_enhanced.CustodyReport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.statusOrder = STATUS_ORDER;
        this.state = useState({
            loading: true,
            data: null,
            view: "both",          // both | charts | table
            tableMode: "lots",     // lots | orders
            status: { paid_auth: true, paid: true, auth: true, assigned: true },
            zone: "",              // bodega seleccionada ("" = todas)
            search: "",
            minDays: 0,
            sortKey: "days",
            sortDir: -1,
            expanded: {},
            limit: 100,
        });
        this.charts = {};
        this.chartSig = {};
        this.chartsReady = false;
        onWillStart(() => this.load());
        onMounted(async () => {
            await loadBundle("web.chartjs_lib");
            if (window.Chart && !window.Chart.registry.plugins.get("ctyCenterText")) {
                window.Chart.register(ctyCenterText);
            }
            this.chartsReady = true;
            this.renderCharts();
        });
        onPatched(() => this.renderCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("stock.quant", "get_custody_report", [], { filters: {} });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Filtros ──
    toggleStatus(key) { this.state.status[key] = !this.state.status[key]; }
    onlyStatus(key) { for (const k of STATUS_ORDER) this.state.status[k] = k === key; }
    allStatus() { for (const k of STATUS_ORDER) this.state.status[k] = true; }
    onSearch(ev) { this.state.search = ev.target.value || ""; this.state.limit = 100; }
    setMinDays(d) { this.state.minDays = this.state.minDays === d ? 0 : d; }
    setZone(z) { this.state.zone = this.state.zone === z ? "" : z; this.state.limit = 100; }
    setView(v) { this.state.view = v; }
    setTableMode(m) { this.state.tableMode = m; this.state.limit = 100; this.state.sortKey = "days"; this.state.sortDir = -1; }
    get showCharts() { return this.state.view !== "table"; }
    get showTable() { return this.state.view !== "charts"; }
    // Orden NATURAL de bodegas (BODEGA 1, 2, 3 … 10), no por m².
    _zoneKey(name) {
        const m = /(\d+)/.exec(name || "");
        return [m ? parseInt(m[1], 10) : 9999, name || ""];
    }
    _zoneSort(a, b) {
        const [na, sa] = this._zoneKey(a), [nb, sb] = this._zoneKey(b);
        return na !== nb ? na - nb : sa.localeCompare(sb);
    }
    get zoneNames() {
        return (this.state.data ? this.state.data.zones : []).map((z) => z.name).sort((a, b) => this._zoneSort(a, b));
    }

    _match(r, q) {
        return [r.lot, r.product, r.block, r.order, r.customer, r.salesperson, r.project, r.zone, r.locations]
            .some((v) => (v || "").toLowerCase().includes(q));
    }
    // Filas con todos los filtros salvo bodega (para la gráfica de bodegas)
    get rowsNoZone() {
        const d = this.state.data;
        if (!d) return [];
        const q = this.state.search.trim().toLowerCase();
        return d.rows.filter((r) => this.state.status[r.status] && r.days >= this.state.minDays && (!q || this._match(r, q)));
    }
    get rows() {
        const z = this.state.zone;
        return z ? this.rowsNoZone.filter((r) => r.zone === z) : this.rowsNoZone;
    }

    // ── Tabla de placas ──
    get sortedLots() {
        const k = this.state.sortKey, dir = this.state.sortDir;
        return this.rows.slice().sort((a, b) => {
            const va = a[k], vb = b[k];
            if (typeof va === "string" || typeof vb === "string") return String(va || "").localeCompare(String(vb || ""), "es", { numeric: true }) * dir;
            return ((va || 0) - (vb || 0)) * dir;
        });
    }
    get visibleLots() { return this.sortedLots.slice(0, this.state.limit); }

    // ── Tabla por orden (derivada de las filas filtradas) ──
    get orders() {
        const map = {};
        for (const r of this.rows) {
            const o = map[r.order_id] || (map[r.order_id] = {
                order_id: r.order_id, order: r.order, customer: r.customer, salesperson: r.salesperson, project: r.project,
                status: r.status, status_label: r.status_label, paid_pct: r.paid_pct, paid_amount: r.paid_amount,
                amount_total: r.amount_total, paid_date: r.paid_date, auth_date: r.auth_date, base_date: r.base_date,
                days: 0, plates: 0, qty: 0, value: 0, products: new Set(), zones: new Set(), lots: [],
            });
            o.plates += 1; o.qty += r.qty; o.value += r.value; o.days = Math.max(o.days, r.days);
            o.products.add(r.product); o.zones.add(r.zone); o.lots.push(r);
        }
        return Object.values(map).map((o) => ({ ...o, products: [...o.products], product_count: o.products.size, zones: [...o.zones].sort() }));
    }
    get sortedOrders() {
        const k = this.state.sortKey, dir = this.state.sortDir;
        return this.orders.slice().sort((a, b) => {
            const va = a[k], vb = b[k];
            if (typeof va === "string" || typeof vb === "string") return String(va || "").localeCompare(String(vb || ""), "es", { numeric: true }) * dir;
            return ((va || 0) - (vb || 0)) * dir;
        });
    }
    get visibleOrders() { return this.sortedOrders.slice(0, this.state.limit); }
    showMore() { this.state.limit += 100; }
    sortBy(key) {
        if (this.state.sortKey === key) this.state.sortDir = -this.state.sortDir;
        else { this.state.sortKey = key; this.state.sortDir = ["days", "qty", "value", "plates", "paid_pct"].includes(key) ? -1 : 1; }
    }
    sortIcon(key) { return this.state.sortKey === key ? (this.state.sortDir < 0 ? "▼" : "▲") : ""; }
    toggleExpand(id) { this.state.expanded[id] = !this.state.expanded[id]; }
    isExpanded(id) { return !!this.state.expanded[id]; }

    // ── KPIs sobre lo filtrado ──
    get kpis() {
        const rows = this.rows;
        const t = { plates: rows.length, qty: 0, value: 0, days: 0, orders: new Set(), customers: new Set(), products: new Set(), over30: 0, over60: 0, m2days: 0 };
        for (const r of rows) {
            t.qty += r.qty; t.value += r.value; t.days += r.days; t.m2days += r.qty * r.days;
            t.orders.add(r.order_id); t.customers.add(r.customer_id); t.products.add(r.product_id);
            if (r.days > 30) t.over30 += r.qty;
            if (r.days > 60) t.over60 += r.qty;
        }
        return { plates: t.plates, qty: t.qty, value: t.value, orders: t.orders.size, customers: t.customers.size, products: t.products.size,
                 avgDays: t.plates ? t.days / t.plates : 0, over30: t.over30, over60: t.over60, m2days: t.m2days };
    }
    get statusStats() {
        const out = STATUS_ORDER.map((k) => ({ key: k, ...STATUS_META[k], plates: 0, qty: 0, value: 0, days: 0, orders: new Set(), active: this.state.status[k] }));
        const map = Object.fromEntries(out.map((s) => [s.key, s]));
        for (const r of this.rows) { const s = map[r.status]; if (!s) continue; s.plates += 1; s.qty += r.qty; s.value += r.value; s.days += r.days; s.orders.add(r.order_id); }
        const totalQty = out.reduce((a, s) => a + s.qty, 0);
        return out.map((s) => ({ ...s, orders: s.orders.size, avgDays: s.plates ? s.days / s.plates : 0, pct: totalQty ? (s.qty / totalQty) * 100 : 0 }));
    }

    // ── Datos para gráficas ──
    // Por BODEGA (todas las bodegas aunque haya una seleccionada, para poder cambiar)
    get zonesData() {
        const map = {};
        for (const r of this.rowsNoZone) {
            const z = map[r.zone] || (map[r.zone] = { name: r.zone, qty: 0, value: 0, plates: 0, days: 0, orders: new Set(), seg: Object.fromEntries(STATUS_ORDER.map((s) => [s, 0])) });
            z.qty += r.qty; z.value += r.value; z.plates += 1; z.days += r.days; z.orders.add(r.order_id); z.seg[r.status] += r.qty;
        }
        return Object.values(map).sort((a, b) => this._zoneSort(a.name, b.name))
            .map((z) => ({ ...z, orders: z.orders.size, avgDays: z.plates ? z.days / z.plates : 0 }));
    }
    // Antigüedad: rangos del servidor × estado
    get agingData() {
        const buckets = this.state.data ? this.state.data.aging : [];
        return buckets.map((b) => {
            const seg = Object.fromEntries(STATUS_ORDER.map((s) => [s, 0]));
            let plates = 0, value = 0;
            for (const r of this.rows) if (r.bucket === b.key) { seg[r.status] += r.qty; plates += 1; value += r.value; }
            return { key: b.key, label: b.label, seg, plates, value, total: STATUS_ORDER.reduce((a, s) => a + seg[s], 0) };
        });
    }
    get materialsData() {
        const map = {};
        for (const r of this.rows) {
            const p = map[r.product_id] || (map[r.product_id] = { name: r.product, qty: 0, value: 0, plates: 0, days: 0, max: 0, zones: new Set() });
            p.qty += r.qty; p.value += r.value; p.plates += 1; p.days += r.days; p.max = Math.max(p.max, r.days); p.zones.add(r.zone);
        }
        return Object.values(map).sort((a, b) => b.qty - a.qty).slice(0, 10)
            .map((p) => ({ ...p, zones: [...p.zones].sort((a, b) => this._zoneSort(a, b)).join(", "), avgDays: p.plates ? p.days / p.plates : 0 }));
    }
    get customersData() {
        const map = {};
        for (const r of this.rows) {
            const c = map[r.customer_id] || (map[r.customer_id] = { name: r.customer, qty: 0, value: 0, plates: 0, days: 0, max: 0, orders: new Set() });
            c.qty += r.qty; c.value += r.value; c.plates += 1; c.days += r.days; c.max = Math.max(c.max, r.days); c.orders.add(r.order_id);
        }
        return Object.values(map).sort((a, b) => b.qty - a.qty).slice(0, 10)
            .map((c) => ({ ...c, orders: c.orders.size, avgDays: c.plates ? c.days / c.plates : 0 }));
    }
    // Altura de las gráficas horizontales según cuántas filas traen
    hbarStyle(n, per = 36, min = 220) { return "height:" + Math.max(min, 60 + n * per) + "px"; }
    get zonesHeight() { return this.hbarStyle(this.zonesData.length, 38, 260); }
    get materialsHeight() { return this.hbarStyle(this.materialsData.length, 34, 220); }
    get customersHeight() { return this.hbarStyle(this.customersData.length, 34, 220); }

    // ── Chart.js ──
    destroyCharts() {
        for (const c of Object.values(this.charts)) { try { c.destroy(); } catch { /* noop */ } }
        this.charts = {};
        this.chartSig = {};
    }

    // Crea o actualiza la gráfica; si el canvas ya no está (vista "Tabla") la destruye.
    mk(key, canvasId, config, sig) {
        const el = document.getElementById(canvasId);
        const existing = this.charts[key];
        if (!el) {
            if (existing) { try { existing.destroy(); } catch { /* noop */ } delete this.charts[key]; delete this.chartSig[key]; }
            return;
        }
        if (existing && existing.canvas === el) {
            if (this.chartSig[key] === sig) return;
            existing.data = config.data;
            existing.options = config.options;
            existing.update();
            this.chartSig[key] = sig;
            return;
        }
        if (existing) { try { existing.destroy(); } catch { /* noop */ } }
        this.charts[key] = new window.Chart(el.getContext("2d"), config);
        this.chartSig[key] = sig;
    }

    baseOptions(onClick) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400, easing: "easeOutQuart" },
            onClick: onClick || (() => {}),
            onHover: (ev, els) => { if (ev.native) ev.native.target.style.cursor = els.length && onClick ? "pointer" : "default"; },
            plugins: {
                legend: {
                    display: false,
                    labels: { boxWidth: 9, boxHeight: 9, usePointStyle: true, pointStyle: "circle", font: { size: 11, family: FONT, weight: "600" }, color: "#475569" },
                },
                tooltip: {
                    backgroundColor: "rgba(15, 23, 42, .96)", titleColor: "#f8fafc", bodyColor: "#cbd5e1", footerColor: "#94a3b8",
                    titleFont: { size: 12, weight: "700", family: FONT }, bodyFont: { size: 11.5, family: FONT }, footerFont: { size: 11, weight: "500", family: FONT },
                    padding: 12, cornerRadius: 10, boxWidth: 8, boxHeight: 8, usePointStyle: true,
                    callbacks: {
                        label: (ctx) => {
                            const v = ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed;
                            if (!v) return null;
                            return ` ${ctx.dataset.label || ""}: ${fmtNum(v)} m²`;
                        },
                    },
                },
            },
        };
    }
    axQty(stacked = false) {
        return {
            stacked, beginAtZero: true, border: { display: false }, grid: { color: "rgba(100,116,139,.10)" },
            ticks: { font: { size: 10.5, family: FONT }, color: "#94a3b8", callback: (v) => fmtTick(v) + " m²" },
        };
    }
    axCat(stacked = false, size = 11) {
        return {
            stacked, border: { display: false }, grid: { display: false },
            ticks: { font: { size, family: FONT, weight: "700" }, color: "#334155", autoSkip: false },
        };
    }
    statusDatasets(rows, segKey = "seg") {
        return STATUS_ORDER.map((s) => ({
            label: STATUS_META[s].label, data: rows.map((r) => r[segKey][s]),
            backgroundColor: STATUS_META[s].color, hoverBackgroundColor: STATUS_META[s].color,
            borderRadius: 4, borderSkipped: false, maxBarThickness: 30,
        }));
    }
    daysColor(d) { return AGING_COLORS[this.daysClass(d)]; }

    renderCharts() {
        if (!this.chartsReady || !window.Chart || this.state.loading || !this.state.data) return;
        const sym = this.state.data.currency_symbol || "$";
        const base = this.baseOptions();

        // 1. Por bodega: barras horizontales apiladas por estado, clic = filtrar
        const zones = this.zonesData;
        const selected = this.state.zone;
        const zoneSig = JSON.stringify([zones.map((z) => [z.name, z.qty, z.seg]), selected]);
        const zoneDatasets = this.statusDatasets(zones).map((ds, i) => {
            const color = STATUS_META[STATUS_ORDER[i]].color;
            // Bodega seleccionada resaltada: las demás se atenúan
            return { ...ds, backgroundColor: zones.map((z) => (!selected || z.name === selected ? color : color + "55")) };
        });
        this.mk("zones", "o_cty_c_zones", {
            type: "bar",
            data: { labels: zones.map((z) => z.name), datasets: zoneDatasets },
            options: {
                ...this.baseOptions((ev, els) => { if (els.length) this.setZone(zones[els[0].index].name); }),
                indexAxis: "y",
                interaction: { mode: "index", intersect: false },
                scales: { x: this.axQty(true), y: this.axCat(true, 11.5) },
                plugins: {
                    ...base.plugins,
                    tooltip: {
                        ...base.plugins.tooltip,
                        callbacks: {
                            ...base.plugins.tooltip.callbacks,
                            title: (items) => zones[items[0].dataIndex].name,
                            footer: (items) => {
                                const z = zones[items[0].dataIndex];
                                return [`Total: ${fmtNum(z.qty)} m² · ${z.plates} placa(s) · ${z.orders} orden(es)`, `Valor ${sym}${fmtNum(z.value, 0)} · promedio ${fmtNum(z.avgDays, 0)} días`, selected === z.name ? "Clic para quitar el filtro" : "Clic para filtrar esta bodega"];
                            },
                        },
                    },
                },
            },
        }, zoneSig);

        // 2. Reparto por estado: dona con total al centro
        const stats = this.statusStats.filter((s) => s.qty > 0);
        const donutSig = JSON.stringify(stats.map((s) => [s.key, s.qty]));
        this.mk("donut", "o_cty_c_donut", {
            type: "doughnut",
            data: {
                labels: stats.map((s) => s.label),
                datasets: [{ data: stats.map((s) => s.qty), backgroundColor: stats.map((s) => s.color), hoverOffset: 8, borderWidth: 3, borderColor: "#fff", borderRadius: 5 }],
            },
            options: {
                ...base, cutout: "68%", layout: { padding: 8 },
                plugins: {
                    ...base.plugins,
                    ctyCenterText: { text: fmtTick(this.kpis.qty), sub: "m² en custodia" },
                    legend: { ...base.plugins.legend, display: true, position: "bottom" },
                    tooltip: {
                        ...base.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => { const s = stats[ctx.dataIndex]; return [` ${fmtNum(s.qty)} m² (${s.pct.toFixed(1)} %)`, ` ${s.plates} placa(s) · ${s.orders} orden(es)`, ` ${sym}${fmtNum(s.value, 0)} · promedio ${fmtNum(s.avgDays, 0)} días`]; },
                        },
                    },
                },
            },
        }, donutSig);

        // 3. Antigüedad: barras verticales apiladas por estado
        const aging = this.agingData;
        const agingSig = JSON.stringify(aging.map((b) => [b.key, b.seg]));
        this.mk("aging", "o_cty_c_aging", {
            type: "bar",
            data: { labels: aging.map((b) => [b.label, b.plates ? `${b.plates} placa(s)` : ""]), datasets: this.statusDatasets(aging).map((d) => ({ ...d, maxBarThickness: 90 })) },
            options: {
                ...base,
                interaction: { mode: "index", intersect: false },
                scales: { y: this.axQty(true), x: this.axCat(true, 11.5) },
                plugins: {
                    ...base.plugins,
                    legend: { ...base.plugins.legend, display: true, position: "top", align: "end" },
                    tooltip: {
                        ...base.plugins.tooltip,
                        callbacks: {
                            ...base.plugins.tooltip.callbacks,
                            title: (items) => aging[items[0].dataIndex].label,
                            footer: (items) => { const b = aging[items[0].dataIndex]; return `Total: ${fmtNum(b.total)} m² · ${b.plates} placa(s) · ${sym}${fmtNum(b.value, 0)}`; },
                        },
                    },
                },
            },
        }, agingSig);

        // 4 y 5. Materiales y clientes: barras horizontales, color = antigüedad promedio
        const hbar = (key, id, list, footer) => {
            const sig = JSON.stringify(list.map((p) => [p.name, p.qty, p.avgDays]));
            this.mk(key, id, {
                type: "bar",
                data: {
                    labels: list.map((p) => truncate(p.name)),
                    datasets: [{ label: "m² en custodia", data: list.map((p) => p.qty), backgroundColor: list.map((p) => this.daysColor(p.avgDays)), borderRadius: 5, borderSkipped: false, maxBarThickness: 24 }],
                },
                options: {
                    ...base, indexAxis: "y",
                    scales: { x: this.axQty(), y: this.axCat(false, 11) },
                    plugins: {
                        ...base.plugins,
                        tooltip: {
                            ...base.plugins.tooltip,
                            callbacks: { ...base.plugins.tooltip.callbacks, title: (items) => list[items[0].dataIndex].name, footer: (items) => footer(list[items[0].dataIndex]) },
                        },
                    },
                },
            }, sig);
        };
        hbar("materials", "o_cty_c_materials", this.materialsData, (p) => [`${p.plates} placa(s) · ${sym}${fmtNum(p.value, 0)}`, `Promedio ${fmtNum(p.avgDays, 0)} días · máximo ${p.max}`, `Bodegas: ${p.zones}`]);
        hbar("customers", "o_cty_c_customers", this.customersData, (c) => [`${c.orders} orden(es) · ${c.plates} placa(s) · ${sym}${fmtNum(c.value, 0)}`, `Promedio ${fmtNum(c.avgDays, 0)} días · máximo ${c.max}`]);
    }

    // ── Formato ──
    fmt(v, d = 2) { return fmtNum(v, d); }
    fmtInt(v) { return Math.round(v || 0).toLocaleString("es-MX"); }
    fmtShort(v) { return fmtTick(v); }
    pct(v) { return (v || 0).toFixed(1) + "%"; }
    daysClass(d) {
        if (d > 60) return "crit";
        if (d > 30) return "hot";
        if (d > 15) return "warn";
        return "ok";
    }
    statusColor(k) { return (STATUS_META[k] || {}).color || "#94a3b8"; }
    statusLabel(k) { return (STATUS_META[k] || {}).label || k; }
    barStyle(w) { return "width:" + Math.max(w || 0, 0) + "%"; }
    dot(k) { return "background:" + this.statusColor(k); }

    // ── Navegación / exportación ──
    openOrder(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order", res_id: id, views: [[false, "form"]], target: "current" });
    }
    exportCsv() {
        const head = ["Estado", "Lote", "Material", "Bloque", "Medidas", "Bodega", "Ubicación", "m2", "Valor", "Orden", "Cliente", "Vendedor", "Proyecto", "Pagado %", "Fecha pago", "Fecha autorización", "Fecha asignación", "Desde", "Días en custodia"];
        const esc = (v) => `"${String(v === undefined || v === null ? "" : v).replace(/"/g, '""')}"`;
        const lines = [head.join(",")];
        for (const r of this.sortedLots) {
            lines.push([r.status_label, r.lot, r.product, r.block, r.dims, r.zone, r.locations, r.qty, r.value, r.order, r.customer, r.salesperson, r.project, r.paid_pct, r.paid_date, r.auth_date, r.assigned_date, r.base_date, r.days].map(esc).join(","));
        }
        const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `custodia_terceros_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
}

registry.category("actions").add("inventory_custody_report", CustodyReport);
