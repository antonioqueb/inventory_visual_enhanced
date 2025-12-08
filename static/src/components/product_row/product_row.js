/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { ProductDetails } from "../product_details/product_details";

export class ProductRow extends Component {
    setup() {
        this.state = useState({
            activeFilter: 'all', // all, hold, committed, available
        });

        // Resetear el filtro a 'all' si la fila se cierra
        onWillUpdateProps((nextProps) => {
            if (this.props.isExpanded && !nextProps.isExpanded) {
                this.state.activeFilter = 'all';
            }
        });
    }

    /**
     * Maneja el click en los textos de estadísticas.
     * Si la fila está cerrada, la abre.
     * Establece el filtro activo.
     */
    handleFilterClick(filterType) {
        // Si la fila no está expandida, la expandimos primero
        if (!this.props.isExpanded) {
            this.props.onToggle(this.props.product.quant_ids);
        }
        
        // Si ya está activo este filtro, lo quitamos (volvemos a 'all'), 
        // a menos que sea 'all' (In Stock), que siempre se queda activo.
        if (this.state.activeFilter === filterType && filterType !== 'all') {
            this.state.activeFilter = 'all';
        } else {
            this.state.activeFilter = filterType;
        }
    }

    /**
     * Filtra los detalles basados en el estado activeFilter
     */
    get filteredDetails() {
        const details = this.props.details || [];
        const filter = this.state.activeFilter;

        if (filter === 'all') {
            return details;
        }

        return details.filter(d => {
            if (filter === 'hold') {
                return d.tiene_hold;
            }
            if (filter === 'committed') {
                return d.reserved_quantity > 0;
            }
            if (filter === 'available') {
                // Disponible: Cantidad > reservada Y no tiene hold manual
                const isAvailable = (d.quantity - d.reserved_quantity) > 0;
                return isAvailable && !d.tiene_hold;
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
    toggleCartSelection: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};