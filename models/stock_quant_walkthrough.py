# -*- coding: utf-8 -*-
"""Walkthrough: inventario que YA SALIÓ del stock.

Espejo del Inventario Visual pero sobre las salidas correctas:

- ENTREGAS: quants con cantidad positiva en ubicaciones usage='customer'
  (partida doble de Odoo: lo entregado se acumula en el cliente).
- BAJAS: movimientos done de stock.scrap (move.scrap_id). NO se puede usar
  el quant de la ubicación de desecho: en Odoo 19 el desecho comparte
  ubicación/usage ('inventory') con la contrapartida de los ajustes, así
  que un material que ENTRÓ por ajuste (−qty) y salió por baja (+qty)
  deja el quant NETO EN CERO. La cantidad real dada de baja se toma de
  los movimientos.

Cada fila de detalle sigue siendo un stock.quant real (el de cliente, o
el de la ubicación de desecho — se garantiza su existencia aunque esté en
cero), para que la cadena existente (get_quant_details, get_lot_history,
get_lot_photos, get_lot_notes) funcione sin cambios con detail.id.

Quedan fuera a propósito:
- Lotes que aún tienen existencias en internal/transit/production (eso es
  el Inventario Visual, no el Walkthrough).
- Ajustes de inventario y reclasificaciones (move.is_inventory, sin
  scrap_id): no son salidas correctas; en la reclasificación el material
  sigue existiendo en el lote espejo.

Ojo con lotes archivados: la baja archiva el lote, y cualquier condición
de dominio que navegue el m2o (lot_id.name, lot_id.x_bloque...) los
excluiría por active_test. Por eso los filtros de lote se resuelven
aparte con active_test=False y los dominios reciben ('lot_id','in',ids).
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockQuantWalkthrough(models.Model):
    _inherit = 'stock.quant'

    # ------------------------------------------------------------------
    # Filtros comunes (aplican a stock.quant Y a stock.move.line: ambos
    # tienen product_id y lot_id)
    # ------------------------------------------------------------------

    @api.model
    def _walkthrough_field_exists(self, model, field_name):
        return field_name in self.env[model]._fields

    @api.model
    def _walkthrough_common_filters(self, filters):
        """Réplica de los filtros del Inventario Visual que tienen sentido
        sin stock actual. almacen_id / ubicacion_id / stock_mode se ignoran
        (el material ya no está en un almacén)."""
        filters = filters or {}
        Lot = self.env['stock.lot']
        # Las búsquedas de abajo van con sudo(): se acotan a las compañías
        # activas del usuario (listado). Aplica a quants y move lines.
        # Los quants de ubicaciones de CLIENTE (y otras compartidas) viven
        # con company_id vacío: exigir compañía aquí borraba TODAS las
        # entregas del Walkthrough (caso S121-15). El vacío también cuenta.
        domain = [('company_id', 'in', self.env.companies.ids + [False])]
        missing_lots = []

        if filters.get('product_name'):
            domain.append(('product_id', 'ilike', filters['product_name']))

        if filters.get('categoria_name'):
            cats = self._som_categories_matching(filters['categoria_name'])
            domain.append(('product_id.categ_id', 'child_of', cats.ids) if cats else ('id', '=', 0))

        if filters.get('marca') and self._walkthrough_field_exists(
                'product.template', 'x_marca'):
            domain.append((
                'product_id.product_tmpl_id.x_marca', 'ilike', filters['marca']))

        if filters.get('grupo') and self._walkthrough_field_exists(
                'product.template', 'x_grupo'):
            domain.append((
                'product_id.product_tmpl_id.x_grupo', 'ilike', filters['grupo']))

        if filters.get('acabado') and self._walkthrough_field_exists(
                'product.template', 'x_acabado'):
            domain.append((
                'product_id.product_tmpl_id.x_acabado', '=', filters['acabado']))

        # --- Filtros sobre el LOTE (resueltos con active_test=False) ---
        lot_domain = []

        lot_field_filters = [
            ('tipo', 'x_tipo', '='),
            ('color', 'x_color', 'ilike'),
            ('bloque', 'x_bloque', 'ilike'),
            ('atado', 'x_atado', 'ilike'),
            ('pedimento', 'x_pedimento', 'ilike'),
            ('contenedor', 'x_contenedor', 'ilike'),
        ]
        for filter_key, lot_field, op in lot_field_filters:
            value = filters.get(filter_key)
            if value and self._walkthrough_field_exists('stock.lot', lot_field):
                lot_domain.append((lot_field, op, value))

        if filters.get('grosor') and self._walkthrough_field_exists(
                'stock.lot', 'x_grosor'):
            try:
                lot_domain.append(('x_grosor', '=', float(filters['grosor'])))
            except (ValueError, TypeError):
                pass

        for filter_key, lot_field in (('alto_min', 'x_alto'), ('ancho_min', 'x_ancho')):
            value = filters.get(filter_key)
            if value and self._walkthrough_field_exists('stock.lot', lot_field):
                try:
                    lot_domain.append((lot_field, '>=', float(value)))
                except (ValueError, TypeError):
                    pass

        # Lotes: propios de las compañías activas o compartidos (sudo).
        lot_company_domain = [
            ('company_id', 'in', self.env.companies.ids + [False])]

        if filters.get('numero_serie'):
            raw = str(filters['numero_serie'])
            names = [n.strip() for n in raw.split(',') if n.strip()]
            if len(names) > 1:
                lot_domain.append(('name', 'in', names))
                found = set(
                    Lot.sudo().with_context(active_test=False)
                    .search([('name', 'in', names)] + lot_company_domain)
                    .mapped('name')
                )
                missing_lots = [n for n in names if n not in found]
            elif names:
                lot_domain.append(('name', 'ilike', names[0]))

        if lot_domain:
            lot_ids = Lot.sudo().with_context(active_test=False).search(
                lot_domain + lot_company_domain).ids
            domain.append(('lot_id', 'in', lot_ids))

        return domain, missing_lots

    # ------------------------------------------------------------------
    # Fuentes de salidas
    # ------------------------------------------------------------------

    @api.model
    def _walkthrough_lots_with_current_stock(self, lot_ids):
        """Lotes que AÚN tienen existencias (internal/transit/production):
        esos pertenecen al Inventario Visual, no al Walkthrough."""
        if not lot_ids:
            return set()
        groups = self.sudo().read_group(
            [
                ('lot_id', 'in', list(lot_ids)),
                ('quantity', '!=', 0),
                ('location_id.usage', 'in', ['internal', 'transit']),
            ],
            ['lot_id'],
            ['lot_id'],
        )
        alive = {g['lot_id'][0] for g in groups if g.get('lot_id')}
        # En producción (taller): vivo solo si NO fue consumido en una OT ya
        # terminada (ese quant es el rastro del consumo, no inventario).
        prod_groups = self.sudo().read_group(
            [
                ('lot_id', 'in', list(lot_ids)),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'production'),
            ],
            ['lot_id'],
            ['lot_id'],
        )
        prod_lots = {g['lot_id'][0] for g in prod_groups if g.get('lot_id')}
        if prod_lots:
            alive |= prod_lots - self._iv_get_workshop_consumed_lot_ids(list(prod_lots))
        return alive

    @api.model
    def _walkthrough_scrap_aggregates(self, common_domain):
        """Bajas reales, agregadas desde los movimientos de stock.scrap:
        {(lot, location_dest): qty_total}."""
        move_lines = self.env['stock.move.line'].sudo().search([
            ('state', '=', 'done'),
            ('move_id.scrap_id', '!=', False),
            ('lot_id', '!=', False),
            ('location_dest_id.usage', '=', 'inventory'),
        ] + list(common_domain))
        aggregates = {}
        for line in move_lines:
            key = (line.lot_id, line.location_dest_id)
            aggregates[key] = aggregates.get(key, 0.0) + (line.quantity or 0.0)
        return aggregates

    @api.model
    def _walkthrough_reclassified_lot_ids(self, lot_ids):
        """Lotes cuyo vaciado vino de una RECLASIFICACIÓN: el material sigue
        vivo en el lote espejo, así que sus ajustes NO son bajas."""
        if not lot_ids or 'stock.lot.reclassification.line' not in self.env:
            return set()
        lines = self.env['stock.lot.reclassification.line'].sudo().search([
            ('lot_from_id', 'in', list(lot_ids)),
        ])
        return set(lines.mapped('lot_from_id').ids)

    @api.model
    def _walkthrough_adjustment_aggregates(self, common_domain):
        """Bajas por AJUSTE DE INVENTARIO (sin stock.scrap): neto por lote de
        lo que salió del stock hacia la contrapartida de ajustes menos lo que
        regresó por ajustes positivos. {(lot, location_dest): qty_neta}.

        Se excluyen los lotes vaciados por reclasificación (lote espejo
        vivo). Antes los ajustes quedaban fuera por completo y un material
        dado de baja con ajuste directo jamás aparecía en el Walkthrough."""
        MoveLine = self.env['stock.move.line'].sudo()
        base = [
            ('state', '=', 'done'),
            ('lot_id', '!=', False),
            ('move_id.scrap_id', '=', False),
        ]
        if 'is_inventory' in self.env['stock.move']._fields:
            base.append(('move_id.is_inventory', '=', True))

        out_lines = MoveLine.search(base + [
            ('location_id.usage', 'in', ('internal', 'transit')),
            ('location_dest_id.usage', '=', 'inventory'),
        ] + list(common_domain))
        in_lines = MoveLine.search(base + [
            ('location_id.usage', '=', 'inventory'),
            ('location_dest_id.usage', 'in', ('internal', 'transit')),
        ] + list(common_domain))

        net = {}
        loss_location = {}
        for line in out_lines:
            lot = line.lot_id
            net[lot] = net.get(lot, 0.0) + (line.quantity or 0.0)
            loss_location.setdefault(lot, line.location_dest_id)
        for line in in_lines:
            lot = line.lot_id
            net[lot] = net.get(lot, 0.0) - (line.quantity or 0.0)

        reclassified = self._walkthrough_reclassified_lot_ids(
            [lot.id for lot in net])

        aggregates = {}
        for lot, qty in net.items():
            if qty <= 0.0001 or lot.id in reclassified:
                continue
            location = loss_location.get(lot)
            if not location:
                continue
            aggregates[(lot, location)] = qty
        return aggregates

    @api.model
    def _walkthrough_ensure_quant(self, lot, location):
        """Garantiza un stock.quant (aunque esté en cero) para usarlo como
        detail.id: el cron de vacuum borra los quants en cero, y el quant de
        la ubicación de desecho puede quedar neto en cero (ver docstring del
        módulo). Un quant en cero no afecta existencias."""
        Quant = self.sudo().with_context(active_test=False)
        quant = Quant.search([
            ('lot_id', '=', lot.id),
            ('location_id', '=', location.id),
        ], limit=1)
        if not quant:
            quant = Quant.create({
                'product_id': lot.product_id.id,
                'lot_id': lot.id,
                'location_id': location.id,
                'quantity': 0.0,
            })
        return quant

    # ------------------------------------------------------------------
    # Agrupación por producto
    # ------------------------------------------------------------------

    @api.model
    def get_walkthrough_grouped_by_product(self, filters=None):
        filters = filters or {}
        common_domain, missing_lots = self._walkthrough_common_filters(filters)

        # Entregas: quants positivos en ubicación de cliente.
        delivered_quants = self.sudo().search([
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('location_id.usage', '=', 'customer'),
        ] + list(common_domain), order='product_id, lot_id, id')

        # Bajas: movimientos de stock.scrap.
        scrap_aggregates = self._walkthrough_scrap_aggregates(common_domain)

        # Bajas por AJUSTE de inventario (sin scrap): también son salidas
        # y deben quedar registradas en el Walkthrough.
        for key, qty in self._walkthrough_adjustment_aggregates(
                common_domain).items():
            scrap_aggregates[key] = scrap_aggregates.get(key, 0.0) + qty

        # Consumidas en TALLER: placas que entraron como ingrediente a una OT
        # ya terminada (corte / cambio de acabado). Odoo deja su quant en la
        # ubicación de producción; aquí se listan como salida "consumida en
        # taller" y desaparecen del Inventario Visual.
        workshop_quants = self.sudo().search([
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('location_id.usage', '=', 'production'),
        ] + list(common_domain), order='product_id, lot_id, id')
        consumed_lot_ids = self._iv_get_workshop_consumed_lot_ids(
            workshop_quants.mapped('lot_id').ids)
        workshop_quants = workshop_quants.filtered(lambda q: q.lot_id.id in consumed_lot_ids)

        # Excluir lotes que siguen teniendo stock (devoluciones/entregas
        # parciales: mientras quede material, viven en el Inventario Visual).
        all_lot_ids = set(delivered_quants.mapped('lot_id').ids)
        all_lot_ids.update(lot.id for (lot, _loc) in scrap_aggregates)
        all_lot_ids.update(workshop_quants.mapped('lot_id').ids)
        lots_alive = self._walkthrough_lots_with_current_stock(all_lot_ids)

        # Entradas normalizadas: (quant, lot, qty, kind).
        entries = []
        for quant in delivered_quants:
            if quant.lot_id.id in lots_alive:
                continue
            entries.append((quant, quant.lot_id, quant.quantity or 0.0, 'delivery'))
        for (lot, location), qty in scrap_aggregates.items():
            if lot.id in lots_alive or qty <= 0:
                continue
            quant = self._walkthrough_ensure_quant(lot, location)
            entries.append((quant, lot, qty, 'scrap'))
        for quant in workshop_quants:
            if quant.lot_id.id in lots_alive:
                continue
            entries.append((quant, quant.lot_id, quant.quantity or 0.0, 'workshop'))

        product_groups = {}
        for quant, lot, qty, kind in entries:
            product = lot.product_id
            group = product_groups.setdefault(product.id, {
                'product': product,
                'entries': [],
            })
            group['entries'].append((quant, lot, qty, kind))

        # Cant. mínima por bloque (sobre lo que salió, espejo del filtro
        # del Inventario Visual).
        min_block = filters.get('cantidad_min_bloque')
        if min_block:
            try:
                min_block_val = float(min_block)
            except (ValueError, TypeError):
                min_block_val = 0.0
            if min_block_val > 0:
                for pid in list(product_groups):
                    group = product_groups[pid]
                    block_sums = {}
                    for _q, lot, qty, _k in group['entries']:
                        block = getattr(lot, 'x_bloque', '') or 'Sin Bloque'
                        block_sums[block] = block_sums.get(block, 0.0) + qty
                    kept = [
                        e for e in group['entries']
                        if block_sums.get(
                            getattr(e[1], 'x_bloque', '') or 'Sin Bloque', 0.0
                        ) >= min_block_val
                    ]
                    if not kept:
                        del product_groups[pid]
                    else:
                        group['entries'] = kept

        # Rango de precios: reutiliza el helper del Inventario Visual.
        product_groups = self._filter_products_by_price(product_groups, filters)

        products = []
        for pid, group in product_groups.items():
            product = group['product']
            group_entries = group['entries']
            first_lot = group_entries[0][1] if group_entries else None
            delivered = [e for e in group_entries if e[3] == 'delivery']
            scrapped = [e for e in group_entries if e[3] == 'scrap']
            consumed = [e for e in group_entries if e[3] == 'workshop']
            products.append({
                'workshop_qty': sum(e[2] for e in consumed),
                'workshop_plates': len(consumed),
                'product_id': pid,
                'product_name': product.display_name,
                'product_code': product.default_code or '',
                'categ_name': product.categ_id.complete_name or '',
                'tipo': (getattr(first_lot, 'x_tipo', '') or '') if first_lot else '',
                'color': (getattr(first_lot, 'x_color', '') or '') if first_lot else '',
                'quant_ids': [e[0].id for e in group_entries],
                'out_qty': sum(e[2] for e in group_entries),
                'out_plates': len(group_entries),
                'delivered_qty': sum(e[2] for e in delivered),
                'delivered_plates': len(delivered),
                'scrapped_qty': sum(e[2] for e in scrapped),
                'scrapped_plates': len(scrapped),
            })

        products.sort(key=lambda p: p['product_name'] or '')

        return {'products': products, 'missing_lots': missing_lots}

    # ------------------------------------------------------------------
    # Detalles por quant (reutiliza get_quant_details + datos de salida)
    # ------------------------------------------------------------------

    @api.model
    def get_walkthrough_details(self, quant_ids):
        # iv_keep_workshop_consumed: aquí SÍ queremos los quants de producción
        # de placas consumidas (el Inventario Visual los descarta).
        details = self.with_context(iv_keep_workshop_consumed=True).get_quant_details(quant_ids=quant_ids)
        if not isinstance(details, list):
            return details

        quants = {
            q.id: q
            for q in self.sudo().with_context(active_test=False)
            .browse(quant_ids).exists()
        }
        MoveLine = self.env['stock.move.line'].sudo()
        has_writeoff = 'stock.lot.writeoff.line' in self.env

        for detail in details:
            quant = quants.get(detail.get('id'))
            if not quant:
                continue

            is_scrap = quant.location_id.usage == 'inventory'
            is_workshop = quant.location_id.usage == 'production'
            detail['exit_type'] = 'workshop' if is_workshop else ('scrap' if is_scrap else 'delivery')
            if is_workshop:
                # Consumida en taller: ya no está "en taller", se usó.
                detail['en_taller'] = False
                detail['reserved_quantity'] = 0.0

            out_domain = [
                ('lot_id', '=', quant.lot_id.id),
                ('location_dest_id', '=', quant.location_id.id),
                ('state', '=', 'done'),
            ]
            if is_scrap:
                # El documento y la CANTIDAD de la baja salen del movimiento
                # de stock.scrap: el quant de la ubicación de desecho puede
                # estar neto en cero (comparte ubicación con los ajustes).
                out_domain.append(('move_id.scrap_id', '!=', False))
                scrap_lines = MoveLine.search(
                    out_domain, order='date desc, id desc')
                if scrap_lines:
                    detail['quantity'] = sum(
                        line.quantity or 0.0 for line in scrap_lines)
                else:
                    # Baja por AJUSTE de inventario (sin stock.scrap): la
                    # cantidad es el NETO de los ajustes contra esta
                    # ubicación (salidas menos regresos).
                    adj_base = [
                        ('lot_id', '=', quant.lot_id.id),
                        ('state', '=', 'done'),
                        ('move_id.scrap_id', '=', False),
                    ]
                    adj_out = MoveLine.search(adj_base + [
                        ('location_dest_id', '=', quant.location_id.id),
                    ], order='date desc, id desc')
                    adj_in = MoveLine.search(adj_base + [
                        ('location_id', '=', quant.location_id.id),
                    ])
                    detail['quantity'] = (
                        sum(line.quantity or 0.0 for line in adj_out)
                        - sum(line.quantity or 0.0 for line in adj_in))
                    scrap_lines = adj_out
                detail['reserved_quantity'] = 0.0
                last_out = scrap_lines[:1]
            else:
                last_out = MoveLine.search(
                    out_domain, order='date desc, id desc', limit=1)

            detail['exit_date'] = (
                last_out.date.strftime('%Y-%m-%d') if last_out and last_out.date else ''
            )
            exit_doc = ''
            exit_partner = ''
            if last_out:
                picking = last_out.picking_id
                exit_doc = (picking and picking.name) or last_out.reference or ''
                if picking and picking.partner_id:
                    exit_partner = picking.partner_id.display_name
                elif last_out.move_id.origin:
                    exit_doc = '%s (%s)' % (exit_doc, last_out.move_id.origin) \
                        if exit_doc else last_out.move_id.origin

            # Si la salida fue una Baja de Material, mostrar folio y motivo.
            if is_scrap and has_writeoff:
                wo_line = self.env['stock.lot.writeoff.line'].sudo().search([
                    ('lot_from_id', '=', quant.lot_id.id),
                    ('writeoff_id.state', '=', 'done'),
                ], order='id desc', limit=1)
                if wo_line:
                    rec = wo_line.writeoff_id
                    reason_label = dict(
                        rec._fields['reason_type'].selection
                    ).get(rec.reason_type, rec.reason_type or '')
                    exit_doc = rec.name
                    exit_partner = reason_label

            # Consumida en taller: folio de la OT y proceso como "motivo".
            if is_workshop and 'workshop.input.line' in self.env:
                wline = self.env['workshop.input.line'].sudo().search([
                    ('lot_id', '=', quant.lot_id.id),
                    ('is_consumed', '=', True),
                    ('order_id.state', '=', 'done'),
                ], order='id desc', limit=1)
                if wline:
                    order = wline.order_id
                    process = ''
                    if 'process_id' in order._fields and order.process_id:
                        process = order.process_id.display_name
                    exit_doc = order.name
                    exit_partner = 'Consumida en taller' + (' · %s' % process if process else '')
                    if 'date_done' in order._fields and order.date_done:
                        detail['exit_date'] = fields.Date.to_string(
                            fields.Date.context_today(self, order.date_done))
                    outputs = order.output_line_ids.filtered(lambda o: o.lot_id) \
                        if 'output_line_ids' in order._fields else False
                    if outputs:
                        detail['workshop_outputs'] = ', '.join(outputs.mapped('lot_id.name'))

            detail['exit_doc'] = exit_doc
            detail['exit_partner'] = exit_partner

        return details
