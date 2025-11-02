/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class CreateHoldDialog extends Component {
    setup() {
        this.detailData = this.props.detailData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            searchTerm: '',
            partners: [],
            selectedPartnerId: null,
            selectedPartnerName: '',
            notas: '',
            isCreating: false,
        });
        
        this.searchTimeout = null;
    }
    
    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }
    
    onSearchPartner(ev) {
        const value = ev.target.value;
        this.state.searchTerm = value;
        
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        this.searchTimeout = setTimeout(() => {
            this.searchPartners();
        }, 300);
    }
    
    async searchPartners() {
        try {
            const partners = await this.orm.call(
                "stock.quant",
                "search_partners",
                [],
                {
                    name: this.state.searchTerm.trim()
                }
            );
            
            this.state.partners = partners;
        } catch (error) {
            console.error("Error buscando clientes:", error);
            this.notification.add("Error al buscar clientes", { type: "danger" });
        }
    }
    
    selectPartner(partner) {
        this.state.selectedPartnerId = partner.id;
        this.state.selectedPartnerName = partner.display_name;
    }
    
    onNotasChange(ev) {
        this.state.notas = ev.target.value;
    }
    
    async createHold() {
        if (!this.state.selectedPartnerId) {
            this.notification.add("Debe seleccionar un cliente", { type: "warning" });
            return;
        }
        
        this.state.isCreating = true;
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "create_lot_hold",
                [],
                {
                    quant_id: this.detailId,
                    partner_id: this.state.selectedPartnerId,
                    notas: this.state.notas
                }
            );
            
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result.success) {
                this.notification.add(result.message, { type: "success" });
                this.props.close();
                
                if (this.props.onReload) {
                    await this.props.onReload();
                }
            }
        } catch (error) {
            console.error("Error creando apartado:", error);
            this.notification.add("Error al crear apartado", { type: "danger" });
        } finally {
            this.state.isCreating = false;
        }
    }
}

CreateHoldDialog.template = "inventory_visual_enhanced.CreateHoldDialog";
CreateHoldDialog.components = { Dialog };