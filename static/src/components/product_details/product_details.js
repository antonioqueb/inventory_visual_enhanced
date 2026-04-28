/** @odoo-module **/
import { Component } from "@odoo/owl";

export class ProductDetails extends Component {
    /**
     * Devuelve true si las filas actuales corresponden a tránsito.
     * Esto permite mostrar ETA solo en T. Available / T. Committed,
     * sin ensuciar la vista normal de almacén.
     */
    get hasTransitDetails() {
        const details = this.props.details || [];
        return details.some((detail) => this.isTransitDetail(detail));
    }

    getDetailColspan() {
        return this.hasTransitDetails ? 17 : 16;
    }

    isTransitDetail(detail) {
        if (!detail) {
            return false;
        }

        return (
            detail.is_transit === true ||
            detail.location_usage === "transit" ||
            ["available", "committed"].includes(detail.transit_inventory_state || "")
        );
    }

    /**
     * Getter principal que transforma la lista plana de detalles (props.details)
     * en una lista agrupada por Bloque, calculando totales y ordenando
     * de mayor cantidad de placas a menor.
     */
    get groupedAndSortedDetails() {
        const details = this.props.details || [];
        const groups = {};

        for (const detail of details) {
            const blockName = detail.bloque || "Sin Bloque";

            if (!groups[blockName]) {
                groups[blockName] = {
                    blockName: blockName,
                    items: [],
                    totalArea: 0,
                    count: 0,
                    productType: null,
                };
            }

            groups[blockName].items.push(detail);
            groups[blockName].count += 1;
            groups[blockName].totalArea += detail.quantity || 0;

            if (!groups[blockName].productType && detail.tipo) {
                groups[blockName].productType = detail.tipo;
            }
        }

        const groupArray = Object.values(groups);

        groupArray.sort((a, b) => b.count - a.count);

        for (const group of groupArray) {
            group.items.sort((a, b) => {
                const cA = (a.contenedor || "").toLowerCase();
                const cB = (b.contenedor || "").toLowerCase();
                return cA.localeCompare(cB);
            });

            let lastContenedor = null;

            for (const item of group.items) {
                const currentContenedor = item.contenedor || "";

                if (lastContenedor !== null && currentContenedor !== lastContenedor) {
                    item._containerBreak = true;
                } else {
                    item._containerBreak = false;
                }

                lastContenedor = currentContenedor;
            }
        }

        return groupArray;
    }

    onMobileSelectAll(ev) {
        if (this.props.onMobileSelectAll) {
            this.props.onMobileSelectAll(ev);
        }
    }

    getUnitLabel(type) {
        const t = type ? type.toString().toLowerCase() : "";
        return t === "pieza" ? "pza" : "m²";
    }

    /**
     * Formato para ETA:
     * 28 / Abril / 2026
     */
    formatDate(value) {
        if (!value) {
            return "—";
        }

        const raw = String(value);
        const datePart = raw.includes(" ") ? raw.split(" ")[0] : raw;
        const parts = datePart.split("-");

        if (parts.length !== 3) {
            return raw;
        }

        const [year, month, day] = parts;

        const monthNames = {
            "01": "Enero",
            "02": "Febrero",
            "03": "Marzo",
            "04": "Abril",
            "05": "Mayo",
            "06": "Junio",
            "07": "Julio",
            "08": "Agosto",
            "09": "Septiembre",
            "10": "Octubre",
            "11": "Noviembre",
            "12": "Diciembre",
        };

        return `${parseInt(day, 10)} / ${monthNames[month] || month} / ${year}`;
    }

    getEtaText(detail) {
        if (!this.isTransitDetail(detail)) {
            return "—";
        }

        if (!detail.eta) {
            return "No registrada";
        }

        return this.formatDate(detail.eta);
    }
}

ProductDetails.template = "inventory_visual_enhanced.ProductDetails";

ProductDetails.props = {
    details: Array,

    areAllCurrentProductSelected: { type: Function, optional: true },
    isInCart: { type: Function, optional: true },

    getDisplayQuantity: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    onInputManualQuantity: { type: Function, optional: true },
    onPhotoClick: { type: Function, optional: true },
    onNotesClick: { type: Function, optional: true },
    onDetailsClick: { type: Function, optional: true },
    onHoldClick: { type: Function, optional: true },
    onSaleOrderClick: { type: Function, optional: true },
    formatNumber: { type: Function, optional: true },
    hasSalesPermissions: { type: Boolean, optional: true },
    onSalesPersonClick: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    hasInventoryPermissions: { type: Boolean, optional: true },
};