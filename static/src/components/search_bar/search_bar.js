/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SearchBar extends Component {
    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");

        this.state = useState({
            // Filtros
            filters: {
                product_name: '',
                almacen_id: null,
                ubicacion_id: null,
                tipo: '',
                categoria_name: '',
                grupo: '',
                acabado: '',
                color: '',
                grosor: '',
                numero_serie: '',
                bloque: '',
                pedimento: '',
                contenedor: '',
                atado: '',
                alto_min: '',
                ancho_min: '',
            },
            
            // Opciones para dropdowns
            almacenes: [],
            ubicaciones: [],
            tipos: [],
            categorias: [],
            grupos: [],
            acabados: [],
            grosores: [],
            colores: [],
            
            // UI
            showAdvancedFilters: false,
            mobileFiltersOpen: false,
        });

        this.searchTimeout = null;
        this.searchDelay = 500;

        onWillStart(async () => {
            await this.loadFilterOptions();
        });

        onMounted(() => {
            this.setupScrollListener();
        });
    }

    setupScrollListener() {
        const searchBar = this.root.el; 
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

    async loadFilterOptions() {
        try {
            // Cargar almacenes
            const almacenes = await this.orm.searchRead(
                "stock.warehouse",
                [],
                ["id", "name"],
                { order: "name" }
            );
            this.state.almacenes = almacenes;

            // Cargar categorías - solo hojas únicas por nombre corto
            const allCategorias = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name", "complete_name", "parent_id"],
                { order: "name" }
            );

            // Obtener IDs de categorías que son padres (tienen hijos)
            const parentIds = new Set(
                allCategorias
                    .filter(cat => cat.parent_id)
                    .map(cat => cat.parent_id[0])
            );

            // Filtrar solo categorías hoja (no son padres de nadie) y agrupar por nombre
            const categoriasMap = new Map();
            allCategorias.forEach(cat => {
                // Es hoja si su ID NO está en la lista de padres
                if (!parentIds.has(cat.id)) {
                    const shortName = cat.name;
                    if (!categoriasMap.has(shortName)) {
                        categoriasMap.set(shortName, {
                            name: shortName,
                            ids: [cat.id]
                        });
                    } else {
                        categoriasMap.get(shortName).ids.push(cat.id);
                    }
                }
            });

            // Convertir a array para el dropdown
            this.state.categorias = Array.from(categoriasMap.values()).sort((a, b) => 
                a.name.localeCompare(b.name)
            );

            // Cargar colores únicos
            try {
                const colores = await this.orm.call(
                    "stock.quant",
                    "read_group",
                    [[["x_color", "!=", false], ["quantity", ">", 0]]],
                    { groupby: ["x_color"], fields: ["x_color"] }
                );
                this.state.colores = colores.map(c => c.x_color).filter(Boolean).sort();
            } catch (e) {
                console.error("Error cargando colores:", e);
                this.state.colores = [];
            }

            // Cargar opciones de selection fields
            const fieldInfo = await this.orm.call(
                "stock.quant",
                "fields_get",
                [],
                { attributes: ["selection"] }
            );

            if (fieldInfo.x_tipo && fieldInfo.x_tipo.selection) {
                this.state.tipos = fieldInfo.x_tipo.selection;
            }

            if (fieldInfo.x_grupo && fieldInfo.x_grupo.selection) {
                this.state.grupos = fieldInfo.x_grupo.selection;
            }

            if (fieldInfo.x_acabado && fieldInfo.x_acabado.selection) {
                this.state.acabados = fieldInfo.x_acabado.selection;
            }

            // Cargar grosores únicos
            try {
                const grosores = await this.orm.call(
                    "stock.quant",
                    "read_group",
                    [[["x_grosor", "!=", false], ["quantity", ">", 0]]],
                    { groupby: ["x_grosor"], fields: ["x_grosor"] }
                );
                const grosorSet = new Set();
                grosores.forEach(g => {
                    if (g.x_grosor !== false && g.x_grosor !== null) {
                        grosorSet.add(g.x_grosor);
                    }
                });
                this.state.grosores = Array.from(grosorSet).sort((a, b) => a - b);
            } catch (e) {
                console.error("Error cargando grosores:", e);
                this.state.grosores = [];
            }

        } catch (error) {
            console.error("Error cargando opciones de filtros:", error);
        }
    }

    async onAlmacenChange(ev) {
        const almacenId = ev.target.value ? parseInt(ev.target.value) : null;
        this.state.filters.almacen_id = almacenId;
        this.state.filters.ubicacion_id = null;
        this.state.ubicaciones = [];

        if (almacenId) {
            try {
                const almacen = await this.orm.read(
                    "stock.warehouse",
                    [almacenId],
                    ["view_location_id"]
                );

                if (almacen.length > 0 && almacen[0].view_location_id) {
                    const ubicaciones = await this.orm.searchRead(
                        "stock.location",
                        [["location_id", "child_of", almacen[0].view_location_id[0]]],
                        ["id", "complete_name"],
                        { order: "complete_name" }
                    );
                    this.state.ubicaciones = ubicaciones;
                }
            } catch (error) {
                console.error("Error cargando ubicaciones:", error);
            }
        }

        this.triggerSearch();
    }

    onFilterChange(filterName, ev) {
        const value = ev.target.value;
        this.state.filters[filterName] = value || null;
        this.triggerSearch();
    }

    onTextFilterChange(filterName, ev) {
        // CAMBIO IMPORTANTE: Quitamos .trim() para permitir escribir espacios cómodamente 
        // (por ejemplo: "LOTE1, LOTE2"). El backend se encargará de limpiar los espacios.
        const value = ev.target.value; 
        this.state.filters[filterName] = value;
        this.triggerSearch();
    }

    triggerSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        this.searchTimeout = setTimeout(() => {
            if (this.props.onSearch) {
                this.props.onSearch({ ...this.state.filters });
            }
        }, this.searchDelay);
    }

    toggleAdvancedFilters() {
        this.state.showAdvancedFilters = !this.state.showAdvancedFilters;
    }
    
    toggleMobileFilters() {
        this.state.mobileFiltersOpen = !this.state.mobileFiltersOpen;
    }

    hasActiveFilters() {
        return Object.values(this.state.filters).some(v => v !== null && v !== '');
    }

    clearAllFilters() {
        this.state.filters = {
            product_name: '',
            almacen_id: null,
            ubicacion_id: null,
            tipo: '',
            categoria_name: '',
            grupo: '',
            acabado: '',
            grosor: '',
            numero_serie: '',
            bloque: '',
            pedimento: '',
            contenedor: '',
            atado: '',
            color: '',
            alto_min: '',
            ancho_min: '',
            
        };
        this.state.ubicaciones = [];
        
        if (this.props.onSearch) {
            this.props.onSearch(null);
        }
    }
}

SearchBar.template = "inventory_visual_enhanced.SearchBar";
SearchBar.props = {
    isLoading: { type: Boolean, optional: true },
    onSearch: Function,
    totalProducts: { type: Number, optional: true },
    hasSearched: { type: Boolean, optional: true },
};