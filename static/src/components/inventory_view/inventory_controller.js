/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
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
        this.root = useRef("root");

        this.state = useState({
            // Filtros
            filters: {
                product_name: '',
                almacen_id: null,
                ubicacion_id: null,
                tipo: '',
                categoria_id: null,
                grupo: '',
                acabado: '',
                grosor: '',
                numero_serie: '',
                bloque: '',
                pedimento: '',
                contenedor: '',
                atado: '',
            },
            
            // Opciones para dropdowns
            almacenes: [],
            ubicaciones: [],
            tipos: [],
            categorias: [],
            grupos: [],
            acabados: [],
            grosores: [],
            
            // Estado de búsqueda
            isSearching: false,
            products: [],
            expandedProducts: new Set(),
            productDetails: {},
            isLoading: false,
            hasSearched: false,
            error: null,
            totalProducts: 0,
            totalAvailable: 0,
            totalReserved: 0,
            
            // UI
            showAdvancedFilters: false,
        });

        this.searchTimeout = null;
        this.searchDelay = 500;

        onWillStart(async () => {
            await this.loadFilterOptions();
        });

        onMounted(() => {
            this.setupScrollListener();
        });
    }

    setupScrollListener() {
        if (!this.root.el) return;
        
        const searchBar = this.root.el.querySelector('.o_inventory_visual_searchbar');
        if (!searchBar) return;

        let ticking = false;
        
        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(() => {
                    if (window.scrollY > 10) {
                        searchBar.classList.add('scrolled');
                    } else {
                        searchBar.classList.remove('scrolled');
                    }
                    ticking = false;
                });
                ticking = true;
            }
        });
    }

    async loadFilterOptions() {
        try {
            // Cargar almacenes
            const almacenes = await this.orm.searchRead(
                "stock.warehouse",
                [],
                ["id", "name"],
                { order: "name" }
            );
            this.state.almacenes = almacenes;

            // Cargar categorías
            const categorias = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name", "complete_name"],
                { order: "complete_name" }
            );
            this.state.categorias = categorias;

            // Cargar opciones de selection fields
            const fieldInfo = await this.orm.call(
                "stock.quant",
                "fields_get",
                [],
                { attributes: ["selection"] }
            );

            if (fieldInfo.x_tipo && fieldInfo.x_tipo.selection) {
                this.state.tipos = fieldInfo.x_tipo.selection;
            }

            if (fieldInfo.x_grupo && fieldInfo.x_grupo.selection) {
                this.state.grupos = fieldInfo.x_grupo.selection;
            }

            if (fieldInfo.x_acabado && fieldInfo.x_acabado.selection) {
                this.state.acabados = fieldInfo.x_acabado.selection;
            }

            // Cargar grosores únicos
            const grosores = await this.orm.call(
                "stock.quant",
                "read_group",
                [],
                {
                    domain: [["x_grosor", "!=", false]],
                    fields: ["x_grosor"],
                    groupby: ["x_grosor"],
                }
            );
            this.state.grosores = grosores.map(g => g.x_grosor).filter(Boolean).sort();

        } catch (error) {
            console.error("Error cargando opciones de filtros:", error);
        }
    }

    async onAlmacenChange(ev) {
        const almacenId = ev.target.value ? parseInt(ev.target.value) : null;
        this.state.filters.almacen_id = almacenId;
        this.state.filters.ubicacion_id = null;
        this.state.ubicaciones = [];

        if (almacenId) {
            try {
                const almacen = await this.orm.read(
                    "stock.warehouse",
                    [almacenId],
                    ["view_location_id"]
                );

                if (almacen.length > 0 && almacen[0].view_location_id) {
                    const ubicaciones = await this.orm.searchRead(
                        "stock.location",
                        [["location_id", "child_of", almacen[0].view_location_id[0]]],
                        ["id", "complete_name"],
                        { order: "complete_name" }
                    );
                    this.state.ubicaciones = ubicaciones;
                }
            } catch (error) {
                console.error("Error cargando ubicaciones:", error);
            }
        }

        this.triggerSearch();
    }

    onFilterChange(filterName, ev) {
        const value = ev.target.value;
        this.state.filters[filterName] = value || null;
        this.triggerSearch();
    }

    onTextFilterChange(filterName, ev) {
        const value = ev.target.value.trim();
        this.state.filters[filterName] = value;
        this.triggerSearch();
    }

    triggerSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        this.searchTimeout = setTimeout(() => {
            this.searchProducts();
        }, this.searchDelay);
    }

    toggleAdvancedFilters() {
        this.state.showAdvancedFilters = !this.state.showAdvancedFilters;
    }

    clearAllFilters() {
        this.state.filters = {
            product_name: '',
            almacen_id: null,
            ubicacion_id: null,
            tipo: '',
            categoria_id: null,
            grupo: '',
            acabado: '',
            grosor: '',
            numero_serie: '',
            bloque: '',
            pedimento: '',
            contenedor: '',
            atado: '',
        };
        this.state.ubicaciones = [];
        this.state.hasSearched = false;
        this.state.products = [];
        this.state.expandedProducts.clear();
        this.state.productDetails = {};
    }

    hasActiveFilters() {
        return Object.values(this.state.filters).some(v => v !== null && v !== '');
    }

    async searchProducts() {
        if (!this.hasActiveFilters()) {
            this.state.hasSearched = false;
            this.state.products = [];
            return;
        }

        this.state.isLoading = true;
        this.state.error = null;

        try {
            const products = await this.orm.call(
                "stock.quant",
                "get_inventory_grouped_by_product",
                [],
                {
                    filters: this.state.filters,
                }
            );

            this.state.products = products;
            this.state.hasSearched = true;
            this.state.totalProducts = products.length;
            this.calculateTotals();
            this.state.expandedProducts.clear();
            this.state.productDetails = {};

            if (products.length === 0) {
                this.notification.add(
                    "No se encontraron productos con los filtros aplicados",
                    { type: "info" }
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

    calculateTotals() {
        let totalAvailable = 0;
        let totalHold = 0;
        let totalCommitted = 0;

        this.state.products.forEach(product => {
            totalAvailable += product.available_qty || 0;
            totalHold += product.hold_qty || 0;
            totalCommitted += product.committed_qty || 0;
        });

        this.state.totalAvailable = totalAvailable;
        this.state.totalHold = totalHold;
        this.state.totalCommitted = totalCommitted;
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
                {
                    quant_id: detailId
                }
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
                {
                    quant_id: detailId
                }
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
        try {
            const history = await this.orm.call(
                "stock.quant",
                "get_lot_history",
                [],
                {
                    quant_id: detailId
                }
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
        console.log('Ver cliente y vendedor:', detailId);
        this.notification.add(
            "Funcionalidad de cliente/vendedor en desarrollo",
            { type: "info" }
        );
    }

    async onHoldClick(detailId, holdInfo) {
        if (!holdInfo || !holdInfo.id) {
            await this.openCreateHoldDialog(detailId);
            return;
        }

        // Obtener detailData completo
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
                    
                    // 🆕 AGREGAR: Añadir product_id al detailData
                    detailData.product_id = parseInt(productId);
                    
                    // 🆕 AGREGAR: Buscar el product_name
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
        console.log('Sale order click:', detailId, saleOrderIds);
        
        if (!saleOrderIds || saleOrderIds.length === 0) {
            this.notification.add("No hay órdenes de venta asociadas", { type: "info" });
            return;
        }

        try {
            const soInfo = await this.orm.call(
                "stock.quant",
                "get_sale_order_info",
                [],
                {
                    sale_order_ids: saleOrderIds
                }
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
InventoryVisualController.components = { ProductRow };

InventoryVisualController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
    "*": true,
};

registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);