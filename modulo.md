## ./__init__.py
```py
# -*- coding: utf-8 -*-
from . import models```

## ./__manifest__.py
```py
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
            
            # JS
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
}```

## ./models/__init__.py
```py
# -*- coding: utf-8 -*-
from . import stock_quant```

## ./models/stock_quant.py
```py
# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__) 

class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    @api.model
    def get_inventory_grouped_by_product(self, filters=None):
        """
        Agrupa el inventario por producto aplicando filtros
        """
        if not filters:
            return []
        
        domain = [('quantity', '>', 0)]
        
        # Filtro por nombre de producto
        if filters.get('product_name'):
            domain.append(('product_id', 'ilike', filters['product_name']))
        
        # Filtro por almacén
        if filters.get('almacen_id'):
            almacen = self.env['stock.warehouse'].browse(int(filters['almacen_id']))
            if almacen.view_location_id:
                domain.append(('location_id', 'child_of', almacen.view_location_id.id))
        
        # Filtro por ubicación específica
        if filters.get('ubicacion_id'):
            domain.append(('location_id', 'child_of', int(filters['ubicacion_id'])))
        
        # Filtro por tipo
        if filters.get('tipo'):
            domain.append(('x_tipo', '=', filters['tipo']))
        
        # Filtro por categoría
        if filters.get('categoria_id'):
            domain.append(('product_id.categ_id', '=', int(filters['categoria_id'])))
        
        # Filtro por grupo
        if filters.get('grupo'):
            domain.append(('x_grupo', '=', filters['grupo']))
        
        # Filtro por acabado
        if filters.get('acabado'):
            domain.append(('x_acabado', '=', filters['acabado']))
        
        # Filtro por grosor
        if filters.get('grosor'):
            domain.append(('x_grosor', '=', float(filters['grosor'])))
        
        # Filtro por número de serie
        if filters.get('numero_serie'):
            domain.append(('lot_id.name', 'ilike', filters['numero_serie']))
        
        # Filtro por bloque
        if filters.get('bloque'):
            domain.append(('x_bloque', 'ilike', filters['bloque']))
        
        # Filtro por pedimento
        if filters.get('pedimento'):
            domain.append(('x_pedimento', 'ilike', filters['pedimento']))
        
        # Filtro por contenedor
        if filters.get('contenedor'):
            domain.append(('x_contenedor', 'ilike', filters['contenedor']))
        
        # Filtro por atado
        if filters.get('atado'):
            domain.append(('x_atado', 'ilike', filters['atado']))
        
        # Buscar quants
        quants = self.search(domain)
        
        # Agrupar por producto
        product_groups = {}
        for quant in quants:
            product_id = quant.product_id.id
            
            if product_id not in product_groups:
                # Obtener el valor display del campo tipo
                tipo_display = ''
                if hasattr(quant, 'x_tipo') and quant.x_tipo:
                    try:
                        field = quant._fields.get('x_tipo')
                        if field:
                            selection = field.selection
                            if callable(selection):
                                selection = selection(quant)
                            tipo_dict = dict(selection)
                            tipo_display = tipo_dict.get(quant.x_tipo, '')
                    except:
                        tipo_display = ''
                
                product_groups[product_id] = {
                    'product_id': product_id,
                    'product_name': quant.product_id.display_name,
                    'product_code': quant.product_id.default_code or '',
                    'categ_name': quant.product_id.categ_id.display_name,
                    'tipo': tipo_display,
                    'quant_ids': [],
                    'stock_qty': 0.0,
                    'stock_plates': 0,
                    'hold_qty': 0.0,
                    'hold_plates': 0,
                    'committed_qty': 0.0,
                    'committed_plates': 0,
                    'available_qty': 0.0,
                    'available_plates': 0,
                }
            
            product_groups[product_id]['quant_ids'].append(quant.id)
            product_groups[product_id]['stock_qty'] += quant.quantity
            product_groups[product_id]['stock_plates'] += 1
            
            # Hold
            if hasattr(quant, 'x_tiene_hold') and quant.x_tiene_hold:
                product_groups[product_id]['hold_qty'] += quant.quantity
                product_groups[product_id]['hold_plates'] += 1
            
            # Committed (reservado)
            if quant.reserved_quantity > 0:
                product_groups[product_id]['committed_qty'] += quant.reserved_quantity
                product_groups[product_id]['committed_plates'] += 1
            
            # Available
            available = quant.quantity - quant.reserved_quantity
            if hasattr(quant, 'x_tiene_hold') and not quant.x_tiene_hold and available > 0:
                product_groups[product_id]['available_qty'] += available
                product_groups[product_id]['available_plates'] += 1
        
        return list(product_groups.values())
    
    @api.model
    def get_quant_details(self, quant_ids=None):
        """
        Obtiene detalles de quants específicos
        """
        if not quant_ids:
            return []
        
        quants = self.browse(quant_ids)
        result = []
        
        for quant in quants:
            # Obtener el valor display del campo tipo
            tipo_display = ''
            if hasattr(quant, 'x_tipo') and quant.x_tipo:
                try:
                    field = quant._fields.get('x_tipo')
                    if field:
                        selection = field.selection
                        if callable(selection):
                            selection = selection(quant)
                        tipo_dict = dict(selection)
                        tipo_display = tipo_dict.get(quant.x_tipo, '')
                except:
                    tipo_display = ''
            
            detail = {
                'id': quant.id,
                'lot_id': quant.lot_id.id if quant.lot_id else False,
                'lot_name': quant.lot_id.name if quant.lot_id else '',
                'location_id': quant.location_id.id,
                'location_name': quant.location_id.complete_name,
                'quantity': quant.quantity,
                'reserved_quantity': quant.reserved_quantity,
                'grosor': quant.x_grosor if hasattr(quant, 'x_grosor') else False,
                'alto': quant.x_alto if hasattr(quant, 'x_alto') else False,
                'ancho': quant.x_ancho if hasattr(quant, 'x_ancho') else False,
                'tipo': tipo_display,
                'bloque': quant.x_bloque if hasattr(quant, 'x_bloque') else '',
                'atado': quant.x_atado if hasattr(quant, 'x_atado') else '',
                'pedimento': quant.x_pedimento if hasattr(quant, 'x_pedimento') else '',
                'contenedor': quant.x_contenedor if hasattr(quant, 'x_contenedor') else '',
                'referencia_proveedor': quant.x_referencia_proveedor if hasattr(quant, 'x_referencia_proveedor') else '',
                'cantidad_fotos': 0,
                'detalles_placa': quant.x_detalles_placa if hasattr(quant, 'x_detalles_placa') else '',
                'tiene_hold': quant.x_tiene_hold if hasattr(quant, 'x_tiene_hold') else False,
                'hold_info': None,
                'en_orden_venta': False,
                'sale_order_ids': [],
            }
            
            # Fotos
            if quant.lot_id and hasattr(quant.lot_id, 'x_fotografia_ids'):
                detail['cantidad_fotos'] = len(quant.lot_id.x_fotografia_ids)
            
            # Hold info
            if detail['tiene_hold'] and hasattr(quant, 'x_hold_activo_id') and quant.x_hold_activo_id:
                hold = quant.x_hold_activo_id
                detail['hold_info'] = {
                    'id': hold.id,
                    'partner_name': hold.partner_id.name if hold.partner_id else '',
                    'proyecto_nombre': hold.project_id.name if hasattr(hold, 'project_id') and hold.project_id else '',
                    'arquitecto_nombre': hold.arquitecto_id.name if hasattr(hold, 'arquitecto_id') and hold.arquitecto_id else '',
                    'vendedor_nombre': hold.user_id.name if hold.user_id else '',
                    'fecha_inicio': hold.fecha_inicio.strftime('%Y-%m-%d') if hasattr(hold, 'fecha_inicio') and hold.fecha_inicio else '',
                    'fecha_expiracion': hold.fecha_expiracion.strftime('%Y-%m-%d') if hasattr(hold, 'fecha_expiracion') and hold.fecha_expiracion else '',
                    'notas': hold.notas if hasattr(hold, 'notas') else '',
                }
            
            # Sale orders - buscar en el campo correcto
            if quant.lot_id:
                # Buscar sale order lines que contengan este quant en sus lotes seleccionados
                sale_lines = self.env['sale.order.line'].search([
                    ('product_id', '=', quant.product_id.id),
                    ('order_id.state', 'in', ['sale', 'done'])
                ])
                # Filtrar las que realmente contienen este lote
                relevant_orders = []
                for line in sale_lines:
                    # Verificar si el lote está en los movimientos de esta línea
                    move_lines = line.move_ids.mapped('move_line_ids').filtered(
                        lambda ml: ml.lot_id.id == quant.lot_id.id
                    )
                    if move_lines:
                        relevant_orders.append(line.order_id.id)
                
                if relevant_orders:
                    detail['en_orden_venta'] = True
                    detail['sale_order_ids'] = list(set(relevant_orders))
            
            result.append(detail)
        
        return result
    
    @api.model
    def get_lot_history(self, quant_id):
        """
        Obtiene el historial completo de un lote
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        lot = quant.lot_id
        
        # Información general
        general_info = {
            'product_name': lot.product_id.display_name,
            'product_code': lot.product_id.default_code or '',
            'lot_name': lot.name,
            'fecha_creacion': lot.create_date.strftime('%Y-%m-%d') if lot.create_date else '',
            'estado_actual': 'Disponible',
            'ubicacion_actual': quant.location_id.complete_name,
            'cantidad_actual': quant.quantity,
            'cantidad_reservada': quant.reserved_quantity,
            'cantidad_disponible': quant.quantity - quant.reserved_quantity,
        }
        
        # Estadísticas
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', '=', lot.id)
        ])
        
        dias_inventario = 0
        if lot.create_date:
            from datetime import datetime
            dias_inventario = (datetime.now() - lot.create_date).days
        
        statistics = {
            'total_movimientos': len(move_lines),
            'total_entradas': len(move_lines.filtered(lambda m: m.location_dest_id.usage == 'internal')),
            'total_salidas': len(move_lines.filtered(lambda m: m.location_id.usage == 'internal')),
            'total_ventas': 0,
            'total_apartados': 0,
            'total_entregas': 0,
            'dias_en_inventario': dias_inventario,
        }
        
        # Información de compra
        purchase_info = []
        purchase_lines = self.env['purchase.order.line'].search([
            ('product_id', '=', lot.product_id.id)
        ], limit=5, order='create_date desc')
        
        for pol in purchase_lines:
            purchase_info.append({
                'orden_compra': pol.order_id.name,
                'proveedor': pol.order_id.partner_id.name,
                'fecha_orden': pol.order_id.date_order.strftime('%Y-%m-%d') if pol.order_id.date_order else '',
                'cantidad': pol.product_qty,
                'precio_unitario': pol.price_unit,
                'total': pol.price_subtotal,
                'moneda': pol.order_id.currency_id.symbol,
                'estado': dict(pol.order_id._fields['state'].selection).get(pol.order_id.state, ''),
            })
        
        # Movimientos
        movements = []
        for ml in move_lines.sorted('date', reverse=True):
            icon = 'fa-arrow-right'
            tipo = 'Transferencia'
            
            if ml.location_id.usage != 'internal' and ml.location_dest_id.usage == 'internal':
                icon = 'fa-arrow-down'
                tipo = 'Entrada'
            elif ml.location_id.usage == 'internal' and ml.location_dest_id.usage != 'internal':
                icon = 'fa-arrow-up'
                tipo = 'Salida'
            
            movements.append({
                'fecha': ml.date.strftime('%Y-%m-%d %H:%M') if ml.date else '',
                'tipo': tipo,
                'icon': icon,
                'origen': ml.location_id.complete_name,
                'destino': ml.location_dest_id.complete_name,
                'cantidad': ml.qty_done,
                'referencia': ml.reference or ml.picking_id.name if ml.picking_id else '',
                'usuario': ml.write_uid.name if ml.write_uid else '',
            })
        
        # Órdenes de venta
        sales_orders = []
        sale_lines = self.env['sale.order.line'].search([
            ('product_id', '=', lot.product_id.id),
            ('order_id.state', 'in', ['sale', 'done'])
        ], limit=10, order='create_date desc')
        
        for sol in sale_lines:
            # Verificar si este lote fue usado en esta línea
            used_in_line = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id),
                ('move_id.sale_line_id', '=', sol.id)
            ], limit=1)
            
            if used_in_line:
                statistics['total_ventas'] += 1
                sales_orders.append({
                    'orden_venta': sol.order_id.name,
                    'cliente': sol.order_id.partner_id.name,
                    'vendedor': sol.order_id.user_id.name if sol.order_id.user_id else '',
                    'fecha_orden': sol.order_id.date_order.strftime('%Y-%m-%d') if sol.order_id.date_order else '',
                    'cantidad': sol.product_uom_qty,
                    'precio_unitario': sol.price_unit,
                    'total': sol.price_subtotal,
                    'moneda': sol.order_id.currency_id.symbol,
                    'estado': dict(sol.order_id._fields['state'].selection).get(sol.order_id.state, ''),
                })
        
        # Reservas/Apartados
        reservations = []
        if hasattr(quant, 'x_hold_ids'):
            for hold in quant.x_hold_ids:
                statistics['total_apartados'] += 1
                reservations.append({
                    'tipo': 'Apartado Manual',
                    'partner': hold.partner_id.name if hold.partner_id else '',
                    'fecha_inicio': hold.fecha_inicio.strftime('%Y-%m-%d') if hold.fecha_inicio else '',
                    'fecha_expiracion': hold.fecha_expiracion.strftime('%Y-%m-%d') if hold.fecha_expiracion else '',
                    'estado': dict(hold._fields['estado'].selection).get(hold.estado, ''),
                    'notas': hold.notas or '',
                })
        
        # Entregas
        deliveries = []
        delivery_moves = self.env['stock.move.line'].search([
            ('lot_id', '=', lot.id),
            ('picking_id.picking_type_code', '=', 'outgoing')
        ])
        
        for dm in delivery_moves:
            if dm.picking_id:
                statistics['total_entregas'] += 1
                deliveries.append({
                    'referencia': dm.picking_id.name,
                    'cliente': dm.picking_id.partner_id.name if dm.picking_id.partner_id else '',
                    'fecha_programada': dm.picking_id.scheduled_date.strftime('%Y-%m-%d') if dm.picking_id.scheduled_date else '',
                    'fecha_efectiva': dm.date.strftime('%Y-%m-%d') if dm.date else '',
                    'cantidad': dm.qty_done,
                    'origen': dm.location_id.complete_name,
                    'estado': dict(dm.picking_id._fields['state'].selection).get(dm.picking_id.state, ''),
                })
        
        return {
            'general_info': general_info,
            'statistics': statistics,
            'purchase_info': purchase_info,
            'movements': movements,
            'sales_orders': sales_orders,
            'reservations': reservations,
            'deliveries': deliveries,
        }
    
    @api.model
    def get_lot_photos(self, quant_id):
        """
        Obtiene las fotografías de un lote
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        lot = quant.lot_id
        photos = []
        
        if hasattr(lot, 'x_fotografia_ids'):
            for photo in lot.x_fotografia_ids:
                photos.append({
                    'id': photo.id,
                    'name': photo.name,
                    'image': photo.image,
                    'fecha_captura': photo.fecha_captura.strftime('%Y-%m-%d %H:%M') if photo.fecha_captura else '',
                    'notas': photo.notas or '',
                })
        
        return {
            'lot_name': lot.name,
            'product_name': lot.product_id.display_name,
            'photos': photos,
        }
    
    @api.model
    def get_lot_notes(self, quant_id):
        """
        Obtiene las notas de un lote
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        lot = quant.lot_id
        
        return {
            'lot_name': lot.name,
            'product_name': lot.product_id.display_name,
            'notes': lot.x_detalles_placa if hasattr(lot, 'x_detalles_placa') else '',
        }
    
    @api.model
    def save_lot_photo(self, quant_id, photo_name, photo_data, sequence=10, notas=''):
        """
        Guarda una fotografía para un lote
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'success': False, 'error': 'Lote no encontrado'}
        
        try:
            self.env['stock.lot.image'].create({
                'lot_id': quant.lot_id.id,
                'name': photo_name,
                'image': photo_data,
                'sequence': sequence,
                'notas': notas,
            })
            
            return {
                'success': True,
                'message': f'Fotografía "{photo_name}" guardada correctamente'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error al guardar fotografía: {str(e)}'
            }
    
    @api.model
    def save_lot_notes(self, quant_id, notes):
        """
        Guarda las notas de un lote
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'success': False, 'error': 'Lote no encontrado'}
        
        try:
            quant.lot_id.write({
                'x_detalles_placa': notes
            })
            
            return {
                'success': True,
                'message': 'Notas guardadas correctamente'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error al guardar notas: {str(e)}'
            }
    
    @api.model
    def search_partners(self, name=''):
        """
        Busca clientes/contactos
        """
        domain = [('customer_rank', '>', 0)]
        
        if name:
            domain = ['|', '|', '|',
                ('name', 'ilike', name),
                ('vat', 'ilike', name),
                ('ref', 'ilike', name),
                ('email', 'ilike', name)
            ] + domain
        
        partners = self.env['res.partner'].search(domain, limit=20, order='name')
        
        result = []
        for partner in partners:
            result.append({
                'id': partner.id,
                'name': partner.name,
                'display_name': partner.display_name,
                'vat': partner.vat or '',
                'ref': partner.ref or '',
                'email': partner.email or '',
            })
        
        return result
    
    @api.model
    def create_partner(self, name, vat='', ref=''):
        """
        Crea un nuevo cliente
        """
        if not name or not name.strip():
            return {'error': 'El nombre es requerido'}
        
        try:
            partner = self.env['res.partner'].create({
                'name': name.strip(),
                'vat': vat.strip() if vat else False,
                'ref': ref.strip() if ref else False,
                'customer_rank': 1,
                'company_type': 'company',
            })
            
            return {
                'success': True,
                'partner': {
                    'id': partner.id,
                    'name': partner.name,
                    'display_name': partner.display_name,
                    'vat': partner.vat or '',
                    'ref': partner.ref or '',
                }
            }
        except Exception as e:
            return {'error': f'Error al crear cliente: {str(e)}'}
    
    @api.model
    def get_projects(self, search_term=''):
        """
        Obtiene proyectos de mármol
        """
        domain = []
        
        if hasattr(self.env['project.project'], 'x_es_proyecto_marmol'):
            domain.append(('x_es_proyecto_marmol', '=', True))
        
        if search_term:
            domain.append(('name', 'ilike', search_term))
        
        projects = self.env['project.project'].search(domain, limit=20, order='name')
        
        result = []
        for project in projects:
            result.append({
                'id': project.id,
                'name': project.name,
            })
        
        return result
    
    @api.model
    def create_project(self, name):
        """
        Crea un nuevo proyecto
        """
        if not name or not name.strip():
            return {'error': 'El nombre del proyecto es requerido'}
        
        try:
            vals = {
                'name': name.strip(),
            }
            
            if hasattr(self.env['project.project'], 'x_es_proyecto_marmol'):
                vals['x_es_proyecto_marmol'] = True
            
            project = self.env['project.project'].create(vals)
            
            return {
                'success': True,
                'project': {
                    'id': project.id,
                    'name': project.name,
                }
            }
        except Exception as e:
            return {'error': f'Error al crear proyecto: {str(e)}'}
    
    @api.model
    def get_architects(self, search_term=''):
        """
        Obtiene arquitectos
        """
        domain = []
        
        if hasattr(self.env['res.partner'], 'x_es_arquitecto'):
            domain.append(('x_es_arquitecto', '=', True))
        
        if search_term:
            domain = ['|', '|',
                ('name', 'ilike', search_term),
                ('vat', 'ilike', search_term),
                ('ref', 'ilike', search_term)
            ] + domain
        
        architects = self.env['res.partner'].search(domain, limit=20, order='name')
        
        result = []
        for architect in architects:
            result.append({
                'id': architect.id,
                'name': architect.name,
                'display_name': architect.display_name,
                'vat': architect.vat or '',
                'ref': architect.ref or '',
            })
        
        return result
    
    @api.model
    def create_architect(self, name, vat='', ref=''):
        """
        Crea un nuevo arquitecto
        """
        if not name or not name.strip():
            return {'error': 'El nombre del arquitecto es requerido'}
        
        try:
            vals = {
                'name': name.strip(),
                'vat': vat.strip() if vat else False,
                'ref': ref.strip() if ref else False,
                'company_type': 'person',
            }
            
            if hasattr(self.env['res.partner'], 'x_es_arquitecto'):
                vals['x_es_arquitecto'] = True
            
            architect = self.env['res.partner'].create(vals)
            
            return {
                'success': True,
                'architect': {
                    'id': architect.id,
                    'name': architect.name,
                    'display_name': architect.display_name,
                    'vat': architect.vat or '',
                    'ref': architect.ref or '',
                }
            }
        except Exception as e:
            return {'error': f'Error al crear arquitecto: {str(e)}'}
    
    @api.model
    def create_lot_hold_enhanced(self, quant_id, partner_id, project_id, architect_id, 
                                  notas='', currency_code='USD', product_prices=None):
        """
        Crea un apartado (hold) para un lote con información completa
        """
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        # Verificar si ya tiene hold activo
        if hasattr(quant, 'x_tiene_hold') and quant.x_tiene_hold:
            return {'error': 'Este lote ya tiene un apartado activo'}
        
        try:
            # Construir notas con información de precios
            full_notes = notas or ''
            
            if product_prices and isinstance(product_prices, dict):
                full_notes += f'\n\n=== PRECIOS ({currency_code}) ===\n'
                for product_id_str, price in product_prices.items():
                    try:
                        product = self.env['product.product'].browse(int(product_id_str))
                        if product.exists():
                            full_notes += f'• {product.display_name}: {price:.2f} {currency_code}/m²\n'
                    except Exception as e:
                        _logger.warning(f"Error procesando precio del producto {product_id_str}: {e}")
            
            # Calcular fecha de expiración (5 días hábiles)
            from datetime import datetime, timedelta
            fecha_inicio = datetime.now()
            fecha_expiracion = fecha_inicio
            dias_agregados = 0
            
            while dias_agregados < 5:
                fecha_expiracion += timedelta(days=1)
                if fecha_expiracion.weekday() < 5:  # Lunes a Viernes
                    dias_agregados += 1
            
            # Verificar que el modelo stock.lot.hold existe
            if 'stock.lot.hold' not in self.env:
                return {'error': 'El modelo stock.lot.hold no está disponible. Verifica que el módulo correspondiente esté instalado.'}
            
            # Preparar valores para crear el hold
            hold_vals = {
                'lot_id': quant.lot_id.id,
                'partner_id': partner_id,
                'user_id': self.env.user.id,
                'fecha_inicio': fecha_inicio,
                'fecha_expiracion': fecha_expiracion,
                'notas': full_notes,
            }
            
            # Agregar campos opcionales solo si existen en el modelo
            hold_model = self.env['stock.lot.hold']
            if 'quant_id' in hold_model._fields:
                hold_vals['quant_id'] = quant.id
            if 'project_id' in hold_model._fields and project_id:
                hold_vals['project_id'] = project_id
            if 'arquitecto_id' in hold_model._fields and architect_id:
                hold_vals['arquitecto_id'] = architect_id
            
        
            hold = hold_model.create(hold_vals)
            
            return {
                'success': True,
                'message': f'Apartado creado exitosamente para el lote {quant.lot_id.name}',
                'hold_id': hold.id,
                'fecha_expiracion': fecha_expiracion.strftime('%Y-%m-%d %H:%M'),
            }
            
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            _logger.error(f"Error al crear apartado: {error_msg}")
            return {'error': f'Error al crear apartado: {str(e)}'}
    
    @api.model
    def get_sale_order_info(self, sale_order_ids):
        """
        Obtiene información de órdenes de venta
        """
        if not sale_order_ids:
            return {'count': 0, 'orders': []}
        
        orders = self.env['sale.order'].browse(sale_order_ids)
        
        result = []
        for order in orders:
            result.append({
                'id': order.id,
                'name': order.name,
                'partner_name': order.partner_id.name,
                'user_name': order.user_id.name if order.user_id else '',
                'date_order': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
                'commitment_date': order.commitment_date.strftime('%Y-%m-%d') if order.commitment_date else '',
                'state': order.state,
                'state_display': dict(order._fields['state'].selection).get(order.state, ''),
                'amount_total': order.amount_total,
                'currency_symbol': order.currency_id.symbol,
            })
        
        return {
            'count': len(result),
            'orders': result,
        }```

