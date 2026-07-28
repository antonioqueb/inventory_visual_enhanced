/** @odoo-module **/
/**
 * Walkthrough: espejo del Inventario Visual para el inventario que YA SALIÓ
 * (entregas a cliente y bajas de material). Controlador independiente — NO
 * subclase del registrado como "inventory_visual_enhanced" — a propósito:
 * inventory_shopping_cart parcha ese prototipo (carrito) y aquí no debe
 * poder venderse material que ya no existe.
 *
 * Reutiliza tal cual: SearchBar, PhotoGalleryDialog, BlockReportDialog,
 * NotesDialog e HistoryDialog. Los detail.id son stock.quant reales (quants
 * en ubicación de cliente o desecho), así que fotos/notas/historial usan
 * los MISMOS métodos backend que el Inventario Visual.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SearchBar } from "../search_bar/search_bar";
import { WalkthroughRow } from "./walkthrough_row";
import { PhotoGalleryDialog } from "../dialogs/photo_gallery/photo_gallery_dialog";
import { BlockReportDialog } from "../dialogs/block_report/block_report_dialog";
import { NotesDialog } from "../dialogs/notes/notes_dialog";
import { HistoryDialog } from "../dialogs/history/history_dialog";

export class WalkthroughController extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            isSearching: false,
            products: [],
            expandedProducts: new Set(),
            productDetails: {},
            isLoading: false,
            hasSearched: false,
            error: null,
            totalProducts: 0,
            hasSalesPermissions: false,
            hasInventoryPermissions: false,
        });

        // Lote inicial: la Búsqueda Global del home puede abrir el
        // Walkthrough con un lote ya salido (params.lot_name).
        this.initialLotName =
            (this.props.action &&
                ((this.props.action.params && this.props.action.params.lot_name) ||
                 (this.props.action.context && this.props.action.context.lot_name))) ||
            "";

        onWillStart(async () => {
            await this.loadPermissions();
        });
    }

    async loadPermissions() {
        try {
            const salesPerms = await this.orm.call("stock.quant", "check_sales_permissions", []);
            const inventoryPerms = await this.orm.call("stock.quant", "check_inventory_permissions", []);
            this.state.hasSalesPermissions = salesPerms;
            this.state.hasInventoryPermissions = inventoryPerms;
        } catch (error) {
            console.error("[WALKTHROUGH] Error verificando permisos:", error);
            this.state.hasSalesPermissions = false;
            this.state.hasInventoryPermissions = false;
        }
    }

    async onSearch(filters) {
        if (!filters || !Object.values(filters).some((v) => v !== null && v !== "")) {
            this.state.hasSearched = false;
            this.state.products = [];
            this.state.expandedProducts.clear();
            this.state.productDetails = {};
            return;
        }

        this.state.isLoading = true;
        this.state.error = null;

        try {
            const result = await this.orm.call(
                "stock.quant",
                "get_walkthrough_grouped_by_product",
                [],
                { filters: filters }
            );

            const products = (result && result.products) || [];
            const missingLots = (result && result.missing_lots) || [];

            this.state.products = products;
            this.state.hasSearched = true;
            this.state.totalProducts = products.length;
            this.state.expandedProducts.clear();
            this.state.productDetails = {};

            if (products.length === 0) {
                this.notification.add(
                    "No se encontraron salidas con los filtros aplicados",
                    { type: "info" }
                );
            }

            if (missingLots.length > 0) {
                this.notification.add(
                    `Lotes no encontrados: ${JSON.stringify(missingLots)}`,
                    { type: "warning", sticky: false }
                );
            }
        } catch (error) {
            console.error("[WALKTHROUGH] Error al buscar:", error);
            this.state.error = "Error al cargar el historial. Por favor intenta nuevamente.";
            this.notification.add("Error al cargar el historial", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async toggleProduct(productId, quantIds) {
        const isExpanded = this.state.expandedProducts.has(productId);

        if (isExpanded) {
            this.state.expandedProducts.delete(productId);
        } else {
            this.state.expandedProducts.add(productId);
            if (!this.state.productDetails[productId]) {
                await this.loadProductDetails(productId, quantIds);
            }
        }

        this.state.expandedProducts = new Set(this.state.expandedProducts);
    }

    async loadProductDetails(productId, quantIds) {
        try {
            const details = await this.orm.call(
                "stock.quant",
                "get_walkthrough_details",
                [],
                { quant_ids: quantIds }
            );
            this.state.productDetails[productId] = details;
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar detalles:", error);
            this.notification.add("Error al cargar detalles del producto", { type: "danger" });
        }
    }

    formatNumber(num) {
        if (num === null || num === undefined) {
            return "0";
        }
        return new Intl.NumberFormat("es-MX", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    isProductExpanded(productId) {
        return this.state.expandedProducts.has(productId);
    }

    getProductDetails(productId) {
        return this.state.productDetails[productId] || [];
    }

    async reloadProductDetailsForDetail(detailId) {
        for (const [productId, details] of Object.entries(this.state.productDetails)) {
            const detail = details.find((d) => d.id === detailId);
            if (detail) {
                const product = this.state.products.find(
                    (p) => p.product_id === parseInt(productId)
                );
                if (product) {
                    await this.loadProductDetails(parseInt(productId), product.quant_ids);
                }
                break;
            }
        }
    }

    async onPhotoClick(detailId) {
        try {
            const photos = await this.orm.call(
                "stock.quant",
                "get_lot_photos",
                [],
                { quant_id: detailId }
            );

            if (photos.error) {
                this.notification.add(photos.error, { type: "warning" });
                return;
            }

            // Solo lectura: el material ya salió, las fotos son historial.
            this.dialog.add(PhotoGalleryDialog, {
                photosData: photos,
                detailId: null,
                readOnly: true,
                title: `Fotografías - ${photos.lot_name}`,
                size: "xl",
            });
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar fotos:", error);
            this.notification.add("Error al cargar fotos", { type: "danger" });
        }
    }

    async onBlockPhotoClick(blockName) {
        try {
            const photosData = await this.orm.call(
                "stock.quant",
                "get_block_photos",
                [],
                { block_name: blockName }
            );
            if (photosData && photosData.error) {
                this.notification.add(photosData.error, { type: "warning" });
                return;
            }
            this.dialog.add(PhotoGalleryDialog, {
                photosData,
                detailId: null,
                readOnly: true,
                title: `Fotografías - ${photosData.lot_name}`,
                size: "xl",
            });
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar fotos del bloque:", error);
            this.notification.add("Error al cargar fotos del bloque", { type: "danger" });
        }
    }

    async onBlockReportClick(blockName) {
        try {
            const report = await this.orm.call(
                "stock.quant",
                "get_block_purchase_report",
                [],
                { block_name: blockName }
            );
            this.dialog.add(BlockReportDialog, { report });
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar el reporte del bloque:", error);
            this.notification.add("Error al cargar el reporte de compra del bloque", { type: "danger" });
        }
    }

    async onNotesClick(detailId) {
        try {
            const notes = await this.orm.call(
                "stock.quant",
                "get_lot_notes",
                [],
                { quant_id: detailId }
            );

            if (notes.error) {
                this.notification.add(notes.error, { type: "warning" });
                return;
            }

            const self = this;
            this.dialog.add(NotesDialog, {
                notesData: notes,
                detailId,
                onReload: async () => await self.reloadProductDetailsForDetail(detailId),
                title: `Notas y Detalles - ${notes.lot_name}`,
                size: "lg",
            });
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar notas:", error);
            this.notification.add("Error al cargar notas", { type: "danger" });
        }
    }

    async onDetailsClick(detailId) {
        if (!this.state.hasSalesPermissions) {
            this.notification.add(
                "No tiene permisos para ver el historial detallado. Contacte al administrador.",
                { type: "warning" }
            );
            return;
        }

        try {
            const history = await this.orm.call(
                "stock.quant",
                "get_lot_history",
                [],
                { quant_id: detailId }
            );

            if (history.error) {
                this.notification.add(history.error, { type: "warning" });
                return;
            }

            this.dialog.add(HistoryDialog, {
                history,
                title: `Historial Detallado - ${history.general_info.lot_name}`,
                size: "xl",
            });
        } catch (error) {
            console.error("[WALKTHROUGH] Error al cargar historial:", error);
            this.notification.add("Error al cargar historial del lote", { type: "danger" });
        }
    }
}

WalkthroughController.template = "inventory_visual_enhanced.WalkthroughView";
WalkthroughController.components = { WalkthroughRow, SearchBar };

WalkthroughController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
    "*": true,
};

registry.category("actions").add("inventory_walkthrough", WalkthroughController);
