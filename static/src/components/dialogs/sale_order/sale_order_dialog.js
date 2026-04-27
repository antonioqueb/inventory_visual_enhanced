/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class SaleOrderDialog extends Component {
    setup() {
        this.soInfo = this.props.soInfo || {
            count: 0,
            orders: [],
        };

        this.action = useService("action");
    }

    get orders() {
        return this.soInfo.orders || [];
    }

    get hasOrders() {
        return this.orders.length > 0;
    }

    get orderCount() {
        return this.orders.length;
    }

    get orderCountLabel() {
        return this.orderCount === 1 ? "1 orden vinculada" : `${this.orderCount} órdenes vinculadas`;
    }

    get customerSummary() {
        const names = [];

        for (const order of this.orders) {
            if (order.partner_name && !names.includes(order.partner_name)) {
                names.push(order.partner_name);
            }
        }

        if (!names.length) {
            return "Sin cliente";
        }

        if (names.length <= 2) {
            return names.join(" · ");
        }

        return `${names.slice(0, 2).join(" · ")} +${names.length - 2}`;
    }

    get currencySymbol() {
        const symbols = [
            ...new Set(
                this.orders
                    .map((order) => order.currency_symbol)
                    .filter((symbol) => symbol)
            ),
        ];

        return symbols.length === 1 ? symbols[0] : "";
    }

    get totalAmount() {
        return this.orders.reduce((sum, order) => {
            const amount = Number(order.amount_total || 0);
            return sum + amount;
        }, 0);
    }

    get totalAmountLabel() {
        if (!this.orders.length) {
            return "—";
        }

        if (!this.currencySymbol) {
            return "Importe mixto";
        }

        return this.formatCurrency(this.totalAmount, this.currencySymbol);
    }

    get primaryStateLabel() {
        const states = [
            ...new Set(
                this.orders
                    .map((order) => order.state)
                    .filter((state) => state)
            ),
        ];

        if (!states.length) {
            return "Sin estado";
        }

        if (states.length === 1) {
            const firstOrder = this.orders.find((order) => order.state === states[0]);
            return this.getStateLabel(firstOrder);
        }

        return "Estados múltiples";
    }

    getStateMeta(state) {
        const meta = {
            draft: {
                label: "Cotización",
                icon: "fa-pencil-square-o",
                className: "sod-state sod-state--draft",
            },
            sent: {
                label: "Enviada",
                icon: "fa-paper-plane-o",
                className: "sod-state sod-state--sent",
            },
            sale: {
                label: "Orden confirmada",
                icon: "fa-check-circle",
                className: "sod-state sod-state--sale",
            },
            done: {
                label: "Bloqueada",
                icon: "fa-lock",
                className: "sod-state sod-state--done",
            },
            cancel: {
                label: "Cancelada",
                icon: "fa-ban",
                className: "sod-state sod-state--cancel",
            },
        };

        return meta[state] || {
            label: state || "Sin estado",
            icon: "fa-circle",
            className: "sod-state sod-state--default",
        };
    }

    getStateBadgeClass(state) {
        return this.getStateMeta(state).className;
    }

    getStateIcon(state) {
        return this.getStateMeta(state).icon;
    }

    getStateLabel(order) {
        if (!order) {
            return "Sin estado";
        }

        return order.state_display || this.getStateMeta(order.state).label;
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

    formatCurrency(amount, symbol) {
        const formatted = new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(amount || 0));

        return `${symbol || ""} ${formatted}`.trim();
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