## ./static/src/components/dialogs/history/history_dialog.js
```js
/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class HistoryDialog extends Component {
    setup() {
        this.history = this.props.history;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            currentTab: 'general',
        });
    }
    
    switchTab(tabName) {
        this.state.currentTab = tabName;
    }
    
    isActiveTab(tabName) {
        return this.state.currentTab === tabName;
    }
    
    formatCurrency(amount, symbol) {
        return `${symbol} ${new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount)}`;
    }
    
    formatNumber(num) {
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }
}

HistoryDialog.template = "inventory_visual_enhanced.HistoryDialog";
HistoryDialog.components = { Dialog };```

## ./static/src/components/dialogs/history/history_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.HistoryDialog" owl="1">
        <Dialog size="'xl'" contentClass="'h-100'">
            <div class="o_history_dialog d-flex flex-column h-100">
                
                <!-- Header con información general -->
                <div class="alert alert-light border-start border-4 border-secondary mb-3">
                    <div class="row">
                        <div class="col-md-6">
                            <h5 class="mb-2 fw-bold">
                                <i class="fa fa-cube fa-lg text-secondary me-2"></i>
                                <t t-esc="history.general_info.product_name"/>
                            </h5>
                            <div class="d-flex gap-3 flex-wrap">
                                <small class="text-muted">
                                    <i class="fa fa-barcode me-1"></i>
                                    Lote: <strong t-esc="history.general_info.lot_name"></strong>
                                </small>
                                <small class="text-muted" t-if="history.general_info.product_code">
                                    <i class="fa fa-tag me-1"></i>
                                    Código: <strong t-esc="history.general_info.product_code"></strong>
                                </small>
                            </div>
                        </div>
                        <div class="col-md-6 text-end">
                            <div class="mb-2">
                                <span class="badge bg-light text-dark border fs-6 px-3 py-2">
                                    <i class="fa fa-calendar me-1"></i>
                                    <t t-esc="history.statistics.dias_en_inventario"/> días en inventario
                                </span>
                            </div>
                            <div>
                                <span class="badge bg-secondary fs-6 px-3 py-2">
                                    Estado: <strong t-esc="history.general_info.estado_actual"></strong>
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Navegación por pestañas -->
                <ul class="nav nav-tabs mb-3" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('general') }"
                            t-on-click="() => this.switchTab('general')"
                            type="button"
                        >
                            <i class="fa fa-info-circle me-2"></i>
                            General
                            <span class="badge bg-secondary ms-2">1</span>
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('purchase') }"
                            t-on-click="() => this.switchTab('purchase')"
                            type="button"
                        >
                            <i class="fa fa-shopping-cart me-2"></i>
                            Compras
                            <span class="badge bg-secondary ms-2" t-esc="history.purchase_info.length"></span>
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('movements') }"
                            t-on-click="() => this.switchTab('movements')"
                            type="button"
                        >
                            <i class="fa fa-exchange me-2"></i>
                            Movimientos
                            <span class="badge bg-secondary ms-2" t-esc="history.statistics.total_movimientos"></span>
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('sales') }"
                            t-on-click="() => this.switchTab('sales')"
                            type="button"
                        >
                            <i class="fa fa-usd me-2"></i>
                            Ventas
                            <span class="badge bg-secondary ms-2" t-esc="history.sales_orders.length"></span>
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('reservations') }"
                            t-on-click="() => this.switchTab('reservations')"
                            type="button"
                        >
                            <i class="fa fa-hand-paper-o me-2"></i>
                            Apartados
                            <span class="badge bg-secondary ms-2" t-esc="history.reservations.length"></span>
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button 
                            class="nav-link"
                            t-att-class="{ active: isActiveTab('deliveries') }"
                            t-on-click="() => this.switchTab('deliveries')"
                            type="button"
                        >
                            <i class="fa fa-truck me-2"></i>
                            Entregas
                            <span class="badge bg-secondary ms-2" t-esc="history.deliveries.length"></span>
                        </button>
                    </li>
                </ul>

                <!-- Contenido de las pestañas -->
                <div class="tab-content flex-grow-1 overflow-auto">
                    
                    <!-- PESTAÑA: GENERAL -->
                    <div t-if="isActiveTab('general')" class="tab-pane fade show active">
                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="card h-100 border">
                                    <div class="card-header bg-light border-bottom">
                                        <h6 class="mb-0">
                                            <i class="fa fa-info-circle me-2"></i>
                                            Información Básica
                                        </h6>
                                    </div>
                                    <div class="card-body">
                                        <table class="table table-sm">
                                            <tr>
                                                <td class="fw-bold">Fecha de creación:</td>
                                                <td t-esc="history.general_info.fecha_creacion"></td>
                                            </tr>
                                            <tr>
                                                <td class="fw-bold">Estado actual:</td>
                                                <td>
                                                    <span class="badge bg-secondary" t-esc="history.general_info.estado_actual"></span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="fw-bold">Ubicación actual:</td>
                                                <td t-esc="history.general_info.ubicacion_actual"></td>
                                            </tr>
                                            <tr>
                                                <td class="fw-bold">Días en inventario:</td>
                                                <td t-esc="history.statistics.dias_en_inventario"></td>
                                            </tr>
                                        </table>
                                    </div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="card h-100 border">
                                    <div class="card-header bg-light border-bottom">
                                        <h6 class="mb-0">
                                            <i class="fa fa-cubes me-2"></i>
                                            Cantidades (m²)
                                        </h6>
                                    </div>
                                    <div class="card-body">
                                        <table class="table table-sm">
                                            <tr>
                                                <td class="fw-bold">Cantidad actual:</td>
                                                <td class="text-end">
                                                    <span class="badge bg-light text-dark border fs-6" t-esc="formatNumber(history.general_info.cantidad_actual)"></span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="fw-bold">Cantidad reservada:</td>
                                                <td class="text-end">
                                                    <span class="badge bg-light text-dark border fs-6" t-esc="formatNumber(history.general_info.cantidad_reservada)"></span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="fw-bold">Cantidad disponible:</td>
                                                <td class="text-end">
                                                    <span class="badge bg-secondary fs-6" t-esc="formatNumber(history.general_info.cantidad_disponible)"></span>
                                                </td>
                                            </tr>
                                        </table>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12">
                                <div class="card border">
                                    <div class="card-header bg-light border-bottom">
                                        <h6 class="mb-0">
                                            <i class="fa fa-bar-chart me-2"></i>
                                            Estadísticas Generales
                                        </h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row g-3 text-center">
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_movimientos"></h3>
                                                    <small class="text-muted">Movimientos</small>
                                                </div>
                                            </div>
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_entradas"></h3>
                                                    <small class="text-muted">Entradas</small>
                                                </div>
                                            </div>
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_salidas"></h3>
                                                    <small class="text-muted">Salidas</small>
                                                </div>
                                            </div>
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_ventas"></h3>
                                                    <small class="text-muted">Ventas</small>
                                                </div>
                                            </div>
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_apartados"></h3>
                                                    <small class="text-muted">Apartados</small>
                                                </div>
                                            </div>
                                            <div class="col-md-2">
                                                <div class="p-3 bg-light rounded border">
                                                    <h3 class="text-secondary mb-1" t-esc="history.statistics.total_entregas"></h3>
                                                    <small class="text-muted">Entregas</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- PESTAÑA: COMPRAS -->
                    <div t-if="isActiveTab('purchase')" class="tab-pane fade show active">
                        <t t-if="history.purchase_info.length === 0">
                            <div class="text-center py-5">
                                <i class="fa fa-shopping-cart" style="font-size: 64px; color: #ccc;"></i>
                                <p class="text-muted mt-3">No hay información de compras para este lote</p>
                            </div>
                        </t>
                        <t t-else="">
                            <t t-foreach="history.purchase_info" t-as="purchase" t-key="purchase_index">
                                <div class="card mb-3 border">
                                    <div class="card-header bg-light border-bottom">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <h6 class="mb-0">
                                                <i class="fa fa-file-text-o me-2"></i>
                                                <t t-esc="purchase.orden_compra"/>
                                            </h6>
                                            <span class="badge bg-secondary" t-esc="purchase.estado"></span>
                                        </div>
                                    </div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <p class="mb-2">
                                                    <strong>Proveedor:</strong> <t t-esc="purchase.proveedor"/>
                                                </p>
                                                <p class="mb-2">
                                                    <strong>Fecha de orden:</strong> <t t-esc="purchase.fecha_orden"/>
                                                </p>
                                            </div>
                                            <div class="col-md-6 text-end">
                                                <p class="mb-2">
                                                    <strong>Cantidad:</strong> <t t-esc="formatNumber(purchase.cantidad)"/> m²
                                                </p>
                                                <p class="mb-2">
                                                    <strong>Precio unitario:</strong> <t t-esc="formatCurrency(purchase.precio_unitario, purchase.moneda)"/>
                                                </p>
                                                <p class="mb-0">
                                                    <strong>Total:</strong> 
                                                    <span class="fs-5 text-dark fw-bold">
                                                        <t t-esc="formatCurrency(purchase.total, purchase.moneda)"/>
                                                    </span>
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </t>
                        </t>
                    </div>

                    <!-- PESTAÑA: MOVIMIENTOS -->
                    <div t-if="isActiveTab('movements')" class="tab-pane fade show active">
                        <t t-if="history.movements.length === 0">
                            <div class="text-center py-5">
                                <i class="fa fa-exchange" style="font-size: 64px; color: #ccc;"></i>
                                <p class="text-muted mt-3">No hay movimientos registrados</p>
                            </div>
                        </t>
                        <t t-else="">
                            <div class="table-responsive">
                                <table class="table table-hover border">
                                    <thead class="table-light">
                                        <tr>
                                            <th>Fecha</th>
                                            <th>Tipo</th>
                                            <th>Origen</th>
                                            <th>Destino</th>
                                            <th class="text-end">Cantidad</th>
                                            <th>Referencia</th>
                                            <th>Usuario</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-foreach="history.movements" t-as="movement" t-key="movement_index">
                                            <tr>
                                                <td>
                                                    <small t-esc="movement.fecha"></small>
                                                </td>
                                                <td>
                                                    <span class="badge bg-secondary">
                                                        <i class="fa" t-att-class="movement.icon"></i>
                                                        <t t-esc="movement.tipo"/>
                                                    </span>
                                                </td>
                                                <td>
                                                    <small t-esc="movement.origen"></small>
                                                </td>
                                                <td>
                                                    <small t-esc="movement.destino"></small>
                                                </td>
                                                <td class="text-end">
                                                    <strong t-esc="formatNumber(movement.cantidad)"></strong>
                                                </td>
                                                <td>
                                                    <small t-esc="movement.referencia"></small>
                                                </td>
                                                <td>
                                                    <small t-esc="movement.usuario"></small>
                                                </td>
                                            </tr>
                                        </t>
                                    </tbody>
                                </table>
                            </div>
                        </t>
                    </div>

                    <!-- PESTAÑA: VENTAS -->
                    <div t-if="isActiveTab('sales')" class="tab-pane fade show active">
                        <t t-if="history.sales_orders.length === 0">
                            <div class="text-center py-5">
                                <i class="fa fa-usd" style="font-size: 64px; color: #ccc;"></i>
                                <p class="text-muted mt-3">No hay órdenes de venta para este lote</p>
                            </div>
                        </t>
                        <t t-else="">
                            <t t-foreach="history.sales_orders" t-as="sale" t-key="sale_index">
                                <div class="card mb-3 border">
                                    <div class="card-header bg-light border-bottom">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <h6 class="mb-0">
                                                <i class="fa fa-file-text-o me-2"></i>
                                                <t t-esc="sale.orden_venta"/>
                                            </h6>
                                            <span class="badge bg-secondary" t-esc="sale.estado"></span>
                                        </div>
                                    </div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <p class="mb-2">
                                                    <strong>Cliente:</strong> <t t-esc="sale.cliente"/>
                                                </p>
                                                <p class="mb-2">
                                                    <strong>Vendedor:</strong> <t t-esc="sale.vendedor"/>
                                                </p>
                                                <p class="mb-2">
                                                    <strong>Fecha de orden:</strong> <t t-esc="sale.fecha_orden"/>
                                                </p>
                                            </div>
                                            <div class="col-md-6 text-end">
                                                <p class="mb-2">
                                                    <strong>Cantidad:</strong> <t t-esc="formatNumber(sale.cantidad)"/> m²
                                                </p>
                                                <p class="mb-2">
                                                    <strong>Precio unitario:</strong> <t t-esc="formatCurrency(sale.precio_unitario, sale.moneda)"/>
                                                </p>
                                                <p class="mb-0">
                                                    <strong>Total:</strong> 
                                                    <span class="fs-5 text-dark fw-bold">
                                                        <t t-esc="formatCurrency(sale.total, sale.moneda)"/>
                                                    </span>
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </t>
                        </t>
                    </div>

                    <!-- PESTAÑA: APARTADOS/RESERVAS -->
                    <div t-if="isActiveTab('reservations')" class="tab-pane fade show active">
                        <t t-if="history.reservations.length === 0">
                            <div class="text-center py-5">
                                <i class="fa fa-hand-paper-o" style="font-size: 64px; color: #ccc;"></i>
                                <p class="text-muted mt-3">No hay apartados o reservas</p>
                            </div>
                        </t>
                        <t t-else="">
                            <t t-foreach="history.reservations" t-as="reservation" t-key="reservation_index">
                                <div class="card mb-3 border">
                                    <div class="card-header bg-light border-bottom">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <h6 class="mb-0">
                                                <i class="fa fa-hand-paper-o me-2"></i>
                                                <t t-esc="reservation.tipo"/>
                                            </h6>
                                            <span class="badge bg-secondary" t-esc="reservation.estado"></span>
                                        </div>
                                    </div>
                                    <div class="card-body">
                                        <p class="mb-2">
                                            <strong>Cliente/Partner:</strong> <t t-esc="reservation.partner"/>
                                        </p>
                                        <div class="row">
                                            <div class="col-md-6">
                                                <p class="mb-2">
                                                    <strong>Fecha inicio:</strong> <t t-esc="reservation.fecha_inicio"/>
                                                </p>
                                            </div>
                                            <div class="col-md-6">
                                                <p class="mb-2">
                                                    <strong>Fecha expiración:</strong> <t t-esc="reservation.fecha_expiracion"/>
                                                </p>
                                            </div>
                                        </div>
                                        <t t-if="reservation.notas">
                                            <hr/>
                                            <p class="mb-0">
                                                <strong>Notas:</strong><br/>
                                                <t t-esc="reservation.notas"/>
                                            </p>
                                        </t>
                                    </div>
                                </div>
                            </t>
                        </t>
                    </div>

                    <!-- PESTAÑA: ENTREGAS -->
                    <div t-if="isActiveTab('deliveries')" class="tab-pane fade show active">
                        <t t-if="history.deliveries.length === 0">
                            <div class="text-center py-5">
                                <i class="fa fa-truck" style="font-size: 64px; color: #ccc;"></i>
                                <p class="text-muted mt-3">No hay entregas registradas</p>
                            </div>
                        </t>
                        <t t-else="">
                            <div class="table-responsive">
                                <table class="table table-hover border">
                                    <thead class="table-light">
                                        <tr>
                                            <th>Referencia</th>
                                            <th>Cliente</th>
                                            <th>Fecha Programada</th>
                                            <th>Fecha Efectiva</th>
                                            <th class="text-end">Cantidad</th>
                                            <th>Origen</th>
                                            <th>Estado</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-foreach="history.deliveries" t-as="delivery" t-key="delivery_index">
                                            <tr>
                                                <td>
                                                    <strong t-esc="delivery.referencia"></strong>
                                                </td>
                                                <td>
                                                    <t t-esc="delivery.cliente"/>
                                                </td>
                                                <td>
                                                    <small t-esc="delivery.fecha_programada"></small>
                                                </td>
                                                <td>
                                                    <small t-esc="delivery.fecha_efectiva"></small>
                                                </td>
                                                <td class="text-end">
                                                    <strong t-esc="formatNumber(delivery.cantidad)"></strong>
                                                </td>
                                                <td>
                                                    <small t-esc="delivery.origen"></small>
                                                </td>
                                                <td>
                                                    <span class="badge bg-secondary" t-esc="delivery.estado"></span>
                                                </td>
                                            </tr>
                                        </t>
                                    </tbody>
                                </table>
                            </div>
                        </t>
                    </div>

                </div>
            </div>

            <t t-set-slot="footer">
                <button class="btn btn-secondary btn-lg" t-on-click="props.close">
                    <i class="fa fa-times me-2"></i>
                    Cerrar
                </button>
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/dialogs/hold/hold_dialog.js
```js
/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class CreateHoldDialog extends Component {
    setup() {
        this.detailData = this.props.detailData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            // Cliente
            searchPartnerTerm: '',
            partners: [],
            selectedPartnerId: null,
            selectedPartnerName: '',
            showCreatePartner: false,
            newPartnerName: '',
            newPartnerVat: '',
            newPartnerRef: '',
            
            // Proyecto
            searchProjectTerm: '',
            projects: [],
            selectedProjectId: null,
            selectedProjectName: '',
            showCreateProject: false,
            newProjectName: '',
            
            // Arquitecto
            searchArchitectTerm: '',
            architects: [],
            selectedArchitectId: null,
            selectedArchitectName: '',
            showCreateArchitect: false,
            newArchitectName: '',
            newArchitectVat: '',
            newArchitectRef: '',
            
            // Vendedor
            sellerName: '',
            
            // Precios
            selectedCurrency: 'USD',
            pricelists: [],
            selectedPricelistId: null,
            productPrice: 0,
            productPriceOptions: [],
            
            // Notas
            notas: '',
            
            // UI
            isCreating: false,
            currentStep: 1,
        });
        
        this.searchTimeout = null;
        
        onWillStart(async () => {
            await this.loadCurrentUser();
            await this.loadPricelists();
        });
    }
    
    async loadCurrentUser() {
        try {
            const userInfo = await this.orm.call(
                "stock.quant",
                "get_current_user_info",
                []
            );
            
            this.state.sellerName = userInfo.name;
        } catch (error) {
            console.error("Error al cargar usuario:", error);
            this.state.sellerName = 'Usuario actual';
        }
    }
    
    async loadPricelists() {
        try {
            const pricelists = await this.orm.searchRead(
                "product.pricelist",
                [['name', 'in', ['USD', 'MXN']]],
                ['id', 'name', 'currency_id']
            );
            this.state.pricelists = pricelists;
            
            const usd = pricelists.find(p => p.name === 'USD');
            if (usd) {
                this.state.selectedPricelistId = usd.id;
                this.state.selectedCurrency = 'USD';
            }
            
            await this.loadProductPrices();
        } catch (error) {
            console.error("Error cargando listas de precios:", error);
            this.notification.add("Error al cargar listas de precios", { type: "warning" });
        }
    }
    
    async loadProductPrices() {
        if (!this.detailData.product_id) return;
        
        try {
            const prices = await this.orm.call(
                "product.template",
                "get_custom_prices",
                [],
                {
                    product_id: this.detailData.product_id,
                    currency_code: this.state.selectedCurrency
                }
            );
            
            this.state.productPriceOptions = prices;
            
            if (prices.length > 0 && !this.state.productPrice) {
                this.state.productPrice = prices[0].value;
            }
        } catch (error) {
            console.error("Error cargando precios del producto:", error);
        }
    }
    
    async onCurrencyChange(ev) {
        const pricelistName = ev.target.value;
        this.state.selectedCurrency = pricelistName;
        
        const pricelist = this.state.pricelists.find(p => p.name === pricelistName);
        if (pricelist) {
            this.state.selectedPricelistId = pricelist.id;
        }
        
        await this.loadProductPrices();
    }
    
    onPriceChange(value) {
        const numValue = parseFloat(value);
        const options = this.state.productPriceOptions || [];
        
        if (options.length === 0) {
            this.state.productPrice = numValue;
            return;
        }
        
        const minPrice = Math.min(...options.map(opt => opt.value));
        
        if (numValue < minPrice) {
            this.notification.add(
                `El precio no puede ser menor a ${this.formatNumber(minPrice)}`,
                { type: "warning" }
            );
            this.state.productPrice = minPrice;
        } else {
            this.state.productPrice = numValue;
        }
    }
    
    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }
    
    // ========== CLIENTE ==========
    
    onSearchPartner(ev) {
        const value = ev.target.value;
        this.state.searchPartnerTerm = value;
        
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        this.searchTimeout = setTimeout(() => {
            this.searchPartners();
        }, 300);
    }
    
    async searchPartners() {
        try {
            const partners = await this.orm.call(
                "stock.quant",
                "search_partners",
                [],
                {
                    name: this.state.searchPartnerTerm.trim()
                }
            );
            
            this.state.partners = partners;
        } catch (error) {
            console.error("Error buscando clientes:", error);
            this.notification.add("Error al buscar clientes", { type: "danger" });
        }
    }
    
    selectPartner(partner) {
        this.state.selectedPartnerId = partner.id;
        this.state.selectedPartnerName = partner.display_name;
        this.state.showCreatePartner = false;
    }
    
    toggleCreatePartner() {
        this.state.showCreatePartner = !this.state.showCreatePartner;
        if (this.state.showCreatePartner) {
            this.state.selectedPartnerId = null;
            this.state.selectedPartnerName = '';
        }
    }
    
    async createPartner() {
        if (!this.state.newPartnerName.trim()) {
            this.notification.add("El nombre del cliente es requerido", { type: "warning" });
            return;
        }
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "create_partner",
                [],
                {
                    name: this.state.newPartnerName.trim(),
                    vat: this.state.newPartnerVat.trim(),
                    ref: this.state.newPartnerRef.trim()
                }
            );
            
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result.success) {
                this.selectPartner(result.partner);
                this.notification.add(`Cliente "${result.partner.name}" creado exitosamente`, { type: "success" });
                this.state.newPartnerName = '';
                this.state.newPartnerVat = '';
                this.state.newPartnerRef = '';
            }
        } catch (error) {
            console.error("Error creando cliente:", error);
            this.notification.add("Error al crear cliente", { type: "danger" });
        }
    }
    
    // ========== PROYECTO ==========
    
    onSearchProject(ev) {
        const value = ev.target.value;
        this.state.searchProjectTerm = value;
        
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        this.searchTimeout = setTimeout(() => {
            this.searchProjects();
        }, 300);
    }
    
    async searchProjects() {
        try {
            const projects = await this.orm.call(
                "stock.quant",
                "get_projects",
                [],
                {
                    search_term: this.state.searchProjectTerm.trim()
                }
            );
            
            this.state.projects = projects;
        } catch (error) {
            console.error("Error buscando proyectos:", error);
            this.notification.add("Error al buscar proyectos", { type: "danger" });
        }
    }
    
    selectProject(project) {
        this.state.selectedProjectId = project.id;
        this.state.selectedProjectName = project.name;
        this.state.showCreateProject = false;
    }
    
    toggleCreateProject() {
        this.state.showCreateProject = !this.state.showCreateProject;
        if (this.state.showCreateProject) {
            this.state.selectedProjectId = null;
            this.state.selectedProjectName = '';
        }
    }
    
    async createProject() {
        if (!this.state.newProjectName.trim()) {
            this.notification.add("El nombre del proyecto es requerido", { type: "warning" });
            return;
        }
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "create_project",
                [],
                {
                    name: this.state.newProjectName.trim()
                }
            );
            
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result.success) {
                this.selectProject(result.project);
                this.notification.add(`Proyecto "${result.project.name}" creado exitosamente`, { type: "success" });
                this.state.newProjectName = '';
            }
        } catch (error) {
            console.error("Error creando proyecto:", error);
            this.notification.add("Error al crear proyecto", { type: "danger" });
        }
    }
    
    // ========== ARQUITECTO ==========
    
    onSearchArchitect(ev) {
        const value = ev.target.value;
        this.state.searchArchitectTerm = value;
        
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        this.searchTimeout = setTimeout(() => {
            this.searchArchitects();
        }, 300);
    }
    
    async searchArchitects() {
        try {
            const architects = await this.orm.call(
                "stock.quant",
                "get_architects",
                [],
                {
                    search_term: this.state.searchArchitectTerm.trim()
                }
            );
            
            this.state.architects = architects;
        } catch (error) {
            console.error("Error buscando arquitectos:", error);
            this.notification.add("Error al buscar arquitectos", { type: "danger" });
        }
    }
    
    selectArchitect(architect) {
        this.state.selectedArchitectId = architect.id;
        this.state.selectedArchitectName = architect.display_name;
        this.state.showCreateArchitect = false;
    }
    
    toggleCreateArchitect() {
        this.state.showCreateArchitect = !this.state.showCreateArchitect;
        if (this.state.showCreateArchitect) {
            this.state.selectedArchitectId = null;
            this.state.selectedArchitectName = '';
        }
    }
    
    async createArchitect() {
        if (!this.state.newArchitectName.trim()) {
            this.notification.add("El nombre del arquitecto es requerido", { type: "warning" });
            return;
        }
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "create_architect",
                [],
                {
                    name: this.state.newArchitectName.trim(),
                    vat: this.state.newArchitectVat.trim(),
                    ref: this.state.newArchitectRef.trim()
                }
            );
            
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result.success) {
                this.selectArchitect(result.architect);
                this.notification.add(`Arquitecto "${result.architect.name}" creado exitosamente`, { type: "success" });
                this.state.newArchitectName = '';
                this.state.newArchitectVat = '';
                this.state.newArchitectRef = '';
            }
        } catch (error) {
            console.error("Error creando arquitecto:", error);
            this.notification.add("Error al crear arquitecto", { type: "danger" });
        }
    }
    
    // ========== NOTAS ==========
    
    onNotasChange(ev) {
        this.state.notas = ev.target.value;
    }
    
    // ========== NAVEGACIÓN ==========
    
    nextStep() {
        if (this.state.currentStep === 1 && !this.state.selectedPartnerId) {
            this.notification.add("Debe seleccionar o crear un cliente", { type: "warning" });
            return;
        }
        if (this.state.currentStep === 2 && !this.state.selectedProjectId) {
            this.notification.add("Debe seleccionar o crear un proyecto", { type: "warning" });
            return;
        }
        if (this.state.currentStep === 3 && !this.state.selectedArchitectId) {
            this.notification.add("Debe seleccionar o crear un arquitecto", { type: "warning" });
            return;
        }
        if (this.state.currentStep === 4) {
            if (!this.state.productPrice || this.state.productPrice <= 0) {
                this.notification.add("Debe configurar un precio válido", { type: "warning" });
                return;
            }
        }
        
        if (this.state.currentStep < 5) {
            this.state.currentStep++;
        }
    }
    
    prevStep() {
        if (this.state.currentStep > 1) {
            this.state.currentStep--;
        }
    }
    
    // ========== CREAR HOLD ==========
    
    async createHold() {
        if (!this.state.selectedPartnerId || !this.state.selectedProjectId || !this.state.selectedArchitectId) {
            this.notification.add("Faltan datos requeridos", { type: "warning" });
            return;
        }
        
        this.state.isCreating = true;
        
        try {
            const productPrices = {};
            if (this.state.productPrice > 0 && this.detailData.product_id) {
                productPrices[this.detailData.product_id] = parseFloat(this.state.productPrice);
            }
            
            const result = await this.orm.call(
                "stock.quant",
                "create_lot_hold_enhanced",
                [],
                {
                    quant_id: this.detailId,
                    partner_id: this.state.selectedPartnerId,
                    project_id: this.state.selectedProjectId,
                    architect_id: this.state.selectedArchitectId,
                    notas: this.state.notas,
                    currency_code: this.state.selectedCurrency,
                    product_prices: Object.keys(productPrices).length > 0 ? productPrices : null
                }
            );
            
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result.success) {
                this.notification.add(result.message, { type: "success" });
                this.props.close();
                
                if (this.props.onReload) {
                    await this.props.onReload();
                }
            }
        } catch (error) {
            console.error("Error creando apartado:", error);
            this.notification.add("Error al crear apartado", { type: "danger" });
        } finally {
            this.state.isCreating = false;
        }
    }
}

CreateHoldDialog.template = "inventory_visual_enhanced.CreateHoldDialog";
CreateHoldDialog.components = { Dialog };```

