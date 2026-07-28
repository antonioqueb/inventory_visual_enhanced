# -*- coding: utf-8 -*-
"""Walkthrough: inventario que YA SALIÓ del stock.

Espejo del Inventario Visual pero sobre las salidas correctas:
- Entregas a cliente (quants en ubicaciones usage='customer').
- Bajas de material / desecho (quants en ubicaciones scrap_location=True).

La clave del diseño: un lote entregado o dado de baja conserva quants con
cantidad positiva en la ubicación de cliente/desecho (partida doble de
Odoo), así que el detail.id sigue siendo un stock.quant real y TODA la
cadena existente (get_quant_details, get_lot_history, get_lot_photos,
get_lot_notes, save_lot_notes) funciona sin cambios.

Quedan fuera a propósito:
- Lotes que aún tienen existencias en internal/transit/production (eso es
  el Inventario Visual, no el Walkthrough).
- Lotes reclasificados: su salida fue un ajuste de inventario (usage
  'inventory' sin scrap_location), no una salida real; el material sigue
  existiendo en el lote espejo.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class StockQuantWalkthrough(models.Model):
    _inherit = 'stock.quant'

    # ------------------------------------------------------------------
    # Dominio base y filtros
    # ------------------------------------------------------------------

    @api.model
    def _walkthrough_field_exists(self, model, field_name):
        return field_name in self.env[model]._fields

    @api.model
    def _walkthrough_base_domain(self):
        # Odoo 19 eliminó el booleano scrap_location: el desecho es una
        # ubicación usage='inventory' (mismo usage que las pérdidas por
        # ajuste). El filtrado fino se hace en
        # _walkthrough_filter_proper_exits vía move.scrap_id.
        return [
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
            ('location_id.usage', 'in', ['customer', 'inventory']),
        ]

    @api.model
    def _walkthrough_filter_proper_exits(self, quants):
        """Solo salidas por proceso correcto.

        Los quants en ubicaciones usage='inventory' mezclan dos orígenes que
        Odoo 19 ya no distingue por ubicación: bajas reales (stock.scrap →
        move.scrap_id) y ajustes de inventario (move.is_inventory, p. ej. la
        reclasificación al vaciar el lote origen). Solo las primeras son
        salidas correctas; las segundas quedan fuera del Walkthrough."""
        inv_quants = quants.filtered(lambda q: q.location_id.usage == 'inventory')
        if not inv_quants:
            return quants
        scrap_lines = self.env['stock.move.line'].sudo().search_read([
            ('lot_id', 'in', inv_quants.mapped('lot_id').ids),
            ('location_dest_id', 'in', inv_quants.mapped('location_id').ids),
            ('state', '=', 'done'),
            ('move_id.scrap_id', '!=', False),
        ], ['lot_id', 'location_dest_id'])
        scrapped_pairs = {
            (line['lot_id'][0], line['location_dest_id'][0])
            for line in scrap_lines
        }
        return quants.filtered(
            lambda q: q.location_id.usage == 'customer'
            or (q.lot_id.id, q.location_id.id) in scrapped_pairs
        )

    @api.model
    def _walkthrough_apply_filters(self, domain, filters):
        """Réplica de los filtros del Inventario Visual que tienen sentido
        sin stock actual. almacen_id / ubicacion_id / stock_mode se ignoran
        (el material ya no está en un almacén)."""
        filters = filters or {}
        Lot = self.env['stock.lot']
        Tmpl = self.env['product.template']
        missing_lots = []

        if filters.get('product_name'):
            domain.append(('product_id', 'ilike', filters['product_name']))

        if filters.get('categoria_name'):
            domain.append((
                'product_id.categ_id.complete_name', 'ilike',
                filters['categoria_name'],
            ))

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
                domain.append(('lot_id.%s' % lot_field, op, value))

        if filters.get('grosor') and self._walkthrough_field_exists(
                'stock.lot', 'x_grosor'):
            try:
                domain.append(('lot_id.x_grosor', '=', float(filters['grosor'])))
            except (ValueError, TypeError):
                pass

        for filter_key, lot_field in (('alto_min', 'x_alto'), ('ancho_min', 'x_ancho')):
            value = filters.get(filter_key)
            if value and self._walkthrough_field_exists('stock.lot', lot_field):
                try:
                    domain.append(('lot_id.%s' % lot_field, '>=', float(value)))
                except (ValueError, TypeError):
                    pass

        if filters.get('numero_serie'):
            raw = str(filters['numero_serie'])
            names = [n.strip() for n in raw.split(',') if n.strip()]
            if len(names) > 1:
                domain.append(('lot_id.name', 'in', names))
                found = set(
                    Lot.sudo().with_context(active_test=False)
                    .search([('name', 'in', names)]).mapped('name')
                )
                missing_lots = [n for n in names if n not in found]
            elif names:
                domain.append(('lot_id.name', 'ilike', names[0]))

        return domain, missing_lots

    # ------------------------------------------------------------------
    # Agrupación por producto
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
                ('location_id.usage', 'in', ['internal', 'transit', 'production']),
            ],
            ['lot_id'],
            ['lot_id'],
        )
        return {g['lot_id'][0] for g in groups if g.get('lot_id')}

    @api.model
    def get_walkthrough_grouped_by_product(self, filters=None):
        filters = filters or {}
        domain = self._walkthrough_base_domain()
        domain, missing_lots = self._walkthrough_apply_filters(domain, filters)

        quants = self.sudo().search(domain, order='product_id, lot_id, id')

        # Excluir lotes que siguen teniendo stock (devoluciones parciales,
        # entregas parciales: mientras quede material, viven en el
        # Inventario Visual).
        lots_alive = self._walkthrough_lots_with_current_stock(
            set(quants.mapped('lot_id').ids))
        quants = quants.filtered(lambda q: q.lot_id.id not in lots_alive)

        # Solo entregas y bajas reales (stock.scrap); los ajustes de
        # inventario no son salidas correctas.
        quants = self._walkthrough_filter_proper_exits(quants)

        product_groups = {}
        for quant in quants:
            product = quant.product_id
            group = product_groups.setdefault(product.id, {
                'product': product,
                'quants': [],
                'out_qty': 0.0,
                'out_plates': 0,
                'delivered_qty': 0.0,
                'delivered_plates': 0,
                'scrapped_qty': 0.0,
                'scrapped_plates': 0,
            })
            qty = quant.quantity or 0.0
            group['quants'].append(quant)
            group['out_qty'] += qty
            group['out_plates'] += 1
            if quant.location_id.usage == 'customer':
                group['delivered_qty'] += qty
                group['delivered_plates'] += 1
            else:
                group['scrapped_qty'] += qty
                group['scrapped_plates'] += 1

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
                    for quant in group['quants']:
                        block = getattr(quant.lot_id, 'x_bloque', '') or 'Sin Bloque'
                        block_sums[block] = block_sums.get(block, 0.0) + (quant.quantity or 0.0)
                    kept = [
                        q for q in group['quants']
                        if block_sums.get(
                            getattr(q.lot_id, 'x_bloque', '') or 'Sin Bloque', 0.0
                        ) >= min_block_val
                    ]
                    if not kept:
                        del product_groups[pid]
                        continue
                    self._walkthrough_regroup(group, kept)

        # Rango de precios: reutiliza el helper del Inventario Visual.
        product_groups = self._filter_products_by_price(product_groups, filters)

        products = []
        for pid, group in product_groups.items():
            product = group['product']
            first_lot = group['quants'][0].lot_id if group['quants'] else None
            products.append({
                'product_id': pid,
                'product_name': product.display_name,
                'product_code': product.default_code or '',
                'categ_name': product.categ_id.complete_name or '',
                'tipo': (getattr(first_lot, 'x_tipo', '') or '') if first_lot else '',
                'color': (getattr(first_lot, 'x_color', '') or '') if first_lot else '',
                'quant_ids': [q.id for q in group['quants']],
                'out_qty': group['out_qty'],
                'out_plates': group['out_plates'],
                'delivered_qty': group['delivered_qty'],
                'delivered_plates': group['delivered_plates'],
                'scrapped_qty': group['scrapped_qty'],
                'scrapped_plates': group['scrapped_plates'],
            })

        products.sort(key=lambda p: p['product_name'] or '')

        return {'products': products, 'missing_lots': missing_lots}

    @api.model
    def _walkthrough_regroup(self, group, kept_quants):
        group['quants'] = kept_quants
        group['out_qty'] = sum(q.quantity or 0.0 for q in kept_quants)
        group['out_plates'] = len(kept_quants)
        delivered = [q for q in kept_quants if q.location_id.usage == 'customer']
        scrapped = [q for q in kept_quants if q.location_id.usage != 'customer']
        group['delivered_qty'] = sum(q.quantity or 0.0 for q in delivered)
        group['delivered_plates'] = len(delivered)
        group['scrapped_qty'] = sum(q.quantity or 0.0 for q in scrapped)
        group['scrapped_plates'] = len(scrapped)

    # ------------------------------------------------------------------
    # Detalles por quant (reutiliza get_quant_details + datos de salida)
    # ------------------------------------------------------------------

    @api.model
    def get_walkthrough_details(self, quant_ids):
        details = self.get_quant_details(quant_ids=quant_ids)
        if not isinstance(details, list):
            return details

        quants = {q.id: q for q in self.sudo().browse(quant_ids).exists()}
        MoveLine = self.env['stock.move.line'].sudo()
        has_writeoff = 'stock.lot.writeoff.line' in self.env

        for detail in details:
            quant = quants.get(detail.get('id'))
            if not quant:
                continue

            is_scrap = quant.location_id.usage == 'inventory'
            detail['exit_type'] = 'scrap' if is_scrap else 'delivery'

            out_domain = [
                ('lot_id', '=', quant.lot_id.id),
                ('location_dest_id', '=', quant.location_id.id),
                ('state', '=', 'done'),
            ]
            if is_scrap:
                # Odoo 19: la ubicación de desecho comparte usage con las
                # pérdidas por ajuste; el documento de salida correcto es el
                # movimiento de stock.scrap.
                out_domain.append(('move_id.scrap_id', '!=', False))
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

            detail['exit_doc'] = exit_doc
            detail['exit_partner'] = exit_partner

        return details
