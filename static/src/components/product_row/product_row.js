/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductDetails } from "../product_details/product_details";

export class ProductRow extends Component {
    setup() {
        this.orm = useService("orm");
        
        this.state = useState({
            activeFilter: 'all',
            showPriceTooltip: false,
            priceData: null,
            priceLoading: false,
        });

        onWillUpdateProps((nextProps) => {
            if (this.props.isExpanded && !nextProps.isExpanded) {
                this.state.activeFilter = 'all';
            }
        });
    }

    get unitLabel() {
        const type = this.props.product.tipo ? this.props.product.tipo.toString().toLowerCase() : '';
        return type === 'pieza' ? 'pza' : 'm²';
    }

    handleFilterClick(filterType) {
        if (!this.props.isExpanded) {
            this.props.onToggle(this.props.product.quant_ids);
        }
        if (this.state.activeFilter === filterType && filterType !== 'all') {
            this.state.activeFilter = 'all';
        } else {
            this.state.activeFilter = filterType;
        }
    }

    // ========== PRICE TOOLTIP ==========

    async onPriceMouseEnter(ev) {
        ev.stopPropagation();
        this.state.showPriceTooltip = true;

        // Solo cargar si no tenemos datos o si queremos refrescar
        if (!this.state.priceData) {
            this.state.priceLoading = true;
            try {
                const productId = this.props.product.product_id;
                const data = await this.orm.call(
                    "product.template",
                    "get_price_tooltip_data",
                    [productId]
                );
                this.state.priceData = data;
            } catch (error) {
                console.error("[ProductRow] Error cargando precios:", error);
                this.state.priceData = null;
            } finally {
                this.state.priceLoading = false;
            }
        }
    }

    onPriceMouseLeave(ev) {
        ev.stopPropagation();
        this.state.showPriceTooltip = false;
    }

    formatPrice(num) {
        if (!num && num !== 0) return "—";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    // ========== FILTERS ==========

    get filteredDetails() {
        const details = this.props.details || [];
        const filter = this.state.activeFilter;

        return details.filter(d => {
            const availableQty = d.quantity - d.reserved_quantity;
            const isTransit = d.location_usage === 'transit';

            if (filter === 'all') {
                return !isTransit;
            }
            if (filter === 'hold') {
                return !isTransit && d.tiene_hold;
            }
            if (filter === 'committed') {
                return !isTransit && d.reserved_quantity > 0;
            }
            if (filter === 'available') {
                return !isTransit && availableQty > 0 && !d.tiene_hold;
            }
            if (filter === 'transit_available') {
                return isTransit && availableQty > 0 && !d.tiene_hold;
            }
            if (filter === 'transit_hold') {
                return isTransit && d.tiene_hold;
            }
            if (filter === 'transit_committed') {
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
    getDisplayQuantity: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    onInputManualQuantity: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};