/** @odoo-module **/

import { Component } from "@odoo/owl";

export class ProductDetails extends Component {
    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    /**
     * Manejador para el botón de "Seleccionar todo" en versión móvil.
     * Verifica el estado actual y alterna entre seleccionar o deseleccionar todo.
     */
    onMobileSelectAll() {
        const areAllSelected = this.props.areAllCurrentProductSelected && this.props.areAllCurrentProductSelected();
        
        if (areAllSelected) {
            if (this.props.deselectAllCurrentProduct) {
                this.props.deselectAllCurrentProduct();
            }
        } else {
            if (this.props.selectAllCurrentProduct) {
                this.props.selectAllCurrentProduct();
            }
        }
    }
}

ProductDetails.template = "inventory_visual_enhanced.ProductDetails";

ProductDetails.props = {
    details: Array,
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