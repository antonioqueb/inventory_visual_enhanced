# -*- coding: utf-8 -*-
from odoo import models, fields, api
from collections import defaultdict

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
        domain = [('quantity', '>', 0)]
        
        if search_term:
            domain += ['|', '|', 
                      ('product_id.name', 'ilike', search_term),
                      ('product_id.default_code', 'ilike', search_term),
                      ('product_id.categ_id.name', 'ilike', search_term)]
        
        quants = self.search(domain)
        
        # Agrupar por producto
        products_data = defaultdict(lambda: {
            'stock_qty': 0.0,  # Total en stock
            'stock_plates': 0,  # Total de placas en stock
            'committed_qty': 0.0,  # Apartado/Comprometido
            'committed_plates': 0,  # Placas comprometidas
            'available_qty': 0.0,  # Disponible = Stock - Comprometido
            'available_plates': 0,  # Placas disponibles
            'total_qty': 0.0,  # Total m²
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
            
            # Calcular métricas
            total_m2 = quant.quantity
            committed_m2 = quant.reserved_quantity
            stock_m2 = total_m2
            available_m2 = total_m2 - committed_m2
            
            # Calcular placas (solo si tenemos área de placa válida)
            total_plates = 0
            committed_plates = 0
            stock_plates = 0
            available_plates = 0
            
            if plate_area > 0:
                total_plates = int(round(total_m2 / plate_area))
                committed_plates = int(round(committed_m2 / plate_area))
                stock_plates = total_plates
                available_plates = stock_plates - committed_plates
            
            # Obtener categoría hija (última categoría en la jerarquía) - CORREGIDO
            category_name = ''
            if product.categ_id:
                current_categ = product.categ_id
                # Navegar hacia abajo hasta encontrar la categoría hoja
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
            products_data[key]['categ_name'] = category_name  # CORREGIDO: era 'category_name'
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
            
            # Guardar área de placa para referencia
            if plate_area > 0 and products_data[key]['plate_area'] == 0:
                products_data[key]['plate_area'] = plate_area
            
            # Verificar si tiene detalles o fotos
            if hasattr(quant, 'x_tiene_detalles') and quant.x_tiene_detalles:
                products_data[key]['has_details'] = True
            if hasattr(quant, 'x_cantidad_fotos') and quant.x_cantidad_fotos > 0:
                products_data[key]['has_photos'] = True
        
        # Convertir a lista y ordenar
        result = list(products_data.values())
        result.sort(key=lambda x: x['product_name'])
        
        return result

    @api.model
    def get_quant_details(self, quant_ids):
        """
        Obtiene detalles completos de quants específicos.
        
        Args:
            quant_ids (list): Lista de IDs de quants
            
        Returns:
            list: Lista de diccionarios con detalles de cada quant
        """
        if not quant_ids:
            return []
        
        quants = self.browse(quant_ids)
        details = []
        
        for quant in quants:
            # Obtener dimensiones
            grosor = getattr(quant, 'x_grosor', None) or ''
            alto = getattr(quant, 'x_alto', None) or ''
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
            
            # Verificar si está en orden de entrega (buscar en movimientos)
            en_orden_entrega = False
            if quant.lot_id:
                delivery_moves = self.env['stock.move.line'].search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('state', 'in', ['assigned', 'done']),
                    ('picking_id.picking_type_id.code', '=', 'outgoing')
                ], limit=1)
                en_orden_entrega = bool(delivery_moves)
            
            # Verificar si está en orden de venta (buscar en movimientos con sale_line_id)
            # COMENTADO TEMPORALMENTE - Solo mostrar holds por ahora
            en_orden_venta = False
            # if quant.lot_id:
            #     sale_moves = self.env['stock.move'].search([
            #         ('lot_ids', 'in', [quant.lot_id.id]),
            #         ('sale_line_id', '!=', False),
            #         ('state', 'in', ['confirmed', 'assigned', 'done'])
            #     ], limit=1)
            #     en_orden_venta = bool(sale_moves)
            
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
            
            # Verificar si tiene detalles especiales
            tiene_detalles = getattr(quant, 'x_tiene_detalles', False) or False
            
            # Contar fotos (attachments de tipo imagen en el lote)
            cantidad_fotos = 0
            if quant.lot_id:
                fotos = self.env['ir.attachment'].search_count([
                    ('res_model', '=', 'stock.quant.lot'),
                    ('res_id', '=', quant.lot_id.id),
                    ('mimetype', 'like', 'image/%')
                ])
                cantidad_fotos = fotos
            
            # Obtener detalles de la placa (notas)
            detalles_placa = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_detalles_placa'):
                detalles_placa = quant.lot_id.x_detalles_placa or ''
            
            # Obtener sales person (si existe en el lote)
            sales_person = ''
            if quant.lot_id and hasattr(quant.lot_id, 'x_sales_person_id'):
                if quant.lot_id.x_sales_person_id:
                    sales_person = quant.lot_id.x_sales_person_id.name
            
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
        
        return details