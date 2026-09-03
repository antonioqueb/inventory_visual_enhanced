/** @odoo-module **/
/**
 * Custodia de terceros — material vendido que sigue en mi almacén.
 *
 * Reporte de consulta rápida: KPIs + gráficas (por BODEGA, antigüedad
 * apilada por estado, reparto por estado, materiales y clientes) + tabla
 * por PLACA (lote, material, bodega, ubicación, días) con la orden como
 * dato más; vista alterna agrupada por orden. El cálculo pesado viene del
 * servidor (stock.quant.get_custody_report); aquí se filtra, ordena y dibuja.
 * Gráficas en SVG a mano (sin librerías); OWL no expone Math en las
 * plantillas, así que toda geometría se calcula en métodos.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATUS_ORDER = ["paid_auth", "paid", "auth", "assigned"];
const STATUS_META = {
    paid_auth: { label: "Pagada + autorizada", color: "#0b57d0", hint: "Pagada al 100 % y con entrega autorizada: el cliente ya podría llevársela" },
    paid: { label: "Pagada", color: "#159957", hint: "Pagada al 100 %: el material es del cliente" },
    auth: { label: "Autorizada sin pago", color: "#f2b705", hint: "Entrega autorizada sin pago completo: se comprometió la salida" },
    assigned: { label: "Asignada", color: "#5cb9f2", hint: "Asignada a una orden confirmada, sin pago completo ni autorización" },
};
const DONUT_R = 52;
const DONUT_C = 2 * Math.PI * DONUT_R;

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
        onWillStart(() => this.load());
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

    // ── Gráfica: por BODEGA (barras horizontales apiladas por estado) ──
    get zonesChart() {
        const map = {};
        for (const r of this.rowsNoZone) {
            const z = map[r.zone] || (map[r.zone] = { name: r.zone, qty: 0, value: 0, plates: 0, days: 0, orders: new Set(), seg: Object.fromEntries(STATUS_ORDER.map((s) => [s, 0])) });
            z.qty += r.qty; z.value += r.value; z.plates += 1; z.days += r.days; z.orders.add(r.order_id); z.seg[r.status] += r.qty;
        }
        const list = Object.values(map).sort((a, b) => this._zoneSort(a.name, b.name));
        const max = Math.max(...list.map((z) => z.qty), 1);
        return list.map((z) => ({
            ...z, orders: z.orders.size, avgDays: z.plates ? z.days / z.plates : 0, width: (z.qty / max) * 100,
            active: this.state.zone === z.name,
            segments: STATUS_ORDER.filter((s) => z.seg[s] > 0).map((s) => ({ status: s, color: STATUS_META[s].color, qty: z.seg[s], width: (z.seg[s] / z.qty) * 100 })),
        }));
    }

    // ── Gráfica: antigüedad apilada por estado (SVG) ──
    get agingChart() {
        const buckets = this.state.data ? this.state.data.aging : [];
        const rows = this.rows;
        const W = 640, H = 230, padL = 46, padB = 34, padT = 18, gap = 14;
        const n = buckets.length || 1;
        const bw = (W - padL - 10 - gap * (n - 1)) / n;
        const sums = buckets.map((b) => {
            const seg = Object.fromEntries(STATUS_ORDER.map((s) => [s, 0]));
            let plates = 0;
            for (const r of rows) if (r.bucket === b.key) { seg[r.status] += r.qty; plates += 1; }
            return { key: b.key, label: b.label, seg, total: STATUS_ORDER.reduce((a, s) => a + seg[s], 0), plates };
        });
        const max = Math.max(...sums.map((s) => s.total), 1);
        const scale = (H - padT - padB) / max;
        const bars = sums.map((s, i) => {
            const x = padL + i * (bw + gap);
            let y = H - padB;
            const segments = [];
            for (const st of STATUS_ORDER) {
                const h = s.seg[st] * scale;
                if (h > 0) { y -= h; segments.push({ status: st, color: STATUS_META[st].color, x, y, h, w: bw, qty: s.seg[st] }); }
            }
            return { ...s, x, w: bw, top: y, labelX: x + bw / 2, segments };
        });
        const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ y: H - padB - f * max * scale, v: max * f }));
        return { W, H, padL, padB, bars, ticks, baseY: H - padB, empty: !rows.length };
    }

    // ── Gráfica: dona por estado ──
    get donut() {
        const stats = this.statusStats.filter((s) => s.qty > 0);
        let offset = 0;
        const segs = stats.map((s) => {
            const len = (s.pct / 100) * DONUT_C;
            const seg = { key: s.key, color: s.color, label: s.label, pct: s.pct, dash: `${len} ${DONUT_C - len}`, offset: -offset };
            offset += len;
            return seg;
        });
        return { r: DONUT_R, c: DONUT_C, segs };
    }

    // ── Gráfica: materiales con más m² en custodia ──
    get materialsChart() {
        const map = {};
        for (const r of this.rows) {
            const p = map[r.product_id] || (map[r.product_id] = { name: r.product, qty: 0, value: 0, plates: 0, days: 0, max: 0, zones: new Set() });
            p.qty += r.qty; p.value += r.value; p.plates += 1; p.days += r.days; p.max = Math.max(p.max, r.days); p.zones.add(r.zone);
        }
        const list = Object.values(map).sort((a, b) => b.qty - a.qty).slice(0, 10);
        const max = Math.max(...list.map((p) => p.qty), 1);
        return list.map((p) => ({ ...p, zones: [...p.zones].sort().join(", "), avgDays: p.plates ? p.days / p.plates : 0, width: (p.qty / max) * 100 }));
    }

    // ── Gráfica: clientes con más m² ──
    get customersChart() {
        const map = {};
        for (const r of this.rows) {
            const c = map[r.customer_id] || (map[r.customer_id] = { name: r.customer, qty: 0, value: 0, plates: 0, days: 0, max: 0, orders: new Set() });
            c.qty += r.qty; c.value += r.value; c.plates += 1; c.days += r.days; c.max = Math.max(c.max, r.days); c.orders.add(r.order_id);
        }
        const list = Object.values(map).sort((a, b) => b.qty - a.qty).slice(0, 10);
        const max = Math.max(...list.map((c) => c.qty), 1);
        return list.map((c) => ({ ...c, orders: c.orders.size, avgDays: c.plates ? c.days / c.plates : 0, width: (c.qty / max) * 100 }));
    }

    // ── Formato ──
    fmt(v, d = 2) { return (v || 0).toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d }); }
    fmtInt(v) { return Math.round(v || 0).toLocaleString("es-MX"); }
    fmtShort(v) {
        const a = Math.abs(v || 0);
        if (a >= 1e6) return (v / 1e6).toFixed(1) + " M";
        if (a >= 1e3) return (v / 1e3).toFixed(a >= 1e5 ? 0 : 1) + " k";
        return (v || 0).toFixed(0);
    }
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
    segStyle(sg) { return "width:" + Math.max(sg.width || 0, 0) + "%;background:" + sg.color; }
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
