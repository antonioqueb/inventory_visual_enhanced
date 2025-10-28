## ./__init__.py
```py
# -*- coding: utf-8 -*-
from . import models
```

## ./__manifest__.py
```py
# -*- coding: utf-8 -*-
{
    'name': 'Inventario Visual Avanzado',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Vista visual mejorada y agrupada del inventario por producto',
    'description': """
        Módulo puramente visual que mejora la experiencia de usuario al visualizar inventario:
        
        Características principales:
        - Vista agrupada por producto con métricas condensadas
        - Búsqueda inteligente por familia de productos
        - Visualización expandible del detalle de placas y lotes
        - Diseño moderno y profesional con SCSS personalizado
        - Información consolidada: disponible, apartado, total m²
        - Interfaz intuitiva y altamente legible
        - Colores personalizables mediante variables SCSS
        - No modifica la lógica de negocio existente
        
        Este módulo NO altera la funcionalidad de Odoo, solo mejora la visualización.
    """,
    'author': 'Alphaqueb Consulting SAS',
    'website': 'https://alphaqueb.com',
    'depends': [
        'stock',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/inventory_visual_views.xml',
        'views/menu_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_visual_enhanced/static/src/scss/inventory_visual.scss',
            'inventory_visual_enhanced/static/src/js/inventory_visual_controller.js',
            'inventory_visual_enhanced/static/src/xml/inventory_visual_template.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

## ./models/__init__.py
```py
# -*- coding: utf-8 -*-
from . import stock_quant_visual
```

## ./models/stock_quant_visual.py
```py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict

