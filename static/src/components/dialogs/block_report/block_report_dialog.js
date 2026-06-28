/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class BlockReportDialog extends Component {
    setup() {
        this.report = this.props.report || {};
        this.action = useService("action");
    }

    money(v) {
        const n = parseFloat(v || 0);
        return (
            (this.report.currency || "$") +
            n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        );
    }

    num(v) {
        return parseFloat(v || 0).toLocaleString("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    async openRecord(model, id) {
        if (!id) return;
        this.props.close();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPO() {
        const ids = this.report.po_ids || [];
        if (ids.length === 1) {
            this.openRecord("purchase.order", ids[0]);
        } else if (ids.length > 1) {
            this.props.close();
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Compras del bloque",
                res_model: "purchase.order",
                domain: [["id", "in", ids]],
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
        }
    }
}

BlockReportDialog.template = "inventory_visual_enhanced.BlockReportDialog";
BlockReportDialog.components = { Dialog };
