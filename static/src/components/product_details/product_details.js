/** @odoo-module **/

import { Component } from "@odoo/owl";

export class ProductDetails extends Component {
    
    /**
     * Getter principal que transforma la lista plana de detalles (props.details)
     * en una lista agrupada por Bloque, calculando totales y ordenando
     * de mayor cantidad de placas a menor.
     */
    get groupedAndSortedDetails() {
        const details = this.props.details || [];
        const groups = {};

        // 1. Agrupación: Recorremos todos los productos
        for (const detail of details) {
            // Si el campo bloque viene vacío, lo etiquetamos como "Sin Bloque"
            const blockName = detail.bloque || 'Sin Bloque'; 
            
            if (!groups[blockName]) {
                groups[blockName] = {
                    blockName: blockName,
                    items: [],      // Aquí guardaremos las filas originales
                    totalArea: 0,   // Acumulador de m2
                    count: 0,       // Acumulador de cantidad
                    productType: null // <--- NUEVO: Guardaremos el tipo aquí
                };
            }

            // Agregamos el item al grupo correspondiente
            groups[blockName].items.push(detail);
            
            // Incrementamos contadores
            groups[blockName].count += 1;
            groups[blockName].totalArea += (detail.quantity || 0);

            // <--- NUEVO: Detectar tipo (Placa/Formato/Pieza) del primer item que tenga dato
            if (!groups[blockName].productType && detail.tipo) {
                groups[blockName].productType = detail.tipo;
            }
        }

        // 2. Conversión: Pasamos de Objeto a Array para poder iterar en el XML
        const groupArray = Object.values(groups);

        // 3. Ordenamiento: Ponemos primero los bloques con más items (Descendente)
        groupArray.sort((a, b) => b.count - a.count);

        return groupArray;
    }

    // Mantenemos la lógica original de selección móvil
    onMobileSelectAll(ev) {
        if (this.props.onMobileSelectAll) {
            this.props.onMobileSelectAll(ev);
        }
    }
    
    /**
     * Método auxiliar para obtener el texto de la unidad
     * Se usa en el XML para mostrar 'pza' si es Pieza, o 'm²' para Placa/Formato
     */
    getUnitLabel(type) {
        const t = type ? type.toString().toLowerCase() : '';
        return t === 'pieza' ? 'pza' : 'm²';
    }
}

ProductDetails.template = "inventory_visual_enhanced.ProductDetails";

// Definición de props para validación y autocompletado
ProductDetails.props = {
    details: Array,
    // Props existentes
    areAllCurrentProductSelected: { type: Function, optional: true },
    isInCart: { type: Function, optional: true },
    // Nuevas props para lógica de cantidad manual
    getDisplayQuantity: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    onInputManualQuantity: { type: Function, optional: true },
    
    onPhotoClick: { type: Function, optional: true },
    onNotesClick: { type: Function, optional: true },
    onDetailsClick: { type: Function, optional: true },
    onHoldClick: { type: Function, optional: true },
    onSaleOrderClick: { type: Function, optional: true },
    formatNumber: { type: Function, optional: true },
    hasSalesPermissions: { type: Boolean, optional: true },
    onSalesPersonClick: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    hasInventoryPermissions: { type: Boolean, optional: true },
};