class StockQuantVisual(models.Model):
    """
    Modelo de solo lectura para proporcionar datos agregados al frontend.
    No modifica ninguna lógica de negocio, solo provee vistas consolidadas.
    """
    _inherit = 'stock.quant'

    @api.model
    def get_inventory_grouped_by_product(self, search_term=''):
        """
        Obtiene inventario agrupado por producto con métricas consolidadas.
        Retorna estructura optimizada para la vista visual.
        
        Args:
            search_term (str): Término de búsqueda para filtrar productos
            
        Returns:
            list: Lista de diccionarios con productos y sus métricas
        """
        domain = [('quantity', '>', 0)]
        
        if search_term:
            domain += ['|', '|', 
                      ('product_id.name', 'ilike', search_term),
                      ('product_id.default_code', 'ilike', search_term),
                      ('product_id.categ_id.name', 'ilike', search_term)]
        
        quants = self.search(domain)
        
        # Agrupar por producto
        products_data = defaultdict(lambda: {
            'stock_qty': 0.0,  # Total en stock
            'stock_plates': 0,  # Total de placas en stock
            'committed_qty': 0.0,  # Apartado/Comprometido
            'committed_plates': 0,  # Placas comprometidas
            'available_qty': 0.0,  # Disponible = Stock - Comprometido
            'available_plates': 0,  # Placas disponibles
            'total_qty': 0.0,  # Total m²
            'quant_ids': [],
            'has_details': False,
            'has_photos': False,
            'plate_area': 0.0,
        })
        
        for quant in quants:
            product = quant.product_id
            key = product.id
            
            # Calcular área de placa (alto × ancho en m²)
            plate_area = 0.0
            if hasattr(quant, 'x_alto') and hasattr(quant, 'x_ancho'):
                if quant.x_alto and quant.x_ancho:
                    try:
                        plate_area = float(quant.x_alto) * float(quant.x_ancho)
                    except (ValueError, TypeError):
                        plate_area = 0.0
            
            # Calcular métricas
            total_m2 = quant.quantity
            committed_m2 = quant.reserved_quantity
            stock_m2 = total_m2
            available_m2 = total_m2 - committed_m2
            
            # Calcular placas (solo si tenemos área de placa válida)
            total_plates = 0
            committed_plates = 0
            stock_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(total_m2 / plate_area))
                committed_plates = int(round(committed_m2 / plate_area))
                stock_plates = total_plates
                available_plates = stock_plates - committed_plates
            
            # Obtener categoría hija (última categoría en la jerarquía) - CORREGIDO
            category_name = ''
            if product.categ_id:
                current_categ = product.categ_id
                # Navegar hacia abajo hasta encontrar la categoría hoja
                while current_categ.child_id and len(current_categ.child_id) > 0:
                    current_categ = current_categ.child_id[0]
                category_name = current_categ.name
            
            # Obtener formato
            formato = ''
            if hasattr(quant, 'x_formato') and quant.x_formato:
                formato = quant.x_formato
            
            products_data[key]['product_id'] = product.id
            products_data[key]['product_name'] = product.display_name
            products_data[key]['product_code'] = product.default_code or ''
            products_data[key]['uom_name'] = product.uom_id.name
            products_data[key]['categ_name'] = category_name  # CORREGIDO: era 'category_name'
            products_data[key]['formato'] = formato
            
            # Acumular cantidades
            products_data[key]['stock_qty'] += stock_m2
            products_data[key]['stock_plates'] += stock_plates
            products_data[key]['committed_qty'] += committed_m2
            products_data[key]['committed_plates'] += committed_plates
            products_data[key]['available_qty'] += available_m2
            products_data[key]['available_plates'] += available_plates
            products_data[key]['total_qty'] += total_m2
            products_data[key]['quant_ids'].append(quant.id)
            
            # Guardar área de placa para referencia
            if plate_area > 0 and products_data[key]['plate_area'] == 0:
                products_data[key]['plate_area'] = plate_area
            
            # Verificar si tiene detalles o fotos
            if hasattr(quant, 'x_tiene_detalles') and quant.x_tiene_detalles:
                products_data[key]['has_details'] = True
            if hasattr(quant, 'x_cantidad_fotos') and quant.x_cantidad_fotos > 0:
                products_data[key]['has_photos'] = True
        
        # Convertir a lista y ordenar
        result = list(products_data.values())
        result.sort(key=lambda x: x['product_name'])
        
        return result

    @api.model
    def get_quant_details(self, quant_ids):
        """
        Obtiene detalles completos de quants específicos.
        
        Args:
            quant_ids (list): Lista de IDs de quants
            
        Returns:
            list: Lista de diccionarios con detalles de cada quant
        """
        if not quant_ids:
            return []
        
        quants = self.browse(quant_ids)
        details = []
        
        for quant in quants:
            # Obtener dimensiones
            grosor = getattr(quant, 'x_grosor', None) or ''
            alto = getattr(quant, 'x_alto', None) or ''
            ancho = getattr(quant, 'x_ancho', None) or ''
            
            # Obtener bloque y formato
            bloque = getattr(quant, 'x_bloque', None) or ''
            formato = getattr(quant, 'x_formato', None) or ''
            
            # Calcular placas
            plate_area = 0.0
            if alto and ancho:
                try:
                    plate_area = float(alto) * float(ancho)
                except (ValueError, TypeError):
                    plate_area = 0.0
            
            total_plates = 0
            committed_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(quant.quantity / plate_area))
                committed_plates = int(round(quant.reserved_quantity / plate_area))
                available_plates = total_plates - committed_plates
            
            # Estados básicos
            esta_reservado = quant.reserved_quantity > 0
            
            # Verificar si está en orden de entrega (buscar en movimientos)
            en_orden_entrega = False
            if quant.lot_id:
                delivery_moves = self.env['stock.move.line'].search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_id.picking_type_id.code', '=', 'outgoing')
                ], limit=1)
                en_orden_entrega = bool(delivery_moves)
            
            # Verificar si está en orden de venta (buscar en movimientos con sale_line_id)
            en_orden_venta = False
            if quant.lot_id:
                sale_moves = self.env['stock.move'].search([
                    ('lot_ids', 'in', [quant.lot_id.id]),
                    ('sale_line_id', '!=', False),
                    ('state', 'in', ['confirmed', 'assigned', 'done'])
                ], limit=1)
                en_orden_venta = bool(sale_moves)
            
            # Verificar si tiene detalles especiales
            tiene_detalles = getattr(quant, 'x_tiene_detalles', False) or False
            
            # Contar fotos (attachments de tipo imagen en el lote)
            cantidad_fotos = 0
            if quant.lot_id:
                fotos = self.env['ir.attachment'].search_count([
                    ('res_model', '=', 'stock.quant.lot'),
                    ('res_id', '=', quant.lot_id.id),
                    ('mimetype', 'like', 'image/%')
                ])
                cantidad_fotos = fotos
            
            # Obtener detalles de la placa (notas)
            detalles_placa = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_detalles_placa'):
                detalles_placa = quant.lot_id.x_detalles_placa or ''
            
            # Obtener sales person (si existe en el lote)
            sales_person = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_sales_person_id'):
                if quant.lot_id.x_sales_person_id:
                    sales_person = quant.lot_id.x_sales_person_id.name
            
            detail = {
                'id': quant.id,
                'location_name': quant.location_id.complete_name,
                'lot_name': quant.lot_id.name if quant.lot_id else '',
                'quantity': quant.quantity,
                'reserved_quantity': quant.reserved_quantity,
                'available_quantity': quant.quantity - quant.reserved_quantity,
                
                # Placas
                'total_plates': total_plates,
                'committed_plates': committed_plates,
                'available_plates': available_plates,
                
                # Dimensiones
                'grosor': grosor,
                'alto': alto,
                'ancho': ancho,
                
                # Información adicional
                'bloque': bloque,
                'formato': formato,
                
                # Estados
                'esta_reservado': esta_reservado,
                'en_orden_entrega': en_orden_entrega,
                'en_orden_venta': en_orden_venta,
                'tiene_detalles': tiene_detalles,
                
                # Multimedia y notas
                'cantidad_fotos': cantidad_fotos,
                'detalles_placa': detalles_placa,
                
                # Sales person
                'sales_person': sales_person,
            }
            
            details.append(detail)
        
        return details```

## ./static/src/js/inventory_visual_controller.js
```js
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
registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);```

## ./static/src/scss/inventory_visual.scss
```scss
/**
 * Inventario Visual Avanzado — Theme Update
 * Paleta Odoo + fondos claros
 */

/* ================================
   COLOR THEME SWATCHES (Referencia)
   ================================ */

/* Hex */
$Odoo-Theme-1-hex: #714B67;
$Odoo-Theme-2-hex: #8F8F8F;
$Odoo-Theme-3-hex: #017E84;
$Odoo-Theme-4-hex: #E46E78;
$Odoo-Theme-5-hex: #21B799;
$Odoo-Theme-6-hex: #5B899E;
$Odoo-Theme-7-hex: #E4A900;

