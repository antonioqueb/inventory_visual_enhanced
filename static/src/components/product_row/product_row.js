/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { ProductDetails } from "../product_details/product_details";

export class ProductRow extends Component {
    setup() {
        this.state = useState({
            activeFilter: 'all', // Valores posibles: all, hold, committed, available, transit_available, transit_hold, transit_committed
        });

        // Resetear el filtro a 'all' si la fila se cierra
        onWillUpdateProps((nextProps) => {
            if (this.props.isExpanded && !nextProps.isExpanded) {
                this.state.activeFilter = 'all';
            }
        });
    }

    /**
     * Getter para determinar la unidad de medida a mostrar.
     * Si es 'pieza', muestra 'pza', de lo contrario 'm²'.
     */
    get unitLabel() {
        const type = this.props.product.tipo ? this.props.product.tipo.toString().toLowerCase() : '';
        return type === 'pieza' ? 'pza' : 'm²';
    }

    /**
     * Maneja el click en los textos de estadísticas.
     */
    handleFilterClick(filterType) {
        // Si la fila no está expandida, la expandimos primero
        if (!this.props.isExpanded) {
            this.props.onToggle(this.props.product.quant_ids);
        }
        
        // Si ya está activo este filtro, lo quitamos (volvemos a 'all'), 
        // EXCEPTO si es 'all', que siempre se queda activo.
        if (this.state.activeFilter === filterType && filterType !== 'all') {
            this.state.activeFilter = 'all';
        } else {
            this.state.activeFilter = filterType;
        }
    }

    /**
     * Filtra los detalles basados en el estado activeFilter.
     * Ahora discrimina por location_usage ('transit' vs otros).
     */
    get filteredDetails() {
        const details = this.props.details || [];
        const filter = this.state.activeFilter;

        return details.filter(d => {
            // Cantidad disponible matemática
            const availableQty = d.quantity - d.reserved_quantity;
            const isTransit = d.location_usage === 'transit';

            // --- FILTROS DE STOCK INTERNO (Ignoran Tránsito) ---
            
            if (filter === 'all') {
                // In Stock: Todo lo que NO sea tránsito
                return !isTransit;
            }
            
            if (filter === 'hold') {
                // On Hold: No tránsito Y tiene hold
                return !isTransit && d.tiene_hold;
            }
            
            if (filter === 'committed') {
                // Committed: No tránsito Y reservado
                return !isTransit && d.reserved_quantity > 0;
            }
            
            if (filter === 'available') {
                // Disponible: No tránsito, disponible > 0 Y sin hold
                return !isTransit && availableQty > 0 && !d.tiene_hold;
            }

            // --- FILTROS DE TRÁNSITO (Solo Tránsito) ---

            if (filter === 'transit_available') {
                // En Tránsito Disponible: Es tránsito, disponible > 0 Y sin hold
                return isTransit && availableQty > 0 && !d.tiene_hold;
            }

            if (filter === 'transit_hold') {
                // En Tránsito Hold: Es tránsito Y tiene hold
                return isTransit && d.tiene_hold;
            }

            if (filter === 'transit_committed') {
                // En Tránsito Comprometido: Es tránsito Y reservado
                return isTransit && d.reserved_quantity > 0;
            }

            return true;
        });
    }

    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    get shortCategoryName() {
        const fullName = this.props.product.categ_name;
        if (!fullName) return "";
        const parts = fullName.split(' / ');
        return parts[parts.length - 1];
    }    
}

ProductRow.template = "inventory_visual_enhanced.ProductRow";
ProductRow.components = { ProductDetails };

ProductRow.props = {
    product: Object,
    isExpanded: Boolean,
    details: Array,
    onToggle: Function,
    onPhotoClick: Function,
    onNotesClick: Function,
    onDetailsClick: Function,
    onSalesPersonClick: Function,
    onHoldClick: Function,
    onSaleOrderClick: Function,
    formatNumber: Function,
    hasSalesPermissions: { type: Boolean, optional: true },
    hasInventoryPermissions: { type: Boolean, optional: true },
    isInCart: { type: Function, optional: true },
    // Nuevas props para el manejo de cantidad manual
    getDisplayQuantity: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    onInputManualQuantity: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};