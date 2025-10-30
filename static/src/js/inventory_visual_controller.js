/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Controlador principal de Inventario Visual Avanzado
 * Alphaqueb Consulting SAS
 */
class InventoryVisualController extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.root = useRef("root");

        this.state = useState({
            searchTerm: "",
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
        });

        this.searchTimeout = null;
        this.searchDelay = 500;

        onWillStart(async () => {});

        onMounted(() => {
            if (this.root.el) {
                const searchInput = this.root.el.querySelector('.searchbar-input-wrapper input');
                if (searchInput) {
                    searchInput.focus();
                }
                this.setupScrollListener();
            }
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

    onSearchInput(ev) {
        const value = ev.target.value;
        this.state.searchTerm = value;

        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        if (!value.trim()) {
            this.state.hasSearched = false;
            this.state.products = [];
            return;
        }

        this.searchTimeout = setTimeout(() => {
            this.searchProducts();
        }, this.searchDelay);
    }

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
            this.calculateTotals();
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

    getMetricClass(type) {
        const classes = {
            available: 'metric-available',
            reserved: 'metric-reserved',
            total: 'metric-total',
        };
        return classes[type] || '';
    }

    isProductExpanded(productId) {
        return this.state.expandedProducts.has(productId);
    }

    getProductDetails(productId) {
        return this.state.productDetails[productId] || [];
    }

    // ========================================
    // FUNCIONALIDADES DE FOTOS Y NOTAS
    // ========================================

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
        
        class PhotoGalleryDialog extends Component {
            setup() {
                this.photosData = photosData;
                this.detailId = detailId;
                this.orm = useService("orm");
                this.notification = useService("notification");
                this.dialog = useService("dialog");
                
                this.state = useState({
                    photoName: `Foto - ${photosData.lot_name}`,
                    selectedFile: null,
                    isUploading: false,
                    showUploadForm: false,
                    currentImageIndex: 0,
                });
            }
            
            get hasPhotos() {
                return this.photosData.photos && this.photosData.photos.length > 0;
            }
            
            get currentPhoto() {
                if (!this.hasPhotos) return null;
                return this.photosData.photos[this.state.currentImageIndex];
            }
            
            toggleUploadForm() {
                this.state.showUploadForm = !this.state.showUploadForm;
                if (!this.state.showUploadForm) {
                    this.state.selectedFile = null;
                    this.state.photoName = `Foto - ${this.photosData.lot_name}`;
                }
            }
            
            nextPhoto() {
                if (this.state.currentImageIndex < this.photosData.photos.length - 1) {
                    this.state.currentImageIndex++;
                }
            }
            
            prevPhoto() {
                if (this.state.currentImageIndex > 0) {
                    this.state.currentImageIndex--;
                }
            }
            
            onFileSelected(ev) {
                this.state.selectedFile = ev.target.files[0];
            }
            
            onPhotoNameChange(ev) {
                this.state.photoName = ev.target.value;
            }
            
            async uploadPhoto() {
                if (!this.state.selectedFile) {
                    this.notification.add("Por favor selecciona una imagen", { type: "warning" });
                    return;
                }
                
                this.state.isUploading = true;
                
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const base64Data = e.target.result.split(',')[1];
                    
                    try {
                        const result = await this.orm.call(
                            "stock.quant",
                            "save_lot_photo",
                            [],
                            {
                                quant_id: this.detailId,
                                photo_name: this.state.photoName,
                                photo_data: base64Data,
                                sequence: 10,
                                notas: ''
                            }
                        );
                        
                        if (result.success) {
                            this.notification.add(result.message, { type: "success" });
                            this.props.close();
                            await self.reloadProductDetailsForDetail(this.detailId);
                        } else {
                            this.notification.add(result.error || "Error al subir foto", { type: "danger" });
                        }
                    } catch (error) {
                        console.error("Error al subir foto:", error);
                        this.notification.add("Error al subir foto", { type: "danger" });
                    } finally {
                        this.state.isUploading = false;
                    }
                };
                reader.readAsDataURL(this.state.selectedFile);
            }
            
            openImageInNewTab(imageData) {
                window.open(`data:image/png;base64,${imageData}`, '_blank');
            }
        }
        
        PhotoGalleryDialog.template = "inventory_visual_enhanced.PhotoGalleryDialog";
        PhotoGalleryDialog.components = { Dialog };
        
        this.dialog.add(PhotoGalleryDialog, {
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
        
        class NotesDialog extends Component {
            setup() {
                this.notesData = notesData;
                this.detailId = detailId;
                this.orm = useService("orm");
                this.notification = useService("notification");
                
                this.state = useState({
                    notes: notesData.notes || '',
                    originalNotes: notesData.notes || '',
                    isSaving: false,
                    isEditing: !notesData.notes // Si no hay notas, comenzar en modo edición
                });
            }
            
            get hasNotes() {
                return this.state.originalNotes.trim().length > 0;
            }
            
            toggleEdit() {
                this.state.isEditing = !this.state.isEditing;
                if (!this.state.isEditing) {
                    // Si cancela, restaurar notas originales
                    this.state.notes = this.state.originalNotes;
                }
            }
            
            onNotesChange(ev) {
                this.state.notes = ev.target.value;
            }
            
            async saveNotes() {
                this.state.isSaving = true;
                
                try {
                    const result = await this.orm.call(
                        "stock.quant",
                        "save_lot_notes",
                        [],
                        {
                            quant_id: this.detailId,
                            notes: this.state.notes
                        }
                    );
                    
                    if (result.success) {
                        this.notification.add(result.message, { type: "success" });
                        this.props.close();
                        await self.reloadProductDetailsForDetail(this.detailId);
                    } else {
                        this.notification.add(result.error || "Error al guardar notas", { type: "danger" });
                    }
                } catch (error) {
                    console.error("Error al guardar notas:", error);
                    this.notification.add("Error al guardar notas", { type: "danger" });
                } finally {
                    this.state.isSaving = false;
                }
            }
        }
        
        NotesDialog.template = "inventory_visual_enhanced.NotesDialog";
        NotesDialog.components = { Dialog };
        
        this.dialog.add(NotesDialog, {
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
        const self = this;
        
        class HistoryDialog extends Component {
            setup() {
                this.history = history;
                this.orm = useService("orm");
                this.notification = useService("notification");
                
                this.state = useState({
                    currentTab: 'general', // general, purchase, movements, sales, reservations, deliveries
                });
            }
            
            switchTab(tabName) {
                this.state.currentTab = tabName;
            }
            
            isActiveTab(tabName) {
                return this.state.currentTab === tabName;
            }
            
            formatCurrency(amount, symbol) {
                return `${symbol} ${new Intl.NumberFormat('es-MX', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                }).format(amount)}`;
            }
            
            formatNumber(num) {
                return new Intl.NumberFormat('es-MX', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                }).format(num);
            }
        }
        
        HistoryDialog.template = "inventory_visual_enhanced.HistoryDialog";
        HistoryDialog.components = { Dialog };
        
        this.dialog.add(HistoryDialog, {
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

    onHoldClick(detailId, holdInfo) {
        console.log('Ver detalles de hold:', detailId, holdInfo);
        
        if (!holdInfo || !holdInfo.id) {
            this.notification.add(
                "No hay información de hold disponible",
                { type: "info" }
            );
            return;
        }

        let message = `Reservado para: ${holdInfo.partner_name}\n`;
        message += `Fecha de inicio: ${holdInfo.fecha_inicio}\n`;
        message += `Fecha de expiración: ${holdInfo.fecha_expiracion}`;
        if (holdInfo.notas) {
            message += `\nNotas: ${holdInfo.notas}`;
        }

        this.notification.add(message, {
            type: "info",
            title: "Información de Reserva (Hold)",
            sticky: false,
        });
    }
}

InventoryVisualController.template = "inventory_visual_enhanced.MainView";

InventoryVisualController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
    "*": true,
};

registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);