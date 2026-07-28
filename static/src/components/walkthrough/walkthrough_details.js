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

    getExitLabel(detail) {
        return this.isDelivery(detail) ? "Entregado" : "Baja";
    }

    getExitTitle(detail) {
        if (!detail) {
            return "";
        }
        const parts = [];
        if (this.isDelivery(detail)) {
            parts.push("Entregado a cliente");
            if (detail.exit_partner) parts.push(`Cliente: ${detail.exit_partner}`);
        } else {
            parts.push("Dado de baja / desecho");
            if (detail.exit_partner) parts.push(`Motivo: ${detail.exit_partner}`);
        }
        if (detail.exit_doc) parts.push(`Documento: ${detail.exit_doc}`);
        if (detail.exit_date) parts.push(`Fecha: ${detail.exit_date}`);
        return parts.join(" | ");
    }
}