## ./static/src/components/dialogs/hold/hold_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.CreateHoldDialog" owl="1">
        <Dialog size="'lg'">
            <div class="o_create_hold_dialog">
                <!-- Header con información del producto -->
                <div class="alert alert-light border-start border-4 border-secondary mb-4">
                    <div class="d-flex align-items-center">
                        <i class="fa fa-cube fa-2x text-secondary me-3"></i>
                        <div>
                            <h5 class="mb-1 fw-bold">
                                <t t-esc="detailData.product_name"/>
                            </h5>
                            <small class="text-muted">
                                <i class="fa fa-barcode me-1"></i>
                                Lote: <strong t-esc="detailData.lot_name"></strong>
                            </small>
                        </div>
                    </div>
                </div>
                
                <!-- Indicador de pasos -->
                <div class="steps-indicator mb-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="step-item" t-att-class="{ active: state.currentStep >= 1, completed: state.currentStep > 1 }">
                            <div class="step-number">1</div>
                            <div class="step-label">Cliente</div>
                        </div>
                        <div class="step-line" t-att-class="{ active: state.currentStep > 1 }"></div>
                        <div class="step-item" t-att-class="{ active: state.currentStep >= 2, completed: state.currentStep > 2 }">
                            <div class="step-number">2</div>
                            <div class="step-label">Proyecto</div>
                        </div>
                        <div class="step-line" t-att-class="{ active: state.currentStep > 2 }"></div>
                        <div class="step-item" t-att-class="{ active: state.currentStep >= 3, completed: state.currentStep > 3 }">
                            <div class="step-number">3</div>
                            <div class="step-label">Arquitecto</div>
                        </div>
                        <div class="step-line" t-att-class="{ active: state.currentStep > 3 }"></div>
                        <div class="step-item" t-att-class="{ active: state.currentStep >= 4, completed: state.currentStep > 4 }">
                            <div class="step-number">4</div>
                            <div class="step-label">Precios</div>
                        </div>
                        <div class="step-line" t-att-class="{ active: state.currentStep > 4 }"></div>
                        <div class="step-item" t-att-class="{ active: state.currentStep >= 5 }">
                            <div class="step-number">5</div>
                            <div class="step-label">Confirmar</div>
                        </div>
                    </div>
                </div>
                
                <!-- PASO 1: CLIENTE -->
                <div class="step-content" t-if="state.currentStep === 1">
                    <h5 class="mb-3">
                        <i class="fa fa-user text-secondary me-2"></i>
                        Seleccionar Cliente
                    </h5>
                    
                    <!-- Toggle: Seleccionar o Crear -->
                    <div class="btn-group w-100 mb-3" role="group">
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="!state.showCreatePartner ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="() => this.state.showCreatePartner = false"
                        >
                            <i class="fa fa-search me-2"></i>
                            Buscar Existente
                        </button>
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="state.showCreatePartner ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="toggleCreatePartner"
                        >
                            <i class="fa fa-plus me-2"></i>
                            Crear Nuevo
                        </button>
                    </div>
                    
                    <!-- Buscar cliente existente -->
                    <t t-if="!state.showCreatePartner">
                        <div class="input-group mb-2">
                            <span class="input-group-text">
                                <i class="fa fa-search"></i>
                            </span>
                            <input 
                                type="text"
                                class="form-control"
                                placeholder="Buscar por nombre, RFC o referencia..."
                                t-model="state.searchPartnerTerm"
                                t-on-input="onSearchPartner"
                            />
                        </div>
                        
                        <!-- Cliente seleccionado -->
                        <div class="alert alert-light border d-flex align-items-center mb-3" t-if="state.selectedPartnerName">
                            <i class="fa fa-check-circle fa-2x text-success me-3"></i>
                            <div>
                                <strong>Cliente seleccionado:</strong><br/>
                                <t t-esc="state.selectedPartnerName"/>
                            </div>
                        </div>
                        
                        <!-- Lista de resultados -->
                        <div class="list-group" style="max-height: 300px; overflow-y: auto;" t-if="state.partners.length > 0 and !state.selectedPartnerName">
                            <t t-foreach="state.partners" t-as="partner" t-key="partner.id">
                                <button 
                                    type="button"
                                    class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                                    t-on-click="() => this.selectPartner(partner)"
                                >
                                    <div>
                                        <strong t-esc="partner.name"></strong>
                                        <small class="text-muted ms-2" t-if="partner.ref">
                                            [<t t-esc="partner.ref"/>]
                                        </small>
                                        <small class="text-muted ms-2" t-if="partner.vat">
                                            RFC: <t t-esc="partner.vat"/>
                                        </small>
                                    </div>
                                    <i class="fa fa-chevron-right text-muted"></i>
                                </button>
                            </t>
                        </div>
                    </t>
                    
                    <!-- Crear nuevo cliente -->
                    <t t-if="state.showCreatePartner">
                        <div class="card bg-light border mb-3">
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">
                                        Nombre del Cliente <span class="text-danger">*</span>
                                    </label>
                                    <input 
                                        type="text"
                                        class="form-control"
                                        placeholder="Nombre completo o razón social..."
                                        t-model="state.newPartnerName"
                                    />
                                </div>
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">RFC (opcional)</label>
                                        <input 
                                            type="text"
                                            class="form-control"
                                            placeholder="RFC..."
                                            t-model="state.newPartnerVat"
                                        />
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">Referencia (opcional)</label>
                                        <input 
                                            type="text"
                                            class="form-control"
                                            placeholder="Código de referencia..."
                                            t-model="state.newPartnerRef"
                                        />
                                    </div>
                                </div>
                                <button 
                                    class="btn btn-secondary w-100"
                                    t-on-click="createPartner"
                                >
                                    <i class="fa fa-plus-circle me-2"></i>
                                    Crear Cliente
                                </button>
                            </div>
                        </div>
                    </t>
                </div>
                
                <!-- PASO 2: PROYECTO -->
                <div class="step-content" t-if="state.currentStep === 2">
                    <h5 class="mb-3">
                        <i class="fa fa-folder text-secondary me-2"></i>
                        Seleccionar Proyecto
                    </h5>
                    
                    <!-- Toggle: Seleccionar o Crear -->
                    <div class="btn-group w-100 mb-3" role="group">
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="!state.showCreateProject ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="() => this.state.showCreateProject = false"
                        >
                            <i class="fa fa-search me-2"></i>
                            Buscar Existente
                        </button>
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="state.showCreateProject ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="toggleCreateProject"
                        >
                            <i class="fa fa-plus me-2"></i>
                            Crear Nuevo
                        </button>
                    </div>
                    
                    <!-- Buscar proyecto existente -->
                    <t t-if="!state.showCreateProject">
                        <div class="input-group mb-2">
                            <span class="input-group-text">
                                <i class="fa fa-search"></i>
                            </span>
                            <input 
                                type="text"
                                class="form-control"
                                placeholder="Buscar proyecto..."
                                t-model="state.searchProjectTerm"
                                t-on-input="onSearchProject"
                            />
                        </div>
                        
                        <!-- Proyecto seleccionado -->
                        <div class="alert alert-light border d-flex align-items-center mb-3" t-if="state.selectedProjectName">
                            <i class="fa fa-check-circle fa-2x text-success me-3"></i>
                            <div>
                                <strong>Proyecto seleccionado:</strong><br/>
                                <t t-esc="state.selectedProjectName"/>
                            </div>
                        </div>
                        
                        <!-- Lista de resultados -->
                        <div class="list-group" style="max-height: 300px; overflow-y: auto;" t-if="state.projects.length > 0 and !state.selectedProjectName">
                            <t t-foreach="state.projects" t-as="project" t-key="project.id">
                                <button 
                                    type="button"
                                    class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                                    t-on-click="() => this.selectProject(project)"
                                >
                                    <div>
                                        <strong t-esc="project.name"></strong>
                                    </div>
                                    <i class="fa fa-chevron-right text-muted"></i>
                                </button>
                            </t>
                        </div>
                    </t>
                    
                    <!-- Crear nuevo proyecto -->
                    <t t-if="state.showCreateProject">
                        <div class="card bg-light border mb-3">
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">
                                        Nombre del Proyecto <span class="text-danger">*</span>
                                    </label>
                                    <input 
                                        type="text"
                                        class="form-control"
                                        placeholder="Nombre del proyecto..."
                                        t-model="state.newProjectName"
                                    />
                                </div>
                                <button 
                                    class="btn btn-secondary w-100"
                                    t-on-click="createProject"
                                >
                                    <i class="fa fa-plus-circle me-2"></i>
                                    Crear Proyecto
                                </button>
                            </div>
                        </div>
                    </t>
                </div>
                
                <!-- PASO 3: ARQUITECTO -->
                <div class="step-content" t-if="state.currentStep === 3">
                    <h5 class="mb-3">
                        <i class="fa fa-user-circle text-secondary me-2"></i>
                        Seleccionar Arquitecto
                    </h5>
                    
                    <!-- Toggle: Seleccionar o Crear -->
                    <div class="btn-group w-100 mb-3" role="group">
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="!state.showCreateArchitect ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="() => this.state.showCreateArchitect = false"
                        >
                            <i class="fa fa-search me-2"></i>
                            Buscar Existente
                        </button>
                        <button 
                            type="button" 
                            class="btn"
                            t-att-class="state.showCreateArchitect ? 'btn-secondary' : 'btn-outline-secondary'"
                            t-on-click="toggleCreateArchitect"
                        >
                            <i class="fa fa-plus me-2"></i>
                            Crear Nuevo
                        </button>
                    </div>
                    
                    <!-- Buscar arquitecto existente -->
                    <t t-if="!state.showCreateArchitect">
                        <div class="input-group mb-2">
                            <span class="input-group-text">
                                <i class="fa fa-search"></i>
                            </span>
                            <input 
                                type="text"
                                class="form-control"
                                placeholder="Buscar arquitecto..."
                                t-model="state.searchArchitectTerm"
                                t-on-input="onSearchArchitect"
                            />
                        </div>
                        
                        <!-- Arquitecto seleccionado -->
                        <div class="alert alert-light border d-flex align-items-center mb-3" t-if="state.selectedArchitectName">
                            <i class="fa fa-check-circle fa-2x text-success me-3"></i>
                            <div>
                                <strong>Arquitecto seleccionado:</strong><br/>
                                <t t-esc="state.selectedArchitectName"/>
                            </div>
                        </div>
                        
                        <!-- Lista de resultados -->
                        <div class="list-group" style="max-height: 300px; overflow-y: auto;" t-if="state.architects.length > 0 and !state.selectedArchitectName">
                            <t t-foreach="state.architects" t-as="architect" t-key="architect.id">
                                <button 
                                    type="button"
                                    class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                                    t-on-click="() => this.selectArchitect(architect)"
                                >
                                    <div>
                                        <strong t-esc="architect.name"></strong>
                                        <small class="text-muted ms-2" t-if="architect.ref">
                                            [<t t-esc="architect.ref"/>]
                                        </small>
                                        <small class="text-muted ms-2" t-if="architect.vat">
                                            RFC: <t t-esc="architect.vat"/>
                                        </small>
                                    </div>
                                    <i class="fa fa-chevron-right text-muted"></i>
                                </button>
                            </t>
                        </div>
                    </t>
                    
                    <!-- Crear nuevo arquitecto -->
                    <t t-if="state.showCreateArchitect">
                        <div class="card bg-light border mb-3">
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">
                                        Nombre del Arquitecto <span class="text-danger">*</span>
                                    </label>
                                    <input 
                                        type="text"
                                        class="form-control"
                                        placeholder="Nombre completo..."
                                        t-model="state.newArchitectName"
                                    />
                                </div>
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">RFC (opcional)</label>
                                        <input 
                                            type="text"
                                            class="form-control"
                                            placeholder="RFC..."
                                            t-model="state.newArchitectVat"
                                        />
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label class="form-label">Referencia (opcional)</label>
                                        <input 
                                            type="text"
                                            class="form-control"
                                            placeholder="Código de referencia..."
                                            t-model="state.newArchitectRef"
                                        />
                                    </div>
                                </div>
                                <button 
                                    class="btn btn-secondary w-100"
                                    t-on-click="createArchitect"
                                >
                                    <i class="fa fa-plus-circle me-2"></i>
                                    Crear Arquitecto
                                </button>
                            </div>
                        </div>
                    </t>
                </div>
                
                <!-- PASO 4: PRECIOS -->
                <div class="step-content" t-if="state.currentStep === 4">
                    <h5 class="mb-3">
                        <i class="fa fa-dollar text-secondary me-2"></i>
                        Configurar Precio
                    </h5>
                    
                    <div class="card border-secondary mb-3">
                        <div class="card-header bg-light border-bottom">
                            <h6 class="mb-0">
                                <i class="fa fa-cube me-2"></i>
                                <t t-esc="detailData.product_name"/>
                            </h6>
                        </div>
                        <div class="card-body">
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <strong>Lote:</strong>
                                    <div class="text-muted">
                                        <t t-esc="detailData.lot_name"/>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <strong>Cantidad:</strong>
                                    <div class="text-muted">
                                        <t t-esc="formatNumber(detailData.quantity)"/> m²
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label fw-bold">Divisa / Lista de Precios *</label>
                                <select class="form-select" t-model="state.selectedCurrency" t-on-change="onCurrencyChange">
                                    <option value="USD">USD - Dólares</option>
                                    <option value="MXN">MXN - Pesos</option>
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label fw-bold">Precio por m² *</label>
                                <t t-if="state.productPriceOptions and state.productPriceOptions.length > 0">
                                    <select 
                                        class="form-select mb-2"
                                        t-model.number="state.productPrice"
                                        t-on-change="(ev) => this.onPriceChange(ev.target.value)"
                                    >
                                        <t t-foreach="state.productPriceOptions" t-as="option" t-key="option_index">
                                            <option t-att-value="option.value">
                                                <t t-esc="option.label"/> - <t t-esc="formatNumber(option.value)"/>
                                            </option>
                                        </t>
                                    </select>
                                </t>
                                <input 
                                    type="number"
                                    class="form-control"
                                    placeholder="Precio personalizado"
                                    t-model.number="state.productPrice"
                                    t-on-change="(ev) => this.onPriceChange(ev.target.value)"
                                    step="0.01"
                                />
                            </div>
                            
                            <div class="alert alert-light border">
                                <strong>Total estimado:</strong>
                                <div class="h4 mb-0 text-secondary">
                                    <t t-esc="formatNumber(detailData.quantity * (state.productPrice || 0))"/>
                                    <small><t t-esc="state.selectedCurrency"/></small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- PASO 5: CONFIRMAR -->
                <div class="step-content" t-if="state.currentStep === 5">
                    <h5 class="mb-3">
                        <i class="fa fa-check-circle text-success me-2"></i>
                        Confirmar Apartado
                    </h5>
                    
                    <!-- Resumen -->
                    <div class="card border mb-3">
                        <div class="card-body">
                            <h6 class="card-title mb-3">Resumen del Apartado</h6>
                            
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <strong>Cliente:</strong><br/>
                                    <t t-esc="state.selectedPartnerName"/>
                                </div>
                                <div class="col-md-6">
                                    <strong>Proyecto:</strong><br/>
                                    <t t-esc="state.selectedProjectName"/>
                                </div>
                                <div class="col-md-6">
                                    <strong>Arquitecto:</strong><br/>
                                    <t t-esc="state.selectedArchitectName"/>
                                </div>
                                <div class="col-md-6">
                                    <strong>Vendedor:</strong><br/>
                                    <span class="badge bg-info text-dark">
                                        <i class="fa fa-user me-1"></i>
                                        <t t-esc="state.sellerName"/>
                                    </span>
                                </div>
                                <div class="col-md-6">
                                    <strong>Lote:</strong><br/>
                                    <t t-esc="detailData.lot_name"/>
                                </div>
                                <div class="col-md-6">
                                    <strong>Cantidad:</strong><br/>
                                    <t t-esc="formatNumber(detailData.quantity)"/> m²
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Resumen de Precio -->
                    <div class="card border mb-3" t-if="state.productPrice and state.productPrice > 0">
                        <div class="card-header bg-light border-bottom">
                            <h6 class="mb-0">
                                <i class="fa fa-usd text-secondary me-2"></i>
                                Precio Configurado
                            </h6>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-4">
                                    <small class="text-muted d-block">Precio/m²:</small>
                                    <strong><t t-esc="formatNumber(state.productPrice)"/> <t t-esc="state.selectedCurrency"/></strong>
                                </div>
                                <div class="col-md-4">
                                    <small class="text-muted d-block">Cantidad:</small>
                                    <strong><t t-esc="formatNumber(detailData.quantity)"/> m²</strong>
                                </div>
                                <div class="col-md-4">
                                    <small class="text-muted d-block">Total:</small>
                                    <h5 class="mb-0 text-secondary">
                                        <t t-esc="formatNumber(detailData.quantity * state.productPrice)"/> 
                                        <t t-esc="state.selectedCurrency"/>
                                    </h5>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Notas -->
                    <div class="mb-3">
                        <label class="form-label fw-bold">
                            <i class="fa fa-commenting text-secondary me-2"></i>
                            Notas adicionales (opcional)
                        </label>
                        <textarea 
                            class="form-control"
                            rows="3"
                            placeholder="Ej: Para proyecto X, Cotización #123, Condiciones especiales, etc."
                            t-model="state.notas"
                            t-on-input="onNotasChange"
                        ></textarea>
                    </div>
                    
                    <!-- Info de expiración -->
                    <div class="alert alert-light border">
                        <div class="d-flex align-items-start">
                            <i class="fa fa-clock-o fa-2x text-muted me-3"></i>
                            <div>
                                <strong class="d-block mb-1">Duración del Apartado</strong>
                                <p class="mb-0">
                                    El apartado tendrá una duración de <strong>5 días hábiles</strong> a partir de hoy.
                                    Podrás renovarlo desde la gestión de apartados si es necesario.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <t t-set-slot="footer">
                <!-- Botones de navegación -->
                <button 
                    class="btn btn-light border btn-lg"
                    t-on-click="prevStep"
                    t-if="state.currentStep > 1 and state.currentStep &lt; 5"
                >
                    <i class="fa fa-chevron-left me-2"></i>
                    Anterior
                </button>
                
                <button 
                    class="btn btn-light border btn-lg"
                    t-on-click="props.close"
                    t-if="state.currentStep === 1"
                >
                    <i class="fa fa-times me-2"></i>
                    Cancelar
                </button>
                
                <button 
                    class="btn btn-secondary btn-lg"
                    t-on-click="nextStep"
                    t-if="state.currentStep &lt; 5"
                >
                    Siguiente
                    <i class="fa fa-chevron-right ms-2"></i>
                </button>
                
                <button 
                    class="btn btn-light border btn-lg"
                    t-on-click="prevStep"
                    t-if="state.currentStep === 5"
                >
                    <i class="fa fa-chevron-left me-2"></i>
                    Anterior
                </button>
                
                <button 
                    class="btn btn-secondary btn-lg"
                    t-on-click="createHold"
                    t-if="state.currentStep === 5"
                    t-att-disabled="state.isCreating"
                >
                    <t t-if="!state.isCreating">
                        <i class="fa fa-hand-paper-o me-2"></i>
                        Crear Apartado
                    </t>
                    <t t-else="">
                        <i class="fa fa-spinner fa-spin me-2"></i>
                        Creando...
                    </t>
                </button>
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/dialogs/hold_info/hold_info_dialog.js
```js
/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class HoldInfoDialog extends Component {
    setup() {
        this.holdInfo = this.props.holdInfo;
        this.detailData = this.props.detailData;
        this.orm = useService("orm");
        this.notification = useService("notification");
    }
    
    formatDate(dateStr) {
        if (!dateStr) return '-';
        return dateStr;
    }
    
    async releaseHold() {
        // Implementar lógica para liberar hold
        this.notification.add("Funcionalidad de liberar hold en desarrollo", { type: "info" });
    }
}

HoldInfoDialog.template = "inventory_visual_enhanced.HoldInfoDialog";
HoldInfoDialog.components = { Dialog };```

