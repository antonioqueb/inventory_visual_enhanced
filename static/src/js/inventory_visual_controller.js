/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Controlador principal de Inventario Visual Avanzado
 * Alphaqueb Consulting SAS
 * 
 * Componente OWL que gestiona la vista visual del inventario
 * Funcionalidades:
 * - Búsqueda inteligente de productos
 * - Agrupación y visualización condensada
 * - Expansión de detalles por producto
 * - Gestión de fotos, notas, detalles y sales person
 * - Interfaz responsive y moderna
 */
class InventoryVisualController extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.root = useRef("root");

        this.state = useState({
            // Estado de búsqueda
            searchTerm: "",
            isSearching: false,
            
            // Estado de datos
            products: [],
            expandedProducts: new Set(),
            productDetails: {},
            
            // Estado de UI
            isLoading: false,
            hasSearched: false,
            error: null,
            
            // Estadísticas
            totalProducts: 0,
            totalAvailable: 0,
            totalReserved: 0,
        });

        // Debounce para búsqueda
        this.searchTimeout = null;
        this.searchDelay = 500; // ms

        onWillStart(async () => {
            // Inicialización si es necesaria
        });

        onMounted(() => {
            // Focus automático en el input de búsqueda
            if (this.root.el) {
                const searchInput = this.root.el.querySelector('.searchbar-input-wrapper input');
                if (searchInput) {
                    searchInput.focus();
                }
                
                // Listener para scroll
                this.setupScrollListener();
            }
        });
    }

    /**
     * Configurar listener para el scroll
     */
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

    /**
     * Manejar cambio en el input de búsqueda
     */
    onSearchInput(ev) {
        const value = ev.target.value;
        this.state.searchTerm = value;

        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        // Si está vacío, no buscar
        if (!value.trim()) {
            this.state.hasSearched = false;
            this.state.products = [];
            return;
        }

        // Debounce: esperar a que el usuario termine de escribir
        this.searchTimeout = setTimeout(() => {
            this.searchProducts();
        }, this.searchDelay);
    }

    /**
     * Buscar productos
     */
    async searchProducts() {
        if (!this.state.searchTerm.trim()) {
            this.notification.add("Por favor ingresa un término de búsqueda", {
                type: "warning",
            });
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
                    search_term: this.state.searchTerm.trim(),
                }
            );

            this.state.products = products;
            this.state.hasSearched = true;
            this.state.totalProducts = products.length;

            // Calcular totales
            this.calculateTotals();

            // Limpiar detalles expandidos previos
            this.state.expandedProducts.clear();
            this.state.productDetails = {};

            if (products.length === 0) {
                this.notification.add(
                    `No se encontraron productos con "${this.state.searchTerm}"`,
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

    /**
     * Calcular totales generales
     */
    calculateTotals() {
        let totalAvailable = 0;
        let totalReserved = 0;

        this.state.products.forEach(product => {
            totalAvailable += product.available_qty || 0;
            totalReserved += product.reserved_qty || 0;
        });

        this.state.totalAvailable = totalAvailable;
        this.state.totalReserved = totalReserved;
    }

    /**
     * Limpiar búsqueda
     */
    clearSearch() {
        this.state.searchTerm = "";
        this.state.hasSearched = false;
        this.state.products = [];
        this.state.expandedProducts.clear();
        this.state.productDetails = {};
        
        if (this.root.el) {
            const searchInput = this.root.el.querySelector('.searchbar-input-wrapper input');
            if (searchInput) {
                searchInput.focus();
            }
        }
    }

    /**
     * Toggle expansión de producto
     */
    async toggleProduct(productId, quantIds) {
        const isExpanded = this.state.expandedProducts.has(productId);

        if (isExpanded) {
            // Colapsar
            this.state.expandedProducts.delete(productId);
        } else {
            // Expandir y cargar detalles si no están cargados
            this.state.expandedProducts.add(productId);

            if (!this.state.productDetails[productId]) {
                await this.loadProductDetails(productId, quantIds);
            }
        }

        // Forzar re-render
        this.state.expandedProducts = new Set(this.state.expandedProducts);
    }

    /**
     * Cargar detalles de un producto
     */
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

    /**
     * Formatear número con separadores de miles
     */
    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    /**
     * Obtener clase para métrica
     */
    getMetricClass(type) {
        const classes = {
            available: 'metric-available',
            reserved: 'metric-reserved',
            total: 'metric-total',
        };
        return classes[type] || '';
    }

    /**
     * Verificar si un producto está expandido
     */
    isProductExpanded(productId) {
        return this.state.expandedProducts.has(productId);
    }

    /**
     * Obtener detalles de un producto
     */
    getProductDetails(productId) {
        return this.state.productDetails[productId] || [];
    }

    // ========================================
    // NUEVAS FUNCIONES PARA COLUMNAS DE ICONOS
    // ========================================

    /**
     * Manejar clic en el botón de fotos (P)
     * TODO: Implementar modal con galería de fotos
     */
    onPhotoClick(detailId) {
        console.log('Ver fotos de placa:', detailId);
        
        // Placeholder: Mostrar notificación temporal
        this.notification.add(
            "Funcionalidad de galería de fotos en desarrollo",
            { type: "info" }
        );
        
        // TODO: Implementar modal de fotos
        // this.openPhotoGalleryModal(detailId);
        
        /*
        // Ejemplo de implementación futura:
        try {
            const photos = await this.orm.call(
                "stock.quant",
                "get_lot_photos",
                [detailId]
            );
            
            // Abrir modal con galería
            this.openPhotoGalleryModal(photos);
        } catch (error) {
            console.error("Error al cargar fotos:", error);
            this.notification.add("Error al cargar fotos", { type: "danger" });
        }
        */
    }

    /**
     * Manejar clic en el botón de notas (N)
     * TODO: Implementar modal de notas con editor
     */
    onNotesClick(detailId) {
        console.log('Ver notas de placa:', detailId);
        
        // Placeholder: Mostrar notificación temporal
        this.notification.add(
            "Funcionalidad de notas en desarrollo",
            { type: "info" }
        );
        
        // TODO: Implementar modal de notas
        // this.openNotesModal(detailId);
        
        /*
        // Ejemplo de implementación futura:
        try {
            const notes = await this.orm.call(
                "stock.quant",
                "get_lot_notes",
                [detailId]
            );
            
            // Abrir modal para ver/editar notas
            this.openNotesModal(notes, detailId);
        } catch (error) {
            console.error("Error al cargar notas:", error);
            this.notification.add("Error al cargar notas", { type: "danger" });
        }
        */
    }

    /**
     * Manejar clic en el botón de detalles (D)
     * TODO: Implementar modal con historial completo del lote
     * Debe mostrar:
     * - Historial de movimientos
     * - Orden de compra original
     * - Recepción
     * - Movimientos de almacén
     * - Reservaciones
     * - Transferencias
     */
    onDetailsClick(detailId) {
        console.log('Ver detalles completos de lote:', detailId);
        
        // Placeholder: Mostrar notificación temporal
        this.notification.add(
            "Funcionalidad de historial detallado en desarrollo",
            { type: "info" }
        );
        
        // TODO: Implementar modal de detalles/historial
        // this.openDetailsModal(detailId);
        
        /*
        // Ejemplo de implementación futura:
        try {
            const details = await this.orm.call(
                "stock.quant",
                "get_lot_full_history",
                [detailId]
            );
            
            // Abrir modal con historial completo
            this.openDetailsModal(details);
        } catch (error) {
            console.error("Error al cargar historial:", error);
            this.notification.add("Error al cargar historial", { type: "danger" });
        }
        */
    }

    /**
     * Manejar clic en el botón de sales person (SP)
     * TODO: Implementar modal con información de cliente y vendedor
     * Debe mostrar:
     * - Nombre del cliente
     * - Contacto del cliente
     * - Vendedor asignado
     * - Fecha de apartado
     * - Detalles de la reservación
     */
    onSalesPersonClick(detailId) {
        console.log('Ver cliente y vendedor:', detailId);
        
        // Placeholder: Mostrar notificación temporal
        this.notification.add(
            "Funcionalidad de cliente/vendedor en desarrollo",
            { type: "info" }
        );
        
        // TODO: Implementar modal de sales person
        // this.openSalesPersonModal(detailId);
        
        /*
        // Ejemplo de implementación futura:
        try {
            const salesInfo = await this.orm.call(
                "stock.quant",
                "get_lot_sales_info",
                [detailId]
            );
            
            // Abrir modal con información de cliente/vendedor
            this.openSalesPersonModal(salesInfo);
        } catch (error) {
            console.error("Error al cargar información de venta:", error);
            this.notification.add("Error al cargar información", { type: "danger" });
        }
        */
    }

    // ========================================
    // FUNCIONES HELPER PARA MODALS (FUTURAS)
    // ========================================

    /**
     * Abrir modal de galería de fotos
     * @param {Object} photoData - Datos de las fotos del lote
     */
    /*
    openPhotoGalleryModal(photoData) {
        // TODO: Implementar con dialog service de Odoo
        // Ejemplo:
        this.dialog.add(PhotoGalleryDialog, {
            lotId: photoData.lot_id,
            lotName: photoData.lot_name,
            photos: photoData.photos,
            onUpload: (file) => this.uploadPhoto(photoData.lot_id, file),
            onDelete: (photoId) => this.deletePhoto(photoId)
        });
    }
    */

    /**
     * Abrir modal de notas
     * @param {Object} notesData - Datos de las notas del lote
     * @param {Number} detailId - ID del detalle
     */
    /*
    openNotesModal(notesData, detailId) {
        // TODO: Implementar con dialog service de Odoo
        this.dialog.add(NotesDialog, {
            lotId: notesData.lot_id,
            lotName: notesData.lot_name,
            notes: notesData.notes,
            onSave: (newNotes) => this.saveNotes(detailId, newNotes)
        });
    }
    */

    /**
     * Abrir modal de detalles/historial
     * @param {Object} detailsData - Datos del historial completo
     */
    /*
    openDetailsModal(detailsData) {
        // TODO: Implementar con dialog service de Odoo
        this.dialog.add(DetailsHistoryDialog, {
            lotId: detailsData.lot_id,
            lotName: detailsData.lot_name,
            purchaseOrder: detailsData.purchase_order,
            reception: detailsData.reception,
            movements: detailsData.movements,
            reservations: detailsData.reservations
        });
    }
    */

    /**
     * Abrir modal de sales person
     * @param {Object} salesInfo - Información de cliente y vendedor
     */
    /*
    openSalesPersonModal(salesInfo) {
        // TODO: Implementar con dialog service de Odoo
        this.dialog.add(SalesPersonDialog, {
            lotId: salesInfo.lot_id,
            lotName: salesInfo.lot_name,
            customer: salesInfo.customer,
            salesperson: salesInfo.salesperson,
            reservation: salesInfo.reservation,
            onAssign: (customerId, salespersonId) => 
                this.assignSalesPerson(salesInfo.lot_id, customerId, salespersonId)
        });
    }
    */

    // ========================================
    // FUNCIONES DE API PARA BACKEND (FUTURAS)
    // ========================================

    /**
     * Subir una foto para un lote
     */
    /*
    async uploadPhoto(lotId, file) {
        try {
            // TODO: Implementar upload de archivo
            const result = await this.orm.call(
                "stock.quant.lot",
                "upload_photo",
                [lotId],
                { file: file }
            );
            
            this.notification.add("Foto subida exitosamente", { type: "success" });
            return result;
        } catch (error) {
            console.error("Error al subir foto:", error);
            this.notification.add("Error al subir foto", { type: "danger" });
        }
    }
    */

    /**
     * Eliminar una foto
     */
    /*
    async deletePhoto(photoId) {
        try {
            await this.orm.call(
                "ir.attachment",
                "unlink",
                [[photoId]]
            );
            
            this.notification.add("Foto eliminada", { type: "success" });
        } catch (error) {
            console.error("Error al eliminar foto:", error);
            this.notification.add("Error al eliminar foto", { type: "danger" });
        }
    }
    */

    /**
     * Guardar notas de un lote
     */
    /*
    async saveNotes(detailId, notes) {
        try {
            await this.orm.call(
                "stock.quant.lot",
                "write",
                [[detailId], { detalles_placa: notes }]
            );
            
            this.notification.add("Notas guardadas", { type: "success" });
            
            // Recargar detalles para reflejar cambios
            const productId = this.getCurrentProductId();
            if (productId) {
                await this.loadProductDetails(productId, this.getCurrentQuantIds());
            }
        } catch (error) {
            console.error("Error al guardar notas:", error);
            this.notification.add("Error al guardar notas", { type: "danger" });
        }
    }
    */

    /**
     * Asignar cliente y vendedor a un lote
     */
    /*
    async assignSalesPerson(lotId, customerId, salespersonId) {
        try {
            await this.orm.call(
                "stock.quant.lot",
                "write",
                [[lotId], {
                    customer_id: customerId,
                    sales_person_id: salespersonId
                }]
            );
            
            this.notification.add(
                "Cliente y vendedor asignados correctamente",
                { type: "success" }
            );
            
            // Recargar detalles
            const productId = this.getCurrentProductId();
            if (productId) {
                await this.loadProductDetails(productId, this.getCurrentQuantIds());
            }
        } catch (error) {
            console.error("Error al asignar cliente/vendedor:", error);
            this.notification.add(
                "Error al asignar cliente y vendedor",
                { type: "danger" }
            );
        }
    }
    */
}

InventoryVisualController.template = "inventory_visual_enhanced.MainView";

// Props estándar que Odoo pasa a los componentes de acción
InventoryVisualController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
};

// Registrar la acción cliente
registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);