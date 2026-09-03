# -*- coding: utf-8 -*-
"""Custodia de terceros — vista NATIVA (lista / pivote / gráfica).

`inventory.custody.line` es una vista SQL (una fila por placa asignada a una
orden confirmada que sigue en una ubicación interna) con el mismo criterio
que el tablero (stock_quant_custody.py): estado (asignada / pagada / pagada
+ autorizada / autorizada sin pago), fecha desde la que el material dejó de
ser mío y días en custodia. Se filtra, agrupa y pivotea como cualquier
modelo de Odoo.

`inventory.custody.zone` = BODEGA (tercer nivel de la ubicación), con
`sequence` numérica para que las agrupaciones salgan en orden natural
(BODEGA 1, 2, 3 … y no 1, 10, 2).
"""
import re

from odoo import api, fields, models, tools

STATUS_SELECTION = [
    ('paid_auth', 'Pagada + autorizada'),
    ('paid', 'Pagada'),
    ('auth', 'Autorizada sin pago'),
    ('assigned', 'Asignada'),
]
BUCKET_SELECTION = [
    ('b0', '0-7 días'), ('b1', '8-15 días'), ('b2', '16-30 días'),
    ('b3', '31-60 días'), ('b4', '61-90 días'), ('b5', 'más de 90 días'),
]


class InventoryCustodyZone(models.Model):
    _name = 'inventory.custody.zone'
    _description = 'Bodega (ubicación padre) para custodia'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=999, index=True)
    location_id = fields.Many2one('stock.location', string='Ubicación')

    _name_uniq = models.Constraint('unique(name)', 'La bodega ya existe.')

    @api.model
    def _som_refresh_from_locations(self):
        """Crea/actualiza una bodega por cada tercer nivel de ubicación
        interna (y por las internas sin tercer nivel). Idempotente."""
        self.env.cr.execute("""
            SELECT DISTINCT
                   COALESCE(NULLIF(split_part(loc.complete_name, '/', 3), ''), loc.complete_name) AS zone,
                   MIN(loc.id) AS location_id
              FROM stock_location loc
             WHERE loc.usage = 'internal' AND loc.active
             GROUP BY zone
        """)
        rows = self.env.cr.fetchall()
        existing = {z.name: z for z in self.sudo().search([])}
        for name, location_id in rows:
            m = re.search(r'(\d+)', name or '')
            seq = int(m.group(1)) if m else 999
            zone = existing.get(name)
            vals = {'sequence': seq, 'location_id': location_id}
            if zone:
                if zone.sequence != seq or zone.location_id.id != location_id:
                    zone.sudo().write(vals)
            else:
                self.sudo().create(dict(vals, name=name))
        return True


