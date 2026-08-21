# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import UserError
from odoo.addons.inventory_visual_enhanced.models.som_date_format import som_format_date
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
    def _iv_get_workshop_lot_ids(self, lot_ids):
        if not lot_ids or 'workshop.input.line' not in self.env:
            return set()
        lines = self.env['workshop.input.line'].sudo().search([
            ('lot_id', 'in', list(lot_ids)),
            ('state', 'not in', ('done', 'cancelled', 'rejected')),
            ('order_id.state', '=', 'in_workshop'),
        ])
        return set(lines.mapped('lot_id').ids)
    
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
        Verifica si CUALQUIERA de los niveles de precio (1, 2 o 3) cae en el rango.
        """
        price_min = filters.get('price_min', '')
        price_max = filters.get('price_max', '')
        
        if not price_min and not price_max:
            return product_groups
        
        currency = filters.get('price_currency') or 'USD'
        
        # Definir los campos a revisar según la moneda
        if currency == 'USD':
            price_fields = ['x_price_usd_1', 'x_price_usd_2', 'x_price_usd_3']
        else:
            price_fields = ['x_price_mxn_1', 'x_price_mxn_2', 'x_price_mxn_3']
        
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
        
        product_ids = list(product_groups.keys())
        if not product_ids:
            return product_groups
        
        products = self.env['product.product'].browse(product_ids)
        
        filtered_groups = {}
        for product in products:
            tmpl = product.product_tmpl_id
            
            match_found = False
            
            for field_name in price_fields:
                price = getattr(tmpl, field_name, 0.0) or 0.0
                
                if price <= 0.001: 
                    continue
                
                is_valid = True
                if price_min_val is not None and price < price_min_val:
                    is_valid = False
                if price_max_val is not None and price > price_max_val:
                    is_valid = False
                
                if is_valid:
                    match_found = True
                    break
            
            if match_found:
                filtered_groups[product.id] = product_groups[product.id]
        
        return filtered_groups


    @api.model
    def get_inventory_grouped_by_product(self, filters=None):
        if not filters:
            return {'products': [], 'missing_lots': []}
        
        # =====================================================================
        # FIX 1: Ubicaciones internas, tránsito y producción (taller).
        # Excluye customer, supplier, inventory (virtuales).
        # Así los lotes ya entregados al cliente NO aparecen en la vista,
        # pero las placas en proceso de taller (production) sí se visualizan.
        # =====================================================================
        # Modo de inventario: 'all' (MIXTO stock + tránsito, el default),
        # 'stock' (solo almacén/taller) o 'transit' (solo tránsito).
        stock_mode = (filters.get('stock_mode') or 'all')
        if stock_mode == 'transit':
            usages = ['transit']
        elif stock_mode == 'stock':
            usages = ['internal', 'production']
        else:
            usages = ['internal', 'production', 'transit']
        domain = [
            ('quantity', '>', 0),
            ('location_id.usage', 'in', usages),
        ]
        search_lot_names = []
        
        if filters.get('product_name'):
            domain.append(('product_id', 'ilike', filters['product_name']))
        
        if filters.get('almacen_id'):
            almacen = self.env['stock.warehouse'].browse(int(filters['almacen_id']))
            if almacen.view_location_id:
                # Las ubicaciones de producción (taller) normalmente cuelgan de
                # "Ubicaciones virtuales" y NO son hijas de la vista del almacén.
                # Se incluyen explícitamente para que el material en taller siga
                # visible aun cuando se filtra por almacén.
                domain += [
                    '|',
                    ('location_id', 'child_of', almacen.view_location_id.id),
                    ('location_id.usage', '=', 'production'),
                ]
        
        if filters.get('ubicacion_id'):
            domain.append(('location_id', 'child_of', int(filters['ubicacion_id'])))
        
        if filters.get('tipo'):
            domain.append(('x_tipo', '=', filters['tipo']))
    
        if filters.get('marca'):
            domain.append(('product_id.product_tmpl_id.x_marca', 'ilike', filters['marca']))
        
        if filters.get('color'):
            domain.append(('product_id.product_tmpl_id.x_color', 'ilike', filters['color']))
        
        if filters.get('categoria_name'):
            # Máximo de niveles expuestos en el filtro (contando la raíz).
            MAX_CATEGORY_DEPTH = 3
            all_cats = self.env['product.category'].search([
                ('name', 'ilike', filters['categoria_name'])
            ])
            parent_ids = set(
                self.env['product.category'].search([('parent_id', '!=', False)]).mapped('parent_id').ids
            )
            # Solo categorías que son opción del filtro: exactamente en el nivel
            # tope, o una hoja real más superficial que el tope.
            capped_cat_ids = []
            for cat in all_cats:
                depth = len((cat.complete_name or cat.name).split(' / '))
                has_children = cat.id in parent_ids
                if depth == MAX_CATEGORY_DEPTH or (depth < MAX_CATEGORY_DEPTH and not has_children):
                    capped_cat_ids.append(cat.id)
            if capped_cat_ids:
                # child_of incluye la categoría y todo su subárbol, de modo que
                # los productos asignados a niveles más profundos también se filtran.
                domain.append(('product_id.categ_id', 'child_of', capped_cat_ids))

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
            domain.append(('x_grosor', '=', filters['grosor']))
        
        if filters.get('numero_serie'):
            raw_input = filters['numero_serie']
            search_lot_names = [name.strip() for name in raw_input.split(',') if name.strip()]
            if search_lot_names:
                if len(search_lot_names) == 1:
                    domain.append(('lot_id.name', 'ilike', search_lot_names[0]))
                else:
                    lot_domain = ['|'] * (len(search_lot_names) - 1)
                    for name in search_lot_names:
                        lot_domain.append(('lot_id.name', 'ilike', name))
                    domain.extend(lot_domain)
        
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
        
        # =====================================================================
        # FILTRO: Cantidad mínima por bloque
        # Agrupa quants por (producto, bloque) y suma su cantidad.
        # Solo conserva los quants cuyo grupo alcance el mínimo solicitado.
        # Los quants sin bloque se descartan cuando este filtro está activo.
        # =====================================================================
        if filters.get('cantidad_min_bloque'):
            try:
                min_bloque = float(filters['cantidad_min_bloque'])
            except (ValueError, TypeError):
                min_bloque = 0.0
            
            if min_bloque > 0 and quants:
                bloque_totals = {}
                for q in quants:
                    bloque_val = q.x_bloque if hasattr(q, 'x_bloque') else ''
                    if not bloque_val:
                        continue
                    key = (q.product_id.id, bloque_val)
                    bloque_totals[key] = bloque_totals.get(key, 0.0) + q.quantity
                
                valid_keys = {k for k, total in bloque_totals.items() if total >= min_bloque}
                
                quants = quants.filtered(lambda q: (
                    q.x_bloque and
                    (q.product_id.id, q.x_bloque) in valid_keys
                ))
        
        missing_lots = []
        if search_lot_names:
            found_lot_names = set(quants.mapped('lot_id.name'))
            for search_term in search_lot_names:
                if not any(search_term.lower() in lot_name.lower() for lot_name in found_lot_names if lot_name):
                    missing_lots.append(search_term)
            missing_lots.sort()
        
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
                    'workshop_qty': 0.0,
                    'workshop_plates': 0,
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
            is_workshop = (usage == 'production')

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
                # En taller (production): cuenta como stock + bucket de taller,
                # pero no como disponible (está en proceso productivo).
                if is_workshop:
                    product_groups[product_id]['workshop_qty'] += qty
                    product_groups[product_id]['workshop_plates'] += 1

                product_groups[product_id]['stock_qty'] += qty
                product_groups[product_id]['stock_plates'] += 1

                # APARTADO PARCIAL (formato/pieza): el hold solo retiene su
                # parcialidad. Antes el lote COMPLETO se iba al bucket On
                # Hold y el remanente libre jamás llegaba a Disponible — el
                # mismo lote debe contar en ambos: lo apartado en On Hold y
                # el resto en Disponible (regla espejo del detalle, que ya
                # pinta dos filas COMPROMETIDO/DISPONIBLE).
                held_qty = 0.0
                if has_hold:
                    held_qty = qty
                    lot_tipo = str(
                        getattr(quant.lot_id, 'x_tipo', '') or '').lower()
                    if lot_tipo in ('formato', 'pieza') and hasattr(
                            quant, 'som_hold_held_qty'):
                        try:
                            partial = quant.som_hold_held_qty()
                            if 0.0001 < partial < qty:
                                held_qty = partial
                        except Exception:
                            pass
                    product_groups[product_id]['hold_qty'] += held_qty
                    product_groups[product_id]['hold_plates'] += 1

                if reserved > 0:
                    product_groups[product_id]['committed_qty'] += reserved
                    product_groups[product_id]['committed_plates'] += 1

                # Disponible = físico − reserva nativa − apartado. Un lote
                # con hold PARCIAL sí aporta su remanente libre.
                free_qty = qty - reserved - held_qty
                if free_qty > 0.0001 and not is_workshop:
                    product_groups[product_id]['available_qty'] += free_qty
                    product_groups[product_id]['available_plates'] += 1
        
        # === FILTRO DE PRECIOS POST-AGRUPACIÓN ===
        if filters.get('price_min') or filters.get('price_max'):
            product_groups = self._filter_products_by_price(product_groups, filters)

        # Solo productos CON existencia en el modo seleccionado: si la cantidad es
        # cero, el producto ni siquiera se muestra.
        if stock_mode == 'transit':
            product_groups = {pid: g for pid, g in product_groups.items() if g['transit_qty'] > 0}
        elif stock_mode == 'stock':
            product_groups = {pid: g for pid, g in product_groups.items() if g['stock_qty'] > 0}
        else:
            product_groups = {
                pid: g for pid, g in product_groups.items()
                if g['stock_qty'] > 0 or g['transit_qty'] > 0}

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

        workshop_lot_ids = self._iv_get_workshop_lot_ids(
            [q.lot_id.id for q in quants if q.lot_id]
        )

        # ------------------------------------------------------------------
        # PREFETCH EN LOTE: las búsquedas por quant (move lines asignadas,
        # líneas de venta con el lote y entregado por línea) costaban ~1 s
        # POR QUANT — un producto con 100+ lotes tardaba minutos y el
        # proxy cortaba la petición ("cargando y cargando" eterno). Todo se
        # trae UNA vez y el bucle consulta mapas en memoria.
        # ------------------------------------------------------------------
        all_lot_ids = list({q.lot_id.id for q in quants if q.lot_id})

        mls_by_lot_loc = {}
        if all_lot_ids:
            for ml in self.env['stock.move.line'].sudo().search([
                ('lot_id', 'in', all_lot_ids),
                ('state', '=', 'assigned'),
                ('move_id.sale_line_id', '!=', False),
            ]):
                key = (ml.lot_id.id, ml.location_id.id)
                mls_by_lot_loc.setdefault(key, []).append(ml)

        sols_by_lot = {}
        delivered_by_sol_lot = {}
        SaleLine = self.env['sale.order.line'].sudo()
        if all_lot_ids and 'lot_ids' in SaleLine._fields:
            all_sols = SaleLine.search([
                ('lot_ids', 'in', all_lot_ids),
                ('state', '=', 'sale'),
            ])
            lot_id_set = set(all_lot_ids)
            for sol in all_sols:
                for _lot in sol.lot_ids:
                    if _lot.id in lot_id_set:
                        sols_by_lot.setdefault(_lot.id, []).append(sol)
                # Entregado por (línea, lote): UNA pasada por línea, no una
                # por cada quant que comparta el lote.
                for dml in sol.move_ids.mapped('move_line_ids'):
                    if (
                        dml.state == 'done'
                        and dml.lot_id
                        and dml.lot_id.id in lot_id_set
                        and dml.picking_id.picking_type_code == 'outgoing'
                    ):
                        dkey = (sol.id, dml.lot_id.id)
                        dq = (dml.quantity or 0.0) if 'quantity' in dml._fields \
                            else (getattr(dml, 'qty_done', 0.0) or 0.0)
                        delivered_by_sol_lot[dkey] = \
                            delivered_by_sol_lot.get(dkey, 0.0) + dq

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
                'numero_placa': quant.lot_id.x_numero_placa if quant.lot_id and hasattr(quant.lot_id, 'x_numero_placa') else '',
                'cantidad_fotos': 0,
                'detalles_placa': quant.x_detalles_placa if hasattr(quant, 'x_detalles_placa') else '',
                'tiene_hold': False,
                'hold_info': None,
                'en_orden_venta': False,
                'sale_order_ids': [],
                'en_taller': False,
                'qty_comprometida': 0.0,
                'qty_disponible': quant.quantity,
                'parcialmente_comprometido': False,
            }

            if quant.lot_id and hasattr(quant.lot_id, 'x_fotografia_ids'):
                detail['cantidad_fotos'] = len(quant.lot_id.x_fotografia_ids)

            # ================================================================
            # tiene_hold: Se calcula SIEMPRE (necesario para bloqueo de carrito)
            # ================================================================
            detail['tiene_hold'] = quant.x_tiene_hold if hasattr(quant, 'x_tiene_hold') else False

            if quant.location_id.usage == 'production' or (
                quant.lot_id and quant.lot_id.id in workshop_lot_ids
            ):
                detail['en_taller'] = True
            
            # hold_info: Solo se expone a usuarios de ventas (info sensible del cliente)
            if detail['tiene_hold'] and is_sales_user and hasattr(quant, 'x_hold_activo_id') and quant.x_hold_activo_id:
                hold = quant.x_hold_activo_id
                detail['hold_info'] = {
                    'id': hold.id,
                    'partner_name': hold.partner_id.name if hold.partner_id else '',
                    'proyecto_nombre': hold.project_id.name if hasattr(hold, 'project_id') and hold.project_id else '',
                    'arquitecto_nombre': hold.arquitecto_id.name if hasattr(hold, 'arquitecto_id') and hold.arquitecto_id else '',
                    'vendedor_nombre': hold.user_id.name if hold.user_id else '',
                    'fecha_inicio': som_format_date(hold.fecha_inicio, empty='') if hasattr(hold, 'fecha_inicio') else '',
                    'fecha_expiracion': som_format_date(hold.fecha_expiracion, empty='') if hasattr(hold, 'fecha_expiracion') else '',
                    'notas': hold.notas if hasattr(hold, 'notas') else '',
                }
            
            # ================================================================
            # en_orden_venta — por quant específico (lote + ubicación)
            #
            # Filtros:
            # - state='assigned' (pendiente). 'done' ya salió, no bloquea.
            # - location_id del quant: solo el quant en la ubicación de
            #   origen del move, no remanentes del mismo lote en otra parte.
            # - move_id.sale_line_id: ata el move a una venta. Cubre rutas
            #   multi-paso (PICK interno + OUT) sin depender del
            #   picking_type_code, ya que en 2/3 pasos el PICK es 'internal'
            #   y es el que sale desde Existencias.
            # ================================================================
            if quant.lot_id:
                move_lines_with_lot = mls_by_lot_loc.get(
                    (quant.lot_id.id, quant.location_id.id), [])

                sale_order_ids = set()
                committed_by_line = {}

                def _ml_qty(ml):
                    if 'quantity' in ml._fields and ml.quantity:
                        return ml.quantity or 0.0
                    return getattr(ml, 'reserved_uom_qty', 0.0) or getattr(ml, 'qty_done', 0.0) or 0.0

                for move_line in move_lines_with_lot:
                    sale_line = move_line.move_id.sale_line_id
                    sale_order = sale_line.order_id
                    if sale_order.state in ['sale', 'done']:
                        sale_order_ids.add(sale_order.id)
                        committed_by_line[sale_line.id] = (
                            committed_by_line.get(sale_line.id, 0.0) + _ml_qty(move_line)
                        )

                # ============================================================
                # PARCIALIDADES (formato/pieza): la cantidad comprometida es
                # la del desglose de la línea de venta, NO el lote completo.
                # También cubre líneas SIN move lines (el guard anti-FIFO omite
                # la reserva nativa para líneas con lotes manuales).
                # ============================================================
                lot_tipo = ''
                if hasattr(quant.lot_id, 'x_tipo') and quant.lot_id.x_tipo:
                    lot_tipo = str(quant.lot_id.x_tipo).strip().lower()
                is_segmentable = lot_tipo in ('formato', 'pieza')

                if 'lot_ids' in SaleLine._fields:
                    sol_lines = sols_by_lot.get(quant.lot_id.id, [])
                    for sol in sol_lines:
                        qty_bd = quant.quantity
                        if is_segmentable and hasattr(sol, '_tc_read_lot_breakdown'):
                            breakdown = sol._tc_read_lot_breakdown() or {}
                            key = str(quant.lot_id.id)
                            if key in breakdown:
                                try:
                                    qty_bd = float(breakdown.get(key) or 0.0)
                                except Exception:
                                    qty_bd = 0.0
                            elif breakdown and hasattr(
                                    sol, '_som_breakdown_qty_for_lot'):
                                # Llave de QUANT (carrito): resolución dual
                                try:
                                    rs = sol._som_breakdown_qty_for_lot(
                                        breakdown, quant.lot_id)
                                    if rs is not None:
                                        qty_bd = float(rs or 0.0)
                                except Exception:
                                    pass

                        # Descuenta lo ya entregado de ESTE lote en esa línea
                        # (pre-calculado en lote arriba).
                        delivered = delivered_by_sol_lot.get(
                            (sol.id, quant.lot_id.id), 0.0)

                        remaining = max(0.0, qty_bd - delivered)
                        if remaining > 0.0001:
                            sale_order_ids.add(sol.order_id.id)
                            committed_by_line[sol.id] = max(
                                committed_by_line.get(sol.id, 0.0), remaining)

                committed_qty = min(
                    quant.quantity, sum(committed_by_line.values()))

                if sale_order_ids:
                    detail['en_orden_venta'] = True
                    detail['sale_order_ids'] = list(sale_order_ids)
                    detail['qty_comprometida'] = committed_qty
                    detail['qty_disponible'] = max(
                        0.0, quant.quantity - committed_qty)
                    detail['parcialmente_comprometido'] = bool(
                        is_segmentable
                        and committed_qty > 0.0001
                        and detail['qty_disponible'] > 0.0001
                    )

            # APARTADO PARCIAL: el hold de un formato/pieza solo retiene su
            # parcialidad — se suma a lo comprometido y el remanente queda
            # disponible (y seleccionable).
            if detail['tiene_hold'] and hasattr(quant, 'som_hold_held_qty'):
                tipo_h = str(getattr(quant.lot_id, 'x_tipo', '') or '').lower()
                if tipo_h in ('formato', 'pieza'):
                    held = quant.som_hold_held_qty()
                    if held > 0.0001 and (quant.quantity - held) > 0.0001:
                        prev = detail.get('qty_comprometida') or 0.0
                        total_ret = min(quant.quantity, prev + held)
                        detail['qty_apartada'] = held
                        detail['qty_comprometida'] = total_ret
                        detail['qty_disponible'] = max(
                            0.0, quant.quantity - total_ret)
                        detail['parcialmente_comprometido'] = (
                            detail['qty_disponible'] > 0.0001)
                        detail['tiene_hold_parcial'] = True

            # DOS LÍNEAS por lote parcialmente retenido (venta y/o hold):
            # una NO seleccionable con lo comprometido/apartado y otra
            # seleccionable con el remanente disponible.
            if detail.get('parcialmente_comprometido') \
                    and (detail.get('qty_comprometida') or 0.0) > 0.0001:
                fila_comp = dict(detail)
                fila_comp.update({
                    'id': '%s-comprometido' % quant.id,
                    'lot_name': '%s · COMPROMETIDO' % detail['lot_name'],
                    'quantity': detail['qty_comprometida'],
                    'is_committed_row': True,
                    # No seleccionable: en venta confirmada sin parcialidad
                    'en_orden_venta': True,
                    'parcialmente_comprometido': False,
                    'qty_disponible': 0.0,
                })
                result.append(fila_comp)

                detail = dict(detail)
                detail.update({
                    'lot_name': '%s · DISPONIBLE' % detail['lot_name'],
                    'quantity': detail['qty_disponible'],
                    'is_available_row': True,
                    # Seleccionable: el remanente es libre
                    'tiene_hold': False,
                    'hold_info': None,
                    'en_orden_venta': False,
                    'parcialmente_comprometido': False,
                })

            result.append(detail)

        # Marca por bloque si tiene foto (para colorear el ícono amarillo).
        # Matching NORMALIZADO en Python (strip + lower): el =ilike anterior
        # fallaba con espacios al final o comodines (_ %) en el nombre y
        # además leía los binarios. Un solo query ligero de todos los
        # nombres de bloque con foto (la tabla es chica).
        blocks_with_photo = set()
        block_names = {(d.get('bloque') or '').strip().lower()
                       for d in result}
        block_names.discard('')
        if block_names and 'supplier.shipment.block.image' in self.env:
            self.env.cr.execute("""
                SELECT DISTINCT LOWER(TRIM(block_name))
                FROM supplier_shipment_block_image
                WHERE COALESCE(block_name, '') != ''
            """)
            photo_names = {r[0] for r in self.env.cr.fetchall()}
            blocks_with_photo = block_names & photo_names
        for d in result:
            d['block_has_photo'] = (
                (d.get('bloque') or '').strip().lower() in blocks_with_photo)

        return result

    @api.model
    def get_workshop_info(self, quant_id=None):
        if not quant_id:
            return {'error': 'Lote no encontrado'}

        quant = self.browse(int(quant_id))
        if not quant.exists() or not quant.lot_id:
            return {'error': 'Lote no encontrado'}

        if 'workshop.input.line' not in self.env:
            return {'error': 'Módulo de taller no instalado'}

        lines = self.env['workshop.input.line'].sudo().search([
            ('lot_id', '=', quant.lot_id.id),
            ('state', 'not in', ('done', 'cancelled', 'rejected')),
            ('order_id.state', '=', 'in_workshop'),
        ], order='id desc')

        if not lines:
            return {'error': 'Esta placa ya no está activa en ninguna orden de taller'}

        operation_mode_labels = dict(
            self.env['workshop.order']._fields['operation_mode'].selection
        ) if 'workshop.order' in self.env else {}
        priority_labels = dict(
            self.env['workshop.order']._fields['priority'].selection
        ) if 'workshop.order' in self.env else {}
        line_state_labels = dict(
            self.env['workshop.input.line']._fields['state'].selection
        )
        material_type_labels = dict(
            self.env['workshop.input.line']._fields['material_type'].selection
        )

        def _fmt_date(value):
            if not value:
                return ''
            try:
                return som_format_date(
                    fields.Datetime.context_timestamp(self, value),
                    empty='', with_time=True)
            except Exception:
                return som_format_date(value, empty='')

        orders = []
        for line in lines:
            order = line.order_id
            orders.append({
                'order_id': order.id,
                'order_name': order.name or '',
                'process_name': order.process_id.display_name if order.process_id else '',
                'process_type': order.process_id.process_type if order.process_id and hasattr(order.process_id, 'process_type') else '',
                'operation_mode': operation_mode_labels.get(order.operation_mode, order.operation_mode or ''),
                'priority': priority_labels.get(order.priority, ''),
                'responsible': order.responsible_id.name if order.responsible_id else '',
                'date_planned': _fmt_date(order.date_planned),
                'date_start': _fmt_date(order.date_start),
                'date_done': _fmt_date(order.date_done),
                'location_src': order.location_src_id.display_name if order.location_src_id else '',
                'location_workshop': order.location_workshop_id.display_name if order.location_workshop_id else '',
                'location_dest': order.location_dest_id.display_name if order.location_dest_id else '',
                'production_target_sqm': order.production_target_sqm or 0.0,
                'target_pieces': order.target_pieces or 0,
                'expected_yield_percent': order.expected_yield_percent or 0.0,
                'line_id': line.id,
                'line_state': line_state_labels.get(line.state, line.state or ''),
                'material_type': material_type_labels.get(line.material_type, line.material_type or ''),
                'qty_in': line.qty_in or 0.0,
                'area_sqm': line.area_sqm or 0.0,
                'width_cm': line.width_cm or 0.0,
                'height_cm': line.height_cm or 0.0,
                'thickness_cm': line.thickness_cm or 0.0,
                'pieces': line.pieces or 0,
                'block_name': line.block_name or '',
                'tone': line.tone or '',
                'current_finish': line.current_finish or '',
                'reserved_origin': line.reserved_origin or '',
            })

        return {
            'product_name': quant.product_id.display_name,
            'product_code': quant.product_id.default_code or '',
            'lot_name': quant.lot_id.name or '',
            'lot_id': quant.lot_id.id,
            'quantity': quant.quantity or 0.0,
            'reserved_quantity': quant.reserved_quantity or 0.0,
            'location_name': quant.location_id.display_name if quant.location_id else '',
            'orders': orders,
            'count': len(orders),
        }

    @api.model
    def get_lot_history(self, quant_id):
        # Historial disponible para ventas E inventario (el rol de almacén lo
        # necesita para etiquetas/traslados aunque no pueda vender ni apartar).
        if not (self.check_sales_permissions() or self.check_inventory_permissions()):
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
            'fecha_creacion': som_format_date(lot.create_date, empty=''),
            'estado_actual': 'Disponible',
            'ubicacion_actual': quant.location_id.complete_name,
            'cantidad_actual': quant.quantity,
            'cantidad_reservada': quant.reserved_quantity,
            'cantidad_disponible': quant.quantity - quant.reserved_quantity,
        }
        
        # Acotado a los 300 movimientos más recientes: el historial del diálogo
        # no necesita la vida completa de un lote muy movido, y sin límite el
        # popup podía cargar miles de líneas.
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', '=', lot.id)
        ], order='date desc', limit=300)
        
        from datetime import datetime
        dias_inventario = 0
        if lot.create_date:
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
        
        general_logs = []
        min_date = datetime.min
        
        # 1. COMPRAS
        purchase_info = []
        if has_purchase_permissions:
            purchase_lines = self.env['purchase.order.line'].search([
                ('product_id', '=', lot.product_id.id)
            ], limit=5, order='create_date desc')
            
            for pol in purchase_lines:
                purchase_info.append({
                    'orden_compra': pol.order_id.name,
                    'proveedor': pol.order_id.partner_id.name,
                    'fecha_orden': som_format_date(pol.order_id.date_order, empty=''),
                    'cantidad': pol.product_qty,
                    'precio_unitario': pol.price_unit,
                    'total': pol.price_subtotal,
                    'moneda': pol.order_id.currency_id.symbol,
                    'estado': dict(pol.order_id._fields['state'].selection).get(pol.order_id.state, ''),
                })
                
                fecha_obj = pol.order_id.date_order or pol.create_date
                general_logs.append({
                    'fecha_obj': fecha_obj,
                    'fecha': som_format_date(fecha_obj, empty='', with_time=True),
                    'usuario': pol.create_uid.name if pol.create_uid else 'Sistema',
                    'origen': 'Compra',
                    'descripcion': f"Orden de compra {pol.order_id.name} al proveedor {pol.order_id.partner_id.name} (Cant: {pol.product_qty})"
                })
        
        # 2. MOVIMIENTOS
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
            
            ref = ml.reference or ml.picking_id.name if ml.picking_id else ''
            movements.append({
                'fecha': som_format_date(ml.date, empty='', with_time=True),
                'tipo': tipo,
                'icon': icon,
                'origen': ml.location_id.complete_name,
                'destino': ml.location_dest_id.complete_name,
                'cantidad': ml.qty_done,
                'referencia': ref,
                'usuario': ml.write_uid.name if ml.write_uid else '',
            })
            
            fecha_obj = ml.date or ml.create_date
            general_logs.append({
                'fecha_obj': fecha_obj,
                'fecha': som_format_date(fecha_obj, empty='', with_time=True),
                'usuario': ml.write_uid.name if ml.write_uid else 'Sistema',
                'origen': f"Movimiento ({tipo})",
                'descripcion': f"De: {ml.location_id.name} -> A: {ml.location_dest_id.name}. Documento: {ref}. Cantidad: {ml.qty_done}"
            })
        
        # 3. VENTAS
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
                    'fecha_orden': som_format_date(sol.order_id.date_order, empty=''),
                    'cantidad': sol.product_uom_qty,
                    'precio_unitario': sol.price_unit,
                    'total': sol.price_subtotal,
                    'moneda': sol.order_id.currency_id.symbol,
                    'estado': dict(sol.order_id._fields['state'].selection).get(sol.order_id.state, ''),
                })
                
                fecha_obj = sol.order_id.date_order or sol.create_date
                general_logs.append({
                    'fecha_obj': fecha_obj,
                    'fecha': som_format_date(fecha_obj, empty='', with_time=True),
                    'usuario': sol.order_id.user_id.name if sol.order_id.user_id else 'Sistema',
                    'origen': 'Venta',
                    'descripcion': f"Orden de venta {sol.order_id.name} confirmada al cliente {sol.order_id.partner_id.name}"
                })
        
        # 4. APARTADOS
        reservations = []
        if hasattr(quant, 'x_hold_ids'):
            for hold in quant.x_hold_ids:
                statistics['total_apartados'] += 1
                
                estado_raw = hold.estado or ''
                try:
                    estado_display = dict(hold._fields['estado'].selection).get(hold.estado, hold.estado)
                except Exception:
                    estado_display = estado_raw
                
                cancel_info = {}
                if estado_raw in ('cancelado', 'expirado'):
                    cancel_info = {
                        'tipo_cancelacion': 'Expiración automática' if estado_raw == 'expirado' else 'Cancelación manual',
                        'cancelado_por': 'Sistema (Cron)' if estado_raw == 'expirado' else (hold.write_uid.name if hold.write_uid else 'Desconocido'),
                        'fecha_cancelacion': som_format_date(hold.write_date, empty='', with_time=True),
                    }
                
                duracion_dias = 0
                if hold.fecha_inicio:
                    if estado_raw in ('cancelado', 'expirado') and hold.write_date:
                        duracion_dias = (hold.write_date - hold.fecha_inicio).days
                    else:
                        duracion_dias = (fields.Datetime.now() - hold.fecha_inicio).days
                
                general_logs.append({
                    'fecha_obj': hold.create_date,
                    'fecha': som_format_date(hold.create_date, empty='', with_time=True),
                    'usuario': hold.create_uid.name if hold.create_uid else 'Sistema',
                    'origen': 'Apartado (Creación)',
                    'descripcion': f"Apartado creado para cliente: {hold.partner_id.name if hold.partner_id else '-'}"
                })

                if estado_raw in ('cancelado', 'expirado') and hold.write_date:
                    general_logs.append({
                        'fecha_obj': hold.write_date,
                        'fecha': som_format_date(hold.write_date, empty='', with_time=True),
                        'usuario': hold.write_uid.name if hold.write_uid and estado_raw != 'expirado' else 'Sistema',
                        'origen': f"Apartado ({estado_raw.capitalize()})",
                        'descripcion': f"El apartado cambió a estado: {estado_raw.upper()}"
                    })

                reservation_data = {
                    'id': hold.id,
                    'name': hold.name or '',
                    'tipo': 'Apartado Manual',
                    'estado': estado_display,
                    'estado_raw': estado_raw,
                    'partner': hold.partner_id.name if hold.partner_id else '',
                    'partner_ref': hold.partner_id.ref or '' if hold.partner_id else '',
                    'partner_email': hold.partner_id.email or '' if hold.partner_id else '',
                    'vendedor': hold.user_id.name if hold.user_id else '',
                    'vendedor_email': hold.user_id.email if hold.user_id else '',
                    'proyecto': hold.project_id.name if hold.project_id else '',
                    'arquitecto': hold.arquitecto_id.name if hold.arquitecto_id else '',
                    'fecha_inicio': som_format_date(hold.fecha_inicio, empty='', with_time=True),
                    'fecha_expiracion': som_format_date(hold.fecha_expiracion, empty='', with_time=True),
                    'fecha_creacion': som_format_date(hold.create_date, empty='', with_time=True),
                    'ultima_modificacion': som_format_date(hold.write_date, empty='', with_time=True),
                    'creado_por': hold.create_uid.name if hold.create_uid else '',
                    'modificado_por': hold.write_uid.name if hold.write_uid else '',
                    'lote_nombre': hold.lot_id.name if hold.lot_id else '',
                    'ubicacion': hold.ubicacion_id.complete_name if hold.ubicacion_id else '',
                    'duracion_dias': duracion_dias,
                    'dias_restantes': hold.dias_restantes if estado_raw == 'activo' else 0,
                    'notas': hold.notas or '',
                    'cancel_info': cancel_info,
                    'hold_order_name': '',
                    'hold_order_state': '',
                    'hold_order_sale': '',
                }
                
                try:
                    hold_order_line = self.env['stock.lot.hold.order.line'].search([('hold_id', '=', hold.id)], limit=1)
                    if hold_order_line and hold_order_line.order_id:
                        order = hold_order_line.order_id
                        reservation_data['hold_order_name'] = order.name or ''
                        reservation_data['hold_order_state'] = dict(order._fields['state'].selection).get(order.state, order.state)
                        reservation_data['hold_order_sale'] = order.sale_order_id.name if order.sale_order_id else ''
                except Exception:
                    pass
                
                # Clave de ORDEN: el datetime crudo. 'fecha_creacion' ya viene
                # formateado para el usuario ("13 ago 2026 14:30") y NO se puede
                # ordenar como texto. Se elimina tras ordenar.
                reservation_data['fecha_creacion_obj'] = hold.create_date

                reservations.append(reservation_data)

            reservations.sort(key=lambda r: (0 if r['estado_raw'] == 'activo' else 1, r.get('fecha_creacion_obj') or min_date))
            for reservation in reservations:
                reservation.pop('fecha_creacion_obj', None)
        
        # 4.b BITÁCORA DE ASIGNACIÓN (stock.lot.assignment.log)
        # Responde "¿a qué pedido se asignó esta placa y quién se la quitó?".
        # Es la ÚNICA fuente: sale.order.line.lot_ids es un many2many sin
        # tracking, así que antes de esta bitácora una desasignación no
        # dejaba rastro en la base.
        assignments = []
        for entry in self.env['stock.lot.assignment.log'].som_get_lot_trail(lot.id):
            fecha_obj = entry.pop('date_obj', None)
            entry['fecha'] = som_format_date(fecha_obj, empty='', with_time=True)
            assignments.append(entry)

            descripcion = '%s %s' % (
                'Asignada a' if entry['action'] == 'assign' else 'Desasignada de',
                entry['documento'] or 'documento sin nombre')
            if entry['cliente']:
                descripcion += ' (cliente %s)' % entry['cliente']
            if entry['motivo']:
                descripcion += ' — %s' % entry['motivo']

            general_logs.append({
                'fecha_obj': fecha_obj,
                'fecha': entry['fecha'],
                'usuario': entry['usuario'],
                'origen': 'Asignación' if entry['action'] == 'assign' else 'Desasignación',
                'descripcion': descripcion,
            })

        statistics['total_asignaciones'] = sum(
            1 for a in assignments if a['action'] == 'assign')
        statistics['total_desasignaciones'] = sum(
            1 for a in assignments if a['action'] == 'unassign')

        # 5. ENTREGAS
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
                    'fecha_programada': som_format_date(dm.picking_id.scheduled_date, empty=''),
                    'fecha_efectiva': som_format_date(dm.date, empty=''),
                    'cantidad': dm.qty_done,
                    'origen': dm.location_id.complete_name,
                    'estado': dict(dm.picking_id._fields['state'].selection).get(dm.picking_id.state, ''),
                })
        
        general_logs.sort(key=lambda x: x.get('fecha_obj') or min_date, reverse=True)
        
        for log in general_logs:
            log.pop('fecha_obj', None)

        return {
            'general_info': general_info,
            'statistics': statistics,
            'purchase_info': purchase_info,
            'has_purchase_permissions': has_purchase_permissions,
            'movements': movements,
            'sales_orders': sales_orders,
            'reservations': reservations,
            'assignments': assignments,
            'deliveries': deliveries,
            'general_logs': general_logs,
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
                    'fecha_captura': som_format_date(photo.fecha_captura, empty='', with_time=True),
                    'notas': photo.notas or '',
                })
        
        return {
            'lot_name': lot.name,
            'product_name': lot.product_id.display_name,
            'photos': photos,
        }

    @api.model
    def get_block_photos(self, block_name):
        """Fotos de un BLOQUE (subidas desde el Portal Proveedor). El bloque es
        único, así que se busca por nombre (insensible a mayúsculas). Las fotos
        viven en 'supplier.shipment.block.image' del módulo stock_lot_packing_import;
        se accede de forma defensiva por si ese módulo no está instalado."""
        block_name = (block_name or '').strip()
        if not block_name or 'supplier.shipment.block.image' not in self.env:
            return {'block_name': block_name, 'photos': []}

        Model = self.env['supplier.shipment.block.image'].sudo()
        images = Model.search([('block_name', '=ilike', block_name)], order='id desc')
        photos = []
        product_names = []
        for img in images:
            if not img.image:
                continue
            data = img.image
            if isinstance(data, bytes):
                data = data.decode('utf-8', 'ignore')
            pname = img.product_id.display_name if img.product_id else ''
            if pname and pname not in product_names:
                product_names.append(pname)
            photos.append({
                'id': img.id,
                'name': img.image_filename or ('Bloque %s' % block_name),
                'image': data,
                'fecha_captura': som_format_date(img.create_date, empty='', with_time=True),
                'notas': img.notes or '',
            })
        # Mismo formato que get_lot_photos para reutilizar el popup de placas.
        return {
            'lot_name': 'Bloque %s' % block_name,
            'block_name': block_name,
            'product_name': ', '.join(product_names),
            'photos': photos,
        }

    @api.model
    def get_block_purchase_report(self, block_name):
        """Reporte de compra de un BLOQUE: costo por lote, info general de la
        compra, todo lo comprado en la(s) misma(s) orden(es) y facturas. Camino:
        stock.lot(x_bloque) → stock.move.line(incoming) → purchase.order.line → PO."""
        block_name = (block_name or '').strip()
        empty = {'block_name': block_name, 'has_data': False}
        if not block_name:
            return empty

        Lot = self.env['stock.lot'].sudo()
        lots = Lot.search([('x_bloque', '=ilike', block_name)])
        if not lots:
            return empty

        MoveLine = self.env['stock.move.line'].sudo()
        lot_info = []          # por lote del bloque: qty + po_line
        block_po_line_ids = set()
        for lot in lots:
            mls = MoveLine.search([
                ('lot_id', '=', lot.id),
                ('picking_id.picking_type_id.code', '=', 'incoming'),
            ])
            qty = sum(mls.mapped('quantity'))
            po_line = mls.mapped('move_id.purchase_line_id')[:1]

            # FALLBACK A — Lotes ya en STOCK: la recepción física (Torre de
            # Control) recrea/renumera lotes en un picking INTERNO, por lo que
            # no tienen move lines de entrada. Se busca cualquier move line del
            # lote cuyo move venga de una línea de compra.
            if not po_line:
                any_mls = MoveLine.search([
                    ('lot_id', '=', lot.id),
                    ('move_id.purchase_line_id', '!=', False),
                ], limit=1)
                po_line = any_mls.mapped('move_id.purchase_line_id')[:1]

            if not qty:
                # Sin recepción de entrada: usa la existencia actual del lote.
                qty = lot.product_qty or 0.0

            if po_line:
                block_po_line_ids.add(po_line.id)
            lot_info.append({'lot': lot, 'qty': qty, 'po_line': po_line})

        pos = self.env['purchase.order.line'].sudo().browse(list(block_po_line_ids)).mapped('order_id')

        # FALLBACK B — Bloques del portal del proveedor: la fila de packing
        # capturada por el proveedor conserva el nombre del bloque y su packing
        # está ligado a la PO (related almacenado). Cubre lotes históricos sin
        # ningún vínculo por move lines. Retroactivo: todo se resuelve al vuelo.
        if not pos and 'supplier.shipment.packing.row' in self.env:
            rows = self.env['supplier.shipment.packing.row'].sudo().search([
                ('bloque', '=ilike', block_name),
            ])
            if rows:
                pos = rows.mapped('packing_id.purchase_id')

        valid_pos = pos.filtered(lambda p: p.state in ('purchase', 'done')) or pos

        # Costo por lote sin vínculo directo: empatar por producto dentro de
        # las órdenes encontradas (mejor aproximación que el costo estándar).
        if valid_pos:
            for info in lot_info:
                if not info['po_line']:
                    info['po_line'] = valid_pos.mapped('order_line').filtered(
                        lambda l: l.product_id == info['lot'].product_id
                    )[:1]
        main_po = valid_pos[:1]
        currency = (main_po.currency_id if main_po else self.env.company.currency_id)
        cur_symbol = currency.symbol or '$'

        def _g(rec, field):
            return getattr(rec, field) if hasattr(rec, field) else ''

        # --- Costo por lote (de ESTE bloque) ---
        block_lots = []
        block_total_cost = 0.0
        block_total_qty = 0.0
        for info in lot_info:
            lot = info['lot']
            unit = info['po_line'].price_unit if info['po_line'] else (lot.product_id.standard_price or 0.0)
            total = unit * (info['qty'] or 0.0)
            block_total_cost += total
            block_total_qty += info['qty'] or 0.0
            block_lots.append({
                'lot_name': lot.name,
                'numero_placa': _g(lot, 'x_numero_placa') or '',
                'product': lot.product_id.display_name,
                'qty': info['qty'] or 0.0,
                'unit_cost': unit,
                'total_cost': total,
            })
        block_lots.sort(key=lambda x: x['lot_name'])
        block_po_line_set = {info['po_line'].id for info in lot_info if info['po_line']}

        # --- Todo lo comprado en la(s) misma(s) orden(es) ---
        purchase_lines = []
        po_total = 0.0
        for po in valid_pos:
            for pl in po.order_line:
                uom = getattr(pl, 'product_uom_id', False) or getattr(pl, 'product_uom', False)
                purchase_lines.append({
                    'po_name': po.name,
                    'product': pl.product_id.display_name,
                    'qty': pl.product_qty,
                    'uom': uom.name if uom else '',
                    'unit_price': pl.price_unit,
                    'subtotal': pl.price_subtotal,
                    'is_block': pl.id in block_po_line_set,
                })
            po_total += po.amount_total

        # --- Facturas ---
        invoices = self.env['account.move'].sudo()
        for po in valid_pos:
            invoices |= po.invoice_ids
        invoice_list = [{
            'id': inv.id,
            'name': inv.name or inv.ref or '(borrador)',
            'date': som_format_date(inv.invoice_date, empty=''),
            'amount': inv.amount_total,
            'currency': inv.currency_id.symbol or '$',
            'state': dict(inv._fields['state'].selection).get(inv.state, inv.state or ''),
            'payment_state': dict(inv._fields['payment_state'].selection).get(inv.payment_state, '') if inv.payment_state else '',
        } for inv in invoices]

        # --- Info general (de los lotes del bloque) ---
        def first_lot_attr(field):
            for lot in lots:
                v = _g(lot, field)
                if v:
                    return v
            return ''

        return {
            'block_name': block_name,
            'has_data': bool(valid_pos),
            'supplier': main_po.partner_id.name if main_po else '',
            'po_names': valid_pos.mapped('name'),
            'po_ids': valid_pos.ids,
            'date': som_format_date(main_po.date_order, empty='') if main_po else '',
            'currency': cur_symbol,
            'partner_ref': main_po.partner_ref if main_po else '',
            'incoterm': (main_po.incoterm_id.code if main_po and main_po.incoterm_id else ''),
            'pedimento': first_lot_attr('x_pedimento'),
            'contenedor': first_lot_attr('x_contenedor'),
            'ref_proveedor': first_lot_attr('x_referencia_proveedor'),
            'lots_count': len(lots),
            'block_lots': block_lots,
            'block_total_cost': block_total_cost,
            'block_total_qty': block_total_qty,
            'purchase_lines': purchase_lines,
            'po_total': po_total,
            'invoices': invoice_list,
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
            # SUDO deliberado: dar de alta clientes es tarea del VENDEDOR (ya
            # validado arriba) y no debe requerir el grupo de administración
            # de contactos ni permisos de contabilidad. Alta acotada a campos
            # comerciales fijos.
            partner = self.env['res.partner'].sudo().create({
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
    def get_projects(self, search_term='', partner_id=None):
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para consultar proyectos. Contacte al administrador.")

        domain = []

        if hasattr(self.env['project.project'], 'x_es_proyecto_marmol'):
            domain.append(('x_es_proyecto_marmol', '=', True))

        # Regla cliente→proyectos: con un cliente seleccionado solo se ofrecen
        # SUS proyectos (o proyectos aún sin cliente); nunca los de otro cliente.
        if partner_id:
            domain += ['|', ('partner_id', '=', False),
                       ('partner_id', 'child_of', int(partner_id))]

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
    def create_project(self, name, partner_id=None):
        if not self.check_sales_permissions():
            raise UserError("No tiene permisos para crear proyectos. Contacte al administrador.")

        if not name or not name.strip():
            return {'error': 'El nombre del proyecto es requerido'}

        try:
            vals = {
                'name': name.strip(),
            }

            # Un proyecto creado desde el flujo comercial nace a nombre del
            # cliente seleccionado (regla cliente→proyectos).
            if partner_id:
                vals['partner_id'] = int(partner_id)

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
            raise UserError("No tiene permisos para consultar embajadores. Contacte al administrador.")
        
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
            raise UserError("No tiene permisos para crear embajadores. Contacte al administrador.")
        
        if not name or not name.strip():
            return {'error': 'El nombre del embajador es requerido'}
        
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
            return {'error': f'Error al crear embajador: {str(e)}'}
    
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

        # Regla cliente→proyectos: el proyecto debe ser del cliente elegido
        # (o no tener cliente aún). Validación en servidor.
        if partner_id and project_id:
            project = self.env['project.project'].browse(int(project_id)).exists()
            partner = self.env['res.partner'].browse(int(partner_id)).exists()
            if project and partner and project.partner_id and \
                    project.partner_id.commercial_partner_id != partner.commercial_partner_id:
                return {'error': 'El proyecto "%s" pertenece al cliente %s. '
                                 'Selecciona un proyecto del cliente elegido.' % (
                                     project.name, project.partner_id.display_name)}
        
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