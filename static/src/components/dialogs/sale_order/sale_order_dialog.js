/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class SaleOrderDialog extends Component {
    setup() {
        this.soInfo = this.props.soInfo;
        this.orm = useService("orm");
        this.notification = useService("notification");
    }
    
    formatCurrency(amount, symbol) {
        return `${symbol} ${new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount)}`;
    }
    
    getStateBadgeClass(state) {
        const stateClasses = {
            'draft': 'bg-secondary',
            'sent': 'bg-info',
            'sale': 'bg-success',
            'done': 'bg-dark',
            'cancel': 'bg-danger',
        };
        return stateClasses[state] || 'bg-secondary';
    }
}

SaleOrderDialog.template = "inventory_visual_enhanced.SaleOrderDialog";
SaleOrderDialog.components = { Dialog };