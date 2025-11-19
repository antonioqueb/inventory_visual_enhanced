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