class InventoryCustodyLine(models.Model):
    _name = 'inventory.custody.line'
    _description = 'Placa en custodia (material vendido en almacén)'
    _auto = False
    _order = 'days desc, lot_name'
    _rec_name = 'lot_name'

    lot_id = fields.Many2one('stock.lot', string='Lote', readonly=True)
    lot_name = fields.Char(string='Lote', readonly=True)
    product_id = fields.Many2one('product.product', string='Material', readonly=True)
    mask_name = fields.Char(string='Descripción comercial', readonly=True)
    block = fields.Char(string='Bloque', readonly=True)
    thickness = fields.Char(string='Grosor', readonly=True)
    largo = fields.Float(string='Largo (m)', readonly=True, digits=(12, 2))
    alto = fields.Float(string='Alto (m)', readonly=True, digits=(12, 2))
    zone_id = fields.Many2one('inventory.custody.zone', string='Bodega', readonly=True)
    location_id = fields.Many2one('stock.location', string='Ubicación', readonly=True)
    qty = fields.Float(string='m²', readonly=True, digits=(12, 2), aggregator='sum')
    value = fields.Monetary(string='Valor', readonly=True, currency_field='currency_id', aggregator='sum')
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    order_id = fields.Many2one('sale.order', string='Orden', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    user_id = fields.Many2one('res.users', string='Vendedor', readonly=True)
    project_id = fields.Many2one('project.project', string='Proyecto', readonly=True)
    status = fields.Selection(STATUS_SELECTION, string='Estado', readonly=True)
    paid_pct = fields.Float(string='Pagado %', readonly=True, digits=(5, 1), aggregator='avg')
    paid_date = fields.Date(string='Fecha de pago', readonly=True)
    auth_date = fields.Date(string='Fecha de autorización', readonly=True)
    assigned_date = fields.Date(string='Fecha de asignación', readonly=True)
    base_date = fields.Date(string='En custodia desde', readonly=True,
                            help='Fecha desde la que el material dejó de ser mío: pago, autorización de entrega '
                                 '(la más antigua si hay ambas) o, si solo está asignada, la asignación.')
    days = fields.Integer(string='Días en custodia', readonly=True, aggregator='avg')
    m2_days = fields.Float(string='m²·día', readonly=True, digits=(14, 1), aggregator='sum',
                           help='m² multiplicados por días en custodia: peso real del almacenamiento.')
    bucket = fields.Selection(BUCKET_SELECTION, string='Antigüedad', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)

    def init(self):
        self.env['inventory.custody.zone']._som_refresh_from_locations()
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
            WITH base AS (
                SELECT q.lot_id, q.product_id, sol.id AS line_id, so.id AS order_id, so.company_id,
                       q.location_id,
                       COALESCE(NULLIF(split_part(loc.complete_name, '/', 3), ''), loc.complete_name) AS zone_name,
                       SUM(q.quantity) AS qty
                  FROM stock_quant q
                  JOIN stock_location loc ON loc.id = q.location_id AND loc.usage = 'internal'
                  JOIN sale_order_line_stock_lot_rel rel ON rel.stock_lot_id = q.lot_id
                  JOIN sale_order_line sol ON sol.id = rel.sale_order_line_id
                  JOIN sale_order so ON so.id = sol.order_id AND so.state = 'sale'
                 WHERE q.quantity > 0 AND q.lot_id IS NOT NULL
                 GROUP BY q.lot_id, q.product_id, sol.id, so.id, so.company_id, q.location_id, loc.complete_name
            ),
            paid AS (
                SELECT so.id AS order_id,
                       MAX(CASE WHEN d.id = rl.id THEN c.date ELSE d.date END) AS d
                  FROM sale_order so
                  JOIN sale_order_line sol ON sol.order_id = so.id
                  JOIN sale_order_line_invoice_rel r ON r.order_line_id = sol.id
                  JOIN account_move_line il ON il.id = r.invoice_line_id
                  JOIN account_move am ON am.id = il.move_id AND am.state = 'posted' AND am.move_type = 'out_invoice'
                  JOIN account_move_line rl ON rl.move_id = am.id
                  JOIN account_account aa ON aa.id = rl.account_id AND aa.account_type = 'asset_receivable'
                  JOIN account_partial_reconcile apr ON apr.debit_move_id = rl.id OR apr.credit_move_id = rl.id
                  JOIN account_move_line d ON d.id = apr.debit_move_id
                  JOIN account_move_line c ON c.id = apr.credit_move_id
                 WHERE so.state = 'sale'
                 GROUP BY so.id
            ),
            auth_req AS (
                SELECT sale_order_id AS order_id, MAX(COALESCE(approval_date, write_date))::date AS d
                  FROM delivery_auth_request WHERE state = 'approved' GROUP BY sale_order_id
            ),
            auth_trk AS (
                SELECT mm.res_id AS order_id, MAX(mm.date)::date AS d
                  FROM mail_tracking_value tv
                  JOIN mail_message mm ON mm.id = tv.mail_message_id
                  JOIN ir_model_fields f ON f.id = tv.field_id
                 WHERE f.model = 'sale.order' AND f.name = 'delivery_auth_manual_authorized'
                   AND tv.new_value_integer = 1 AND mm.model = 'sale.order'
                 GROUP BY mm.res_id
            ),
            assign AS (
                SELECT lot_id, document_name, MAX(date)::date AS d
                  FROM stock_lot_assignment_log WHERE action = 'assign'
                 GROUP BY lot_id, document_name
            ),
            calc AS (
                SELECT b.*, z.id AS zone_id,
                       so.partner_id, so.user_id, so.x_project_id AS project_id, so.currency_id,
                       so.amount_total, so.delivery_paid_amount,
                       sol.price_unit, COALESCE(sol.discount, 0) AS discount, sol.x_mask_name,
                       (so.delivery_is_fully_paid IS TRUE) AS is_paid,
                       (so.delivery_auth_manual_authorized IS TRUE OR so.delivery_auth_state = 'authorized') AS is_auth,
                       CASE WHEN so.delivery_is_fully_paid IS TRUE THEN paid.d END AS paid_date,
                       CASE WHEN (so.delivery_auth_manual_authorized IS TRUE OR so.delivery_auth_state = 'authorized')
                            THEN COALESCE(ar.d, atk.d) END AS auth_date,
                       COALESCE(asg.d, so.date_order::date) AS assigned_date,
                       COALESCE((SELECT rr.rate FROM res_currency_rate rr
                                  WHERE rr.currency_id = so.currency_id
                                    AND (rr.company_id = so.company_id OR rr.company_id IS NULL)
                                    AND rr.name <= CURRENT_DATE
                                  ORDER BY rr.name DESC LIMIT 1), 1.0) AS rate,
                       (so.currency_id = rc.currency_id) AS same_currency
                  FROM base b
                  JOIN sale_order so ON so.id = b.order_id
                  JOIN sale_order_line sol ON sol.id = b.line_id
                  JOIN res_company rc ON rc.id = b.company_id
                  LEFT JOIN inventory_custody_zone z ON z.name = b.zone_name
                  LEFT JOIN paid ON paid.order_id = so.id
                  LEFT JOIN auth_req ar ON ar.order_id = so.id
                  LEFT JOIN auth_trk atk ON atk.order_id = so.id
                  LEFT JOIN assign asg ON asg.lot_id = b.lot_id AND asg.document_name = so.name
            ),
            final AS (
                SELECT c.*,
                       CASE WHEN c.is_paid AND c.is_auth THEN 'paid_auth'
                            WHEN c.is_paid THEN 'paid'
                            WHEN c.is_auth THEN 'auth'
                            ELSE 'assigned' END AS status,
                       CASE WHEN c.is_paid AND c.is_auth THEN COALESCE(LEAST(c.paid_date, c.auth_date), c.assigned_date)
                            WHEN c.is_paid THEN COALESCE(c.paid_date, c.assigned_date)
                            WHEN c.is_auth THEN COALESCE(c.auth_date, c.assigned_date)
                            ELSE c.assigned_date END AS base_date
                  FROM calc c
            )
            SELECT row_number() OVER (ORDER BY f.lot_id, f.order_id, f.location_id) AS id,
                   f.lot_id, l.name AS lot_name, f.product_id, f.x_mask_name AS mask_name,
                   l.x_bloque AS block, l.x_grosor AS thickness, l.x_ancho AS largo, l.x_alto AS alto,
                   f.zone_id, f.location_id, f.qty,
                   CASE WHEN f.same_currency OR f.rate = 0 THEN f.price_unit * (1 - f.discount / 100.0) * f.qty
                        ELSE f.price_unit * (1 - f.discount / 100.0) * f.qty / f.rate END AS value,
                   rc.currency_id,
                   f.order_id, f.partner_id, f.user_id, f.project_id,
                   f.status,
                   CASE WHEN f.amount_total > 0 THEN ROUND((COALESCE(f.delivery_paid_amount, 0) / f.amount_total * 100)::numeric, 1) ELSE 0 END AS paid_pct,
                   f.paid_date, f.auth_date, f.assigned_date, f.base_date,
                   GREATEST(CURRENT_DATE - f.base_date, 0) AS days,
                   f.qty * GREATEST(CURRENT_DATE - f.base_date, 0) AS m2_days,
                   CASE WHEN CURRENT_DATE - f.base_date <= 7 THEN 'b0'
                        WHEN CURRENT_DATE - f.base_date <= 15 THEN 'b1'
                        WHEN CURRENT_DATE - f.base_date <= 30 THEN 'b2'
                        WHEN CURRENT_DATE - f.base_date <= 60 THEN 'b3'
                        WHEN CURRENT_DATE - f.base_date <= 90 THEN 'b4'
                        ELSE 'b5' END AS bucket,
                   f.company_id
              FROM final f
              JOIN stock_lot l ON l.id = f.lot_id
              JOIN res_company rc ON rc.id = f.company_id
            )
        """ % self._table)

    @api.model
    def action_open_custody(self):
        """Menú: refresca las bodegas (por si nació una nueva) y abre la lista."""
        self.env['inventory.custody.zone']._som_refresh_from_locations()
        action = self.env['ir.actions.act_window']._for_xml_id('inventory_visual_enhanced.action_custody_lines')
        return action

    def action_open_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': self.order_id.id,
            'view_mode': 'form', 'target': 'current',
        }
