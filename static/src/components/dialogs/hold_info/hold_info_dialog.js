/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class HoldInfoDialog extends Component {
    setup() {
        this.holdInfo = this.props.holdInfo;
        this.detailData = this.props.detailData;
        this.orm = useService("orm");
        this.notification = useService("notification");
    }
    
    formatDate(dateStr) {
        if (!dateStr) return '-';
        return dateStr;
    }
    
    async releaseHold() {
        // Implementar lógica para liberar hold
        this.notification.add("Funcionalidad de liberar hold en desarrollo", { type: "info" });
    }
}

HoldInfoDialog.template = "inventory_visual_enhanced.HoldInfoDialog";
HoldInfoDialog.components = { Dialog };