/* RGBA */
$Odoo-Theme-1-rgba: rgba(113,75,103, 1);
$Odoo-Theme-2-rgba: rgba(143,143,143, 1);
$Odoo-Theme-3-rgba: rgba(1,126,132, 1);
$Odoo-Theme-4-rgba: rgba(228,110,120, 1);
$Odoo-Theme-5-rgba: rgba(33,183,153, 1);
$Odoo-Theme-6-rgba: rgba(91,137,158, 1);
$Odoo-Theme-7-rgba: rgba(228,169,0, 1);

/* HSLA */
$Odoo-Theme-1-hsla: hsla(315, 20, 36, 1);
$Odoo-Theme-2-hsla: hsla(0, 0, 56, 1);
$Odoo-Theme-3-hsla: hsla(182, 98, 26, 1);
$Odoo-Theme-4-hsla: hsla(354, 68, 66, 1);
$Odoo-Theme-5-hsla: hsla(167, 69, 42, 1);
$Odoo-Theme-6-hsla: hsla(198, 26, 48, 1);
$Odoo-Theme-7-hsla: hsla(44, 100, 44, 1);

/**
 * Estilos principales para Inventario Visual Avanzado
 * Alphaqueb Consulting SAS
 */

/* ========================================
   VARIABLES DE DISEÑO (Tokens de UI)
   ======================================== */

