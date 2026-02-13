# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__) 

class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    @api.model
    def get_current_user_info(self):
        return {
            'id': self.env.user.id,
            'name': self.env.user.name
        }
    
    @api.model
    def check_sales_permissions(self):
        return self.env.user.has_group('sales_team.group_sale_salesman') or \
               self.env.user.has_group('sales_team.group_sale_salesman_all_leads') or \
               self.env.user.has_group('sales_team.group_sale_manager')
    
    @api.model
    def check_inventory_permissions(self):
        return self.env.user.has_group('stock.group_stock_user')
    
    @api.model
    def _get_price_field_name(self, currency, level):
        """Determina el campo de precio según divisa y nivel"""
        field_map = {
            ('USD', 'high'): 'x_price_usd_1',
            ('USD', 'medium'): 'x_price_usd_2',
            ('MXN', 'high'): 'x_price_mxn_1',
            ('MXN', 'medium'): 'x_price_mxn_2',
        }
        return field_map.get((currency, level), 'x_price_usd_1')
    
    @api.model
    def _filter_products_by_price(self, product_groups, filters):
        """
        Filtra productos por rango de precio post-agrupación.
        Los precios están en product.template (x_price_usd_1/2, x_price_mxn_1/2).
        """
        price_min = filters.get('price_min', '')
        price_max = filters.get('price_max', '')
        
        if not price_min and not price_max:
            return product_groups
        
        currency = filters.get('price_currency') or 'USD'
        level = filters.get('price_level') or 'high'
        field_name = self._get_price_field_name(currency, level)
        
        try:
            price_min_val = float(price_min) if price_min else None
        except (ValueError, TypeError):
            price_min_val = None
        
        try:
            price_max_val = float(price_max) if price_max else None
        except (ValueError, TypeError):
            price_max_val = None
        
        if price_min_val is None and price_max_val is None:
            return product_groups
        
        # Obtener IDs de productos agrupados
        product_ids = list(product_groups.keys())
        if not product_ids:
            return product_groups
        
        # Leer precios desde product.product -> product.template
        products = self.env['product.product'].browse(product_ids)
        
        filtered_groups = {}
        for product in products:
            tmpl = product.product_tmpl_id
            price = getattr(tmpl, field_name, 0.0) or 0.0
            
            if price_min_val is not None and price < price_min_val:
                continue
            if price_max_val is not None and price > price_max_val:
                continue
            
            filtered_groups[product.id] = product_groups[product.id]
        
        return filtered_groups
    
    @api.model
    def get_inventory_grouped_by_product(self, filters=None):
        if not filters:
            return {'products': [], 'missing_lots': []}
        
        domain = [('quantity', '>', 0)]
        search_lot_names = []
        
        if filters.get('product_name'):
            domain.append(('product_id', 'ilike', filters['product_name']))
        
        if filters.get('almacen_id'):
            almacen = self.env['stock.warehouse'].browse(int(filters['almacen_id']))
            if almacen.view_location_id:
                domain.append(('location_id', 'child_of', almacen.view_location_id.id))
        
        if filters.get('ubicacion_id'):
            domain.append(('location_id', 'child_of', int(filters['ubicacion_id'])))
        
        if filters.get('tipo'):
            domain.append(('x_tipo', '=', filters['tipo']))
        
        if filters.get('categoria_name'):
            all_cats = self.env['product.category'].search([
                ('name', 'ilike', filters['categoria_name'])
            ])
            parent_ids = set(
                self.env['product.category'].search([('parent_id', '!=', False)]).mapped('parent_id').ids
            )
            leaf_cat_ids = [cat.id for cat in all_cats if cat.id not in parent_ids]
            if leaf_cat_ids:
                domain.append(('product_id.categ_id', 'in', leaf_cat_ids))

        if filters.get('grupo'):
            grupo_search = filters['grupo']
            field = self._fields.get('x_grupo')
            if field and hasattr(field, 'comodel_name'):
                related_model = self.env[field.comodel_name]
                matching_records = related_model.search([('name', 'ilike', grupo_search)])
                if matching_records:
                    domain.append(('x_grupo', 'in', matching_records.ids))
                else:
                    domain.append(('id', '=', 0))
        
        if filters.get('acabado'):
            domain.append(('x_acabado', '=', filters['acabado']))

        if filters.get('color'):
            domain.append(('x_color', 'ilike', filters['color']))
        
        if filters.get('grosor'):
            try:
                grosor_val = float(filters['grosor'])
                domain.append(('x_grosor', '>=', grosor_val - 0.001))
                domain.append(('x_grosor', '<=', grosor_val + 0.001))
            except (ValueError, TypeError):
                pass
        
        if filters.get('numero_serie'):
            raw_input = filters['numero_serie']
            search_lot_names = [name.strip() for name in raw_input.split(',') if name.strip()]
            if search_lot_names:
                domain.append(('lot_id.name', 'in', search_lot_names))
        
        if filters.get('bloque'):
            domain.append(('x_bloque', 'ilike', filters['bloque']))
        
        if filters.get('pedimento'):
            pedimento_normalized = filters['pedimento'].replace(' ', '').replace('-', '')
            quants_con_pedimento = self.search([('x_pedimento', '!=', False), ('quantity', '>', 0)])
            matching_quant_ids = [
                q.id for q in quants_con_pedimento
                if q.x_pedimento and q.x_pedimento.replace(' ', '').replace('-', '') == pedimento_normalized
            ]
            if matching_quant_ids:
                domain.append(('id', 'in', matching_quant_ids))
            else:
                domain.append(('id', '=', 0))
        
        if filters.get('contenedor'):
            domain.append(('x_contenedor', 'ilike', filters['contenedor']))
        
        if filters.get('atado'):
            domain.append(('x_atado', 'ilike', filters['atado']))

        if filters.get('alto_min'):
            try:
                domain.append(('x_alto', '>=', float(filters['alto_min'])))
            except (ValueError, TypeError):
                pass

        if filters.get('ancho_min'):
            try:
                domain.append(('x_ancho', '>=', float(filters['ancho_min'])))
            except (ValueError, TypeError):
                pass
        
        quants = self.search(domain)
        
        missing_lots = []
        if search_lot_names:
            found_lots = set(quants.mapped('lot_id.name'))
            missing_lots = sorted(list(set(search_lot_names) - found_lots))
        
        product_groups = {}
        for quant in quants:
            product_id = quant.product_id.id
            
            if product_id not in product_groups:
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
                    'transit_qty': 0.0,
                    'transit_plates': 0,
                    'transit_hold_qty': 0.0,
                    'transit_hold_plates': 0,
                    'transit_committed_qty': 0.0,
                    'transit_committed_plates': 0,
                    'transit_available_qty': 0.0,
                    'transit_available_plates': 0,
                    'color': quant.x_color if hasattr(quant, 'x_color') else '',
                }
            
            product_groups[product_id]['quant_ids'].append(quant.id)
            
            qty = quant.quantity
            reserved = quant.reserved_quantity
            available = qty - reserved
            has_hold = hasattr(quant, 'x_tiene_hold') and quant.x_tiene_hold
            
            usage = quant.location_id.usage
            is_transit = (usage == 'transit')
            
            if is_transit:
                product_groups[product_id]['transit_qty'] += qty
                product_groups[product_id]['transit_plates'] += 1
                
                if has_hold:
                    product_groups[product_id]['transit_hold_qty'] += qty
                    product_groups[product_id]['transit_hold_plates'] += 1
                
                if reserved > 0:
                    product_groups[product_id]['transit_committed_qty'] += reserved
                    product_groups[product_id]['transit_committed_plates'] += 1
                
                if not has_hold and available > 0:
                    product_groups[product_id]['transit_available_qty'] += available
                    product_groups[product_id]['transit_available_plates'] += 1
                    
            else:
                product_groups[product_id]['stock_qty'] += qty
                product_groups[product_id]['stock_plates'] += 1
                
                if has_hold:
                    product_groups[product_id]['hold_qty'] += qty
                    product_groups[product_id]['hold_plates'] += 1
                
                if reserved > 0:
                    product_groups[product_id]['committed_qty'] += reserved
                    product_groups[product_id]['committed_plates'] += 1
                
                if not has_hold and available > 0:
                    product_groups[product_id]['available_qty'] += available
                    product_groups[product_id]['available_plates'] += 1
        
        # === FILTRO DE PRECIOS POST-AGRUPACIÓN ===
        if filters.get('price_min') or filters.get('price_max'):
            product_groups = self._filter_products_by_price(product_groups, filters)
        
        return {
            'products': list(product_groups.values()),
            'missing_lots': missing_lots
        }
    
    @api.model
    def get_quant_details(self, quant_ids=None):
        if not quant_ids:
            return []
        
        quants = self.browse(quant_ids)
        result = []
        
        is_sales_user = self.env.user.has_group('sales_team.group_sale_salesman') or \
                        self.env.user.has_group('sales_team.group_sale_salesman_all_leads') or \
                        self.env.user.has_group('sales_team.group_sale_manager')
        
        for quant in quants:
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
                'location_name': quant.location_id.name,
                'location_usage': quant.location_id.usage,
                'quantity': quant.quantity,
                'reserved_quantity': quant.reserved_quantity,
                'grosor': quant.x_grosor if hasattr(quant, 'x_grosor') else False,
                'alto': quant.x_alto if hasattr(quant, 'x_alto') else False,
                'ancho': quant.x_ancho if hasattr(quant, 'x_ancho') else False,
                'color': quant.x_color if hasattr(quant, 'x_color') else '',
                'tipo': tipo_display,
                'bloque': quant.x_bloque if hasattr(quant, 'x_bloque') else '',
                'atado': quant.x_atado if hasattr(quant, 'x_atado') else '',
                'pedimento': quant.x_pedimento if hasattr(quant, 'x_pedimento') else '',
                'contenedor': quant.x_contenedor if hasattr(quant, 'x_contenedor') else '',
                'referencia_proveedor': quant.x_referencia_proveedor if hasattr(quant, 'x_referencia_proveedor') else '',
                'cantidad_fotos': 0,
                'detalles_placa': quant.x_detalles_placa if hasattr(quant, 'x_detalles_placa') else '',
                'tiene_hold': False,
                'hold_info': None,
                'en_orden_venta': False,
                'sale_order_ids': [],
            }
            
            if quant.lot_id and hasattr(quant.lot_id, 'x_fotografia_ids'):
                detail['cantidad_fotos'] = len(quant.lot_id.x_fotografia_ids)
            
            if is_sales_user:
                detail['tiene_hold'] = quant.x_tiene_hold if hasattr(quant, 'x_tiene_hold') else False
                
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
            
            if quant.lot_id and is_sales_user:
                move_lines_with_lot = self.env['stock.move.line'].sudo().search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_id.picking_type_code', '=', 'outgoing'),
                ])
                
                sale_order_ids = set()
                for move_line in move_lines_with_lot:
                    if move_line.move_id and move_line.move_id.sale_line_id:
                        sale_order = move_line.move_id.sale_line_id.order_id
                        if sale_order.state in ['sale', 'done']:
                            sale_order_ids.add(sale_order.id)
                
                if sale_order_ids:
                    detail['en_orden_venta'] = True
                    detail['sale_order_ids'] = list(sale_order_ids)
            
            result.append(detail)
        
        return result
    
    @api.model
    def get_lot_history(self, quant_id):
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para ver el historial detallado. Contacte al administrador.")
        
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        lot = quant.lot_id
        
        has_purchase_permissions = self.env.user.has_group('purchase.group_purchase_user') or \
                                   self.env.user.has_group('purchase.group_purchase_manager')
        
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
        
        purchase_info = []
        if has_purchase_permissions:
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
        
        sales_orders = []
        sale_lines = self.env['sale.order.line'].search([
            ('product_id', '=', lot.product_id.id),
            ('order_id.state', 'in', ['sale', 'done'])
        ], limit=10, order='create_date desc')
        
        for sol in sale_lines:
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
            'has_purchase_permissions': has_purchase_permissions,
            'movements': movements,
            'sales_orders': sales_orders,
            'reservations': reservations,
            'deliveries': deliveries,
        }
    
    @api.model
    def get_lot_photos(self, quant_id):
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para buscar clientes. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear clientes. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para consultar proyectos. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear proyectos. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para consultar arquitectos. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear arquitectos. Contacte al administrador.")
        
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
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear apartados. Contacte al administrador.")
        
        quant = self.browse(quant_id)
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}
        
        if hasattr(quant, 'x_tiene_hold') and quant.x_tiene_hold:
            return {'error': 'Este lote ya tiene un apartado activo'}
        
        if product_prices and isinstance(product_prices, dict):
            auth_check = self.env['product.template'].check_price_authorization_needed(
                product_prices, 
                currency_code
            )
            
            if auth_check['needs_authorization']:
                product_groups = {}
                pid = quant.product_id.id
                product_groups[str(pid)] = {
                    'name': quant.product_id.display_name,
                    'lots': [{
                        'id': quant_id,
                        'lot_name': quant.lot_id.name,
                        'quantity': quant.quantity
                    }],
                    'total_quantity': quant.quantity
                }
                
                result = self.create_price_authorization(
                    operation_type='hold',
                    partner_id=partner_id,
                    project_id=project_id,
                    selected_lots=[quant_id],
                    currency_code=currency_code,
                    product_prices=product_prices,
                    product_groups=product_groups,
                    notes=notas,
                    architect_id=architect_id
                )
                
                if result['success']:
                    return {
                        'needs_authorization': True,
                        'authorization_id': result['authorization_id'],
                        'authorization_name': result['authorization_name'],
                        'message': f'Solicitud de autorización {result["authorization_name"]} creada. Espere aprobación del autorizador.'
                    }
        
        try:
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
            
            from datetime import datetime, timedelta
            fecha_inicio = datetime.now()
            fecha_expiracion = fecha_inicio
            dias_agregados = 0
            
            while dias_agregados < 5:
                fecha_expiracion += timedelta(days=1)
                if fecha_expiracion.weekday() < 5:
                    dias_agregados += 1
            
            if 'stock.lot.hold' not in self.env:
                return {'error': 'El modelo stock.lot.hold no está disponible.'}
            
            hold_vals = {
                'lot_id': quant.lot_id.id,
                'partner_id': partner_id,
                'user_id': self.env.user.id,
                'fecha_inicio': fecha_inicio,
                'fecha_expiracion': fecha_expiracion,
                'notas': full_notes,
            }
            
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
    def create_price_authorization(self, operation_type, partner_id, project_id, 
                                   selected_lots, currency_code, product_prices, 
                                   product_groups, notes=None, architect_id=None):
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear autorizaciones. Contacte al administrador.")
        
        if isinstance(product_prices, dict):
            product_prices = {str(k): v for k, v in product_prices.items()}
        
        auth = self.env['price.authorization'].create({
            'seller_id': self.env.user.id,
            'operation_type': operation_type,
            'partner_id': partner_id,
            'project_id': project_id,
            'currency_code': currency_code,
            'notes': notes or '',
            'temp_data': {
                'selected_lots': selected_lots,
                'product_prices': product_prices,
                'product_groups': product_groups,
                'architect_id': architect_id
            }
        })
        
        for product_id_str, group in product_groups.items():
            product_id = int(product_id_str)
            product = self.env['product.product'].browse(product_id)
            
            if currency_code == 'USD':
                medium_price = product.product_tmpl_id.x_price_usd_2
                minimum_price = product.product_tmpl_id.x_price_usd_3
            else:
                medium_price = product.product_tmpl_id.x_price_mxn_2
                minimum_price = product.product_tmpl_id.x_price_mxn_3
            
            requested_price = float(product_prices.get(str(product_id), 0))
            
            self.env['price.authorization.line'].create({
                'authorization_id': auth.id,
                'product_id': product_id,
                'quantity': group['total_quantity'],
                'lot_count': len(group['lots']),
                'requested_price': requested_price,
                'authorized_price': requested_price,
                'medium_price': medium_price,
                'minimum_price': minimum_price
            })
        
        return {
            'success': True,
            'authorization_id': auth.id,
            'authorization_name': auth.name
        }
    
    @api.model
    def get_sale_order_info(self, sale_order_ids):
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
        }