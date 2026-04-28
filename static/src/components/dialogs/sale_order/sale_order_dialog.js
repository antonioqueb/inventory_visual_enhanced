/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class SaleOrderDialog extends Component {
    setup() {
        this.soInfo = this.props.soInfo || {
            count: 0,
            orders: [],
            lot_info: {},
        };

        this.action = useService("action");
    }

    get orders() {
        return this.soInfo.orders || [];
    }

    get lotInfo() {
        return this.soInfo.lot_info || {};
    }

    get hasOrders() {
        return this.orders.length > 0;
    }

    get hasLotInfo() {
        return !!(this.lotInfo && (this.lotInfo.lot_name || this.lotInfo.product_name));
    }

    get orderCount() {
        return this.orders.length;
    }

    get orderCountLabel() {
        return this.orderCount === 1 ? "1 orden de venta" : `${this.orderCount} órdenes de venta`;
    }

    get isTransitLot() {
        return !!this.lotInfo.is_transit;
    }

    get lotUnitLabel() {
        const tipo = (this.lotInfo.tipo || "").toString().toLowerCase();
        return tipo === "pieza" ? "pza" : "m²";
    }

    getPaymentBadgeClass(status) {
        const map = {
            paid: "sod-payment-badge sod-payment-badge--paid",
            partial: "sod-payment-badge sod-payment-badge--partial",
            no_payment: "sod-payment-badge sod-payment-badge--none",
        };

        return map[status] || map.no_payment;
    }

    getPaymentIcon(status) {
        const map = {
            paid: "fa-check-circle",
            partial: "fa-adjust",
            no_payment: "fa-exclamation-circle",
        };

        return map[status] || map.no_payment;
    }

    clampPercentage(value) {
        const number = Number(value || 0);

        if (number < 0) {
            return 0;
        }

        if (number > 100) {
            return 100;
        }

        return number;
    }

    formatCurrency(amount, symbol) {
        const formatted = new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(amount || 0));

        return `${symbol || ""} ${formatted}`.trim();
    }

    formatNumber(num) {
        return new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(num || 0));
    }

    formatPercent(value) {
        return `${this.formatNumber(this.clampPercentage(value))}%`;
    }

    formatDate(value) {
        if (!value) {
            return "—";
        }

        const raw = String(value);
        const datePart = raw.includes(" ") ? raw.split(" ")[0] : raw;
        const parts = datePart.split("-");

        if (parts.length !== 3) {
            return raw;
        }

        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    getInitials(name) {
        if (!name) {
            return "SO";
        }

        const parts = name
            .trim()
            .split(/\s+/)
            .filter((part) => part);

        if (!parts.length) {
            return "SO";
        }

        return parts
            .slice(0, 2)
            .map((part) => part[0])
            .join("")
            .toUpperCase();
    }

    async openSaleOrder(orderId, ev) {
        if (ev) {
            ev.stopPropagation();
        }

        if (!orderId) {
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: orderId,
            views: [[false, "form"]],
            target: "current",
        });

        if (this.props.close) {
            this.props.close();
        }
    }
}

SaleOrderDialog.template = "inventory_visual_enhanced.SaleOrderDialog";
SaleOrderDialog.components = { Dialog };