$primary-color:  $Odoo-Theme-3-hex !default; // Teal
$primary-hover:  darken($primary-color, 12%) !default;
$primary-light:  mix(#fff, $primary-color, 88%) !default;

$secondary-color: $Odoo-Theme-1-hex !default; // Morado
$success-color:   $Odoo-Theme-5-hex !default; // Verde éxito
$warning-color:   $Odoo-Theme-7-hex !default; // Amarillo
$danger-color:    $Odoo-Theme-4-hex !default; // Rosa/rojo sutil
$info-color:      $Odoo-Theme-6-hex !default; // Azul grisáceo

/* Métricas de inventario */
$stock-color:      $info-color !default;
$committed-color:  $warning-color !default;
$available-color:  $success-color !default;

/* Fondos claros forzados */
$background-primary:   #ffffff !default;
$background-secondary: mix(#fff, $info-color, 94%) !default;   // muy claro
$background-hover:     mix(#fff, $primary-color, 90%) !default;

$border-color:       mix(#fff, $Odoo-Theme-2-hex, 85%) !default; // gris muy claro
$border-color-dark:  mix(#fff, $Odoo-Theme-2-hex, 70%) !default;
$divider-color:      mix(#fff, $Odoo-Theme-2-hex, 88%) !default;

$icon-gray: #999 !default;
$icon-red:  $danger-color !default;

$font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !default;
$font-family-monospace: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace !default;

$font-size-base: 14px !default;
$font-size-small: 12px !default;
$font-size-large: 16px !default;
$font-size-xlarge: 18px !default;
$font-size-xxlarge: 24px !default;

$font-weight-normal: 400 !default;
$font-weight-medium: 500 !default;
$font-weight-semibold: 600 !default;
$font-weight-bold: 700 !default;

$line-height-base: 1.5 !default;
$line-height-tight: 1.3 !default;

$spacing-xs: 4px !default;
$spacing-sm: 8px !default;
$spacing-md: 16px !default;
$spacing-lg: 24px !default;
$spacing-xl: 32px !default;
$spacing-xxl: 48px !default;

$shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08) !default;
$shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1) !default;
$shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.12) !default;
$shadow-hover: 0 4px 12px rgba($primary-color, 0.18) !default;

$border-radius-sm: 4px !default;
$border-radius-md: 6px !default;
$border-radius-lg: 8px !default;
$border-radius-pill: 50px !default;

$transition-fast: 150ms ease !default;
$transition-base: 250ms ease !default;
$transition-all: all $transition-base !default;

$container-max-width: 1600px !default;

$z-index-searchbar: 100 !default;

$breakpoint-md: 992px !default;
$breakpoint-lg: 1200px !default;

$animation-duration-base: 300ms !default;
$ease-out: cubic-bezier(0, 0, 0.2, 1) !default;

/* ========================================
   CONTENEDOR PRINCIPAL
   ======================================== */

.o_inventory_visual_container {
  width: 100%;
  background: $background-secondary;
  padding: 0;
  margin: 0;
  font-family: $font-family-base;
  font-size: $font-size-base;
  color: #333;
  overflow: hidden;
}

/* ========================================
   BARRA DE BÚSQUEDA SUPERIOR - STICKY
   ======================================== */

.o_inventory_visual_searchbar {
  z-index: $z-index-searchbar;
  background: $background-primary;
  border-bottom: 2px solid $border-color;
  padding: $spacing-md $spacing-xl;
  box-shadow: $shadow-sm;
  transition: $transition-all;

  &.scrolled { box-shadow: $shadow-md; }

  .searchbar-inner {
    max-width: $container-max-width;
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: $spacing-md;
  }

  .searchbar-label {
    font-size: $font-size-large;
    font-weight: $font-weight-semibold;
    color: $primary-color;
    white-space: nowrap;
    min-width: 180px;

    .icon { margin-right: $spacing-sm; color: $primary-color; }
  }

  .searchbar-input-wrapper {
    flex: 1;
    position: relative;
    max-width: 600px;

    .search-icon {
      position: absolute;
      left: $spacing-md;
      top: 50%;
      transform: translateY(-50%);
      color: #999;
      font-size: $font-size-large;
      pointer-events: none;
      transition: color $transition-fast;
    }

    input {
      width: 100%;
      height: 44px;
      padding: 0 $spacing-md 0 48px;
      border: 2px solid $border-color;
      border-radius: $border-radius-lg;
      font-size: $font-size-base;
      font-family: $font-family-base;
      background: $background-secondary;
      transition: $transition-all;
      outline: none;

      &::placeholder { color: #999; font-weight: $font-weight-normal; }

      &:focus {
        border-color: $primary-color;
        background: $background-primary;
        box-shadow: 0 0 0 3px $primary-light;
        ~ .search-icon { color: $primary-color; }
      }

      &:disabled {
        background: #f5f5f5;
        cursor: not-allowed;
        opacity: 0.6;
      }
    }

    .clear-search {
      position: absolute;
      right: $spacing-md;
      top: 50%;
      transform: translateY(-50%);
      background: transparent;
      border: none;
      color: #999;
      cursor: pointer;
      padding: $spacing-xs;
      border-radius: $border-radius-sm;
      transition: $transition-all;
      display: none;

      &.visible { display: block; }

      &:hover {
        color: $danger-color;
        background: rgba($danger-color, 0.1);
      }
    }
  }

  .searchbar-info {
    font-size: $font-size-small;
    color: #666;
    white-space: nowrap;

    .count { font-weight: $font-weight-semibold; color: $primary-color; }
  }
}

/* ========================================
   MENSAJE DE ESTADO INICIAL
   ======================================== */

.o_inventory_visual_empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 500px;
  padding: $spacing-xxl;
  text-align: center;

  .empty-icon {
    font-size: 80px;
    color: #ddd;
    margin-bottom: $spacing-lg;
    animation: float 3s ease-in-out infinite;
  }

  .empty-title {
    font-size: $font-size-xxlarge;
    font-weight: $font-weight-semibold;
    color: #666;
    margin-bottom: $spacing-sm;
  }

  .empty-subtitle {
    font-size: $font-size-base;
    color: #999;
    max-width: 400px;
    line-height: $line-height-base;
  }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* ========================================
   CONTENEDOR DE PRODUCTOS - CON SCROLL
   ======================================== */

.o_inventory_visual_content {
  max-width: $container-max-width;
  margin: 0 auto;
  padding: $spacing-lg $spacing-xl;
  width: 100%;
}

.o_inventory_products_list {
  display: flex;
  flex-direction: column;
  gap: $spacing-md;
  padding-bottom: $spacing-lg;
}

/* ========================================
   TARJETA DE PRODUCTO - ANCHO COMPLETO
   ======================================== */

.o_inventory_product_card {
  background: $background-primary;
  border: 1px solid $border-color;
  border-radius: $border-radius-lg;
  overflow: hidden;
  transition: $transition-all;
  box-shadow: $shadow-sm;

  &:hover { box-shadow: $shadow-hover; }

  &.expanded {
    box-shadow: $shadow-lg;
    border-color: $primary-color;
  }

  .product-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: $spacing-lg $spacing-xl;
    cursor: pointer;
    transition: $transition-all;
    border-left: 4px solid transparent;

    &:hover {
      background: $background-hover;
      border-left-color: $primary-color;
      .product-title { color: $primary-color; }
    }

    .product-info {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: $spacing-md;
    }

    .product-main { flex: 1; min-width: 0; }

    .product-title {
      font-size: $font-size-large;
      font-weight: $font-weight-semibold;
      color: #333;
      margin: 0 0 $spacing-xs 0;
      transition: color $transition-fast;
      line-height: $line-height-tight;
    }

    .product-code {
      display: inline-block;
      font-size: $font-size-small;
      font-family: $font-family-monospace;
      color: #666;
      background: $background-secondary;
      padding: 2px 8px;
      border-radius: $border-radius-sm;
      margin-top: $spacing-xs;
    }

    .product-metrics-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: $spacing-lg;
      margin-top: $spacing-md;
    }

    .metrics-column {
      display: flex;
      flex-direction: column;
      gap: $spacing-sm;
      padding-right: $spacing-md;
      border-right: 1px solid $divider-color;

      &:last-child { border-right: none; padding-right: 0; }

      .column-header {
        font-size: $font-size-small;
        font-weight: $font-weight-semibold;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: $spacing-xs;
      }

      .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: $font-size-small;

        .metric-label { color: #666; }

        .metric-value {
          font-weight: $font-weight-semibold;
          font-size: $font-size-base;

          &.stock { color: $stock-color; }
          &.committed { color: darken($committed-color, 15%); }
          &.available { color: $available-color; }
        }
      }
    }

    .product-actions {
      display: flex;
      align-items: center;
      gap: $spacing-sm;
    }

    .btn-expand {
      display: flex;
      align-items: center;
      gap: $spacing-sm;
      padding: $spacing-sm $spacing-md;
      background: $primary-light;
      color: $primary-color;
      border: 1px solid $primary-color;
      border-radius: $border-radius-md;
      font-size: $font-size-small;
      font-weight: $font-weight-medium;
      cursor: pointer;
      transition: $transition-all;
      white-space: nowrap;

      .expand-icon { font-size: 14px; transition: transform $transition-base; }

      &:hover { background: $primary-color; color: #fff; }
    }
  }

  &.expanded { .btn-expand .expand-icon { transform: rotate(180deg); } }
}

/* ========================================
   DETALLES DEL PRODUCTO - TABLA
   ======================================== */

.o_inventory_product_details {
  border-top: 2px solid $divider-color;
  background: $background-secondary;
  padding: 0;
}

.table-wrapper {
  overflow-x: auto;
  max-height: 600px;
}

.o_inventory_details_table {
  width: 100%;
  background: $background-primary;
  border-collapse: collapse;
  font-size: $font-size-small;

  thead {
    position: sticky;
    top: 0;
    z-index: 10;
    background: $background-secondary;
    border-bottom: 2px solid $border-color-dark;

    th {
      padding: $spacing-md;
      text-align: left;
      font-weight: $font-weight-semibold;
      color: #333;
      font-size: $font-size-small;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      white-space: nowrap;
      border-bottom: 2px solid $border-color-dark;

      &:first-child { padding-left: $spacing-xl; }
      &:last-child  { padding-right: $spacing-xl; }
    }
  }

  tbody {
    tr {
      border-bottom: 1px solid $border-color;
      transition: background-color $transition-fast;

      &:hover { background: $background-hover; }
      &:last-child { border-bottom: none; }
    }

    td {
      padding: $spacing-md;
      vertical-align: middle;
      color: #333;

      &:first-child { padding-left: $spacing-xl; }
      &:last-child  { padding-right: $spacing-xl; }
    }
  }

  /* Helper para marcar celdas en negritas desde el DOM si se usa */
  .cell-strong { font-weight: $font-weight-semibold; }

  /* Columnas específicas */
  .col-lot {
    min-width: 120px;   /* antes 150px */
    max-width: 160px;
    font-family: $font-family-monospace;
    color: #333;
    font-weight: $font-weight-semibold; /* negritas */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;

    span {
      display: inline-block;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      vertical-align: bottom;
    }
  }

  .col-bloque {
    min-width: 120px;
    text-align: center;
    font-family: $font-family-monospace;
    font-weight: $font-weight-semibold; /* negritas */
    color: #333;
  }

  .col-location {
    min-width: 180px;
    font-weight: $font-weight-semibold; /* negritas */
    color: #333;

    .location-icon { color: $primary-color; margin-right: $spacing-xs; }
  }

  .col-dimensions {
    min-width: 200px;
    font-weight: $font-weight-semibold; /* negritas */
    color: #333;
    
    .dimensions-cell {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .dimensions-measures { font-size: $font-size-small; }

    .dimensions-total {
      font-weight: $font-weight-bold;
      color: $primary-color;

      .m2-value { font-size: $font-size-base; }
    }
  }

  /* Columnas de iconos (súper compactas) — mantienen ancho p/ “E” */
  .col-icon {
    width: 50px;
    min-width: 50px;
    max-width: 50px;
    text-align: center;
    padding: $spacing-sm !important;
  }

  .icon-btn {
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: $border-radius-sm;
    cursor: pointer;
    transition: $transition-all;
    background: transparent;
    font-size: 16px;

    &.no-content {
      color: $icon-gray;
      background: transparent;
      cursor: default;
      opacity: 0.5;
      &:hover { background: transparent; }
    }

    &.has-content {
      color: $primary-color;
      background: rgba($primary-color, 0.1);
      &:hover { background: $primary-color; color: #fff; transform: scale(1.1); }
    }

    &.has-alert {
      color: $icon-red;
      background: rgba($icon-red, 0.1);
      &:hover { background: $icon-red; color: #fff; transform: scale(1.1); }
    }
  }

  /* Estado específico */
  .col-state {
    .state-cell {
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .state-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: $border-radius-sm;
      font-weight: $font-weight-semibold;
      font-size: 14px;

      &.hold-icon {
        color: $committed-color;
        background: rgba($committed-color, 0.1);
        i { font-size: 18px; }
      }

      &.so-icon {
        color: $success-color;
        background: rgba($success-color, 0.1);
        font-size: 11px; /* “SO” cabe sin desbordar */
      }
    }
  }
}

/* Loading dentro de tabla */
.table-loading {
  padding: $spacing-xl;
  text-align: center;

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid $primary-light;
    border-top-color: $primary-color;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto $spacing-md;
  }

  .loading-text { color: #666; font-size: $font-size-base; }
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ========================================
   LOADING Y MENSAJES
   ======================================== */

.o_inventory_loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  flex-direction: column;
  gap: $spacing-md;

  .spinner {
    width: 50px;
    height: 50px;
    border: 4px solid $primary-light;
    border-top-color: $primary-color;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .loading-text { color: #666; font-size: $font-size-base; font-weight: $font-weight-medium; }
}

.o_inventory_error {
  background: rgba($danger-color, 0.1);
  border: 1px solid $danger-color;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
  margin: $spacing-lg;
  text-align: center;

  .error-icon { font-size: 48px; color: $danger-color; margin-bottom: $spacing-md; }
  .error-message { color: $danger-color; font-weight: $font-weight-medium; }
}

.o_inventory_no_results {
  text-align: center;
  padding: $spacing-xxl;

  .no-results-icon { font-size: 64px; color: #ddd; margin-bottom: $spacing-md; }
  .no-results-title { font-size: $font-size-large; font-weight: $font-weight-semibold; color: #666; margin-bottom: $spacing-sm; }
  .no-results-message { color: #999; }
}

/* ========================================
   RESPONSIVE
   ======================================== */

@media (max-width: $breakpoint-lg) {
  .o_inventory_visual_searchbar {
    padding: $spacing-md;
    .searchbar-inner { flex-wrap: wrap; }
    .searchbar-label { min-width: auto; }
    .searchbar-input-wrapper { max-width: 100%; flex: 1 1 100%; }
  }

  .o_inventory_product_card .product-header {
    flex-direction: column;
    align-items: flex-start;
    gap: $spacing-md;

    .product-info { width: 100%; }
    .product-metrics-grid { grid-template-columns: 1fr; gap: $spacing-md; }

    .metrics-column {
      border-right: none !important;
      border-bottom: 1px solid $divider-color;
      padding-right: 0;
      padding-bottom: $spacing-md;

      &:last-child { border-bottom: none; }
    }

    .product-actions {
      width: 100%;
      justify-content: space-between;
    }
  }
}

@media (max-width: $breakpoint-md) {
  .o_inventory_visual_content { padding: $spacing-md; }

  .o_inventory_details_table {
    display: block;
    overflow-x: auto;

    thead, tbody, tr, th, td { display: block; }
    thead { display: none; }

    tbody tr {
      margin-bottom: $spacing-md;
      border: 1px solid $border-color;
      border-radius: $border-radius-md;
      padding: $spacing-md;
    }

    tbody td {
      padding: $spacing-xs 0;
      &::before {
        content: attr(data-label);
        font-weight: $font-weight-semibold;
        display: inline-block;
        width: 150px;
        margin-right: $spacing-sm;
      }
    }
  }
}

/* ========================================
   SCROLLBAR PERSONALIZADO
   ======================================== */

.o_inventory_visual_content,
.o_inventory_product_details,
.table-wrapper {
  scrollbar-width: thin;
  scrollbar-color: $border-color-dark $background-secondary;

  &::-webkit-scrollbar { width: 10px; height: 10px; }
  &::-webkit-scrollbar-track { background: $background-secondary; }
  &::-webkit-scrollbar-thumb {
    background: $border-color-dark;
    border-radius: $border-radius-pill;
    &:hover { background: #999; }
  }
}
```

## ./static/src/xml/inventory_visual_template.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <!-- Template principal del componente -->
    <t t-name="inventory_visual_enhanced.MainView" owl="1">
        <div class="o_inventory_visual_container d-flex flex-column vh-100" t-ref="root">
            
            <!-- Barra de búsqueda superior (sticky) -->
            <div class="o_inventory_visual_searchbar flex-shrink-0 sticky-top">
            <div class="searchbar-inner container d-flex align-items-center justify-content-between gap-2">

                <!-- Wrapper centrado con Bootstrap -->
                <div class="searchbar-input-wrapper mx-auto col-12 col-md-8 col-lg-6 px-0 position-relative">
                <i class="fa fa-search search-icon"></i>
                <input 
                    type="text"
                    class="form-control"
                    placeholder="Buscar por producto, código o familia (ej: Tajmahal)..."
                    t-model="state.searchTerm"
                    t-on-input="onSearchInput"
                    t-att-disabled="state.isLoading"
                />
                <button 
                    class="clear-search btn btn-link p-0"
                    t-att-class="{ visible: state.searchTerm.length > 0 }"
                    t-on-click="clearSearch"
                >
                    <i class="fa fa-times"></i>
                </button>
                </div>

                <!-- Métrica a la derecha -->
                <div class="searchbar-info text-nowrap ms-auto" t-if="state.hasSearched">
                <span class="count" t-esc="state.totalProducts"></span>
                <span t-if="state.totalProducts === 1"> producto</span>
                <span t-else=""> productos</span>
                </div>
            </div>
            </div>


            <!-- Contenido principal con scroll -->
            <div class="o_inventory_visual_content flex-grow-1 overflow-auto">
                
                <!-- Estado inicial: sin búsqueda -->
                <div class="o_inventory_visual_empty" t-if="!state.hasSearched and !state.isLoading">
                    <i class="fa fa-search empty-icon"></i>
                    <h2 class="empty-title">Busca para visualizar tu inventario</h2>
                    <p class="empty-subtitle">
                        Escribe el nombre de un producto, código o familia en el buscador superior
                        para ver el inventario agrupado con métricas detalladas.
                    </p>
                </div>

                <!-- Loading -->
                <div class="o_inventory_loading" t-if="state.isLoading">
                    <div class="spinner"></div>
                    <div class="loading-text">Cargando inventario...</div>
                </div>

                <!-- Error -->
                <div class="o_inventory_error" t-if="state.error">
                    <i class="fa fa-exclamation-triangle error-icon"></i>
                    <div class="error-message" t-esc="state.error"></div>
                </div>

                <!-- Sin resultados -->
                <div class="o_inventory_no_results" t-if="state.hasSearched and state.products.length === 0 and !state.isLoading">
                    <i class="fa fa-inbox no-results-icon"></i>
                    <h3 class="no-results-title">No se encontraron productos</h3>
                    <p class="no-results-message">
                        Intenta con otro término de búsqueda o verifica el inventario disponible.
                    </p>
                </div>

                <!-- Lista de productos -->
                <div class="o_inventory_products_list" t-if="state.products.length > 0 and !state.isLoading">
                    <t t-foreach="state.products" t-as="product" t-key="product.product_id">
                        <t t-call="inventory_visual_enhanced.ProductCard">
                            <t t-set="product" t-value="product"/>
                        </t>
                    </t>
                </div>

            </div>

        </div>
    </t>

    <!-- Template de tarjeta de producto (SIN CAMBIOS) -->
    <t t-name="inventory_visual_enhanced.ProductCard" owl="1">
        <div 
            class="o_inventory_product_card"
            t-att-class="{ expanded: isProductExpanded(product.product_id) }"
        >
            <!-- Header del producto (clickeable) -->
            <div class="product-header" t-on-click="() => this.toggleProduct(product.product_id, product.quant_ids)">
                <div class="product-info">
                    <div class="product-main">
                        <h3 class="product-title" t-esc="product.product_name"></h3>
                        <span 
                            class="product-code" 
                            t-if="product.product_code"
                            t-esc="product.product_code"
                        ></span>
                    </div>

                    <!-- Métricas organizadas en columnas -->
                    <div class="product-metrics-grid">
                        <!-- Primera columna: Placas -->
                        <div class="metrics-column metrics-placas">
                            <div class="column-header">Piezas</div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Stock:</span>
                                <span class="metric-value stock" t-esc="product.stock_plates"></span>
                            </div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Comprometido:</span>
                                <span class="metric-value committed" t-esc="product.committed_plates"></span>
                            </div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Disponible:</span>
                                <span class="metric-value available" t-esc="product.available_plates"></span>
                            </div>
                        </div>

                        <!-- Segunda columna: Metros cuadrados -->
                        <div class="metrics-column metrics-m2">
                            <div class="column-header">m²</div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Stock:</span>
                                <span class="metric-value stock" t-esc="formatNumber(product.stock_qty)"></span>
                            </div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Comprometido:</span>
                                <span class="metric-value committed" t-esc="formatNumber(product.committed_qty)"></span>
                            </div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Disponible:</span>
                                <span class="metric-value available" t-esc="formatNumber(product.available_qty)"></span>
                            </div>
                        </div>

                        <!-- Tercera columna: Información adicional -->
                        <div class="metrics-column metrics-info">
                            <div class="column-header">Información</div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Categoría:</span>
                                <span class="metric-value" t-esc="product.categ_name || 'N/A'"></span>
                            </div>
                            
                            <div class="metric-row">
                                <span class="metric-label">Formato:</span>
                                <span class="metric-value" t-esc="product.formato || 'N/A'"></span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="product-actions">
                    <button class="btn-expand" type="button">
                        <i class="fa fa-chevron-down expand-icon"></i>
                        <span class="expand-text">Ver detalle</span>
                    </button>
                </div>
            </div>

            <!-- Detalle expandido (tabla completa con NUEVA ESTRUCTURA) -->
            <div class="o_inventory_product_details" t-if="isProductExpanded(product.product_id)">
                <t t-call="inventory_visual_enhanced.ProductDetailsTable">
                    <t t-set="details" t-value="getProductDetails(product.product_id)"/>
                    <t t-set="uom_name" t-value="product.uom_name"/>
                </t>
            </div>
        </div>
    </t>

    <!-- Template de tabla de detalles - NUEVA ESTRUCTURA -->
    <t t-name="inventory_visual_enhanced.ProductDetailsTable" owl="1">
        <t t-if="details.length === 0">
            <div class="table-loading">
                <div class="spinner"></div>
                <div class="loading-text">Cargando detalles...</div>
            </div>
        </t>
        <t t-else="">
            <div class="table-wrapper overflow-auto">
                <table class="o_inventory_details_table">
                    <thead>
                        <tr>
                            <!-- 1. Lote -->
                            <th class="col-lot"><strong>Lote</strong></th>
                            
                            <!-- 2. Bloque -->
                            <th class="col-bloque"><strong>Bloque</strong></th>
                            
                            <!-- 3. Ubicación -->
                            <th class="col-location"><strong>Ubicación</strong></th>
                            
                            <!-- 4. Dimensiones -->
                            <th class="col-dimensions"><strong>Dimensiones</strong></th>
                            
                            <!-- 5. P (Pick/Foto) -->
                            <th class="col-icon"><strong>P</strong></th>
                            
                            <!-- 6. N (Notas) -->
                            <th class="col-icon"><strong>N</strong></th>
                            
                            <!-- 7. D (Detalles) -->
                            <th class="col-icon"><strong>D</strong></th>
                            
                            <!-- 8. SP (Sales Person) -->
                            <th class="col-icon"><strong>SP</strong></th>
                            
                            <!-- 9. Estado (Hold/SO) -> E -->
                            <th class="col-icon" title="Estado"><strong>E</strong></th>
                        </tr>
                    </thead>
                    <tbody>
                        <t t-foreach="details" t-as="detail" t-key="detail.id">
                            <tr>
                                <!-- 1. Lote -->
                                <td class="col-lot cell-strong" data-label="Lote">
                                    <t t-if="detail.lot_name">
                                        <strong t-esc="detail.lot_name"/>
                                    </t>
                                    <t t-else="">
                                        <span class="text-muted">-</span>
                                    </t>
                                </td>

                                <!-- 2. Bloque -->
                                <td class="col-bloque cell-strong" data-label="Bloque">
                                    <t t-if="detail.bloque">
                                        <strong t-esc="detail.bloque"/>
                                    </t>
                                    <t t-else="">
                                        <span class="text-muted">-</span>
                                    </t>
                                </td>

                                <!-- 3. Ubicación -->
                                <td class="col-location cell-strong" data-label="Ubicación">
                                    <i class="fa fa-map-marker location-icon"></i>
                                    <strong t-esc="detail.location_name"/>
                                </td>

                                <!-- 4. Dimensiones (medidas + m²) -->
                                <td class="col-dimensions cell-strong" data-label="Dimensiones">
                                    <div class="dimensions-cell">
                                        <div class="dimensions-measures">
                                            <t t-if="detail.grosor or detail.alto or detail.ancho">
                                                <t t-if="detail.grosor">
                                                    <strong><t t-esc="detail.grosor"/></strong>cm × 
                                                </t>
                                                <t t-if="detail.alto">
                                                    <strong><t t-esc="detail.alto"/></strong>m × 
                                                </t>
                                                <t t-if="detail.ancho">
                                                    <strong><t t-esc="detail.ancho"/></strong>m
                                                </t>
                                            </t>
                                            <span t-else="" class="text-muted">-</span>
                                        </div>
                                        <div class="dimensions-total" t-if="detail.quantity">
                                            <strong class="m2-value" t-esc="formatNumber(detail.quantity)"/> m²
                                        </div>
                                    </div>
                                </td>

                                <!-- 5. P (Pick/Foto) -->
                                <td class="col-icon col-photo" data-label="Foto">
                                    <button 
                                        class="icon-btn"
                                        t-att-class="detail.cantidad_fotos ? 'has-content' : 'no-content'"
                                        t-on-click="() => this.onPhotoClick(detail.id)"
                                        type="button"
                                        title="Ver fotos"
                                    >
                                        <i class="fa fa-camera"></i>
                                    </button>
                                </td>

                                <!-- 6. N (Notas) -->
                                <td class="col-icon col-notes" data-label="Notas">
                                    <button 
                                        class="icon-btn"
                                        t-att-class="detail.detalles_placa ? 'has-alert' : 'no-content'"
                                        t-on-click="() => this.onNotesClick(detail.id)"
                                        type="button"
                                        title="Ver notas"
                                    >
                                        <i class="fa fa-info-circle"></i>
                                    </button>
                                </td>

                                <!-- 7. D (Detalles) -->
                                <td class="col-icon col-details" data-label="Detalles">
                                    <button 
                                        class="icon-btn has-content"
                                        t-on-click="() => this.onDetailsClick(detail.id)"
                                        type="button"
                                        title="Ver historial y detalles"
                                    >
                                        <i class="fa fa-list-alt"></i>
                                    </button>
                                </td>

                                <!-- 8. SP (Sales Person) -->
                                <td class="col-icon col-salesperson" data-label="Cliente/Vendedor">
                                    <button 
                                        class="icon-btn"
                                        t-att-class="detail.sales_person ? 'has-content' : 'no-content'"
                                        t-on-click="() => this.onSalesPersonClick(detail.id)"
                                        type="button"
                                        title="Ver cliente y vendedor"
                                    >
                                        <i class="fa fa-user"></i>
                                    </button>
                                </td>

                                <!-- 9. Estado (Hold/SO) -->
                                <td class="col-icon col-state" data-label="E">
                                    <div class="state-cell">
                                        <!-- Apartado/Hold -->
                                        <span 
                                            class="state-icon hold-icon" 
                                            t-if="detail.esta_reservado and !detail.en_orden_venta"
                                            title="Apartado"
                                        >
                                            <i class="fa fa-hand-paper-o"></i>
                                        </span>
                                        
                                        <!-- Sales Order -->
                                        <span 
                                            class="state-icon so-icon" 
                                            t-if="detail.en_orden_venta"
                                            title="En orden de venta"
                                        >
                                            SO
                                        </span>
                                    </div>
                                </td>
                            </tr>
                        </t>
                    </tbody>
                </table>
            </div>
        </t>
    </t>

</templates>
```

## ./views/inventory_visual_views.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Vista personalizada de inventario visual -->
    <record id="view_inventory_visual_kanban" model="ir.ui.view">
        <field name="name">inventory.visual.kanban</field>
        <field name="model">stock.quant</field>
        <field name="arch" type="xml">
            <kanban class="o_inventory_visual_kanban" js_class="inventory_visual_kanban">
                <field name="id"/>
                <field name="product_id"/>
                <templates>
                    <t t-name="kanban-box">
                        <div class="oe_kanban_global_click o_inventory_visual_card">
                            <div class="o_kanban_record_top">
                                <div class="o_kanban_record_headings">
                                    <strong class="o_kanban_record_title">
                                        <field name="product_id"/>
                                    </strong>
                                </div>
                            </div>
                            <div class="o_kanban_record_body">
                                <field name="quantity" widget="float"/>
                                <field name="reserved_quantity" widget="float"/>
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>

    <!-- Acción principal para la vista visual -->
    <record id="action_inventory_visual_main" model="ir.actions.client">
        <field name="name">Inventario Visual</field>
        <field name="tag">inventory_visual_enhanced</field>
        <field name="target">current</field>
    </record>

</odoo>
```

## ./views/menu_items.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Menú principal en Inventario - Primera posición -->
    <menuitem 
        id="menu_inventory_visual_main"
        name="Inventario Visual"
        parent="stock.menu_stock_root"
        action="action_inventory_visual_main"
        sequence="-10"/>
</odoo>```

