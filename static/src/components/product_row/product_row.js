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
};