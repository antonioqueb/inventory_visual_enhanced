/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class SearchBar extends Component {
    setup() {
        this.orm = useService("orm");
        this.root = useRef("root");

        this.state = useState({
            filters: {
                product_name: '',
                almacen_id: null,
                ubicacion_id: null,
                tipo: '',
                categoria_name: '',
                grupo: '',
                marca: '',
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
                price_currency: '',
                price_min: '',
                price_max: '',
            },
            
            almacenes: [],
            ubicaciones: [],
            tipos: [],
            categorias: [],
            grupos: [],
            marcas: [],
            acabados: [],
            grosores: [],
            colores: [],
            
            showAdvancedFilters: false,
            mobileFiltersOpen: false,
        });

        this.searchTimeout = null;
        this.selectSearchDelay = 300;   // Selects/dropdowns: respuesta rápida
        this.textSearchDelay = 1200;    // Texto libre: esperar a que termine de escribir
        this.minCharsToSearch = 3;      // No buscar con menos de 3 caracteres en texto

        // Tracking para evitar búsquedas duplicadas
        this._lastSearchPayload = null;

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
            const almacenes = await this.orm.searchRead(
                "stock.warehouse", [], ["id", "name"], { order: "name" }
            );
            this.state.almacenes = almacenes;

            const allCategorias = await this.orm.searchRead(
                "product.category", [],
                ["id", "name", "complete_name", "parent_id"],
                { order: "name" }
            );

            const parentIds = new Set(
                allCategorias.filter(cat => cat.parent_id).map(cat => cat.parent_id[0])
            );

            const categoriasMap = new Map();
            allCategorias.forEach(cat => {
                if (!parentIds.has(cat.id)) {
                    const shortName = cat.name;
                    if (!categoriasMap.has(shortName)) {
                        categoriasMap.set(shortName, { name: shortName, ids: [cat.id] });
                    } else {
                        categoriasMap.get(shortName).ids.push(cat.id);
                    }
                }
            });

            this.state.categorias = Array.from(categoriasMap.values()).sort((a, b) => 
                a.name.localeCompare(b.name)
            );

            try {
                const marcas = await this.orm.call(
                    "product.template", "read_group",
                    [[["x_marca", "!=", false]]],
                    { groupby: ["x_marca"], fields: ["x_marca"] }
                );
                this.state.marcas = marcas.map(m => m.x_marca).filter(Boolean).sort();
            } catch (e) {
                console.warn("Error cargando marcas:", e);
                this.state.marcas = [];
            }

            try {
                const colores = await this.orm.call(
                    "stock.quant", "read_group",
                    [[["x_color", "!=", false], ["quantity", ">", 0]]],
                    { groupby: ["x_color"], fields: ["x_color"] }
                );
                this.state.colores = colores.map(c => c.x_color).filter(Boolean).sort();
            } catch (e) {
                console.warn("Error cargando colores:", e);
                this.state.colores = [];
            }

            const fieldInfo = await this.orm.call(
                "stock.quant", "fields_get", [], { attributes: ["selection"] }
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

            try {
                const grosores = await this.orm.call(
                    "stock.quant", "read_group",
                    [[["x_grosor", "!=", false], ["quantity", ">", 0]]],
                    { groupby: ["x_grosor"], fields: ["x_grosor"] }
                );
                const grosorSet = new Set();
                grosores.forEach(g => {
                    if (g.x_grosor !== false && g.x_grosor !== null) grosorSet.add(g.x_grosor);
                });
                this.state.grosores = Array.from(grosorSet).sort((a, b) => a - b);
            } catch (e) {
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
                const almacen = await this.orm.read("stock.warehouse", [almacenId], ["view_location_id"]);
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
        this._triggerSearchImmediate();
    }

    // Para selects y dropdowns — búsqueda rápida
    onFilterChange(filterName, ev) {
        const value = ev.target.value;
        this.state.filters[filterName] = value || null;
        this._triggerSearchImmediate();
    }

    // Para campos de texto libre — debounce largo + mínimo de caracteres
    onTextFilterChange(filterName, ev) {
        this.state.filters[filterName] = ev.target.value;
        this._triggerSearchDebounced(filterName);
    }

    // Enter en cualquier campo de texto = búsqueda inmediata
    onTextFilterKeydown(filterName, ev) {
        if (ev.key === 'Enter') {
            ev.preventDefault();
            if (this.searchTimeout) clearTimeout(this.searchTimeout);
            this._executeSearch();
        }
    }

    onPriceSettingChange(filterName, ev) {
        this.state.filters[filterName] = ev.target.value;
        if (this.state.filters.price_min || this.state.filters.price_max) {
            this._triggerSearchDebounced(filterName);
        }
    }

    onPriceValueChange(filterName, ev) {
        this.state.filters[filterName] = ev.target.value;
        this._triggerSearchDebounced(filterName);
    }

    // ── Estrategia de búsqueda ──────────────────────────────────────

    /**
     * Búsqueda inmediata (selects, dropdowns, almacén).
     * Cancela cualquier debounce pendiente.
     */
    _triggerSearchImmediate() {
        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        this._executeSearch();
    }

    /**
     * Búsqueda con debounce largo para campos de texto.
     * Solo dispara si el valor cumple el mínimo de caracteres
     * o si el campo quedó vacío (para limpiar el filtro).
     */
    _triggerSearchDebounced(filterName) {
        if (this.searchTimeout) clearTimeout(this.searchTimeout);

        const value = this.state.filters[filterName];
        const isTextFilter = typeof value === 'string';

        // Si el texto es muy corto (pero no vacío), no buscar aún
        if (isTextFilter && value.length > 0 && value.length < this.minCharsToSearch) {
            return;
        }

        this.searchTimeout = setTimeout(() => {
            this._executeSearch();
        }, this.textSearchDelay);
    }

    /**
     * Ejecuta la búsqueda real.
     * Evita búsquedas duplicadas comparando el payload.
     */
    _executeSearch() {
        if (!this.props.onSearch) return;

        const payload = JSON.stringify(this.state.filters);
        if (payload === this._lastSearchPayload) return;

        this._lastSearchPayload = payload;
        this.props.onSearch({ ...this.state.filters });
    }

    // ── Legacy wrapper (por si el template llama a triggerSearch) ────
    triggerSearch() {
        this._triggerSearchImmediate();
    }

    toggleAdvancedFilters() {
        this.state.showAdvancedFilters = !this.state.showAdvancedFilters;
    }
    
    toggleMobileFilters() {
        this.state.mobileFiltersOpen = !this.state.mobileFiltersOpen;
    }

    hasActiveFilters() {
        return Object.entries(this.state.filters).some(([key, v]) => v !== null && v !== '');
    }

    clearAllFilters() {
        this.state.filters = {
            product_name: '',
            almacen_id: null,
            ubicacion_id: null,
            tipo: '',
            categoria_name: '',
            grupo: '',
            marca: '',
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
            price_currency: '',
            price_min: '',
            price_max: '',
        };
        this.state.ubicaciones = [];
        this._lastSearchPayload = null;
        if (this.props.onSearch) this.props.onSearch(null);
    }
}

SearchBar.template = "inventory_visual_enhanced.SearchBar";
SearchBar.props = {
    isLoading: { type: Boolean, optional: true },
    onSearch: Function,
    totalProducts: { type: Number, optional: true },
    hasSearched: { type: Boolean, optional: true },
};