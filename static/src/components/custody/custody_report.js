/** @odoo-module **/
/**
 * Custodia de terceros — material vendido que sigue en mi almacén.
 *
 * Reporte de consulta rápida: KPIs + gráficas (antigüedad apilada por
 * estado, reparto por estado, clientes con más material) + tabla por orden
 * con detalle de placas. Todo el cálculo pesado viene del servidor
 * (stock.quant.get_custody_report); aquí solo se filtra, ordena y dibuja.
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
        this.statusMeta = STATUS_META;
        this.state = useState({
            loading: true,
            data: null,
            view: "both",          // both | charts | table
            status: { paid_auth: true, paid: true, auth: true, assigned: true },
            search: "",
            minDays: 0,
            sortKey: "days",
            sortDir: -1,
            expanded: {},
            limit: 60,
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
    onlyStatus(key) {
        for (const k of STATUS_ORDER) this.state.status[k] = k === key;
    }
    allStatus() { for (const k of STATUS_ORDER) this.state.status[k] = true; }
    onSearch(ev) { this.state.search = ev.target.value || ""; this.state.limit = 60; }
    setMinDays(d) { this.state.minDays = this.state.minDays === d ? 0 : d; }
    setView(v) { this.state.view = v; }
    get showCharts() { return this.state.view !== "table"; }
    get showTable() { return this.state.view !== "charts"; }

    get orders() {
        const d = this.state.data;
        if (!d) return [];
        const q = this.state.search.trim().toLowerCase();
        return d.orders.filter((o) => {
            if (!this.state.status[o.status]) return false;
            if (o.days < this.state.minDays) return false;
            if (!q) return true;
            return [o.order, o.customer, o.salesperson, o.project, ...(o.products || [])]
                .some((v) => (v || "").toLowerCase().includes(q));
        });
    }
    get sortedOrders() {
        const k = this.state.sortKey, dir = this.state.sortDir;
        return this.orders.slice().sort((a, b) => {
            const va = a[k], vb = b[k];
            if (typeof va === "string" || typeof vb === "string") return String(va || "").localeCompare(String(vb || "")) * dir;
            return ((va || 0) - (vb || 0)) * dir;
        });
    }
    get visibleOrders() { return this.sortedOrders.slice(0, this.state.limit); }
    showMore() { this.state.limit += 60; }
    sortBy(key) {
        if (this.state.sortKey === key) this.state.sortDir = -this.state.sortDir;
        else { this.state.sortKey = key; this.state.sortDir = key === "order" || key === "customer" ? 1 : -1; }
    }
    sortIcon(key) { return this.state.sortKey === key ? (this.state.sortDir < 0 ? "▼" : "▲") : ""; }
    toggleExpand(id) { this.state.expanded[id] = !this.state.expanded[id]; }
    isExpanded(id) { return !!this.state.expanded[id]; }

    get rows() {
        const ids = new Set(this.orders.map((o) => o.order_id));
        return (this.state.data ? this.state.data.rows : []).filter((r) => ids.has(r.order_id));
    }

    // ── KPIs sobre lo filtrado ──
    get kpis() {
        const rows = this.rows;
        const t = { plates: rows.length, qty: 0, value: 0, days: 0, orders: new Set(), customers: new Set(), over30: 0, over60: 0 };
        for (const r of rows) {
            t.qty += r.qty; t.value += r.value; t.days += r.days;
            t.orders.add(r.order_id); t.customers.add(r.customer_id);
            if (r.days > 30) t.over30 += r.qty;
            if (r.days > 60) t.over60 += r.qty;
        }
        return {
            plates: t.plates, qty: t.qty, value: t.value,
            orders: t.orders.size, customers: t.customers.size,
            avgDays: t.plates ? t.days / t.plates : 0,
            over30: t.over30, over60: t.over60,
            m2days: rows.reduce((a, r) => a + r.qty * r.days, 0),
        };
    }
    get statusStats() {
        const rows = this.rows;
        const out = STATUS_ORDER.map((k) => ({ key: k, ...STATUS_META[k], plates: 0, qty: 0, value: 0, days: 0, orders: new Set(), active: this.state.status[k] }));
        const map = Object.fromEntries(out.map((s) => [s.key, s]));
        for (const r of rows) {
            const s = map[r.status]; if (!s) continue;
            s.plates += 1; s.qty += r.qty; s.value += r.value; s.days += r.days; s.orders.add(r.order_id);
        }
        const totalQty = out.reduce((a, s) => a + s.qty, 0);
        return out.map((s) => ({ ...s, orders: s.orders.size, avgDays: s.plates ? s.days / s.plates : 0, pct: totalQty ? (s.qty / totalQty) * 100 : 0 }));
    }

    // ── Gráfica 1: antigüedad apilada por estado (SVG) ──
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

    // ── Gráfica 2: dona por estado ──
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

    // ── Gráfica 3: clientes con más m² en custodia ──
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
    dot(k) { return "background:" + this.statusColor(k); }

    // ── Navegación / exportación ──
    openOrder(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order", res_id: id, views: [[false, "form"]], target: "current" });
    }
    exportCsv() {
        const head = ["Estado", "Orden", "Cliente", "Vendedor", "Proyecto", "Producto", "Lote", "Bloque", "Medidas", "m2", "Valor", "Ubicación", "Pagado %", "Fecha pago", "Fecha autorización", "Fecha asignación", "Desde", "Días en custodia"];
        const esc = (v) => `"${String(v === undefined || v === null ? "" : v).replace(/"/g, '""')}"`;
        const lines = [head.join(",")];
        for (const r of this.rows) {
            lines.push([r.status_label, r.order, r.customer, r.salesperson, r.project, r.product, r.lot, r.block, r.dims, r.qty, r.value, r.locations, r.paid_pct, r.paid_date, r.auth_date, r.assigned_date, r.base_date, r.days].map(esc).join(","));
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
