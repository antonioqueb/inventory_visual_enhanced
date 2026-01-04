# -*- coding: utf-8 -*-
{
    'name': 'Inventario Visual Avanzado',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Vista visual mejorada y agrupada del inventario por producto',
    'description': """
        Módulo puramente visual que mejora la experiencia de usuario al visualizar inventario:
        
        Características principales:
        - Vista agrupada por producto con métricas condensadas
        - Búsqueda inteligente por familia de productos
        - Visualización expandible del detalle de placas y lotes
        - Diseño moderno y profesional con SCSS personalizado
        - Información consolidada: disponible, apartado, total m²
        - Interfaz intuitiva y altamente legible
        - Colores personalizables mediante variables SCSS
        - Arquitectura modular con componentes separados
        - Diálogos especializados para fotos, notas, historial y apartados
        - No modifica la lógica de negocio existente
        
        Este módulo NO altera la funcionalidad de Odoo, solo mejora la visualización.
    """,
    'author': 'Alphaqueb Consulting SAS',
    'website': 'https://alphaqueb.com',
    'depends': [
        'stock',
        'web',
        'purchase',
        'sale',
        'stock_lot_dimensions',
    ],
    'data': [
        'views/inventory_visual_views.xml',
        'views/menu_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Variables PRIMERO (pero dentro de assets_backend)
            'inventory_visual_enhanced/static/src/scss/_variables.scss',
            
            # SCSS de componentes
            'inventory_visual_enhanced/static/src/scss/components/_hold-wizard.scss',
            'inventory_visual_enhanced/static/src/scss/components/_searchbar.scss',
            'inventory_visual_enhanced/static/src/scss/components/_states.scss',
            'inventory_visual_enhanced/static/src/scss/components/_data-grid.scss',
            'inventory_visual_enhanced/static/src/scss/components/_product-row.scss',
            'inventory_visual_enhanced/static/src/scss/components/_product-details.scss',
            'inventory_visual_enhanced/static/src/scss/components/_badges.scss',
            'inventory_visual_enhanced/static/src/scss/components/_notes-dialog.scss',
            'inventory_visual_enhanced/static/src/scss/components/_history-dialog.scss',
            'inventory_visual_enhanced/static/src/scss/components/_hold-info-dialog.scss',
            
            # JS
            'inventory_visual_enhanced/static/src/components/search_bar/search_bar.js', # <--- NUEVO
            'inventory_visual_enhanced/static/src/components/product_details/product_details.js',
            'inventory_visual_enhanced/static/src/components/product_row/product_row.js',
            'inventory_visual_enhanced/static/src/components/inventory_view/inventory_controller.js',
            'inventory_visual_enhanced/static/src/components/dialogs/photo_gallery/photo_gallery_dialog.js',
            'inventory_visual_enhanced/static/src/components/dialogs/notes/notes_dialog.js',
            'inventory_visual_enhanced/static/src/components/dialogs/history/history_dialog.js',
            'inventory_visual_enhanced/static/src/components/dialogs/hold/hold_dialog.js',
            'inventory_visual_enhanced/static/src/components/dialogs/hold_info/hold_info_dialog.js',
            'inventory_visual_enhanced/static/src/components/dialogs/sale_order/sale_order_dialog.js',
            
            # XML
            'inventory_visual_enhanced/static/src/components/search_bar/search_bar.xml', # <--- NUEVO
            'inventory_visual_enhanced/static/src/components/product_details/product_details.xml',
            'inventory_visual_enhanced/static/src/components/product_row/product_row.xml',
            'inventory_visual_enhanced/static/src/components/inventory_view/inventory_controller.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/photo_gallery/photo_gallery_dialog.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/notes/notes_dialog.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/history/history_dialog.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/hold/hold_dialog.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/hold_info/hold_info_dialog.xml',
            'inventory_visual_enhanced/static/src/components/dialogs/sale_order/sale_order_dialog.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}