## ./static/src/components/dialogs/hold_info/hold_info_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.HoldInfoDialog" owl="1">
        <Dialog size="'lg'">
            <div class="o_hold_info_dialog">
                <!-- Header con información del producto -->
                <div class="alert alert-light border-start border-4 border-warning mb-4">
                    <div class="d-flex align-items-center">
                        <i class="fa fa-hand-paper-o fa-2x text-warning me-3"></i>
                        <div>
                            <h5 class="mb-1 fw-bold">
                                <t t-esc="detailData.product_name"/>
                            </h5>
                            <small class="text-muted">
                                <i class="fa fa-barcode me-1"></i>
                                Lote: <strong t-esc="detailData.lot_name"></strong>
                            </small>
                        </div>
                    </div>
                </div>

                <!-- Estado del apartado -->
                <div class="card border-warning mb-4">
                    <div class="card-header bg-warning bg-opacity-10 border-bottom border-warning">
                        <h5 class="mb-0">
                            <i class="fa fa-info-circle me-2"></i>
                            Estado del Apartado
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row g-3">
                            <div class="col-md-12">
                                <div class="alert alert-warning mb-0">
                                    <div class="d-flex align-items-center">
                                        <i class="fa fa-exclamation-triangle fa-2x me-3"></i>
                                        <div>
                                            <strong class="d-block mb-1">Este lote está apartado actualmente</strong>
                                            <p class="mb-0 small">
                                                El material está reservado y no disponible para otros clientes hasta que se libere o expire el apartado.
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Información del apartado -->
                <div class="card border mb-4">
                    <div class="card-header bg-light border-bottom">
                        <h6 class="mb-0">
                            <i class="fa fa-user me-2"></i>
                            Detalles del Apartado
                        </h6>
                    </div>
                    <div class="card-body">
                        <table class="table table-borderless mb-0">
                            <tbody>
                                <tr>
                                    <td class="fw-bold" style="width: 40%;">Cliente:</td>
                                    <td>
                                        <span class="badge bg-light text-dark border fs-6 px-3 py-2">
                                            <i class="fa fa-user-circle me-2"></i>
                                            <t t-esc="holdInfo.partner_name"/>
                                        </span>
                                    </td>
                                </tr>
                                <tr t-if="holdInfo.proyecto_nombre">
                                    <td class="fw-bold">Proyecto:</td>
                                    <td>
                                        <i class="fa fa-folder text-secondary me-2"></i>
                                        <t t-esc="holdInfo.proyecto_nombre"/>
                                    </td>
                                </tr>
                                <tr t-if="holdInfo.arquitecto_nombre">
                                    <td class="fw-bold">Arquitecto:</td>
                                    <td>
                                        <i class="fa fa-user-circle-o text-secondary me-2"></i>
                                        <t t-esc="holdInfo.arquitecto_nombre"/>
                                    </td>
                                </tr>
                                <tr t-if="holdInfo.vendedor_nombre">
                                    <td class="fw-bold">Vendedor:</td>
                                    <td>
                                        <i class="fa fa-user text-info me-2"></i>
                                        <strong t-esc="holdInfo.vendedor_nombre"></strong>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="fw-bold">Fecha de inicio:</td>
                                    <td>
                                        <i class="fa fa-calendar-check-o text-success me-2"></i>
                                        <t t-esc="holdInfo.fecha_inicio"/>
                                    </td>
                                </tr>
                                <tr>
                                    <td class="fw-bold">Fecha de expiración:</td>
                                    <td>
                                        <i class="fa fa-calendar-times-o text-danger me-2"></i>
                                        <t t-esc="holdInfo.fecha_expiracion"/>
                                    </td>
                                </tr>
                                <tr t-if="holdInfo.notas">
                                    <td class="fw-bold align-top">Notas:</td>
                                    <td>
                                        <div class="p-3 bg-light rounded border">
                                            <t t-esc="holdInfo.notas"/>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Información del lote -->
                <div class="card border">
                    <div class="card-header bg-light border-bottom">
                        <h6 class="mb-0">
                            <i class="fa fa-cube me-2"></i>
                            Información del Lote
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="row g-3">
                            <div class="col-md-6">
                                <small class="text-muted d-block mb-1">Ubicación</small>
                                <strong>
                                    <i class="fa fa-map-marker text-secondary me-1"></i>
                                    <t t-esc="detailData.location_name"/>
                                </strong>
                            </div>
                            <div class="col-md-6">
                                <small class="text-muted d-block mb-1">Cantidad Total</small>
                                <strong class="text-secondary fs-5">
                                    <t t-esc="detailData.quantity"/> m²
                                </strong>
                            </div>
                            <div class="col-md-6" t-if="detailData.grosor or detailData.alto or detailData.ancho">
                                <small class="text-muted d-block mb-1">Dimensiones</small>
                                <strong>
                                    <t t-if="detailData.grosor"><t t-esc="detailData.grosor"/>cm × </t>
                                    <t t-if="detailData.alto"><t t-esc="detailData.alto"/>m × </t>
                                    <t t-if="detailData.ancho"><t t-esc="detailData.ancho"/>m</t>
                                </strong>
                            </div>
                            <div class="col-md-6" t-if="detailData.bloque">
                                <small class="text-muted d-block mb-1">Bloque</small>
                                <strong><t t-esc="detailData.bloque"/></strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <t t-set-slot="footer">
                <button class="btn btn-light border btn-lg" t-on-click="props.close">
                    <i class="fa fa-times me-2"></i>
                    Cerrar
                </button>
                <!-- 
                <button class="btn btn-warning btn-lg" t-on-click="releaseHold">
                    <i class="fa fa-unlock me-2"></i>
                    Liberar Apartado
                </button>
                -->
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/dialogs/notes/notes_dialog.js
```js
/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class NotesDialog extends Component {
    setup() {
        this.notesData = this.props.notesData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            notes: this.props.notesData.notes || '',
            originalNotes: this.props.notesData.notes || '',
            isSaving: false,
            isEditing: !this.props.notesData.notes
        });
    }
    
    get hasNotes() {
        return this.state.originalNotes.trim().length > 0;
    }
    
    toggleEdit() {
        this.state.isEditing = !this.state.isEditing;
        if (!this.state.isEditing) {
            this.state.notes = this.state.originalNotes;
        }
    }
    
    onNotesChange(ev) {
        this.state.notes = ev.target.value;
    }
    
    async saveNotes() {
        this.state.isSaving = true;
        
        try {
            const result = await this.orm.call(
                "stock.quant",
                "save_lot_notes",
                [],
                {
                    quant_id: this.detailId,
                    notes: this.state.notes
                }
            );
            
            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                this.props.close();
                if (this.props.onReload) {
                    await this.props.onReload();
                }
            } else {
                this.notification.add(result.error || "Error al guardar notas", { type: "danger" });
            }
        } catch (error) {
            console.error("Error al guardar notas:", error);
            this.notification.add("Error al guardar notas", { type: "danger" });
        } finally {
            this.state.isSaving = false;
        }
    }
}

NotesDialog.template = "inventory_visual_enhanced.NotesDialog";
NotesDialog.components = { Dialog };```

