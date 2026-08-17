# -*- coding: utf-8 -*-
"""Crear lotes de formato desde Ajustes de Formatos.

Alta directa de lotes con control de SERIE (prefijo + consecutivo +
dígitos) y los atributos que normalmente se capturan en recepción
(bloque/tono, grosor, contenedor, pedimento, ref. proveedor, fecha).
Cada lote nace con su quant en la ubicación elegida: si trae cantidad,
se aplica como ajuste de inventario (trazable); con cantidad 0 el quant
queda listo para capturar la contada en la lista y Aplicar.
"""
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SomFormatoLotCreate(models.TransientModel):
    _name = 'som.formato.lot.create'
    _description = 'Crear lotes de formato'

    product_id = fields.Many2one(
        'product.product', string='Producto', required=True,
        domain="[('product_tmpl_id.x_unidad_del_producto', '=ilike', 'formato')]")
    location_id = fields.Many2one(
        'stock.location', string='Ubicación', required=True,
        domain="[('usage', '=', 'internal')]")
    qty_per_lot = fields.Float(
        string='Cantidad por lote', digits='Product Unit of Measure',
        help='Cantidad a la mano con la que nace cada lote (se aplica como '
             'ajuste de inventario). Con 0 el lote se crea sin existencia y '
             'la cantidad se captura después en la lista.')

    prefix = fields.Char(
        string='Serie / prefijo',
        help='Prefijo de la serie, p. ej. T26 → T26-01, T26-02… '
             'Vacío = solo el número.')
    next_number = fields.Integer(string='Número inicial', default=1, required=True)
    padding = fields.Integer(string='Dígitos', default=2, required=True)
    lot_count = fields.Integer(string='Lotes a crear', default=1, required=True)
    name_preview = fields.Char(
        string='Se crearán', compute='_compute_name_preview')

    x_bloque = fields.Char(string='Bloque/Tono')
    x_grosor = fields.Char(string='Grosor (cm)')
    x_fecha_lote = fields.Date(string='Fecha de lote')
    x_contenedor = fields.Char(string='Contenedor')
    x_pedimento = fields.Char(string='Pedimento')
    x_referencia_proveedor = fields.Char(string='Ref. Proveedor')

    def _format_name(self, number):
        pad = max(int(self.padding or 1), 1)
        num = '%0*d' % (pad, int(number))
        prefix = (self.prefix or '').strip()
        return '%s-%s' % (prefix, num) if prefix else num

    @api.depends('prefix', 'next_number', 'padding', 'lot_count')
    def _compute_name_preview(self):
        for wiz in self:
            count = max(int(wiz.lot_count or 0), 0)
            if not count or not wiz.next_number:
                wiz.name_preview = ''
                continue
            first = wiz._format_name(wiz.next_number)
            if count == 1:
                wiz.name_preview = first
            else:
                last = wiz._format_name(wiz.next_number + count - 1)
                wiz.name_preview = '%s … %s (%s lotes)' % (first, last, count)

    @api.onchange('prefix', 'product_id')
    def _onchange_suggest_next_number(self):
        """Sugiere el consecutivo siguiente de la serie para el producto:
        busca los lotes existentes que siguen el patrón y continúa."""
        for wiz in self:
            if not wiz.product_id:
                continue
            prefix = (wiz.prefix or '').strip()
            domain = [('product_id', '=', wiz.product_id.id)]
            if prefix:
                domain.append(('name', '=like', prefix + '-%'))
            lots = self.env['stock.lot'].with_context(
                active_test=False).search(domain, order='id desc', limit=1000)
            pattern = (
                re.compile(r'^%s-(\d+)$' % re.escape(prefix))
                if prefix else re.compile(r'^(\d+)$')
            )
            best = 0
            for lot in lots:
                match = pattern.match(lot.name or '')
                if match:
                    best = max(best, int(match.group(1)))
            wiz.next_number = best + 1

    def action_create_lots(self):
        self.ensure_one()

        if self.lot_count <= 0:
            raise UserError(_('Indica cuántos lotes crear.'))
        if self.lot_count > 500:
            raise UserError(_('Máximo 500 lotes por corrida.'))
        if self.next_number <= 0:
            raise UserError(_('El número inicial debe ser mayor a cero.'))
        if self.qty_per_lot < 0:
            raise UserError(_('La cantidad por lote no puede ser negativa.'))

        names = [
            self._format_name(self.next_number + i)
            for i in range(self.lot_count)
        ]
        existing = self.env['stock.lot'].with_context(active_test=False).search([
            ('product_id', '=', self.product_id.id),
            ('name', 'in', names),
        ])
        if existing:
            raise UserError(_(
                'Estos nombres de lote ya existen para el producto:\n%s\n\n'
                'Ajusta la serie o el número inicial.'
            ) % ', '.join(sorted(existing.mapped('name'))))

        company = self.env.company
        Lot = self.env['stock.lot']
        lot_vals_list = []
        for name in names:
            vals = {
                'name': name,
                'product_id': self.product_id.id,
                'company_id': company.id,
            }
            if 'x_tipo' in Lot._fields:
                vals['x_tipo'] = 'formato'
            for fname in ('x_bloque', 'x_grosor', 'x_fecha_lote',
                          'x_contenedor', 'x_pedimento',
                          'x_referencia_proveedor'):
                value = self[fname]
                if value and fname in Lot._fields:
                    vals[fname] = value
            lot_vals_list.append(vals)

        lots = Lot.create(lot_vals_list)

        Quant = self.env['stock.quant'].with_context(inventory_mode=True)
        for lot in lots:
            quant = Quant.create({
                'product_id': self.product_id.id,
                'lot_id': lot.id,
                'location_id': self.location_id.id,
                'inventory_quantity': self.qty_per_lot or 0.0,
            })
            if self.qty_per_lot > 0:
                quant.action_apply_inventory()

        # Regresa a Ajustes de Formatos mostrando SOLO lo recién creado.
        action = self.env['ir.actions.act_window']._for_xml_id(
            'inventory_visual_enhanced.action_formato_adjustments')
        action['domain'] = [('lot_id', 'in', lots.ids)]
        action['context'] = {'inventory_mode': True}
        return action
