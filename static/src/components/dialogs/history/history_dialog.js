/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class HistoryDialog extends Component {
    setup() {
        this.history = this.props.history;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            currentTab: 'general',
        });
    }
    
    switchTab(tabName) {
        this.state.currentTab = tabName;
    }
    
    isActiveTab(tabName) {
        return this.state.currentTab === tabName;
    }
    
    formatCurrency(amount, symbol) {
        return `${symbol} ${new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount)}`;
    }
    
    formatNumber(num) {
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }
}

HistoryDialog.template = "inventory_visual_enhanced.HistoryDialog";
HistoryDialog.components = { Dialog };