## ./static/src/components/dialogs/notes/notes_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.NotesDialog" owl="1">
        <Dialog size="'lg'">
            <div class="o_notes_dialog">
                <!-- Header con información del producto -->
                <div class="alert alert-light border-start border-4 border-secondary mb-4">
                    <div class="d-flex align-items-center">
                        <i class="fa fa-cube fa-2x text-secondary me-3"></i>
                        <div>
                            <h5 class="mb-1 fw-bold">
                                <t t-esc="notesData.product_name"/>
                            </h5>
                            <small class="text-muted">
                                <i class="fa fa-barcode me-1"></i>
                                Lote: <strong t-esc="notesData.lot_name"></strong>
                            </small>
                        </div>
                    </div>
                </div>
                
                <!-- MODO VISUALIZACIÓN -->
                <t t-if="hasNotes and !state.isEditing">
                    <div class="card border mb-4">
                        <div class="card-header bg-light border-bottom">
                            <h5 class="mb-0">
                                <i class="fa fa-exclamation-triangle text-muted me-2"></i>
                                <strong>Notas y Detalles Especiales</strong>
                            </h5>
                        </div>
                        <div class="card-body">
                            <div 
                                class="p-4 bg-light rounded border"
                                style="
                                    white-space: pre-wrap; 
                                    font-size: 20px; 
                                    line-height: 1.8; 
                                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                    min-height: 200px;
                                    max-height: 400px;
                                    overflow-y: auto;
                                "
                            >
                                <t t-esc="state.notes"/>
                            </div>
                        </div>
                    </div>
                    
                    <div class="text-center">
                        <button 
                            class="btn btn-secondary btn-lg px-5"
                            t-on-click="toggleEdit"
                        >
                            <i class="fa fa-edit me-2"></i>
                            Editar Notas
                        </button>
                    </div>
                </t>
                
                <!-- MODO EDICIÓN -->
                <t t-if="!hasNotes or state.isEditing">
                    <div class="mb-3">
                        <label class="form-label fw-bold fs-5 mb-3">
                            <i class="fa fa-edit text-secondary me-2"></i> 
                            <t t-if="hasNotes">Editar Notas y Detalles Especiales:</t>
                            <t t-else="">Agregar Notas y Detalles Especiales:</t>
                        </label>
                        
                        <textarea 
                            class="form-control form-control-lg border-2"
                            rows="12"
                            placeholder="Ej: 
                            - Placa con barreno
                            - Release en esquina superior
                            - Placa rota en un extremo
                            - Veta pronunciada diagonal
                            - Manchas de óxido
                            - Color irregular..."
                            t-model="state.notes"
                            t-on-input="onNotesChange"
                            style="
                                font-size: 16px; 
                                line-height: 1.8;
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            "
                        ></textarea>
                        
                        <div class="alert alert-light border mt-3 mb-0">
                            <div class="d-flex align-items-start">
                                <i class="fa fa-info-circle text-muted me-2 mt-1"></i>
                                <div>
                                    <strong class="d-block mb-2">¿Qué puedes incluir?</strong>
                                    <ul class="mb-0 ps-3">
                                        <li>Defectos físicos (roturas, barrenos, grietas)</li>
                                        <li>Características visuales (vetas, manchas, colores irregulares)</li>
                                        <li>Estado general de la placa</li>
                                        <li>Observaciones del proceso de corte</li>
                                        <li>Cualquier detalle relevante para producción o venta</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </t>
            </div>

            <t t-set-slot="footer">
                <!-- Modo visualización -->
                <t t-if="hasNotes and !state.isEditing">
                    <button class="btn btn-secondary btn-lg" t-on-click="props.close">
                        <i class="fa fa-times me-2"></i>
                        Cerrar
                    </button>
                </t>
                
                <!-- Modo edición -->
                <t t-if="!hasNotes or state.isEditing">
                    <button 
                        class="btn btn-light border btn-lg" 
                        t-on-click="hasNotes ? toggleEdit : props.close"
                    >
                        <i class="fa fa-times me-2"></i>
                        Cancelar
                    </button>
                    <button 
                        class="btn btn-secondary btn-lg"
                        t-on-click="saveNotes"
                        t-att-disabled="state.isSaving"
                    >
                        <t t-if="!state.isSaving">
                            <i class="fa fa-save me-2"></i> 
                            Guardar Notas
                        </t>
                        <t t-else="">
                            <i class="fa fa-spinner fa-spin me-2"></i> 
                            Guardando...
                        </t>
                    </button>
                </t>
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/dialogs/photo_gallery/photo_gallery_dialog.js
```js
/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class PhotoGalleryDialog extends Component {
    setup() {
        this.photosData = this.props.photosData;
        this.detailId = this.props.detailId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        this.state = useState({
            photoName: `Foto - ${this.photosData.lot_name}`,
            selectedFile: null,
            isUploading: false,
            showUploadForm: false,
            currentImageIndex: 0,
        });
    }
    
    get hasPhotos() {
        return this.photosData.photos && this.photosData.photos.length > 0;
    }
    
    get currentPhoto() {
        if (!this.hasPhotos) return null;
        return this.photosData.photos[this.state.currentImageIndex];
    }
    
    toggleUploadForm() {
        this.state.showUploadForm = !this.state.showUploadForm;
        if (!this.state.showUploadForm) {
            this.state.selectedFile = null;
            this.state.photoName = `Foto - ${this.photosData.lot_name}`;
        }
    }
    
    nextPhoto() {
        if (this.state.currentImageIndex < this.photosData.photos.length - 1) {
            this.state.currentImageIndex++;
        }
    }
    
    prevPhoto() {
        if (this.state.currentImageIndex > 0) {
            this.state.currentImageIndex--;
        }
    }
    
    onFileSelected(ev) {
        this.state.selectedFile = ev.target.files[0];
    }
    
    onPhotoNameChange(ev) {
        this.state.photoName = ev.target.value;
    }
    
    async uploadPhoto() {
        if (!this.state.selectedFile) {
            this.notification.add("Por favor selecciona una imagen", { type: "warning" });
            return;
        }
        
        this.state.isUploading = true;
        
        const reader = new FileReader();
        reader.onload = async (e) => {
            const base64Data = e.target.result.split(',')[1];
            
            try {
                const result = await this.orm.call(
                    "stock.quant",
                    "save_lot_photo",
                    [],
                    {
                        quant_id: this.detailId,
                        photo_name: this.state.photoName,
                        photo_data: base64Data,
                        sequence: 10,
                        notas: ''
                    }
                );
                
                if (result.success) {
                    this.notification.add(result.message, { type: "success" });
                    this.props.close();
                    if (this.props.onReload) {
                        await this.props.onReload();
                    }
                } else {
                    this.notification.add(result.error || "Error al subir foto", { type: "danger" });
                }
            } catch (error) {
                console.error("Error al subir foto:", error);
                this.notification.add("Error al subir foto", { type: "danger" });
            } finally {
                this.state.isUploading = false;
            }
        };
        reader.readAsDataURL(this.state.selectedFile);
    }
    
    openImageInNewTab(imageData) {
        window.open(`data:image/png;base64,${imageData}`, '_blank');
    }
}

PhotoGalleryDialog.template = "inventory_visual_enhanced.PhotoGalleryDialog";
PhotoGalleryDialog.components = { Dialog };```

## ./static/src/components/dialogs/photo_gallery/photo_gallery_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.PhotoGalleryDialog" owl="1">
        <Dialog size="'xl'" contentClass="'h-100'">
            <div class="o_photo_gallery_dialog d-flex flex-column h-100">
                
                <!-- SI HAY FOTOS: Mostrar visor grande -->
                <t t-if="hasPhotos">
                    <div class="photo-viewer-section flex-grow-1 d-flex flex-column mb-3" style="min-height: 0;">
                        <div class="position-relative flex-grow-1 d-flex flex-column" style="min-height: 0;">
                            <!-- Imagen principal grande -->
                            <div class="text-center bg-dark rounded p-2 flex-grow-1 d-flex align-items-center justify-content-center" style="min-height: 0; overflow: hidden;">
                                <img 
                                    t-att-src="`data:image/png;base64,${currentPhoto.image}`"
                                    class="img-fluid rounded shadow-lg"
                                    style="max-height: calc(100vh - 350px); max-width: 100%; object-fit: contain; cursor: pointer;"
                                    t-on-click="() => this.openImageInNewTab(currentPhoto.image)"
                                    t-att-alt="currentPhoto.name"
                                    title="Click para ver en tamaño completo"
                                />
                            </div>
                            
                            <!-- Botones de navegación -->
                            <t t-if="photosData.photos.length > 1">
                                <button 
                                    class="btn btn-light position-absolute top-50 start-0 translate-middle-y ms-3 shadow-lg"
                                    style="z-index: 10; opacity: 0.9; width: 50px; height: 50px;"
                                    t-on-click="prevPhoto"
                                    t-att-disabled="state.currentImageIndex === 0"
                                >
                                    <i class="fa fa-chevron-left fa-lg"></i>
                                </button>
                                <button 
                                    class="btn btn-light position-absolute top-50 end-0 translate-middle-y me-3 shadow-lg"
                                    style="z-index: 10; opacity: 0.9; width: 50px; height: 50px;"
                                    t-on-click="nextPhoto"
                                    t-att-disabled="state.currentImageIndex === photosData.photos.length - 1"
                                >
                                    <i class="fa fa-chevron-right fa-lg"></i>
                                </button>
                            </t>
                            
                            <!-- Contador de imágenes -->
                            <div class="position-absolute top-0 end-0 m-3">
                                <span class="badge bg-dark bg-opacity-75 px-3 py-2 fs-6">
                                    <i class="fa fa-image me-2"></i>
                                    <strong><t t-esc="state.currentImageIndex + 1"/> / <t t-esc="photosData.photos.length"/></strong>
                                </span>
                            </div>
                        </div>
                        
                        <!-- Información de la foto actual -->
                        <div class="mt-2 p-2 bg-light rounded border">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="flex-grow-1">
                                    <h6 class="mb-1">
                                        <i class="fa fa-tag text-secondary me-2"></i>
                                        <strong t-esc="currentPhoto.name"></strong>
                                    </h6>
                                    <div class="d-flex gap-3">
                                        <small class="text-muted">
                                            <i class="fa fa-calendar me-1"></i>
                                            <t t-esc="currentPhoto.fecha_captura"/>
                                        </small>
                                        <small t-if="currentPhoto.notas" class="text-muted flex-grow-1" t-esc="currentPhoto.notas"></small>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Miniaturas -->
                        <t t-if="photosData.photos.length > 1">
                            <div class="d-flex gap-2 mt-2 overflow-auto pb-2" style="max-height: 100px;">
                                <t t-foreach="photosData.photos" t-as="photo" t-key="photo.id">
                                    <div 
                                        class="border rounded p-1 flex-shrink-0"
                                        t-att-class="{ 'border-secondary border-3': photo_index === state.currentImageIndex }"
                                        t-on-click="() => this.state.currentImageIndex = photo_index"
                                        style="cursor: pointer; width: 80px; height: 80px;"
                                    >
                                        <img 
                                            t-att-src="`data:image/png;base64,${photo.image}`"
                                            class="img-fluid rounded"
                                            style="width: 100%; height: 100%; object-fit: cover;"
                                            t-att-alt="photo.name"
                                        />
                                    </div>
                                </t>
                            </div>
                        </t>
                    </div>
                    
                    <hr class="my-2"/>
                </t>
                
                <!-- SI NO HAY FOTOS -->
                <t t-if="!hasPhotos">
                    <div class="text-center py-5 mb-3">
                        <i class="fa fa-camera" style="font-size: 64px; color: #ccc;"></i>
                        <p class="text-muted mt-3 mb-0">No hay fotografías para este lote</p>
                    </div>
                    
                    <hr class="my-2"/>
                </t>

                <!-- Botón para mostrar formulario -->
                <div class="text-center mb-2">
                    <button 
                        class="btn btn-secondary"
                        t-on-click="toggleUploadForm"
                        t-if="!state.showUploadForm"
                    >
                        <i class="fa fa-plus-circle me-2"></i>
                        Agregar Nueva Fotografía
                    </button>
                    <button 
                        class="btn btn-light border"
                        t-on-click="toggleUploadForm"
                        t-if="state.showUploadForm"
                    >
                        <i class="fa fa-times me-2"></i>
                        Cancelar
                    </button>
                </div>

                <!-- Formulario para agregar foto -->
                <t t-if="state.showUploadForm">
                    <div class="card bg-light border">
                        <div class="card-body p-3">
                            <h6 class="card-title mb-3">
                                <i class="fa fa-upload text-secondary"></i>
                                Agregar Nueva Fotografía
                            </h6>
                            <div class="row g-2">
                                <div class="col-md-4">
                                    <input 
                                        type="text" 
                                        class="form-control"
                                        placeholder="Nombre de la foto"
                                        t-model="state.photoName"
                                        t-on-input="onPhotoNameChange"
                                    />
                                </div>
                                <div class="col-md-6">
                                    <input 
                                        type="file" 
                                        class="form-control"
                                        accept="image/*"
                                        t-on-change="onFileSelected"
                                    />
                                </div>
                                <div class="col-md-2">
                                    <button 
                                        type="button" 
                                        class="btn btn-secondary w-100"
                                        t-on-click="uploadPhoto"
                                        t-att-disabled="state.isUploading"
                                    >
                                        <t t-if="!state.isUploading">
                                            <i class="fa fa-upload"></i> Subir
                                        </t>
                                        <t t-else="">
                                            <i class="fa fa-spinner fa-spin"></i> Subiendo...
                                        </t>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </t>
            </div>

            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="props.close">
                    Cerrar
                </button>
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/dialogs/sale_order/sale_order_dialog.js
```js
/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class SaleOrderDialog extends Component {
    setup() {
        this.soInfo = this.props.soInfo;
        this.orm = useService("orm");
        this.notification = useService("notification");
    }
    
    formatCurrency(amount, symbol) {
        return `${symbol} ${new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(amount)}`;
    }
    
    getStateBadgeClass(state) {
        const stateClasses = {
            'draft': 'bg-secondary',
            'sent': 'bg-info',
            'sale': 'bg-success',
            'done': 'bg-dark',
            'cancel': 'bg-danger',
        };
        return stateClasses[state] || 'bg-secondary';
    }
}

SaleOrderDialog.template = "inventory_visual_enhanced.SaleOrderDialog";
SaleOrderDialog.components = { Dialog };```

