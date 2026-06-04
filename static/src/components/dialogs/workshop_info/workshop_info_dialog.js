/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class WorkshopInfoDialog extends Component {
    setup() {
        this.workshopInfo = this.props.workshopInfo;
        this.detailData = this.props.detailData;
    }

    get orders() {
        return this.workshopInfo?.orders || [];
    }

    get primaryOrder() {
        return this.orders[0] || null;
    }
}

WorkshopInfoDialog.template = "inventory_visual_enhanced.WorkshopInfoDialog";
WorkshopInfoDialog.components = { Dialog };
