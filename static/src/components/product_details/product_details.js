/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProductDetails extends Component {
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
    }

    get hasTransitDetails() {
        const details = this.props.details || [];
        return details.some((detail) => this.isTransitDetail(detail));
    }

    getDetailColspan() {
        return this.hasTransitDetails ? 18 : 17;
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
        if (!detail || !detail.has_packing_list) {
            return "—";
        }

        return "Accesar";
    }

    getPackingListTitle(detail) {
        if (!detail || !detail.has_packing_list) {
            return "Sin Packing List vinculado";
        }

        const parts = ["Accesar Packing List / Embarque"];

        if (detail.packing_list_name) {
            parts.push(`Packing List: ${detail.packing_list_name}`);
        }

        if (detail.packing_shipment_name) {
            parts.push(`Embarque proveedor: ${detail.packing_shipment_name}`);
        }

        if (detail.packing_voyage_name) {
            parts.push(`Viaje: ${detail.packing_voyage_name}`);
        }

        if (detail.packing_container_name) {
            parts.push(`Contenedor: ${detail.packing_container_name}`);
        }

        return parts.join(" | ");
    }

    async openPackingList(detail, ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        console.log("[Inventario Visual] openPackingList - detail:", {
            id: detail?.id,
            has_packing_list: detail?.has_packing_list,
            packing_shipment_id: detail?.packing_shipment_id,
            packing_list_id: detail?.packing_list_id,
            packing_row_id: detail?.packing_row_id,
            packing_voyage_id: detail?.packing_voyage_id,
            packing_voyage_name: detail?.packing_voyage_name,
        });

        if (!detail) {
            console.warn("[Inventario Visual] openPackingList: detail vacío");
            return;
        }

        if (!detail.has_packing_list) {
            this.notification.add(
                "Este lote no tiene Packing List, embarque o viaje vinculado.",
                { type: "warning" }
            );
            return;
        }

        const shipmentId = detail.packing_shipment_id;
        const packingListId = detail.packing_list_id;
        const voyageId = detail.packing_voyage_id;

        try {
            // Prioridad 1: Embarque proveedor.
            if (shipmentId) {
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Embarque proveedor",
                    res_model: "supplier.shipment",
                    res_id: shipmentId,
                    views: [[false, "form"]],
                    target: "current",
                });
                return;
            }

            // Prioridad 2: Packing List proveedor.
            if (packingListId) {
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Packing List",
                    res_model: "supplier.shipment.packing",
                    res_id: packingListId,
                    views: [[false, "form"]],
                    target: "current",
                });
                return;
            }

            // Prioridad 3: Viaje / Embarque de Torre de Control.
            // Este fallback cubre el caso donde no existe supplier.shipment,
            // pero sí existe stock.transit.voyage.
            if (voyageId) {
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Embarque",
                    res_model: "stock.transit.voyage",
                    res_id: voyageId,
                    views: [[false, "form"]],
                    target: "current",
                });
                return;
            }

            this.notification.add(
                "No se pudo localizar el embarque, Packing List o viaje para este lote.",
                { type: "warning" }
            );
        } catch (error) {
            console.error("[Inventario Visual] Error abriendo packing list / embarque:", error);
            this.notification.add(
                `Error al abrir el embarque: ${error.message || error}`,
                { type: "danger", sticky: true }
            );
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