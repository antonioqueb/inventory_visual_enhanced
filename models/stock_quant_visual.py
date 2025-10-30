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
            committed_m2 = total_m2 if hold_activo else 0.0
            stock_m2 = total_m2
            available_m2 = total_m2 - committed_m2
            
            # Calcular placas
            total_plates = 0
            committed_plates = 0
            stock_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(total_m2 / plate_area))
                committed_plates = 1 if hold_activo else 0
                stock_plates = total_plates
                available_plates = stock_plates - committed_plates
            
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
            
            en_orden_venta = False
            
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