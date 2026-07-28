/** @odoo-module **/
/**
 * Fila de producto del Walkthrough. Subclase de ProductRow: hereda el
 * tooltip de precios y el recorte de categoría; cambia las métricas
 * (Salida total / Entregado / De baja) y el filtrado de detalles por tipo
 * de salida en lugar de stock/hold/comprometido.
 */
import { ProductRow } from "../product_row/product_row";
import { WalkthroughDetails } from "./walkthrough_details";

export class WalkthroughRow extends ProductRow {
    static template = "inventory_visual_enhanced.WalkthroughRow";
    static components = { WalkthroughDetails };

    static props = {
        product: Object,
        isExpanded: Boolean,
        details: Array,
        onToggle: Function,
        onPhotoClick: Function,
        onBlockPhotoClick: { type: Function, optional: true },
        onBlockReportClick: { type: Function, optional: true },
        onNotesClick: Function,
        onDetailsClick: Function,
        formatNumber: Function,
        hasSalesPermissions: { type: Boolean, optional: true },
        hasInventoryPermissions: { type: Boolean, optional: true },
    };

    setup() {
        super.setup();
        // El filtro base del Walkthrough es "todas las salidas".
        this.state.activeFilter = "all";
    }

    handleFilterClick(filterType) {
        if (!this.props.isExpanded) {
            this.props.onToggle(this.props.product.quant_ids);
        }

        if (this.state.activeFilter === filterType && filterType !== "all") {
            this.state.activeFilter = "all";
        } else {
            this.state.activeFilter = filterType;
        }
    }

    get filteredDetails() {
        const details = this.props.details || [];
        const filter = this.state.activeFilter;

        return details.filter((d) => {
            if (filter === "delivered") {
                return d.exit_type === "delivery";
            }
            if (filter === "scrapped") {
                return d.exit_type === "scrap";
            }
            return true;
        });
    }
}
