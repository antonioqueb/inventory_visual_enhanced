/** @odoo-module **/

import { Component, useState, onWillUpdateProps, useRef, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductDetails } from "../product_details/product_details";

export class ProductRow extends Component {
    setup() {
        this.orm = useService("orm");
        this.priceIconRef = useRef("priceIcon");
        
        this.state = useState({
            activeFilter: 'all',
            showPriceTooltip: false,
            priceData: null,
            priceLoading: false,
        });

        this._tooltipEl = null;

        onWillUpdateProps((nextProps) => {
            if (this.props.isExpanded && !nextProps.isExpanded) {
                this.state.activeFilter = 'all';
            }
        });

        onWillUnmount(() => {
            this._removeTooltipEl();
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

    // ========== PRICE TOOLTIP (FIXED - rendered in body) ==========

    _removeTooltipEl() {
        if (this._tooltipEl && this._tooltipEl.parentNode) {
            this._tooltipEl.parentNode.removeChild(this._tooltipEl);
            this._tooltipEl = null;
        }
    }

    _createTooltipEl() {
        this._removeTooltipEl();
        
        const el = document.createElement('div');
        el.className = 'price-tooltip-fixed';
        el.style.cssText = `
            position: fixed;
            z-index: 99999;
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.18);
            padding: 12px 16px;
            min-width: 280px;
            white-space: nowrap;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.15s ease;
        `;
        document.body.appendChild(el);
        this._tooltipEl = el;
        return el;
    }

    _positionTooltip() {
        if (!this._tooltipEl || !this.priceIconRef.el) return;
        
        const iconRect = this.priceIconRef.el.getBoundingClientRect();
        const tooltipWidth = 280;
        const tooltipHeight = this._tooltipEl.offsetHeight || 140;
        const margin = 8;
        
        let top = iconRect.bottom + margin;
        let left = iconRect.left;
        
        if (top + tooltipHeight > window.innerHeight) {
            top = iconRect.top - tooltipHeight - margin;
        }
        if (left + tooltipWidth > window.innerWidth) {
            left = window.innerWidth - tooltipWidth - 10;
        }
        if (left < 10) left = 10;
        
        this._tooltipEl.style.top = `${top}px`;
        this._tooltipEl.style.left = `${left}px`;
    }

    _renderTooltipContent(content) {
        if (!this._tooltipEl) return;
        this._tooltipEl.innerHTML = content;
        this._positionTooltip();
        this._tooltipEl.style.opacity = '1';
    }

    async onPriceMouseEnter(ev) {
        ev.stopPropagation();
        this.state.showPriceTooltip = true;
        
        this._createTooltipEl();
        
        this._renderTooltipContent(`
            <div style="text-align: center; padding: 8px 0;">
                <i class="fa fa-spinner fa-spin" style="margin-right: 6px; color: #714B67;"></i>
                <span style="color: #999;">Cargando precios...</span>
            </div>
        `);

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

        if (!this.state.showPriceTooltip) {
            this._removeTooltipEl();
            return;
        }

        const d = this.state.priceData;
        if (!d) {
            this._renderTooltipContent(`
                <div style="text-align: center; padding: 8px 0; color: #999;">
                    Sin información de precios
                </div>
            `);
            return;
        }

        this._renderTooltipContent(`
            <div style="font-weight: 700; font-size: 13px; color: #714B67;
                        margin-bottom: 8px; border-bottom: 2px solid #714B67;
                        padding-bottom: 4px;">
                Precios de Referencia
            </div>
            <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid #eee;">
                        <th style="padding: 3px 6px; text-align: left; color: #666;"></th>
                        <th style="padding: 3px 6px; text-align: right; color: #017E84; font-weight: 700;">USD</th>
                        <th style="padding: 3px 6px; text-align: right; color: #714B67; font-weight: 700;">MXN</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #f5f5f5;">
                        <td style="padding: 4px 6px; font-weight: 600;">
                            <span style="color: #28a745;">●</span> Alto
                        </td>
                        <td style="padding: 4px 6px; text-align: right; font-family: monospace;">
                            $${this.formatPrice(d.usd_high)}
                        </td>
                        <td style="padding: 4px 6px; text-align: right; font-family: monospace;">
                            $${this.formatPrice(d.mxn_high)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 6px; font-weight: 600;">
                            <span style="color: #ffc107;">●</span> Medio
                        </td>
                        <td style="padding: 4px 6px; text-align: right; font-family: monospace;">
                            $${this.formatPrice(d.usd_medium)}
                        </td>
                        <td style="padding: 4px 6px; text-align: right; font-family: monospace;">
                            $${this.formatPrice(d.mxn_medium)}
                        </td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top: 6px; font-size: 10px; color: #999; text-align: right;">
                Precio por m²
            </div>
        `);
    }

    onPriceMouseLeave(ev) {
        ev.stopPropagation();
        this.state.showPriceTooltip = false;
        this._removeTooltipEl();
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

            if (filter === 'all') return !isTransit;
            if (filter === 'hold') return !isTransit && d.tiene_hold;
            if (filter === 'committed') return !isTransit && d.reserved_quantity > 0;
            if (filter === 'available') return !isTransit && availableQty > 0 && !d.tiene_hold;
            if (filter === 'transit_available') return isTransit && availableQty > 0 && !d.tiene_hold;
            if (filter === 'transit_hold') return isTransit && d.tiene_hold;
            if (filter === 'transit_committed') return isTransit && d.reserved_quantity > 0;
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