## ./static/src/components/dialogs/sale_order/sale_order_dialog.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.SaleOrderDialog" owl="1">
        <Dialog size="'lg'">
            <div class="o_sale_order_dialog">
                <t t-if="soInfo.orders.length === 0">
                    <div class="text-center py-5">
                        <i class="fa fa-shopping-cart" style="font-size: 64px; color: #ccc;"></i>
                        <p class="text-muted mt-3">No hay órdenes de venta</p>
                    </div>
                </t>
                <t t-else="">
                    <t t-foreach="soInfo.orders" t-as="order" t-key="order.id">
                        <div class="card mb-3 border">
                            <div class="card-header bg-light border-bottom">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h6 class="mb-0">
                                        <i class="fa fa-file-text-o me-2"></i>
                                        <strong t-esc="order.name"></strong>
                                    </h6>
                                    <span class="badge fs-6" t-att-class="getStateBadgeClass(order.state)">
                                        <t t-esc="order.state_display"/>
                                    </span>
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <div class="mb-2">
                                            <i class="fa fa-user text-muted me-2"></i>
                                            <strong>Cliente:</strong>
                                            <span class="ms-1" t-esc="order.partner_name"></span>
                                        </div>
                                        <div class="mb-2" t-if="order.user_name">
                                            <i class="fa fa-user-circle text-muted me-2"></i>
                                            <strong>Vendedor:</strong>
                                            <span class="ms-1" t-esc="order.user_name"></span>
                                        </div>
                                        <div>
                                            <i class="fa fa-calendar text-muted me-2"></i>
                                            <strong>Fecha:</strong>
                                            <span class="ms-1" t-esc="order.date_order"></span>
                                        </div>
                                    </div>
                                    <div class="col-md-6 text-end">
                                        <div t-if="order.commitment_date" class="mb-2">
                                            <small class="text-muted">Fecha de compromiso:</small><br/>
                                            <span class="badge bg-light text-dark border" t-esc="order.commitment_date"></span>
                                        </div>
                                        <div class="mt-2">
                                            <small class="text-muted d-block">Total:</small>
                                            <h4 class="mb-0 text-dark">
                                                <t t-esc="formatCurrency(order.amount_total, order.currency_symbol)"/>
                                            </h4>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </t>
                </t>
            </div>

            <t t-set-slot="footer">
                <button class="btn btn-secondary btn-lg" t-on-click="props.close">
                    <i class="fa fa-times me-2"></i>
                    Cerrar
                </button>
            </t>
        </Dialog>
    </t>
    
</templates>```

## ./static/src/components/inventory_view/inventory_controller.js
```js
/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ProductRow } from "../product_row/product_row";
import { PhotoGalleryDialog } from "../dialogs/photo_gallery/photo_gallery_dialog";
import { NotesDialog } from "../dialogs/notes/notes_dialog";
import { HistoryDialog } from "../dialogs/history/history_dialog";
import { CreateHoldDialog } from "../dialogs/hold/hold_dialog";
import { SaleOrderDialog } from "../dialogs/sale_order/sale_order_dialog";
import { HoldInfoDialog } from "../dialogs/hold_info/hold_info_dialog";

