/** @odoo-module **/
/**
 * Detalle de lotes del Walkthrough. Subclase de ProductDetails: hereda el
 * agrupado por bloque/contenedor y los formateadores; su template propio
 * elimina el checkbox de carrito y la columna de estado (el material ya no
 * existe en stock) y reemplaza "Ubicación" por la columna "Salida"
 * (entrega o baja, con fecha, documento y cliente/motivo).
 */
import { ProductDetails } from "../product_details/product_details";

export class WalkthroughDetails extends ProductDetails {
    static template = "inventory_visual_enhanced.WalkthroughDetails";

    static props = {
        details: Array,
        detailsLoading: { type: Boolean, optional: true },
        onPhotoClick: { type: Function, optional: true },
        onBlockPhotoClick: { type: Function, optional: true },
        onBlockReportClick: { type: Function, optional: true },
        onNotesClick: { type: Function, optional: true },
        onDetailsClick: { type: Function, optional: true },
        formatNumber: { type: Function, optional: true },
        hasSalesPermissions: { type: Boolean, optional: true },
        hasInventoryPermissions: { type: Boolean, optional: true },
        "*": true,
    };

    getDetailColspan() {
        // lote, salida, dimensiones, color, bloque, atado, pedimento,
        // contenedor, num-placa, P, N, D.
        return 12;
    }

    getSummaryMidColspan() {
        // color, bloque, atado, pedimento, contenedor, num-placa.
        return 6;
    }

    isDelivery(detail) {
        return detail && detail.exit_type === "delivery";
    }

    isWorkshop(detail) {
        return detail && detail.exit_type === "workshop";
    }

    exitBadgeClass(detail) {
        if (this.isDelivery(detail)) return "wt-exit-delivery";
        if (this.isWorkshop(detail)) return "wt-exit-workshop";
        return "wt-exit-scrap";
    }

    exitIconClass(detail) {
        if (this.isDelivery(detail)) return "fa fa-truck";
        if (this.isWorkshop(detail)) return "fa fa-cut";
        return "fa fa-trash";
    }

    getExitLabel(detail) {
        if (this.isDelivery(detail)) return "Entregado";
        if (this.isWorkshop(detail)) return "Taller";
        return "Baja";
    }

    getExitTitle(detail) {
        if (!detail) {
            return "";
        }
        const parts = [];
        if (this.isDelivery(detail)) {
            parts.push("Entregado a cliente");
            if (detail.exit_partner) parts.push(`Cliente: ${detail.exit_partner}`);
        } else if (this.isWorkshop(detail)) {
            parts.push("Consumida como ingrediente en un proceso de taller");
            if (detail.exit_partner) parts.push(detail.exit_partner);
            if (detail.workshop_outputs) parts.push(`Salió como: ${detail.workshop_outputs}`);
        } else {
            parts.push("Dado de baja / desecho");
            if (detail.exit_partner) parts.push(`Motivo: ${detail.exit_partner}`);
        }
        if (detail.exit_doc) parts.push(`Documento: ${detail.exit_doc}`);
        if (detail.exit_date) parts.push(`Fecha: ${this.formatDate(detail.exit_date)}`);
        return parts.join(" | ");
    }
}
