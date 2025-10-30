# -*- coding: utf-8 -*-
{
    'name': 'Inventario Visual Avanzado',
    'version': '18.0.1.0.0',
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
        - No modifica la lógica de negocio existente
        
        Este módulo NO altera la funcionalidad de Odoo, solo mejora la visualización.
    """,
    'author': 'Alphaqueb Consulting SAS',
    'website': 'https://alphaqueb.com',
    'depends': [
        'stock',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/inventory_visual_views.xml',
        'views/menu_items.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_visual_enhanced/static/src/scss/inventory_visual.scss',
            'inventory_visual_enhanced/static/src/js/inventory_visual_controller.js',
            'inventory_visual_enhanced/static/src/xml/inventory_visual_template.xml',
            'inventory_visual_enhanced/static/src/xml/inventory_visual_dialogs.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}