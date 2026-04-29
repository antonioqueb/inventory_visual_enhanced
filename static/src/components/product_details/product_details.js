/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProductDetails extends Component {
    setup() {
        this.action = useService("action");
    }

    /**
     * Devuelve true si las filas actuales corresponden a tránsito.
     * Esto permite mostrar ETA solo en T. Available / T. Committed,
     * sin ensuciar la vista normal de almacén.
     */
    get hasTransitDetails() {
        const details = this.props.details || [];
        return details.some((detail) => this.isTransitDetail(detail));
    }

    /**
     * Columnas actuales:
     * Sin ETA: 16
     * Con ETA: 17
     *
     * Se mantiene col-checkbox para compatibilidad con inventory_shopping_cart
     * y otros módulos que heredan este template por xpath.
     */
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
     * Agrupa detalles por bloque, calcula totales y ordena.
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
            groups[blockName].totalArea += Number(detail.quantity || 0);

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

                const containerCompare = cA.localeCompare(cB);
                if (containerCompare !== 0) {
                    return containerCompare;
                }

                const lotA = (a.lot_name || "").toLowerCase();
                const lotB = (b.lot_name || "").toLowerCase();
                return lotA.localeCompare(lotB);
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

    getTypeLabel(type) {
        const t = type ? type.toString().toLowerCase() : "";

        if (t === "formato") {
            return "Formatos";
        }

        if (t === "pieza") {
            return "Piezas";
        }

        return "Placas";
    }

    formatNumber(value) {
        if (this.props.formatNumber) {
            return this.props.formatNumber(value);
        }

        return new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(value || 0));
    }

    /**
     * Formato:
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

    getPackingListLabel(detail) {
        if (!detail) {
            return "—";
        }

        if (detail.packing_list_name) {
            return detail.packing_list_name;
        }

        if (detail.packing_shipment_name) {
            return detail.packing_shipment_name;
        }

        if (detail.has_packing_list) {
            return "Ver embarque";
        }

        return "—";
    }

    getPackingListTitle(detail) {
        if (!detail || !detail.has_packing_list) {
            return "Sin Packing List vinculado";
        }

        const parts = [];

        if (detail.packing_list_name) {
            parts.push(`Packing List: ${detail.packing_list_name}`);
        }

        if (detail.packing_shipment_name) {
            parts.push(`Embarque: ${detail.packing_shipment_name}`);
        }

        if (detail.packing_container_name) {
            parts.push(`Contenedor: ${detail.packing_container_name}`);
        }

        return parts.join(" | ") || "Abrir embarque";
    }

    async openPackingList(detail, ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        if (!detail || !detail.has_packing_list) {
            return;
        }

        /*
         * Regla solicitada:
         * El hipervínculo visible está en columna Packing List,
         * pero debe llevar al Embarque proveedor, porque tu Packing List
         * operativamente representa el embarque.
         */
        if (detail.packing_shipment_id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Embarque proveedor",
                res_model: "supplier.shipment",
                res_id: detail.packing_shipment_id,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }

        /*
         * Fallback: si por alguna razón solo se resolvió el PL
         * pero no el embarque, abre el Packing List.
         */
        if (detail.packing_list_id) {
            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Packing List",
                res_model: "supplier.shipment.packing",
                res_id: detail.packing_list_id,
                views: [[false, "form"]],
                target: "current",
            });
        }
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
    onSalesPersonClick: { type: Function, optional: true },

    formatNumber: { type: Function, optional: true },
    hasSalesPermissions: { type: Boolean, optional: true },
    hasInventoryPermissions: { type: Boolean, optional: true },

    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    onMobileSelectAll: { type: Function, optional: true },

    "*": true,
};