class InventoryVisualController extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.root = useRef("root");

        this.state = useState({
            // Filtros
            filters: {
                product_name: '',
                almacen_id: null,
                ubicacion_id: null,
                tipo: '',
                categoria_id: null,
                grupo: '',
                acabado: '',
                grosor: '',
                numero_serie: '',
                bloque: '',
                pedimento: '',
                contenedor: '',
                atado: '',
            },
            
            // Opciones para dropdowns
            almacenes: [],
            ubicaciones: [],
            tipos: [],
            categorias: [],
            grupos: [],
            acabados: [],
            grosores: [],
            
            // Estado de búsqueda
            isSearching: false,
            products: [],
            expandedProducts: new Set(),
            productDetails: {},
            isLoading: false,
            hasSearched: false,
            error: null,
            totalProducts: 0,
            totalAvailable: 0,
            totalReserved: 0,
            
            // UI
            showAdvancedFilters: false,
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
        if (!this.root.el) return;
        
        const searchBar = this.root.el.querySelector('.o_inventory_visual_searchbar');
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

            // Cargar categorías
            const categorias = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name", "complete_name"],
                { order: "complete_name" }
            );
            this.state.categorias = categorias;

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
            const grosores = await this.orm.call(
                "stock.quant",
                "read_group",
                [],
                {
                    domain: [["x_grosor", "!=", false]],
                    fields: ["x_grosor"],
                    groupby: ["x_grosor"],
                }
            );
            this.state.grosores = grosores.map(g => g.x_grosor).filter(Boolean).sort();

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
        const value = ev.target.value.trim();
        this.state.filters[filterName] = value;
        this.triggerSearch();
    }

    triggerSearch() {
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }

        this.searchTimeout = setTimeout(() => {
            this.searchProducts();
        }, this.searchDelay);
    }

    toggleAdvancedFilters() {
        this.state.showAdvancedFilters = !this.state.showAdvancedFilters;
    }

    clearAllFilters() {
        this.state.filters = {
            product_name: '',
            almacen_id: null,
            ubicacion_id: null,
            tipo: '',
            categoria_id: null,
            grupo: '',
            acabado: '',
            grosor: '',
            numero_serie: '',
            bloque: '',
            pedimento: '',
            contenedor: '',
            atado: '',
        };
        this.state.ubicaciones = [];
        this.state.hasSearched = false;
        this.state.products = [];
        this.state.expandedProducts.clear();
        this.state.productDetails = {};
    }

    hasActiveFilters() {
        return Object.values(this.state.filters).some(v => v !== null && v !== '');
    }

    async searchProducts() {
        if (!this.hasActiveFilters()) {
            this.state.hasSearched = false;
            this.state.products = [];
            return;
        }

        this.state.isLoading = true;
        this.state.error = null;

        try {
            const products = await this.orm.call(
                "stock.quant",
                "get_inventory_grouped_by_product",
                [],
                {
                    filters: this.state.filters,
                }
            );

            this.state.products = products;
            this.state.hasSearched = true;
            this.state.totalProducts = products.length;
            this.calculateTotals();
            this.state.expandedProducts.clear();
            this.state.productDetails = {};

            if (products.length === 0) {
                this.notification.add(
                    "No se encontraron productos con los filtros aplicados",
                    { type: "info" }
                );
            }

        } catch (error) {
            console.error("Error al buscar productos:", error);
            this.state.error = "Error al cargar los productos. Por favor intenta nuevamente.";
            this.notification.add("Error al cargar los productos", {
                type: "danger",
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    calculateTotals() {
        let totalAvailable = 0;
        let totalHold = 0;
        let totalCommitted = 0;

        this.state.products.forEach(product => {
            totalAvailable += product.available_qty || 0;
            totalHold += product.hold_qty || 0;
            totalCommitted += product.committed_qty || 0;
        });

        this.state.totalAvailable = totalAvailable;
        this.state.totalHold = totalHold;
        this.state.totalCommitted = totalCommitted;
    }

    async toggleProduct(productId, quantIds) {
        const isExpanded = this.state.expandedProducts.has(productId);

        if (isExpanded) {
            this.state.expandedProducts.delete(productId);
        } else {
            this.state.expandedProducts.add(productId);

            if (!this.state.productDetails[productId]) {
                await this.loadProductDetails(productId, quantIds);
            }
        }

        this.state.expandedProducts = new Set(this.state.expandedProducts);
    }

    async loadProductDetails(productId, quantIds) {
        try {
            const details = await this.orm.call(
                "stock.quant",
                "get_quant_details",
                [],
                {
                    quant_ids: quantIds,
                }
            );

            this.state.productDetails[productId] = details;

        } catch (error) {
            console.error("Error al cargar detalles:", error);
            this.notification.add("Error al cargar detalles del producto", {
                type: "danger",
            });
        }
    }

    formatNumber(num) {
        if (num === null || num === undefined) return "0";
        return new Intl.NumberFormat('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    }

    isProductExpanded(productId) {
        return this.state.expandedProducts.has(productId);
    }

    getProductDetails(productId) {
        return this.state.productDetails[productId] || [];
    }

    async onPhotoClick(detailId) {
        try {
            const photos = await this.orm.call(
                "stock.quant",
                "get_lot_photos",
                [],
                {
                    quant_id: detailId
                }
            );
            
            if (photos.error) {
                this.notification.add(photos.error, { type: "warning" });
                return;
            }
            
            this.openPhotoGalleryModal(photos, detailId);
            
        } catch (error) {
            console.error("Error al cargar fotos:", error);
            this.notification.add("Error al cargar fotos", { type: "danger" });
        }
    }
    
    openPhotoGalleryModal(photosData, detailId) {
        const self = this;
        this.dialog.add(PhotoGalleryDialog, {
            photosData,
            detailId,
            onReload: async () => await self.reloadProductDetailsForDetail(detailId),
            title: `Fotografías - ${photosData.lot_name}`,
            size: 'xl',
        });
    }

    async onNotesClick(detailId) {
        try {
            const notes = await this.orm.call(
                "stock.quant",
                "get_lot_notes",
                [],
                {
                    quant_id: detailId
                }
            );
            
            if (notes.error) {
                this.notification.add(notes.error, { type: "warning" });
                return;
            }
            
            this.openNotesModal(notes, detailId);
            
        } catch (error) {
            console.error("Error al cargar notas:", error);
            this.notification.add("Error al cargar notas", { type: "danger" });
        }
    }
    
    openNotesModal(notesData, detailId) {
        const self = this;
        this.dialog.add(NotesDialog, {
            notesData,
            detailId,
            onReload: async () => await self.reloadProductDetailsForDetail(detailId),
            title: `Notas y Detalles - ${notesData.lot_name}`,
            size: 'lg',
        });
    }

    async reloadProductDetailsForDetail(detailId) {
        for (const [productId, details] of Object.entries(this.state.productDetails)) {
            const detail = details.find(d => d.id === detailId);
            if (detail) {
                const product = this.state.products.find(p => p.product_id === parseInt(productId));
                if (product) {
                    await this.loadProductDetails(parseInt(productId), product.quant_ids);
                }
                break;
            }
        }
    }

    async onDetailsClick(detailId) {
        try {
            const history = await this.orm.call(
                "stock.quant",
                "get_lot_history",
                [],
                {
                    quant_id: detailId
                }
            );
            
            if (history.error) {
                this.notification.add(history.error, { type: "warning" });
                return;
            }
            
            this.openHistoryModal(history);
            
        } catch (error) {
            console.error("Error al cargar historial:", error);
            this.notification.add("Error al cargar historial del lote", { type: "danger" });
        }
    }

    openHistoryModal(history) {
        this.dialog.add(HistoryDialog, {
            history,
            title: `Historial Detallado - ${history.general_info.lot_name}`,
            size: 'xl',
        });
    }

    onSalesPersonClick(detailId) {
        console.log('Ver cliente y vendedor:', detailId);
        this.notification.add(
            "Funcionalidad de cliente/vendedor en desarrollo",
            { type: "info" }
        );
    }

    async onHoldClick(detailId, holdInfo) {
        if (!holdInfo || !holdInfo.id) {
            await this.openCreateHoldDialog(detailId);
            return;
        }

        // Obtener detailData completo
        let detailData = null;
        for (const [productId, details] of Object.entries(this.state.productDetails)) {
            const detail = details.find(d => d.id === detailId);
            if (detail) {
                detailData = detail;
                break;
            }
        }
        
        if (!detailData) {
            this.notification.add("No se encontró información del lote", { type: "danger" });
            return;
        }

        this.openHoldInfoDialog(holdInfo, detailData);
    }

    openHoldInfoDialog(holdInfo, detailData) {
        this.dialog.add(HoldInfoDialog, {
            holdInfo,
            detailData,
            title: `Apartado Activo - ${detailData.lot_name}`,
            size: 'lg',
        });
    }

    async openCreateHoldDialog(detailId) {
        const self = this;
        
        try {
            let detailData = null;
            
            for (const [productId, details] of Object.entries(this.state.productDetails)) {
                const detail = details.find(d => d.id === detailId);
                if (detail) {
                    detailData = detail;
                    
                    // 🆕 AGREGAR: Añadir product_id al detailData
                    detailData.product_id = parseInt(productId);
                    
                    // 🆕 AGREGAR: Buscar el product_name
                    const product = this.state.products.find(p => p.product_id === parseInt(productId));
                    if (product) {
                        detailData.product_name = product.product_name;
                    }
                    
                    break;
                }
            }
            
            if (!detailData) {
                this.notification.add("No se encontró información del lote", { type: "danger" });
                return;
            }
            
            this.dialog.add(CreateHoldDialog, {
                detailData,
                detailId,
                onReload: async () => await self.reloadProductDetailsForDetail(detailId),
                title: `Crear Apartado - ${detailData.lot_name}`,
                size: 'lg',
            });
            
        } catch (error) {
            console.error("Error abriendo diálogo:", error);
            this.notification.add("Error al abrir diálogo de apartado", { type: "danger" });
        }
    }

    async onSaleOrderClick(detailId, saleOrderIds) {
        console.log('Sale order click:', detailId, saleOrderIds);
        
        if (!saleOrderIds || saleOrderIds.length === 0) {
            this.notification.add("No hay órdenes de venta asociadas", { type: "info" });
            return;
        }

        try {
            const soInfo = await this.orm.call(
                "stock.quant",
                "get_sale_order_info",
                [],
                {
                    sale_order_ids: saleOrderIds
                }
            );
            
            if (soInfo.error) {
                this.notification.add(soInfo.error, { type: "warning" });
                return;
            }
            
            this.openSaleOrderModal(soInfo);
            
        } catch (error) {
            console.error("Error al cargar info de órdenes de venta:", error);
            this.notification.add("Error al cargar información de órdenes de venta", { type: "danger" });
        }
    }

    openSaleOrderModal(soInfo) {
        this.dialog.add(SaleOrderDialog, {
            soInfo,
            title: `Órdenes de Venta (${soInfo.count})`,
            size: 'lg',
        });
    }
}

InventoryVisualController.template = "inventory_visual_enhanced.InventoryView";
InventoryVisualController.components = { ProductRow };

InventoryVisualController.props = {
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
    "*": true,
};

registry.category("actions").add("inventory_visual_enhanced", InventoryVisualController);```

## ./static/src/components/inventory_view/inventory_controller.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.InventoryView" owl="1">
        <div class="o_inventory_visual_container d-flex flex-column vh-100" t-ref="root">
            
            <!-- Barra de filtros superior -->
            <div class="o_inventory_visual_searchbar flex-shrink-0 sticky-top">
                <div class="searchbar-inner container">
                    
                    <!-- Filtros principales (siempre visibles) -->
                    <div class="filters-row main-filters">
                        <!-- Búsqueda por nombre -->
                        <div class="filter-group search-product-name">
                            <label class="filter-label">Buscar Producto</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Nombre o código del producto..."
                                t-model="state.filters.product_name"
                                t-on-input="(ev) => this.onTextFilterChange('product_name', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>

                        <!-- Almacén -->
                        <div class="filter-group">
                            <label class="filter-label">Almacén</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.almacen_id"
                                t-on-change="onAlmacenChange"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todos los almacenes</option>
                                <t t-foreach="state.almacenes" t-as="almacen" t-key="almacen.id">
                                    <option t-att-value="almacen.id" t-esc="almacen.name"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Ubicación -->
                        <div class="filter-group">
                            <label class="filter-label">Ubicación</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.ubicacion_id"
                                t-on-change="(ev) => this.onFilterChange('ubicacion_id', ev)"
                                t-att-disabled="state.isLoading or !state.filters.almacen_id or state.ubicaciones.length === 0"
                            >
                                <option value="">Todas las ubicaciones</option>
                                <t t-foreach="state.ubicaciones" t-as="ubicacion" t-key="ubicacion.id">
                                    <option t-att-value="ubicacion.id" t-esc="ubicacion.complete_name"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Tipo -->
                        <div class="filter-group">
                            <label class="filter-label">Tipo</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.tipo"
                                t-on-change="(ev) => this.onFilterChange('tipo', ev)"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todos los tipos</option>
                                <t t-foreach="state.tipos" t-as="tipo" t-key="tipo_index">
                                    <option t-att-value="tipo[0]" t-esc="tipo[1]"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Categoría -->
                        <div class="filter-group">
                            <label class="filter-label">Categoría</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.categoria_id"
                                t-on-change="(ev) => this.onFilterChange('categoria_id', ev)"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todas las categorías</option>
                                <t t-foreach="state.categorias" t-as="categoria" t-key="categoria.id">
                                    <option t-att-value="categoria.id" t-esc="categoria.complete_name"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Botones de acción -->
                        <div class="filter-actions">
                            <button 
                                class="btn btn-sm btn-light border"
                                t-on-click="toggleAdvancedFilters"
                                title="Filtros avanzados"
                            >
                                <i class="fa fa-sliders me-1"></i>
                                <t t-if="!state.showAdvancedFilters">Más filtros</t>
                                <t t-else="">Menos filtros</t>
                            </button>
                            <button 
                                class="btn btn-sm btn-light border"
                                t-on-click="clearAllFilters"
                                t-att-disabled="!hasActiveFilters()"
                                title="Limpiar todos los filtros"
                            >
                                <i class="fa fa-times"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Filtros avanzados (desplegables) -->
                    <div class="filters-row advanced-filters" t-if="state.showAdvancedFilters">
                        <!-- Grupo -->
                        <div class="filter-group">
                            <label class="filter-label">Grupo</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.grupo"
                                t-on-change="(ev) => this.onFilterChange('grupo', ev)"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todos los grupos</option>
                                <t t-foreach="state.grupos" t-as="grupo" t-key="grupo_index">
                                    <option t-att-value="grupo[0]" t-esc="grupo[1]"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Acabado -->
                        <div class="filter-group">
                            <label class="filter-label">Acabado</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.acabado"
                                t-on-change="(ev) => this.onFilterChange('acabado', ev)"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todos los acabados</option>
                                <t t-foreach="state.acabados" t-as="acabado" t-key="acabado_index">
                                    <option t-att-value="acabado[0]" t-esc="acabado[1]"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Grosor -->
                        <div class="filter-group">
                            <label class="filter-label">Grosor</label>
                            <select 
                                class="form-select filter-select"
                                t-model="state.filters.grosor"
                                t-on-change="(ev) => this.onFilterChange('grosor', ev)"
                                t-att-disabled="state.isLoading"
                            >
                                <option value="">Todos los grosores</option>
                                <t t-foreach="state.grosores" t-as="grosor" t-key="grosor">
                                    <option t-att-value="grosor" t-esc="grosor + ' cm'"></option>
                                </t>
                            </select>
                        </div>

                        <!-- Número de serie -->
                        <div class="filter-group">
                            <label class="filter-label">N° Serie</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Buscar..."
                                t-model="state.filters.numero_serie"
                                t-on-input="(ev) => this.onTextFilterChange('numero_serie', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>

                        <!-- Bloque -->
                        <div class="filter-group">
                            <label class="filter-label">Bloque</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Buscar..."
                                t-model="state.filters.bloque"
                                t-on-input="(ev) => this.onTextFilterChange('bloque', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>

                        <!-- Pedimento -->
                        <div class="filter-group">
                            <label class="filter-label">Pedimento</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Buscar..."
                                t-model="state.filters.pedimento"
                                t-on-input="(ev) => this.onTextFilterChange('pedimento', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>

                        <!-- Contenedor -->
                        <div class="filter-group">
                            <label class="filter-label">Contenedor</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Buscar..."
                                t-model="state.filters.contenedor"
                                t-on-input="(ev) => this.onTextFilterChange('contenedor', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>

                        <!-- Atado -->
                        <div class="filter-group">
                            <label class="filter-label">Atado</label>
                            <input 
                                type="text"
                                class="form-control filter-input"
                                placeholder="Buscar..."
                                t-model="state.filters.atado"
                                t-on-input="(ev) => this.onTextFilterChange('atado', ev)"
                                t-att-disabled="state.isLoading"
                            />
                        </div>
                    </div>

                    <!-- Información de resultados -->
                    <div class="filters-info" t-if="state.hasSearched">
                        <span class="results-count">
                            <strong t-esc="state.totalProducts"></strong>
                            <span t-if="state.totalProducts === 1"> producto encontrado</span>
                            <span t-else=""> productos encontrados</span>
                        </span>
                    </div>
                </div>
            </div>
            
            <!-- Contenido principal -->
            <div class="o_inventory_visual_content flex-grow-1 overflow-auto">
                
                <!-- Estado inicial -->
                <div class="o_inventory_visual_empty" t-if="!state.hasSearched and !state.isLoading">
                    <i class="fa fa-filter empty-icon"></i>
                    <h2 class="empty-title">Aplica filtros para visualizar tu inventario</h2>
                    <p class="empty-subtitle">
                        Selecciona uno o más filtros en la barra superior
                        para ver el inventario agrupado con métricas detalladas.
                    </p>
                </div>
                
                <!-- Loading -->
                <div class="o_inventory_loading" t-if="state.isLoading">
                    <div class="spinner"></div>
                    <div class="loading-text">Cargando inventario...</div>
                </div>
                
                <!-- Error -->
                <div class="o_inventory_error" t-if="state.error">
                    <i class="fa fa-exclamation-triangle error-icon"></i>
                    <div class="error-message" t-esc="state.error"></div>
                </div>
                
                <!-- Sin resultados -->
                <div class="o_inventory_no_results" t-if="state.hasSearched and state.products.length === 0 and !state.isLoading">
                    <i class="fa fa-inbox no-results-icon"></i>
                    <h3 class="no-results-title">No se encontraron productos</h3>
                    <p class="no-results-message">
                        Intenta con otros filtros o verifica el inventario disponible.
                    </p>
                </div>
                
                <!-- DATA GRID -->
                <div class="o_inventory_data_grid" t-if="state.products.length > 0 and !state.isLoading">
                    <table class="o_inventory_grid_table">
                        <thead>
                            <tr>
                                <th class="col-product-name">Product Name (SKU)</th>
                                <th class="col-inventory">Inventory</th>
                                <th class="col-type">Type</th>
                                <th class="col-category">Category</th>
                                <th class="col-actions">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <t t-foreach="state.products" t-as="product" t-key="product.product_id">
                                <ProductRow 
                                    product="product"
                                    isExpanded="isProductExpanded(product.product_id)"
                                    details="getProductDetails(product.product_id)"
                                    onToggle.bind="(quantIds) => this.toggleProduct(product.product_id, quantIds)"
                                    onPhotoClick.bind="onPhotoClick"
                                    onNotesClick.bind="onNotesClick"
                                    onDetailsClick.bind="onDetailsClick"
                                    onSalesPersonClick.bind="onSalesPersonClick"
                                    onHoldClick.bind="onHoldClick"
                                    onSaleOrderClick.bind="onSaleOrderClick"
                                    formatNumber.bind="formatNumber"
                                    isInCart.bind="isInCart"
                                    toggleCartSelection.bind="toggleCartSelection"
                                    areAllCurrentProductSelected.bind="() => this.areAllCurrentProductSelected()"
                                    selectAllCurrentProduct.bind="() => this.selectAllCurrentProduct()"
                                    deselectAllCurrentProduct.bind="() => this.deselectAllCurrentProduct()"
                                />
                            </t>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </t>
    
</templates>```

## ./static/src/components/product_details/product_details.js
```js
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
    isInCart: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};```

## ./static/src/components/product_details/product_details.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="inventory_visual_enhanced.ProductDetails" owl="1">
        <div class="details-wrapper">
            <table class="o_inventory_details_table">
                <thead>
                    <tr>
                        <th class="col-checkbox">☑</th>
                        <th class="col-lot">Lote</th>
                        <th class="col-location">Ubicación</th>
                        <th class="col-dimensions">Dimensiones</th>
                        <th class="col-tipo">Tipo</th>
                        <th class="col-bloque">Bloque</th>
                        <th class="col-atado">Atado</th>
                        <th class="col-pedimento">Pedimento</th>
                        <th class="col-contenedor">Contenedor</th>
                        <th class="col-ref-proveedor">Ref. Prov.</th>
                        <th class="col-icon">P</th>
                        <th class="col-icon">N</th>
                        <th class="col-icon">D</th>
                        <th class="col-icon">E</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="props.details" t-as="detail" t-key="detail.id">
                        <tr>
                            <!-- Checkbox -->
                            <td class="col-checkbox text-center">
                                <input 
                                    type="checkbox"
                                    class="form-check-input cart-checkbox"
                                    t-att-checked="props.isInCart(detail.id)"
                                    t-on-change="() => props.toggleCartSelection(detail)"
                                />
                            </td>
                            
                            <!-- Lote -->
                            <td class="col-lot">
                                <span t-esc="detail.lot_name"></span>
                            </td>
                            
                            <!-- Ubicación -->
                            <td class="col-location">
                                <i class="fa fa-map-marker"></i>
                                <span t-esc="detail.location_name"></span>
                            </td>
                            
                            <!-- Dimensiones -->
                            <td class="col-dimensions">
                                <span class="dimensions-inline">
                                    <t t-if="detail.alto and detail.ancho">
                                        <t t-esc="detail.alto"/>m × <t t-esc="detail.ancho"/>m
                                    </t>
                                    <t t-elif="!detail.alto and !detail.ancho">-</t>
                                    <t t-elif="detail.alto">
                                        <t t-esc="detail.alto"/>m
                                    </t>
                                    <t t-else="">
                                        <t t-esc="detail.ancho"/>m
                                    </t>
                                    <strong class="dimensions-total-inline">
                                        <t t-esc="props.formatNumber(detail.quantity)"/> m²
                                    </strong>
                                </span>
                            </td>
                            
                            <!-- Tipo -->
                            <td class="col-tipo">
                                <span t-if="detail.tipo" t-esc="detail.tipo"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Bloque -->
                            <td class="col-bloque">
                                <span t-if="detail.bloque" t-esc="detail.bloque"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Atado -->
                            <td class="col-atado">
                                <span t-if="detail.atado" t-esc="detail.atado"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Pedimento -->
                            <td class="col-pedimento">
                                <span t-if="detail.pedimento" t-esc="detail.pedimento"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Contenedor -->
                            <td class="col-contenedor">
                                <span t-if="detail.contenedor" t-esc="detail.contenedor"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Referencia Proveedor -->
                            <td class="col-ref-proveedor">
                                <span t-if="detail.referencia_proveedor" t-esc="detail.referencia_proveedor"></span>
                                <span t-else="" class="text-muted">-</span>
                            </td>
                            
                            <!-- Fotos (P) -->
                            <td class="col-icon">
                                <button 
                                    type="button"
                                    class="icon-btn"
                                    t-att-class="{ 'has-photos': detail.cantidad_fotos > 0, 'no-content': detail.cantidad_fotos === 0 }"
                                    t-on-click="() => props.onPhotoClick(detail.id)"
                                    t-att-title="detail.cantidad_fotos > 0 ? detail.cantidad_fotos + ' fotos' : 'Sin fotos'"
                                >
                                    <strong>P</strong>
                                </button>
                            </td>
                            
                            <!-- Notas (N) -->
                            <td class="col-icon">
                                <button 
                                    type="button"
                                    class="icon-btn"
                                    t-att-class="{ 'has-notes': detail.detalles_placa, 'no-content': !detail.detalles_placa }"
                                    t-on-click="() => props.onNotesClick(detail.id)"
                                    title="Notas y detalles"
                                >
                                    <strong>N</strong>
                                </button>
                            </td>
                            
                            <!-- Detalles/Historial (D) -->
                            <td class="col-icon">
                                <button 
                                    type="button"
                                    class="icon-btn has-details"
                                    t-on-click="() => props.onDetailsClick(detail.id)"
                                    title="Ver historial completo"
                                >
                                    <strong>D</strong>
                                </button>
                            </td>
                            
                            <!-- Estado (Combinado: Hold o SO) -->
                            <td class="col-icon">
                                <!-- Prioridad 1: Hold Activo -->
                                <button 
                                    t-if="detail.tiene_hold"
                                    type="button"
                                    class="status-badge-btn status-hold-active"
                                    t-on-click="() => props.onHoldClick(detail.id, detail.hold_info)"
                                    title="Apartado activo"
                                >
                                    <i class="fa fa-hand-paper-o"></i>
                                </button>
                                
                                <!-- Prioridad 2: Sale Order -->
                                <button 
                                    t-elif="detail.en_orden_venta"
                                    type="button"
                                    class="status-badge-btn status-sale-order"
                                    t-on-click="() => props.onSaleOrderClick(detail.id, detail.sale_order_ids)"
                                    t-att-title="detail.sale_order_ids.length + ' orden(es) de venta'"
                                >
                                    <strong>SO</strong>
                                </button>
                                
                                <!-- Prioridad 3: Disponible (sin estado especial) -->
                                <button 
                                    t-else=""
                                    type="button"
                                    class="status-badge-btn status-no-state"
                                    t-on-click="() => props.onHoldClick(detail.id, detail.hold_info)"
                                    title="Disponible - Click para crear apartado"
                                >
                                    <i class="fa fa-hand-paper-o"></i>
                                </button>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
            
            <div class="table-loading" t-if="props.details.length === 0">
                <div class="spinner"></div>
                <div class="loading-text">Cargando detalles...</div>
            </div>
        </div>
    </t>
</templates>```

## ./static/src/components/product_row/product_row.js
```js
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
    isInCart: { type: Function, optional: true },
    toggleCartSelection: { type: Function, optional: true },
    areAllCurrentProductSelected: { type: Function, optional: true },
    selectAllCurrentProduct: { type: Function, optional: true },
    deselectAllCurrentProduct: { type: Function, optional: true },
    cart: { type: Object, optional: true },
};```

## ./static/src/components/product_row/product_row.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    
    <t t-name="inventory_visual_enhanced.ProductRow" owl="1">
        <tr class="o_inventory_product_row" t-att-class="{ expanded: props.isExpanded }">
            
            <!-- Product Name -->
            <td class="col-product-name">
                <div class="product-name-cell">
                    <div class="product-title" t-esc="props.product.product_name"></div>
                    <div class="product-sku" t-if="props.product.product_code" t-esc="props.product.product_code"></div>
                </div>
            </td>
            
            <!-- Inventory -->
            <td class="col-inventory">
                <div class="inventory-subgrid">
                    <div class="inventory-row">
                        <span class="inventory-label">In Stock</span>
                        <span class="inventory-value inventory-units" t-esc="props.product.stock_plates || 0"></span>
                        <span class="inventory-value inventory-measure">
                            <t t-esc="props.formatNumber(props.product.stock_qty)"/> M²
                        </span>
                    </div>
                    <div class="inventory-row">
                        <span class="inventory-label">On Hold</span>
                        <span class="inventory-value inventory-units" t-esc="props.product.hold_plates || 0"></span>
                        <span class="inventory-value inventory-measure">
                            <t t-esc="props.formatNumber(props.product.hold_qty)"/> M²
                        </span>
                    </div>
                    <div class="inventory-row">
                        <span class="inventory-label">Committed</span>
                        <span class="inventory-value inventory-units" t-esc="props.product.committed_plates || 0"></span>
                        <span class="inventory-value inventory-measure">
                            <t t-esc="props.formatNumber(props.product.committed_qty)"/> M²
                        </span>
                    </div>
                    <div class="inventory-row">
                        <span class="inventory-label">Available</span>
                        <span class="inventory-value inventory-units" t-esc="props.product.available_plates || 0"></span>
                        <span class="inventory-value inventory-measure">
                            <t t-esc="props.formatNumber(props.product.available_qty)"/> M²
                        </span>
                    </div>
                </div>
            </td>
            
            <!-- Type -->
            <td class="col-type">
                <span t-if="props.product.tipo" t-esc="props.product.tipo"/>
                <span t-else="" class="text-muted">-</span>
            </td>
            
            <!-- Category -->
            <td class="col-category">
                <span t-if="props.product.categ_name" t-esc="props.product.categ_name"/>
                <span t-else="" class="text-muted">-</span>
            </td>
            
            <!-- Actions -->
            <td class="col-actions">
                <button 
                    type="button" 
                    class="btn-expand-details"
                    t-on-click="() => props.onToggle(props.product.quant_ids)"
                >
                    <i class="fa fa-chevron-down" t-att-class="{ 'fa-chevron-up': props.isExpanded }"></i>
                </button>
            </td>
        </tr>
        
        <!-- Fila de detalles -->
        <tr class="o_inventory_details_row" t-if="props.isExpanded">
            <td colspan="6" class="details-cell">
                <ProductDetails 
                    details="props.details"
                    onPhotoClick="props.onPhotoClick"
                    onNotesClick="props.onNotesClick"
                    onDetailsClick="props.onDetailsClick"
                    onSalesPersonClick="props.onSalesPersonClick"
                    onHoldClick="props.onHoldClick"
                    onSaleOrderClick="props.onSaleOrderClick"
                    formatNumber="props.formatNumber"
                    isInCart="props.isInCart"
                    toggleCartSelection="props.toggleCartSelection"
                    areAllCurrentProductSelected="props.areAllCurrentProductSelected"
                    selectAllCurrentProduct="props.selectAllCurrentProduct"
                    deselectAllCurrentProduct="props.deselectAllCurrentProduct"
                />
            </td>
        </tr>
    </t>
    
</templates>```

## ./static/src/scss/_variables.scss
```scss
// Colores Odoo
$odoo-primary: #714B67;
$odoo-gray: #8F8F8F;
$odoo-secondary: #017E84;
$odoo-learning: #E46E78;
$odoo-ready: #21B799;
$odoo-silver: #5B899E;
$odoo-gold: #E4A900;

// Colores principales
$primary-color: $odoo-primary;
$primary-hover: darken($odoo-primary, 10%);
$primary-light: mix(#fff, $odoo-primary, 90%);
$primary-dark: darken($odoo-primary, 15%);

$secondary-color: $odoo-secondary;
$accent-color: $odoo-gold;
$neutral-color: $odoo-gray;

$success-color: $odoo-ready;
$warning-color: $odoo-gold;
$danger-color: $odoo-learning;
$info-color: $odoo-silver;

$stock-color: $odoo-gray;
$committed-color: $odoo-learning;
$available-color: $odoo-ready;

// Fondos
$background-primary: #FFFFFF;
$background-secondary: #FAFAFA;
$background-tertiary: #F5F5F5;
$background-hover: mix(#fff, $odoo-gray, 95%);
$background-elevated: #FFFFFF;

// Bordes
$border-color: #E0E0E0;
$border-color-medium: #CCCCCC;
$border-color-dark: $odoo-gray;
$divider-color: #F0F0F0;

// Textos
$text-primary: #2C2C2C;
$text-secondary: #7a7a7a;
$text-tertiary: $odoo-gray;
$text-muted: #808080;

// Iconos
$icon-default: $odoo-gray;
$icon-active: $odoo-primary;
$icon-alert: $odoo-learning;

// Tipografía
$font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
$font-family-monospace: "SF Mono", Monaco, Consolas, "Courier New", monospace;

$font-size-base: 13px;
$font-size-small: 12px;
$font-size-xsmall: 11px;
$font-size-large: 16px;
$font-size-xlarge: 18px;
$font-size-xxlarge: 24px;

$font-weight-normal: 400;
$font-weight-medium: 500;
$font-weight-semibold: 600;
$font-weight-bold: 700;

$line-height-base: 1.5;
$line-height-tight: 1.3;
$line-height-compact: 1;

// Espaciado
$spacing-xs: 4px;
$spacing-sm: 8px;
$spacing-md: 12px;
$spacing-lg: 16px;
$spacing-xl: 24px;
$spacing-xxl: 48px;

// Sombras
$shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.06);
$shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
$shadow-md: 0 4px 8px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.08);
$shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.08);
$shadow-xl: 0 12px 24px rgba(0, 0, 0, 0.14), 0 6px 12px rgba(0, 0, 0, 0.1);
$shadow-hover: 0 6px 16px rgba($odoo-primary, 0.2), 0 3px 8px rgba($odoo-primary, 0.12);
$shadow-focus: 0 0 0 3px rgba($odoo-primary, 0.15);

// Border radius
$border-radius-sm: 4px;
$border-radius-md: 8px;
$border-radius-lg: 12px;
$border-radius-xl: 16px;
$border-radius-pill: 50px;

// Transiciones
$transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
$transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
$transition-slow: 350ms cubic-bezier(0.4, 0, 0.2, 1);
$transition-all: all $transition-base;

// Layout
$container-max-width: 1600px;
$z-index-searchbar: 100;
$breakpoint-md: 992px;
$breakpoint-lg: 1200px;```

## ./static/src/scss/components/_badges.scss
```scss
.icon-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid $border-color;
  border-radius: $border-radius-sm;
  cursor: pointer;
  transition: all $transition-fast;
  font-size: 12px;

  &.no-content {
    background: #c2c2c2;
    color: #FFFFFF;
    border-color: #c2c2c2;
    cursor: default;
    opacity: 0.6;

    &:hover {
      background: #c2c2c2;
      border-color: #c2c2c2;
      transform: none;
    }
  }

  &.has-photos {
    background: $odoo-gold;
    color: #FFFFFF;
    border-color: $odoo-gold;

    &:hover {
      background: darken($odoo-gold, 10%);
      border-color: darken($odoo-gold, 10%);
      transform: scale(1.1);
    }
  }

  &.has-notes {
    background: $odoo-learning;
    color: #FFFFFF;
    border-color: $odoo-learning;

    &:hover {
      background: darken($odoo-learning, 8%);
      border-color: darken($odoo-learning, 8%);
      transform: scale(1.1);
    }
  }

  &.has-details {
    background: $odoo-primary;
    color: #FFFFFF;
    border-color: $odoo-primary;
    cursor: pointer;

    &:hover {
      background: darken($odoo-primary, 8%);
      transform: scale(1.1);
    }
  }

  &.has-sales-person {
    background: $odoo-silver;
    color: #FFFFFF;
    border-color: $odoo-silver;

    &:hover {
      background: darken($odoo-silver, 8%);
      border-color: darken($odoo-silver, 8%);
      transform: scale(1.1);
    }
  }

  &.has-hold-active {
    background: $odoo-ready;
    color: #FFFFFF;
    border-color: $odoo-ready;

    &:hover {
      background: darken($odoo-ready, 10%);
      border-color: darken($odoo-ready, 10%);
      transform: scale(1.1);
    }
  }

  &.has-hold-available {
    background: $odoo-gold;
    color: #FFFFFF;
    border-color: $odoo-gold;

    &:hover {
      background: darken($odoo-gold, 10%);
      border-color: darken($odoo-gold, 10%);
      transform: scale(1.1);
    }
  }
}

.so-badge-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 8px;
  background: $success-color;
  color: #FFFFFF;
  border: 2px solid $success-color;
  border-radius: $border-radius-sm;
  font-size: 10px;
  font-weight: $font-weight-bold;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all $transition-fast;
  min-width: 32px;

  &:hover {
    background: darken($success-color, 10%);
    border-color: darken($success-color, 10%);
    transform: scale(1.1);
    box-shadow: 0 2px 8px rgba($success-color, 0.3);
  }

  &:active {
    transform: scale(0.95);
  }

  &.no-content {
    background: #c2c2c2;
    border-color: #c2c2c2;
    cursor: default;
    opacity: 0.6;

    &:hover {
      background: #c2c2c2;
      border-color: #c2c2c2;
      transform: none;
      box-shadow: none;
    }
  }
}

.status-badge-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  border: 2px solid;
  border-radius: $border-radius-sm;
  font-size: 10px;
  font-weight: $font-weight-bold;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all $transition-fast;
  min-width: 40px;
  height: 28px;

  i.fa {
    font-size: 22px;
  }

  &.status-hold-active {
    background: #ffff;
    color: #000000;
    border-color: #ffff;

    &:hover {
      background: darken(#ffff, 8%);
      border-color: darken(#ffff, 8%);
      color: lighten(#000000, 5%);
      transform: scale(1.1);
      box-shadow: 0 2px 8px rgba(#000000, 0.3);
    }

    &:active {
      transform: scale(0.95);
    }
  }

  &.status-sale-order {
    background: #528F76;
    color: #FFFFFF;
    border-color: #528F76;

    &:hover {
      background: darken(#528F76, 10%);
      border-color: darken(#528F76, 10%);
      transform: scale(1.1);
      box-shadow: 0 2px 8px rgba(#528F76, 0.3);
    }

    &:active {
      transform: scale(0.95);
    }
  }

  &.status-no-state {
    background: #FFFFFF;
    color: #909090;
    border-color: #FFFFFF;
    cursor: pointer;
    opacity: 0.85;

    &:hover {
      background: darken(#FFFFFF, 8%);
      border-color: darken(#FFFFFF, 8%);
      color: #b0b0b0;
      transform: scale(1.05);
    }
  }
}```

## ./static/src/scss/components/_data-grid.scss
```scss
.o_inventory_data_grid {
  width: 100%;
  overflow-x: auto;
  
  // Scrollbar inline (sin @include)
  scrollbar-width: thin;
  scrollbar-color: #8F8F8F #FAFAFA;

  &::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }

  &::-webkit-scrollbar-track {
    background: #FAFAFA;
    border-radius: 50px;
  }

  &::-webkit-scrollbar-thumb {
    background: linear-gradient(to bottom, #8F8F8F 0%, #714B67 100%);
    border-radius: 50px;
    border: 2px solid #FAFAFA;

    &:hover {
      background: linear-gradient(to bottom, #714B67 0%, #017E84 100%);
    }
  }
}

.o_inventory_grid_table {
  width: 100%;
  border-collapse: collapse;
  background: #FFFFFF;
  border: 1px solid #E0E0E0;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;

  thead {
    background: #F5F5F5;
    border-bottom: 1px solid #E0E0E0;

    th {
      padding: 12px;
      text-align: left;
      font-weight: 700;
      color: #2C2C2C;
      font-size: 12px;
      border-right: 1px solid #E0E0E0;
      white-space: nowrap;
      line-height: 1.4;
      text-transform: uppercase;
      letter-spacing: 0.5px;

      &:last-child {
        border-right: none;
      }

      &.col-product-name {
        width: 22%;
        min-width: 200px;
      }

      &.col-inventory {
        width: 28%;
        min-width: 280px;
      }

      &.col-type,
      &.col-category,
      &.col-format {
        width: 12%;
        min-width: 100px;
      }

      &.col-actions {
        width: 6%;
        min-width: 60px;
        text-align: center;
      }
    }
  }

  .col-type,
  .col-category,
  .col-format {
    font-size: 13px;
    color: #2C2C2C;
    font-weight: 400;

    .text-muted {
      color: #808080;
    }
  }

  .col-actions {
    text-align: center;

    .btn-expand-details {
      width: 28px;
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #E0E0E0;
      border-radius: 4px;
      background: #FFFFFF;
      color: #7a7a7a;
      cursor: pointer;
      transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
      font-size: 12px;

      &:hover {
        background: #F5F5F5;
        border-color: #CCCCCC;
        color: #2C2C2C;
      }

      i {
        transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1);
      }
    }
  }
}```

## ./static/src/scss/components/_hold-wizard.scss
```scss
.o_create_hold_dialog {
  .steps-indicator {
    padding: 16px 0;
    
    .step-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      flex: 1;
      
      .step-number {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #E0E0E0;
        color: #808080;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
        transition: all 0.3s ease;
      }
      
      .step-label {
        font-size: 12px;
        color: #808080;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
      }
      
      &.active {
        .step-number {
          background: #714B67;
          color: white;
        }
        
        .step-label {
          color: #714B67;
        }
      }
      
      &.completed {
        .step-number {
          background: #21B799;
          color: white;
        }
        
        .step-label {
          color: #21B799;
        }
      }
    }
    
    .step-line {
      flex: 1;
      height: 2px;
      background: #E0E0E0;
      margin: 0 8px;
      align-self: center;
      transition: all 0.3s ease;
      margin-top: -24px;
      
      &.active {
        background: #714B67;
      }
    }
  }
  
  .step-content {
    min-height: 400px;
    animation: fadeIn 0.3s ease-in;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}```

## ./static/src/scss/components/_product-details.scss
```scss
.details-wrapper {
  padding: 16px;
  background: #FAFAFA;
  overflow-x: auto;
  
  // Scrollbar inline (sin @include)
  scrollbar-width: thin;
  scrollbar-color: #8F8F8F #FAFAFA;

  &::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }

  &::-webkit-scrollbar-track {
    background: #FAFAFA;
    border-radius: 50px;
  }

  &::-webkit-scrollbar-thumb {
    background: linear-gradient(to bottom, #8F8F8F 0%, #714B67 100%);
    border-radius: 50px;
    border: 2px solid #FAFAFA;

    &:hover {
      background: linear-gradient(to bottom, #714B67 0%, #017E84 100%);
    }
  }
}

.o_inventory_details_table {
  width: 100%;
  border-collapse: collapse;
  background: #FFFFFF;
  border: 1px solid #E0E0E0;
  border-radius: 8px;
  font-size: 12px;

  thead {
    background: #F5F5F5;
    border-bottom: 2px solid #CCCCCC;

    th {
      padding: 8px 12px;
      text-align: left;
      font-weight: 700;
      color: #2C2C2C;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-right: 1px solid #E0E0E0;
      white-space: nowrap;

      &:last-child {
        border-right: none;
      }

      &.col-icon {
        width: 40px;
        text-align: center;
      }
    }
  }

  tbody {
    tr {
      border-bottom: 1px solid #E0E0E0;
      transition: background-color 150ms cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        background: #FAFAFA;
      }

      &:last-child {
        border-bottom: none;
      }
    }

    td {
      padding: 8px 12px;
      vertical-align: middle;
      color: #2C2C2C;
      border-right: 1px solid #E0E0E0;

      &:last-child {
        border-right: none;
      }

      &.col-icon {
        text-align: center;
        padding: 4px;
      }

      .text-muted {
        color: #808080;
      }
    }
  }

  .col-lot,
  .col-bloque,
  .col-atado {
    font-family: "SF Mono", Monaco, Consolas, "Courier New", monospace;
    font-weight: 600;
    white-space: nowrap;
  }

  .col-location {
    font-weight: 500;

    .fa-map-marker {
      color: #714B67;
      margin-right: 4px;
    }
  }

  .col-dimensions {
    .dimensions-inline {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      font-size: 11px;
      color: #7a7a7a;
    }

    .dimensions-total-inline {
      font-weight: 700;
      color: #714B67;
      font-family: sans-serif;
      font-size: 13px;
      margin-left: 4px;
    }
  }

  .state-cell {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 4px;

    .so-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 2px 6px;
      background: #F5F5F5;
      color: #2C2C2C;
      border: 1px solid #E0E0E0;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }
  }
}

.table-loading {
  padding: 24px;
  text-align: center;

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #f0ebef;
    border-top-color: #714B67;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 12px;
  }

  .loading-text {
    color: #7a7a7a;
    font-size: 12px;
  }
}

.col-tipo {
  font-family: $font-family-monospace;
  font-weight: 600;
  white-space: nowrap;
  
  .text-muted {
    color: $text-muted;
  }
}```

## ./static/src/scss/components/_product-row.scss
```scss
.o_inventory_grid_table tbody {
  tr.o_inventory_product_row {
    border-bottom: 1px solid $border-color;
    background: $background-primary;
    transition: background-color $transition-fast;

    &:hover {
      background: $background-secondary;
    }

    &.expanded {
      background: rgba($primary-color, 0.02);
    }

    td {
      padding: $spacing-md;
      vertical-align: top;
      color: $text-primary;
      border-right: 1px solid $border-color;
      line-height: 1.4;

      &:last-child {
        border-right: none;
      }
    }
  }

  tr.o_inventory_details_row {
    background: $background-secondary;
    border-bottom: 1px solid $border-color;

    td.details-cell {
      padding: 0;
      border-right: none;
    }
  }
}

.col-product-name {
  .product-name-cell {
    display: flex;
    flex-direction: column;
    gap: $spacing-xs;
  }

  .product-title {
    font-weight: $font-weight-bold;
    color: $text-primary;
    font-size: $font-size-base;
    line-height: 1.3;
  }

  .product-sku {
    font-size: $font-size-small;
    color: $text-secondary;
    font-family: $font-family-monospace;
    line-height: 1.3;
  }
}

.col-inventory {
  .inventory-subgrid {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .inventory-row {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: $spacing-lg;
    align-items: center;
    line-height: 1.3;
  }

  .inventory-label {
    font-size: $font-size-small;
    color: $text-primary;
    font-weight: $font-weight-normal;
    text-align: left;
  }

  .inventory-units {
    font-size: $font-size-small;
    color: $text-primary;
    font-weight: $font-weight-medium;
    font-family: $font-family-base;
    text-align: right;
    min-width: 40px;
  }

  .inventory-measure {
    font-size: $font-size-small;
    color: $text-primary;
    font-weight: $font-weight-medium;
    font-family: $font-family-base;
    text-align: right;
    min-width: 90px;
  }
}```

## ./static/src/scss/components/_searchbar.scss
```scss
.o_inventory_visual_searchbar {
  position: sticky;
  top: 0;
  z-index: $z-index-searchbar;
  background: rgba($background-elevated, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid $border-color;
  padding: $spacing-md $spacing-lg;
  box-shadow: $shadow-sm;
  transition: $transition-all;

  &.scrolled {
    box-shadow: $shadow-md;
    background: rgba($background-elevated, 0.98);
  }

  .searchbar-inner {
    max-width: $container-max-width;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: $spacing-md;
  }

  .filters-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: $spacing-md;
    align-items: end;

    &.main-filters {
      grid-template-columns: 1.5fr repeat(4, 1fr) auto;
      
      .search-product-name {
        grid-column: span 1;
      }
    }

    &.advanced-filters {
      padding-top: $spacing-md;
      border-top: 1px solid $border-color;
      animation: slideDown 0.3s ease-out;
    }
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .filter-label {
    font-size: $font-size-small;
    font-weight: $font-weight-semibold;
    color: $text-secondary;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin: 0;
  }

  .filter-select,
  .filter-input {
    height: 40px;
    padding: 0 $spacing-md;
    border: 1px solid $border-color;
    border-radius: $border-radius-sm;
    font-size: $font-size-base;
    font-family: $font-family-base;
    background: $background-primary;
    color: $text-primary;
    transition: $transition-all;
    outline: none;

    &:focus {
      border-color: $primary-color;
      box-shadow: 0 0 0 3px rgba($primary-color, 0.1);
    }

    &:disabled {
      background: $background-tertiary;
      cursor: not-allowed;
      opacity: 0.6;
    }
  }

  .filter-actions {
    display: flex;
    gap: $spacing-sm;
    align-items: center;

    .btn {
      height: 40px;
      padding: 0 $spacing-md;
      white-space: nowrap;
      font-size: $font-size-small;
      font-weight: $font-weight-medium;
      border-radius: $border-radius-sm;
      transition: $transition-all;

      &:hover:not(:disabled) {
        background: $primary-color;
        color: white;
        border-color: $primary-color;
      }

      &:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
    }
  }

  .filters-info {
    padding: $spacing-sm $spacing-md;
    background: $background-secondary;
    border-radius: $border-radius-sm;
    border: 1px solid $border-color;

    .results-count {
      font-size: $font-size-small;
      color: $text-secondary;

      strong {
        color: $primary-color;
        font-weight: $font-weight-bold;
      }
    }
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: $breakpoint-md) {
  .o_inventory_visual_searchbar {
    .filters-row {
      grid-template-columns: 1fr 1fr;

      &.main-filters {
        grid-template-columns: 1fr;
      }
    }
  }
}```

## ./static/src/scss/components/_states.scss
```scss
.o_inventory_visual_empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 48px;
  text-align: center;

  .empty-icon {
    font-size: 64px;
    color: #8F8F8F;
    margin-bottom: 16px;
    animation: float 3s ease-in-out infinite;
  }

  .empty-title {
    font-size: 20px;
    font-weight: 600;
    color: #7a7a7a;
    margin-bottom: 8px;
  }

  .empty-subtitle {
    font-size: 13px;
    color: #808080;
    max-width: 400px;
  }
}

.o_inventory_loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  flex-direction: column;
  gap: 12px;

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #f0ebef;
    border-top-color: #714B67;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .loading-text {
    color: #7a7a7a;
    font-size: 13px;
  }
}

.o_inventory_error {
  background: rgba(228, 110, 120, 0.1);
  border: 1px solid rgba(228, 110, 120, 0.3);
  border-radius: 12px;
  padding: 16px;
  margin: 16px;
  text-align: center;

  .error-icon {
    font-size: 40px;
    color: #E46E78;
    margin-bottom: 12px;
  }

  .error-message {
    color: #c74854;
    font-weight: 500;
  }
}

.o_inventory_no_results {
  text-align: center;
  padding: 24px;

  .no-results-icon {
    font-size: 56px;
    color: #8F8F8F;
    margin-bottom: 12px;
  }

  .no-results-title {
    font-size: 18px;
    font-weight: 600;
    color: #7a7a7a;
    margin-bottom: 8px;
  }

  .no-results-message {
    color: #808080;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}```

## ./views/inventory_visual_views.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Vista personalizada de inventario visual -->
    <record id="view_inventory_visual_kanban" model="ir.ui.view">
        <field name="name">inventory.visual.kanban</field>
        <field name="model">stock.quant</field>
        <field name="arch" type="xml">
            <kanban class="o_inventory_visual_kanban" js_class="inventory_visual_kanban">
                <field name="id"/>
                <field name="product_id"/>
                <templates>
                    <t t-name="kanban-box">
                        <div class="oe_kanban_global_click o_inventory_visual_card">
                            <div class="o_kanban_record_top">
                                <div class="o_kanban_record_headings">
                                    <strong class="o_kanban_record_title">
                                        <field name="product_id"/>
                                    </strong>
                                </div>
                            </div>
                            <div class="o_kanban_record_body">
                                <field name="quantity" widget="float"/>
                                <field name="reserved_quantity" widget="float"/>
                            </div>
                        </div>
                    </t>
                </templates>
            </kanban>
        </field>
    </record>

    <!-- Acción principal para la vista visual -->
    <record id="action_inventory_visual_main" model="ir.actions.client">
        <field name="name">Inventario Visual</field>
        <field name="tag">inventory_visual_enhanced</field>
        <field name="target">current</field>
    </record>

</odoo>
```

## ./views/menu_items.xml
```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Menú principal en Inventario - Primera posición -->
    <menuitem 
        id="menu_inventory_visual_main"
        name="Gestión Integral"
        parent="stock.menu_stock_root"
        action="action_inventory_visual_main"
        sequence="-10"/>
</odoo>```

