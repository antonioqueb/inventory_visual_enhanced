/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ProductDetails } from "../product_details/product_details";

export class ProductRow extends Component {
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
        // Odoo usa " / " (espacio barra espacio) para separar categorías
        const parts = fullName.split(' / ');
        // Retorna el último elemento del array (la categoría hija)
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
    // Props para selección
    isInCart: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};