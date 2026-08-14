/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { somFormatDate } from "@inventory_visual_enhanced/utils/som_date";

export class HoldInfoDialog extends Component {
    setup() {
        this.holdInfo = this.props.holdInfo;
        this.action = useService("action");
        this.detailData = this.props.detailData;
        this.orm = useService("orm");
        this.notification = useService("notification");
    }
    
    formatDate(dateStr) {
        return somFormatDate(dateStr, { empty: '-' });
    }
    
    async releaseHold() {
        // Implementar lógica para liberar hold
        this.notification.add("Funcionalidad de liberar hold en desarrollo", { type: "info" });
    }
    openHoldOrder() {
        if (!this.holdInfo || !this.holdInfo.order_id) {
            return;
        }
        this.props.close();
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.lot.hold.order",
            res_id: this.holdInfo.order_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

}

HoldInfoDialog.template = "inventory_visual_enhanced.HoldInfoDialog";
HoldInfoDialog.components = { Dialog };