/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SearchBar } from "../search_bar/search_bar"; // <--- Importamos SearchBar
import { ProductRow } from "../product_row/product_row";
import { PhotoGalleryDialog } from "../dialogs/photo_gallery/photo_gallery_dialog";
import { NotesDialog } from "../dialogs/notes/notes_dialog";
import { HistoryDialog } from "../dialogs/history/history_dialog";
import { CreateHoldDialog } from "../dialogs/hold/hold_dialog";
import { SaleOrderDialog } from "../dialogs/sale_order/sale_order_dialog";
import { HoldInfoDialog } from "../dialogs/hold_info/hold_info_dialog";

class InventoryVisualController extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            // Estado de búsqueda
            isSearching: false,
            products: [],
            expandedProducts: new Set(),
            productDetails: {},
            isLoading: false,
            hasSearched: false,
            error: null,
            totalProducts: 0,
            
            // Permisos
            hasSalesPermissions: false,
            hasInventoryPermissions: false,
        });

        onWillStart(async () => {
            await this.loadPermissions();
        });
    }

    async loadPermissions() {
        try {
            const salesPerms = await this.orm.call('stock.quant', 'check_sales_permissions', []);
            const inventoryPerms = await this.orm.call('stock.quant', 'check_inventory_permissions', []);
            
            this.state.hasSalesPermissions = salesPerms;
            this.state.hasInventoryPermissions = inventoryPerms;
        } catch (error) {
            console.error('[PERMISOS] Error verificando permisos:', error);
            this.state.hasSalesPermissions = false;
            this.state.hasInventoryPermissions = false;
        }
    }

    // Esta función recibe los filtros del componente hijo SearchBar
    async onSearch(filters) {
        // Si filters es null o no tiene valores activos, limpiamos la vista
        if (!filters || !Object.values(filters).some(v => v !== null && v !== '')) {
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
                "get_inventory_grouped_by_product",
                [],
                { filters: filters }
            );

            // Manejo de compatibilidad: Si viene como lista (versión anterior) o dict (nueva versión)
            let products = [];
            let missingLots = [];

            if (Array.isArray(result)) {
                products = result;
            } else if (result && typeof result === 'object') {
                products = result.products || [];
                missingLots = result.missing_lots || [];
            }

            this.state.products = products;
            this.state.hasSearched = true;
            this.state.totalProducts = products.length;
            this.state.expandedProducts.clear();
            this.state.productDetails = {};

            if (products.length === 0) {
                this.notification.add(
                    "No se encontraron productos con los filtros aplicados",
                    { type: "info" }
                );
            }

            // Notificación de lotes no encontrados (Efímera y no limitante)
            if (missingLots.length > 0) {
                const missingJson = JSON.stringify(missingLots);
                this.notification.add(
                    `Lotes no encontrados: ${missingJson}`, 
                    { type: "warning", sticky: false } 
                );
            }

        } catch (error) {
            console.error("Error al buscar productos:", error);
            this.state.error = "Error al cargar los productos. Por favor intenta nuevamente.";
            this.notification.add("Error al cargar los productos", {
                type: "danger",
            });
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
                "get_quant_details",
                [],
                {
                    quant_ids: quantIds,
                }
            );

            this.state.productDetails[productId] = details;

        } catch (error) {
            console.error("Error al cargar detalles:", error);
            this.notification.add("Error al cargar detalles del producto", {
                type: "danger",
            });
        }
    }

    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
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
            
            this.openPhotoGalleryModal(photos, detailId);
            
        } catch (error) {
            console.error("Error al cargar fotos:", error);
            this.notification.add("Error al cargar fotos", { type: "danger" });
        }
    }
    
    openPhotoGalleryModal(photosData, detailId) {
        const self = this;
        this.dialog.add(PhotoGalleryDialog, {
            photosData,
            detailId,
            onReload: async () => await self.reloadProductDetailsForDetail(detailId),
            title: `Fotografías - ${photosData.lot_name}`,
            size: 'xl',
        });
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
            
            this.openNotesModal(notes, detailId);
            
        } catch (error) {
            console.error("Error al cargar notas:", error);
            this.notification.add("Error al cargar notas", { type: "danger" });
        }
    }
    
    openNotesModal(notesData, detailId) {
        const self = this;
        this.dialog.add(NotesDialog, {
            notesData,
            detailId,
            onReload: async () => await self.reloadProductDetailsForDetail(detailId),
            title: `Notas y Detalles - ${notesData.lot_name}`,
            size: 'lg',
        });
    }

    async reloadProductDetailsForDetail(detailId) {
        for (const [productId, details] of Object.entries(this.state.productDetails)) {
            const detail = details.find(d => d.id === detailId);
            if (detail) {
                const product = this.state.products.find(p => p.product_id === parseInt(productId));
                if (product) {
                    await this.loadProductDetails(parseInt(productId), product.quant_ids);
                }
                break;
            }
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
            
            this.openHistoryModal(history);
            
        } catch (error) {
            console.error("Error al cargar historial:", error);
            this.notification.add("Error al cargar historial del lote", { type: "danger" });
        }
    }

    openHistoryModal(history) {
        this.dialog.add(HistoryDialog, {
            history,
            title: `Historial Detallado - ${history.general_info.lot_name}`,
            size: 'xl',
        });
    }

    onSalesPersonClick(detailId) {
        this.notification.add(
            "Funcionalidad de cliente/vendedor en desarrollo",
            { type: "info" }
        );
    }

    async onHoldClick(detailId, holdInfo) {
        if (!holdInfo || !holdInfo.id) {
            if (!this.state.hasSalesPermissions) {
                this.notification.add(
                    "No tiene permisos para crear apartados. Contacte al administrador.", 
                    { type: "warning" }
                );
                return;
            }
            await this.openCreateHoldDialog(detailId);
            return;
        }

        let detailData = null;
        for (const [productId, details] of Object.entries(this.state.productDetails)) {
            const detail = details.find(d => d.id === detailId);
            if (detail) {
                detailData = detail;
                break;
            }
        }
        
        if (!detailData) {
            this.notification.add("No se encontró información del lote", { type: "danger" });
            return;
        }

        this.openHoldInfoDialog(holdInfo, detailData);
    }

    openHoldInfoDialog(holdInfo, detailData) {
        this.dialog.add(HoldInfoDialog, {
            holdInfo,
            detailData,
            title: `Apartado Activo - ${detailData.lot_name}`,
            size: 'lg',
        });
    }

    async openCreateHoldDialog(detailId) {
        const self = this;
        
        try {
            let detailData = null;
            
            for (const [productId, details] of Object.entries(this.state.productDetails)) {
                const detail = details.find(d => d.id === detailId);
                if (detail) {
                    detailData = detail;
                    detailData.product_id = parseInt(productId);
                    
                    const product = this.state.products.find(p => p.product_id === parseInt(productId));
                    if (product) {
                        detailData.product_name = product.product_name;
                    }
                    
                    break;
                }
            }
            
            if (!detailData) {
                this.notification.add("No se encontró información del lote", { type: "danger" });
                return;
            }
            
            this.dialog.add(CreateHoldDialog, {
                detailData,
                detailId,
                onReload: async () => await self.reloadProductDetailsForDetail(detailId),
                title: `Crear Apartado - ${detailData.lot_name}`,
                size: 'lg',
            });
            
        } catch (error) {
            console.error("Error abriendo diálogo:", error);
            this.notification.add("Error al abrir diálogo de apartado", { type: "danger" });
        }
    }

    async onSaleOrderClick(detailId, saleOrderIds) {
        if (!saleOrderIds || saleOrderIds.length === 0) {
            this.notification.add("No hay órdenes de venta asociadas", { type: "info" });
            return;
        }

        try {
            const soInfo = await this.orm.call(
                "stock.quant",
                "get_sale_order_info",
                [],
                { sale_order_ids: saleOrderIds }
            );
            
            if (soInfo.error) {
                this.notification.add(soInfo.error, { type: "warning" });
                return;
            }
            
            this.openSaleOrderModal(soInfo);
            
        } catch (error) {
            console.error("Error al cargar info de órdenes de venta:", error);
            this.notification.add("Error al cargar información de órdenes de venta", { type: "danger" });
        }
    }

    openSaleOrderModal(soInfo) {
        this.dialog.add(SaleOrderDialog, {
            soInfo,
            title: `Órdenes de Venta (${soInfo.count})`,
            size: 'lg',
        });
    }
}

InventoryVisualController.template = "inventory_visual_enhanced.InventoryView";
InventoryVisualController.components = { ProductRow, SearchBar }; // <--- Añadimos SearchBar a componentes

InventoryVisualController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
    "*": true,
};

registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);