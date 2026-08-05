/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProductDetails extends Component {
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        // Orden por antigüedad del lote (Stone Profit): 'desc' = más nuevos
        // arriba (default), 'asc' = más viejos arriba. Se alterna clickeando
        // el encabezado de la columna Lote.
        this.state = useState({ lotSortDir: "desc" });
    }

    toggleLotSort() {
        this.state.lotSortDir = this.state.lotSortDir === "desc" ? "asc" : "desc";
    }

    // El modo de agrupación viene de la barra de filtros (props):
    // 'block' = por bloque (default); 'prefix' = por el segmento inicial
    // del folio del lote (141231-2 → 141231), que corresponde al contenedor.
    get groupMode() {
        return this.props.groupMode === "prefix" ? "prefix" : "block";
    }

    lotPrefix(lotName) {
        const m = String(lotName || "").trim().match(/^([A-Za-z]*\d+)/);
        return m ? m[1].toUpperCase() : "";
    }

    // Clave de antigüedad del lote. El folio es "<segmento>-<consecutivo>":
    // - Segmento numérico (Stone Profit): más pequeño = más antiguo.
    // - Segmento "S<n>" (procesos propios, desde ago/2026): SIEMPRE más
    //   nuevo que cualquier numérico; entre S, más pequeño = más antiguo.
    lotSeriesKey(lotName) {
        const name = String(lotName || "").trim();
        const m = name.match(/^([A-Za-z]*)(\d+)/);
        if (!m) {
            return [-1, -1, -1];
        }
        const isS = m[1].toUpperCase() === "S" ? 1 : 0;
        const num = parseInt(m[2], 10) || 0;
        const consMatch = name.slice(m[0].length).match(/(\d+)/);
        const cons = consMatch ? parseInt(consMatch[1], 10) : 0;
        return [isS, num, cons];
    }

    compareLotKeys(a, b) {
        for (let i = 0; i < 3; i++) {
            if (a[i] !== b[i]) {
                return a[i] - b[i];
            }
        }
        return 0;
    }

    get hasTransitDetails() {
        const details = this.props.details || [];
        return details.some((detail) => this.isTransitDetail(detail));
    }

    get hasPackingList() {
        const details = this.props.details || [];
        return details.some((detail) => detail && detail.has_packing_list);
    }

    getDetailColspan() {
        // Base 14: checkbox, lot, location, dimensions, color, bloque, atado,
        // pedimento, contenedor, num-placa, P, N, D, E.
        // +1 si hay ETA (tránsito), +1 si hay packing list.
        return 14 + (this.hasTransitDetails ? 1 : 0) + (this.hasPackingList ? 1 : 0);
    }

    getSummaryMidColspan() {
        // Columnas centrales fusionadas en la fila de resumen del bloque:
        // color, bloque, atado, pedimento, contenedor, num-placa = 6.
        // +1 si la columna Packing List está visible.
        return 6 + (this.hasPackingList ? 1 : 0);
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
        const byPrefix = this.groupMode === "prefix";

        for (const detail of details) {
            const blockName = byPrefix
                ? (this.lotPrefix(detail.lot_name) || "Sin prefijo")
                : (detail.bloque || "Sin Bloque");

            if (!groups[blockName]) {
                groups[blockName] = {
                    blockName: blockName,
                    isBlock: !byPrefix,
                    items: [],
                    totalArea: 0,
                    count: 0,
                    productType: null,
                    hasPhoto: false,
                };
            }

            groups[blockName].items.push(detail);
            groups[blockName].count += 1;
            groups[blockName].totalArea += detail.quantity || 0;
            if (detail.block_has_photo) {
                groups[blockName].hasPhoto = true;
            }

            if (!groups[blockName].productType && detail.tipo) {
                groups[blockName].productType = detail.tipo;
            }

            // Clave de antigüedad del bloque = su lote más NUEVO.
            const key = this.lotSeriesKey(detail.lot_name);
            if (!groups[blockName].sortKey ||
                this.compareLotKeys(key, groups[blockName].sortKey) > 0) {
                groups[blockName].sortKey = key;
            }
        }

        const groupArray = Object.values(groups);

        // Bloques ordenados por antigüedad del segmento del lote:
        // desc (default) = más nuevos arriba, asc = más viejos arriba.
        const dir = this.state.lotSortDir === "asc" ? 1 : -1;
        groupArray.sort(
            (a, b) =>
                dir * this.compareLotKeys(a.sortKey, b.sortKey) ||
                b.count - a.count ||
                a.blockName.localeCompare(b.blockName)
        );

        for (const group of groupArray) {
            group.items.sort((a, b) => {
                const cA = (a.contenedor || "").toLowerCase();
                const cB = (b.contenedor || "").toLowerCase();

                const containerCompare = cA.localeCompare(cB);
                if (containerCompare !== 0) {
                    return containerCompare;
                }

                // Dentro del bloque el consecutivo SIEMPRE va del más chico
                // al más grande — la flecha solo invierte el orden de los
                // bloques (por prefijo), no el de las placas.
                const lotCompare = this.compareLotKeys(
                    this.lotSeriesKey(a.lot_name),
                    this.lotSeriesKey(b.lot_name)
                );
                if (lotCompare !== 0) {
                    return lotCompare;
                }

                const lotA = (a.lot_name || "").toLowerCase();
                const lotB = (b.lot_name || "").toLowerCase();
                return lotA.localeCompare(lotB, undefined, { numeric: true });
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
    onBlockPhotoClick: { type: Function, optional: true },
    onBlockReportClick: { type: Function, optional: true },
    onNotesClick: { type: Function, optional: true },
    onDetailsClick: { type: Function, optional: true },
    onHoldClick: { type: Function, optional: true },
    onSaleOrderClick: { type: Function, optional: true },
    onWorkshopClick: { type: Function, optional: true },
    onSalesPersonClick: { type: Function, optional: true },

    formatNumber: { type: Function, optional: true },
    hasSalesPermissions: { type: Boolean, optional: true },
    hasInventoryPermissions: { type: Boolean, optional: true },

    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    onMobileSelectAll: { type: Function, optional: true },

    "*": true,
};