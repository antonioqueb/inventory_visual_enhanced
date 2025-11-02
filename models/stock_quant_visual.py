# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class StockQuantVisual(models.Model):
    """
    Modelo de solo lectura para proporcionar datos agregados al frontend.
    No modifica ninguna lógica de negocio, solo provee vistas consolidadas.
    """
    _inherit = 'stock.quant'

    @api.model
    def get_inventory_grouped_by_product(self, search_term=''):
        """
        Obtiene inventario agrupado por producto con métricas consolidadas.
        Retorna estructura optimizada para la vista visual.
        
        Args:
            search_term (str): Término de búsqueda para filtrar productos
            
        Returns:
            list: Lista de diccionarios con productos y sus métricas
        """
        _logger.info(f"=== get_inventory_grouped_by_product called with search_term: '{search_term}'")
        
        domain = [('quantity', '>', 0)]
        
        if search_term:
            domain += ['|', '|', 
                    ('product_id.name', 'ilike', search_term),
                    ('product_id.default_code', 'ilike', search_term),
                    ('product_id.categ_id.name', 'ilike', search_term)]
        
        quants = self.search(domain)
        _logger.info(f"Found {len(quants)} quants matching domain")
        
        # Agrupar por producto
        products_data = defaultdict(lambda: {
            'stock_qty': 0.0,
            'stock_plates': 0,
            'hold_qty': 0.0,
            'hold_plates': 0,
            'committed_qty': 0.0,
            'committed_plates': 0,
            'available_qty': 0.0,
            'available_plates': 0,
            'total_qty': 0.0,
            'quant_ids': [],
            'has_details': False,
            'has_photos': False,
            'plate_area': 0.0,
        })
        
        for quant in quants:
            product = quant.product_id
            key = product.id
            
            # Calcular área de placa (alto × ancho en m²)
            plate_area = 0.0
            if hasattr(quant, 'x_alto') and hasattr(quant, 'x_ancho'):
                if quant.x_alto and quant.x_ancho:
                    try:
                        plate_area = float(quant.x_alto) * float(quant.x_ancho)
                    except (ValueError, TypeError):
                        plate_area = 0.0
            
            # Verificar si tiene hold activo
            hold_activo = self.env['stock.lot.hold'].search([
                ('quant_id', '=', quant.id),
                ('estado', '=', 'activo')
            ], limit=1)
            
            # Calcular métricas
            total_m2 = quant.quantity
            hold_m2 = total_m2 if hold_activo else 0.0
            
            # 🔑 COMMITTED: Cantidad reservada por el sistema (reserved_quantity)
            committed_m2 = quant.reserved_quantity
            
            # Stock = Total
            stock_m2 = total_m2
            
            # Available = Total - Hold - Committed
            available_m2 = total_m2 - hold_m2 - committed_m2
            
            # Calcular placas
            total_plates = 0
            hold_plates = 0
            committed_plates = 0
            stock_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(total_m2 / plate_area))
                hold_plates = 1 if hold_activo else 0
                committed_plates = int(round(committed_m2 / plate_area))
                stock_plates = total_plates
                available_plates = stock_plates - hold_plates - committed_plates
            
            # Obtener categoría hija
            category_name = ''
            if product.categ_id:
                current_categ = product.categ_id
                while current_categ.child_id and len(current_categ.child_id) > 0:
                    current_categ = current_categ.child_id[0]
                category_name = current_categ.name
            
            # Obtener formato
            formato = ''
            if hasattr(quant, 'x_formato') and quant.x_formato:
                formato = quant.x_formato
            
            products_data[key]['product_id'] = product.id
            products_data[key]['product_name'] = product.display_name
            products_data[key]['product_code'] = product.default_code or ''
            products_data[key]['uom_name'] = product.uom_id.name
            products_data[key]['categ_name'] = category_name
            products_data[key]['formato'] = formato
            
            # Acumular cantidades
            products_data[key]['stock_qty'] += stock_m2
            products_data[key]['stock_plates'] += stock_plates
            products_data[key]['hold_qty'] += hold_m2
            products_data[key]['hold_plates'] += hold_plates
            products_data[key]['committed_qty'] += committed_m2
            products_data[key]['committed_plates'] += committed_plates
            products_data[key]['available_qty'] += available_m2
            products_data[key]['available_plates'] += available_plates
            products_data[key]['total_qty'] += total_m2
            products_data[key]['quant_ids'].append(quant.id)
            
            if plate_area > 0 and products_data[key]['plate_area'] == 0:
                products_data[key]['plate_area'] = plate_area
            
            if hasattr(quant, 'x_tiene_detalles') and quant.x_tiene_detalles:
                products_data[key]['has_details'] = True
            if hasattr(quant, 'x_cantidad_fotos') and quant.x_cantidad_fotos > 0:
                products_data[key]['has_photos'] = True
        
        result = list(products_data.values())
        result.sort(key=lambda x: x['product_name'])
        
        _logger.info(f"Returning {len(result)} products")
        return result
    
    @api.model
    def get_lot_photos(self, quant_id=None):
        """
        Obtiene las fotos de un lote específico.
        
        Args:
            quant_id: ID del quant (puede ser int, list, o None)
            
        Returns:
            dict: Información del lote con sus fotos
        """
        _logger.info(f"=== get_lot_photos called ===")
        _logger.info(f"quant_id: {quant_id} (type: {type(quant_id)})")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            photos = self.env['stock.lot.image'].search([
                ('lot_id', '=', quant.lot_id.id)
            ], order='sequence, id')
            
            _logger.info(f"Found {len(photos)} photos for lot {quant.lot_id.name}")
            
            photos_data = []
            for photo in photos:
                photos_data.append({
                    'id': photo.id,
                    'name': photo.name,
                    'image': photo.image,
                    'sequence': photo.sequence,
                    'notas': photo.notas or '',
                    'fecha_captura': photo.fecha_captura.strftime('%d/%m/%Y %H:%M') if photo.fecha_captura else '',
                })
            
            result = {
                'lot_id': quant.lot_id.id,
                'lot_name': quant.lot_id.name,
                'product_name': quant.product_id.name,
                'photos': photos_data,
            }
            
            _logger.info(f"Returning success result with {len(photos_data)} photos")
            return result
            
        except Exception as e:
            _logger.error(f"ERROR in get_lot_photos: {str(e)}", exc_info=True)
            return {'error': f'Error interno: {str(e)}'}
    
    @api.model
    def save_lot_photo(self, quant_id=None, photo_name='', photo_data='', sequence=10, notas=''):
        """
        Guarda una nueva foto para un lote.
        
        Args:
            quant_id: ID del quant
            photo_name (str): Nombre de la foto
            photo_data (str): Datos de la imagen en base64
            sequence (int): Orden de la foto
            notas (str): Notas adicionales
            
        Returns:
            dict: Resultado de la operación
        """
        _logger.info(f"=== save_lot_photo called ===")
        _logger.info(f"quant_id: {quant_id}, photo_name: {photo_name}, sequence: {sequence}")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            # Crear registro de foto
            photo = self.env['stock.lot.image'].create({
                'lot_id': quant.lot_id.id,
                'name': photo_name,
                'image': photo_data,
                'sequence': sequence,
                'notas': notas,
            })
            
            _logger.info(f"Photo created successfully with id: {photo.id}")
            
            return {
                'success': True,
                'photo_id': photo.id,
                'message': f'Foto agregada correctamente al lote {quant.lot_id.name}'
            }
            
        except Exception as e:
            _logger.error(f"ERROR in save_lot_photo: {str(e)}", exc_info=True)
            return {'error': str(e)}
    
    @api.model
    def delete_lot_photo(self, photo_id):
        """
        Elimina una foto de un lote.
        
        Args:
            photo_id (int): ID de la foto a eliminar
            
        Returns:
            dict: Resultado de la operación
        """
        _logger.info(f"=== delete_lot_photo called with photo_id: {photo_id} ===")
        
        try:
            photo = self.env['stock.lot.image'].browse(photo_id)
            
            if not photo.exists():
                _logger.warning(f"Photo {photo_id} not found")
                return {'error': 'Foto no encontrada'}
            
            photo.unlink()
            _logger.info(f"Photo {photo_id} deleted successfully")
            
            return {
                'success': True,
                'message': 'Foto eliminada correctamente'
            }
            
        except Exception as e:
            _logger.error(f"ERROR in delete_lot_photo: {str(e)}", exc_info=True)
            return {'error': str(e)}
    
    @api.model
    def get_lot_notes(self, quant_id=None):
        """
        Obtiene las notas de un lote.
        
        Args:
            quant_id: ID del quant
            
        Returns:
            dict: Información de las notas del lote
        """
        _logger.info(f"=== get_lot_notes called ===")
        _logger.info(f"quant_id: {quant_id} (type: {type(quant_id)})")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            notes = quant.lot_id.x_detalles_placa or ''
            _logger.info(f"Notes length: {len(notes)}")
            
            result = {
                'lot_id': quant.lot_id.id,
                'lot_name': quant.lot_id.name,
                'product_name': quant.product_id.name,
                'notes': notes,
            }
            
            _logger.info(f"Returning success result")
            return result
            
        except Exception as e:
            _logger.error(f"ERROR in get_lot_notes: {str(e)}", exc_info=True)
            return {'error': f'Error interno: {str(e)}'}
    
    @api.model
    def save_lot_notes(self, quant_id=None, notes=''):
        """
        Guarda las notas de un lote.
        
        Args:
            quant_id: ID del quant
            notes (str): Notas a guardar
            
        Returns:
            dict: Resultado de la operación
        """
        _logger.info(f"=== save_lot_notes called ===")
        _logger.info(f"quant_id: {quant_id}, notes length: {len(notes) if notes else 0}")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            quant.lot_id.write({
                'x_detalles_placa': notes
            })
            
            _logger.info(f"Notes saved successfully for lot {quant.lot_id.name}")
            
            return {
                'success': True,
                'message': f'Notas guardadas correctamente para el lote {quant.lot_id.name}'
            }
            
        except Exception as e:
            _logger.error(f"ERROR in save_lot_notes: {str(e)}", exc_info=True)
            return {'error': str(e)}

    @api.model
    def get_quant_details(self, quant_ids):
        """
        Obtiene detalles completos de quants específicos.
        
        Args:
            quant_ids (list): Lista de IDs de quants
            
        Returns:
            list: Lista de diccionarios con detalles de cada quant
        """
        _logger.info(f"=== get_quant_details called with {len(quant_ids) if quant_ids else 0} quant_ids ===")
        
        if not quant_ids:
            _logger.warning("quant_ids is empty")
            return []
        
        quants = self.browse(quant_ids)
        _logger.info(f"Browsed {len(quants)} quants")
        
        details = []
        
        for quant in quants:
            _logger.info(f"Processing quant {quant.id}, lot: {quant.lot_id.name if quant.lot_id else 'No lot'}")
            
            # Obtener dimensiones
            grosor = getattr(quant, 'x_grosor', None) or ''
            alto = getattr(quant, 'x_alto', None) or ''
            atado = getattr(quant, 'x_atado', None) or ''
            ancho = getattr(quant, 'x_ancho', None) or ''
            
            # Obtener bloque y formato
            bloque = getattr(quant, 'x_bloque', None) or ''
            formato = getattr(quant, 'x_formato', None) or ''
            
            # Calcular placas
            plate_area = 0.0
            if alto and ancho:
                try:
                    plate_area = float(alto) * float(ancho)
                except (ValueError, TypeError):
                    plate_area = 0.0
            
            total_plates = 0
            committed_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(quant.quantity / plate_area))
                committed_plates = int(round(quant.reserved_quantity / plate_area))
                available_plates = total_plates - committed_plates
            
            # Estados básicos
            esta_reservado = quant.reserved_quantity > 0
            
            # Verificar si está en orden de entrega
            en_orden_entrega = False
            if quant.lot_id:
                delivery_moves = self.env['stock.move.line'].search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_id.picking_type_id.code', '=', 'outgoing')
                ], limit=1)
                en_orden_entrega = bool(delivery_moves)
            
            # Verificar si tiene orden de venta
            en_orden_venta = False
            sale_order_ids = []
            if quant.lot_id:
                sale_moves = self.env['stock.move.line'].search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', 'in', ['assigned', 'partially_available', 'done']),
                    ('move_id.sale_line_id', '!=', False)
                ])
                
                if sale_moves:
                    en_orden_venta = True
                    for move in sale_moves:
                        if move.move_id.sale_line_id and move.move_id.sale_line_id.order_id:
                            so = move.move_id.sale_line_id.order_id
                            if so.id not in sale_order_ids:
                                sale_order_ids.append(so.id)
                    _logger.info(f"Quant {quant.id} has {len(sale_order_ids)} sale orders")
            
            # Verificar si tiene hold activo
            tiene_hold = False
            hold_info = {}
            if quant.lot_id:
                hold = self.env['stock.lot.hold'].search([
                    ('quant_id', '=', quant.id),
                    ('estado', '=', 'activo')
                ], limit=1)
                
                if hold:
                    tiene_hold = True
                    hold_info = {
                        'id': hold.id,
                        'partner_name': hold.partner_id.name,
                        'fecha_inicio': hold.fecha_inicio.strftime('%d/%m/%Y %H:%M') if hold.fecha_inicio else '',
                        'fecha_expiracion': hold.fecha_expiracion.strftime('%d/%m/%Y %H:%M') if hold.fecha_expiracion else '',
                        'notas': hold.notas or '',
                    }
                    _logger.info(f"Quant {quant.id} has active hold for partner: {hold.partner_id.name}")
            
            # Verificar si tiene detalles especiales
            tiene_detalles = getattr(quant, 'x_tiene_detalles', False) or False
            
            # Contar fotos
            cantidad_fotos = 0
            if quant.lot_id:
                fotos = self.env['stock.lot.image'].search_count([
                    ('lot_id', '=', quant.lot_id.id)
                ])
                cantidad_fotos = fotos
                _logger.info(f"Quant {quant.id} has {cantidad_fotos} photos")
            
            # Obtener detalles de la placa
            detalles_placa = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_detalles_placa'):
                detalles_placa = quant.lot_id.x_detalles_placa or ''
                if detalles_placa:
                    _logger.info(f"Quant {quant.id} has plate details (length: {len(detalles_placa)})")
            
            # Obtener sales person
            sales_person = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_sales_person_id'):
                if quant.lot_id.x_sales_person_id:
                    sales_person = quant.lot_id.x_sales_person_id.name
                    _logger.info(f"Quant {quant.id} has sales person: {sales_person}")
            
            detail = {
                'id': quant.id,
                'location_name': quant.location_id.complete_name,
                'lot_name': quant.lot_id.name if quant.lot_id else '',
                'quantity': quant.quantity,
                'reserved_quantity': quant.reserved_quantity,
                'available_quantity': quant.quantity - quant.reserved_quantity,
                
                # Placas
                'total_plates': total_plates,
                'committed_plates': committed_plates,
                'available_plates': available_plates,
                
                # Dimensiones
                'grosor': grosor,
                'alto': alto,
                'ancho': ancho,
                
                # Información adicional
                'bloque': bloque,
                'atado': atado,
                'formato': formato,
                
                # Estados
                'esta_reservado': esta_reservado,
                'en_orden_entrega': en_orden_entrega,
                'en_orden_venta': en_orden_venta,
                'sale_order_ids': sale_order_ids,
                'tiene_detalles': tiene_detalles,
                'tiene_hold': tiene_hold,
                'hold_info': hold_info,
                
                # Multimedia y notas
                'cantidad_fotos': cantidad_fotos,
                'detalles_placa': detalles_placa,
                
                # Sales person
                'sales_person': sales_person,
            }
            
            details.append(detail)
        
        _logger.info(f"Returning {len(details)} detail records")
        return details

    @api.model
    def get_sale_order_info(self, sale_order_ids=None):
        """
        Obtiene información detallada de órdenes de venta.
        
        Args:
            sale_order_ids: Lista de IDs de órdenes de venta
            
        Returns:
            dict: Información de las órdenes de venta
        """
        _logger.info(f"=== get_sale_order_info called ===")
        _logger.info(f"sale_order_ids: {sale_order_ids}")
        
        if not sale_order_ids:
            _logger.warning("sale_order_ids is empty")
            return {'error': 'IDs de órdenes de venta inválidos'}
        
        try:
            sale_orders = self.env['sale.order'].browse(sale_order_ids)
            _logger.info(f"Found {len(sale_orders)} sale orders")
            
            orders_data = []
            
            for so in sale_orders:
                if not so.exists():
                    continue
                
                orders_data.append({
                    'id': so.id,
                    'name': so.name,
                    'partner_name': so.partner_id.name,
                    'partner_id': so.partner_id.id,
                    'date_order': so.date_order.strftime('%d/%m/%Y') if so.date_order else '',
                    'amount_total': so.amount_total,
                    'currency_symbol': so.currency_id.symbol,
                    'state': so.state,
                    'state_display': dict(so._fields['state'].selection).get(so.state),
                    'user_name': so.user_id.name if so.user_id else '',
                    'commitment_date': so.commitment_date.strftime('%d/%m/%Y') if so.commitment_date else '',
                })
            
            result = {
                'orders': orders_data,
                'count': len(orders_data),
            }
            
            _logger.info(f"Returning {len(orders_data)} sale orders")
            return result
            
        except Exception as e:
            _logger.error(f"ERROR in get_sale_order_info: {str(e)}", exc_info=True)
            return {'error': f'Error interno: {str(e)}'}

    @api.model
    def get_lot_history(self, quant_id=None):
        """
        Obtiene el historial completo y detallado de un lote.
        
        Args:
            quant_id: ID del quant
            
        Returns:
            dict: Información completa del historial del lote
        """
        _logger.info(f"=== get_lot_history called ===")
        _logger.info(f"quant_id: {quant_id} (type: {type(quant_id)})")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            lot = quant.lot_id
            
            # ===== INFORMACIÓN GENERAL =====
            general_info = {
                'lot_name': lot.name,
                'product_name': quant.product_id.name,
                'product_code': quant.product_id.default_code or '',
                'fecha_creacion': lot.create_date.strftime('%d/%m/%Y %H:%M') if lot.create_date else '',
                'estado_actual': 'Disponible',
                'cantidad_actual': quant.quantity,
                'cantidad_reservada': quant.reserved_quantity,
                'cantidad_disponible': quant.quantity - quant.reserved_quantity,
                'ubicacion_actual': quant.location_id.complete_name,
            }
            
            # Determinar estado
            if quant.reserved_quantity > 0:
                general_info['estado_actual'] = 'Reservado'
            
            hold_activo = self.env['stock.lot.hold'].search([
                ('quant_id', '=', quant.id),
                ('estado', '=', 'activo')
            ], limit=1)
            
            if hold_activo:
                general_info['estado_actual'] = 'Apartado (Hold)'
            
            # ===== INFORMACIÓN DE COMPRA =====
            purchase_info = []
            
            # Buscar movimientos de entrada asociados a este lote
            incoming_moves = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id),
                ('picking_id.picking_type_id.code', '=', 'incoming')
            ])
            
            # Obtener las órdenes de compra desde los movimientos
            po_line_ids = set()
            for move_line in incoming_moves:
                if move_line.move_id and move_line.move_id.purchase_line_id:
                    po_line_ids.add(move_line.move_id.purchase_line_id.id)
            
            if po_line_ids:
                purchase_lines = self.env['purchase.order.line'].browse(list(po_line_ids))
                
                # Filtrar por estado y ordenar
                valid_lines = [pl for pl in purchase_lines if pl.order_id and pl.order_id.state in ['purchase', 'done']]
                valid_lines.sort(key=lambda x: x.order_id.date_order if x.order_id.date_order else fields.Datetime.now(), reverse=True)
                
                for po_line in valid_lines[:5]:  # Limitar a 5 registros
                    purchase_info.append({
                        'orden_compra': po_line.order_id.name,
                        'proveedor': po_line.order_id.partner_id.name,
                        'fecha_orden': po_line.order_id.date_order.strftime('%d/%m/%Y') if po_line.order_id.date_order else '',
                        'cantidad': po_line.product_qty,
                        'precio_unitario': po_line.price_unit,
                        'total': po_line.price_subtotal,
                        'moneda': po_line.order_id.currency_id.symbol,
                        'estado': dict(po_line.order_id._fields['state'].selection).get(po_line.order_id.state),
                    })
            
            # ===== HISTORIAL DE MOVIMIENTOS =====
            movements = []
            
            # Buscar todos los movimientos relacionados con este lote
            stock_moves = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id)
            ], order='date desc', limit=50)
            
            for move in stock_moves:
                movement_type = 'Otro'
                icon = 'fa-exchange'
                color = 'secondary'
                
                # Determinar tipo de movimiento
                if move.picking_id:
                    picking_code = move.picking_id.picking_type_id.code
                    if picking_code == 'incoming':
                        movement_type = 'Entrada'
                        icon = 'fa-arrow-down'
                        color = 'success'
                    elif picking_code == 'outgoing':
                        movement_type = 'Salida'
                        icon = 'fa-arrow-up'
                        color = 'danger'
                    elif picking_code == 'internal':
                        movement_type = 'Movimiento Interno'
                        icon = 'fa-exchange'
                        color = 'info'
                
                movements.append({
                    'fecha': move.date.strftime('%d/%m/%Y %H:%M') if move.date else '',
                    'tipo': movement_type,
                    'icon': icon,
                    'color': color,
                    'origen': move.location_id.name,
                    'destino': move.location_dest_id.name,
                    'cantidad': move.qty_done,
                    'referencia': move.picking_id.name if move.picking_id else move.reference or '-',
                    'usuario': move.create_uid.name if move.create_uid else '-',
                })
            
            # ===== ÓRDENES DE VENTA =====
            sales_orders = []
            
            # Buscar movimientos de salida asociados a este lote
            outgoing_moves = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id),
                ('picking_id.picking_type_id.code', '=', 'outgoing')
            ])
            
            # Obtener las órdenes de venta desde los movimientos
            so_line_ids = set()
            for move_line in outgoing_moves:
                if move_line.move_id and move_line.move_id.sale_line_id:
                    so_line_ids.add(move_line.move_id.sale_line_id.id)
            
            if so_line_ids:
                sale_lines = self.env['sale.order.line'].browse(list(so_line_ids))
                
                # Filtrar por estado y ordenar
                valid_lines = [sl for sl in sale_lines if sl.order_id and sl.order_id.state in ['sale', 'done']]
                valid_lines.sort(key=lambda x: x.order_id.date_order if x.order_id.date_order else fields.Datetime.now(), reverse=True)
                
                for so_line in valid_lines[:10]:  # Limitar a 10 registros
                    sales_orders.append({
                        'orden_venta': so_line.order_id.name,
                        'cliente': so_line.order_id.partner_id.name,
                        'vendedor': so_line.order_id.user_id.name if so_line.order_id.user_id else '-',
                        'fecha_orden': so_line.order_id.date_order.strftime('%d/%m/%Y') if so_line.order_id.date_order else '',
                        'cantidad': so_line.product_uom_qty,
                        'precio_unitario': so_line.price_unit,
                        'total': so_line.price_subtotal,
                        'moneda': so_line.order_id.currency_id.symbol,
                        'estado': dict(so_line.order_id._fields['state'].selection).get(so_line.order_id.state),
                    })
            
            # ===== RESERVAS Y APARTADOS =====
            reservations = []
            
            # Buscar todos los holds (activos e históricos)
            holds = self.env['stock.lot.hold'].search([
                ('quant_id', '=', quant.id)
            ], order='fecha_inicio desc')
            
            for hold in holds:
                reservations.append({
                    'tipo': 'Apartado (Hold)',
                    'partner': hold.partner_id.name,
                    'fecha_inicio': hold.fecha_inicio.strftime('%d/%m/%Y %H:%M') if hold.fecha_inicio else '',
                    'fecha_expiracion': hold.fecha_expiracion.strftime('%d/%m/%Y %H:%M') if hold.fecha_expiracion else '',
                    'estado': 'Activo' if hold.estado == 'activo' else 'Liberado',
                    'notas': hold.notas or '',
                    'color': 'warning' if hold.estado == 'activo' else 'secondary'
                })
            
            # Buscar reservas de stock a través de stock.move.line
            # En Odoo 18, las reservas se manejan directamente en stock.move.line
            reserved_move_lines = self.env['stock.move.line'].search([
                ('product_id', '=', quant.product_id.id),
                ('lot_id', '=', lot.id),
                ('state', 'in', ['assigned', 'partially_available']),
                ('quantity', '>', 0)  # Odoo 18 usa 'quantity' en lugar de 'product_qty'
            ])
            
            for move_line in reserved_move_lines:
                partner_name = '-'
                move = move_line.move_id
                
                if move:
                    if move.sale_line_id and move.sale_line_id.order_id:
                        partner_name = move.sale_line_id.order_id.partner_id.name
                    elif move.picking_id and move.picking_id.partner_id:
                        partner_name = move.picking_id.partner_id.name
                
                reservations.append({
                    'tipo': 'Reserva de Stock',
                    'partner': partner_name,
                    'fecha_inicio': move_line.date.strftime('%d/%m/%Y %H:%M') if move_line.date else '',
                    'fecha_expiracion': '-',
                    'estado': 'Activo',
                    'notas': move_line.picking_id.name if move_line.picking_id else move_line.reference or '',
                    'color': 'info'
                })
            
            # ===== ENTREGAS =====
            deliveries = []
            
            # Buscar entregas (outgoing pickings)
            delivery_moves = self.env['stock.move.line'].search([
                ('lot_id', '=', lot.id),
                ('picking_id.picking_type_id.code', '=', 'outgoing')
            ], order='date desc')
            
            for move in delivery_moves:
                picking = move.picking_id
                if picking:
                    deliveries.append({
                        'referencia': picking.name,
                        'cliente': picking.partner_id.name if picking.partner_id else '-',
                        'fecha_programada': picking.scheduled_date.strftime('%d/%m/%Y') if picking.scheduled_date else '',
                        'fecha_efectiva': picking.date_done.strftime('%d/%m/%Y %H:%M') if picking.date_done else '-',
                        'cantidad': move.qty_done,
                        'estado': dict(picking._fields['state'].selection).get(picking.state),
                        'origen': picking.origin or '-',
                        'color': 'success' if picking.state == 'done' else 'warning' if picking.state == 'assigned' else 'secondary'
                    })
            
            # ===== ESTADÍSTICAS =====
            statistics = {
                'total_movimientos': len(movements),
                'total_entradas': len([m for m in movements if m['tipo'] == 'Entrada']),
                'total_salidas': len([m for m in movements if m['tipo'] == 'Salida']),
                'total_ventas': len(sales_orders),
                'total_apartados': len(reservations),
                'total_entregas': len(deliveries),
                'dias_en_inventario': (fields.Datetime.now() - lot.create_date).days if lot.create_date else 0,
            }
            
            result = {
                'general_info': general_info,
                'purchase_info': purchase_info,
                'movements': movements,
                'sales_orders': sales_orders,
                'reservations': reservations,
                'deliveries': deliveries,
                'statistics': statistics,
            }
            
            _logger.info(f"Returning history with {len(movements)} movements, {len(sales_orders)} sales, {len(purchase_info)} purchases, {len(reservations)} reservations")
            return result
            
        except Exception as e:
            _logger.error(f"ERROR in get_lot_history: {str(e)}", exc_info=True)
            return {'error': f'Error interno: {str(e)}'}

    @api.model
    def create_lot_hold(self, quant_id=None, partner_id=None, notas=''):
        """
        Crea un hold/apartado para un lote desde la vista visual.
        
        Args:
            quant_id: ID del quant
            partner_id: ID del cliente/partner
            notas: Notas adicionales
            
        Returns:
            dict: Resultado de la operación
        """
        _logger.info(f"=== create_lot_hold called ===")
        _logger.info(f"quant_id: {quant_id}, partner_id: {partner_id}")
        
        # Normalizar quant_id
        if isinstance(quant_id, list):
            quant_id = quant_id[0] if quant_id else False
        
        if not quant_id:
            _logger.warning("quant_id is empty or False")
            return {'error': 'ID de quant inválido'}
        
        if not partner_id:
            _logger.warning("partner_id is empty or False")
            return {'error': 'Debe seleccionar un cliente'}
        
        try:
            quant = self.browse(quant_id)
            _logger.info(f"Browsed quant: {quant}, exists: {quant.exists()}")
            
            if not quant.exists():
                _logger.warning(f"Quant {quant_id} does not exist")
                return {'error': 'Quant no encontrado'}
            
            if not quant.lot_id:
                _logger.warning(f"Quant {quant_id} does not have a lot assigned")
                return {'error': 'Este quant no tiene un lote asignado'}
            
            # Verificar si ya existe un hold activo
            hold_existente = self.env['stock.lot.hold'].search([
                ('quant_id', '=', quant.id),
                ('estado', '=', 'activo')
            ], limit=1)
            
            if hold_existente:
                return {
                    'error': f'Este lote ya tiene una reserva activa para {hold_existente.partner_id.name}'
                }
            
            # Crear el hold
            hold = self.env['stock.lot.hold'].create({
                'lot_id': quant.lot_id.id,
                'quant_id': quant.id,
                'partner_id': partner_id,
                'notas': notas or '',
            })
            
            _logger.info(f"Hold created successfully with id: {hold.id}")
            
            return {
                'success': True,
                'hold_id': hold.id,
                'message': f'Lote {quant.lot_id.name} apartado para {hold.partner_id.name} hasta {hold.fecha_expiracion.strftime("%d/%m/%Y")}'
            }
            
        except Exception as e:
            _logger.error(f"ERROR in create_lot_hold: {str(e)}", exc_info=True)
            return {'error': f'Error al crear apartado: {str(e)}'}

    @api.model
    def search_partners(self, name=''):
        """
        Busca clientes/partners para el selector de apartados.
        
        Args:
            name: Término de búsqueda
            
        Returns:
            list: Lista de partners encontrados
        """
        _logger.info(f"=== search_partners called with name: '{name}' ===")
        
        if not name or name.strip() == '':
            domain = [
                ('active', '=', True),
                '|', '|',
                ('customer_rank', '>', 0),
                ('supplier_rank', '>', 0),
                ('is_company', '=', True)
            ]
        else:
            search_term = name.strip()
            domain = [
                ('active', '=', True),
                '|', '|', '|', '|',
                ('name', 'ilike', search_term),
                ('ref', 'ilike', search_term),
                ('vat', 'ilike', search_term),
                ('email', 'ilike', search_term),
                ('phone', 'ilike', search_term)
            ]
        
        partners = self.env['res.partner'].search(domain, limit=50, order='name')
        _logger.info(f"Found {len(partners)} partners in database")
        
        result = []
        for partner in partners:
            display_parts = [partner.name]
            if partner.ref:
                display_parts.append(f"[{partner.ref}]")
            if partner.vat:
                display_parts.append(f"RFC: {partner.vat}")
            
            display_name = ' '.join(display_parts)
            
            result.append({
                'id': partner.id,
                'name': partner.name,
                'ref': partner.ref or '',
                'vat': partner.vat or '',
                'display_name': display_name
            })
        
        _logger.info(f"Returning {len(result)} partners")
        return result