# -*- coding: utf-8 -*-
"""Custodia: material vendido que sigue en mi almacén.

Reporte de consulta rápida (Inventario › Custodia de terceros). Responde
"¿qué de mi stock ya no me pertenece y lo sigo almacenando, y desde cuándo?":
placas en ubicaciones internas ASIGNADAS a una orden de venta confirmada,
clasificadas en cuatro estados:

* assigned  — asignada a la orden, sin pago completo ni autorización;
* paid      — pagada al 100 % (delivery_is_fully_paid), sin autorización;
* paid_auth — pagada al 100 % Y con autorización de entrega;
* auth      — NO pagada pero con autorización de entrega.

"Días en custodia" cuenta desde que el material dejó de ser mío: la fecha
del pago que completó el 100 % o la de la autorización de entrega (la más
antigua si hay ambas); para las solo asignadas, desde la asignación.
"""
from collections import defaultdict
from datetime import date, datetime

from odoo import api, fields, models
from odoo.tools.misc import format_date

STATUS_LABELS = {
    'assigned': 'Asignada',
    'paid': 'Pagada',
    'paid_auth': 'Pagada + autorizada',
    'auth': 'Autorizada sin pago',
}
STATUS_ORDER = ['paid_auth', 'paid', 'auth', 'assigned']
AGING_BUCKETS = [
    ('0-7', 0, 7), ('8-15', 8, 15), ('16-30', 16, 30),
    ('31-60', 31, 60), ('61-90', 61, 90), ('90+', 91, 10 ** 6),
]


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _custody_paid_dates(self, order_ids):
        """{order_id: fecha del último cobro aplicado a sus facturas}."""
        if not order_ids:
            return {}
        self.env.cr.execute("""
            SELECT so.id,
                   MAX(CASE WHEN d.id = rl.id THEN c.date ELSE d.date END)
              FROM sale_order so
              JOIN sale_order_line sol ON sol.order_id = so.id
              JOIN sale_order_line_invoice_rel r ON r.order_line_id = sol.id
              JOIN account_move_line il ON il.id = r.invoice_line_id
              JOIN account_move am ON am.id = il.move_id
                   AND am.state = 'posted' AND am.move_type = 'out_invoice'
              JOIN account_move_line rl ON rl.move_id = am.id
              JOIN account_account aa ON aa.id = rl.account_id AND aa.account_type = 'asset_receivable'
              JOIN account_partial_reconcile apr ON apr.debit_move_id = rl.id OR apr.credit_move_id = rl.id
              JOIN account_move_line d ON d.id = apr.debit_move_id
              JOIN account_move_line c ON c.id = apr.credit_move_id
             WHERE so.id IN %s
             GROUP BY so.id
        """, (tuple(order_ids),))
        return dict(self.env.cr.fetchall())

    @api.model
    def _custody_auth_dates(self, order_ids):
        """{order_id: fecha de autorización de entrega}: solicitud aprobada o,
        si se autorizó a mano, la fecha del cambio de la bandera."""
        if not order_ids:
            return {}
        result = {}
        if 'delivery.auth.request' in self.env:
            self.env.cr.execute("""
                SELECT sale_order_id, MAX(COALESCE(approval_date, write_date))
                  FROM delivery_auth_request
                 WHERE state = 'approved' AND sale_order_id IN %s
                 GROUP BY sale_order_id
            """, (tuple(order_ids),))
            result.update(dict(self.env.cr.fetchall()))
        missing = [i for i in order_ids if i not in result]
        if missing:
            self.env.cr.execute("""
                SELECT mm.res_id, MAX(mm.date)
                  FROM mail_tracking_value tv
                  JOIN mail_message mm ON mm.id = tv.mail_message_id
                  JOIN ir_model_fields f ON f.id = tv.field_id
                 WHERE f.model = 'sale.order' AND f.name = 'delivery_auth_manual_authorized'
                   AND tv.new_value_integer = 1
                   AND mm.model = 'sale.order' AND mm.res_id IN %s
                 GROUP BY mm.res_id
            """, (tuple(missing),))
            result.update(dict(self.env.cr.fetchall()))
        return result

    @api.model
    def _custody_assign_dates(self, pairs):
        """{(lot_id, order_name): fecha de asignación} desde la bitácora."""
        if not pairs or 'stock.lot.assignment.log' not in self.env:
            return {}
        lot_ids = tuple({p[0] for p in pairs})
        names = tuple({p[1] for p in pairs})
        self.env.cr.execute("""
            SELECT lot_id, document_name, MAX(date)
              FROM stock_lot_assignment_log
             WHERE action = 'assign' AND lot_id IN %s AND document_name IN %s
             GROUP BY lot_id, document_name
        """, (lot_ids, names))
        return {(r[0], r[1]): r[2] for r in self.env.cr.fetchall()}

    @api.model
    def get_custody_report(self, filters=None):
        filters = filters or {}
        today = fields.Date.context_today(self)
        company_ids = tuple(self.env.companies.ids) or (0,)
        company = self.env.company
        ccur = company.currency_id

        self.env.cr.execute("""
            SELECT q.lot_id, q.product_id, sol.id, so.id,
                   SUM(q.quantity), SUM(q.reserved_quantity),
                   STRING_AGG(DISTINCT loc.complete_name, ' · ')
              FROM stock_quant q
              JOIN stock_location loc ON loc.id = q.location_id AND loc.usage = 'internal'
              JOIN sale_order_line_stock_lot_rel rel ON rel.stock_lot_id = q.lot_id
              JOIN sale_order_line sol ON sol.id = rel.sale_order_line_id
              JOIN sale_order so ON so.id = sol.order_id AND so.state = 'sale'
             WHERE q.quantity > 0 AND q.company_id IN %s AND q.lot_id IS NOT NULL
             GROUP BY q.lot_id, q.product_id, sol.id, so.id
        """, (company_ids,))
        raw = self.env.cr.fetchall()
        if not raw:
            return self._custody_pack([], today, ccur)

        Lot = self.env['stock.lot'].sudo()
        Line = self.env['sale.order.line'].sudo()
        Order = self.env['sale.order'].sudo()
        lots = {l.id: l for l in Lot.browse(list({r[0] for r in raw}))}
        lines = {l.id: l for l in Line.browse(list({r[2] for r in raw}))}
        orders = {o.id: o for o in Order.browse(list({r[3] for r in raw}))}
        order_ids = list(orders)
        paid_dates = self._custody_paid_dates(order_ids)
        auth_dates = self._custody_auth_dates(order_ids)
        assign_dates = self._custody_assign_dates(
            [(r[0], orders[r[3]].name) for r in raw])

        def to_date(value):
            # datetime ES subclase de date: comparar con isinstance(datetime)
            if not value:
                return False
            if isinstance(value, datetime):
                return value.date()
            return value

        rows = []
        for lot_id, product_id, line_id, order_id, qty, reserved, locations in raw:
            lot, line, so = lots.get(lot_id), lines.get(line_id), orders.get(order_id)
            if not (lot and line and so):
                continue
            paid = bool(getattr(so, 'delivery_is_fully_paid', False))
            authorized = bool(getattr(so, 'delivery_auth_manual_authorized', False)) or \
                getattr(so, 'delivery_auth_state', '') == 'authorized'
            if paid and authorized:
                status = 'paid_auth'
            elif paid:
                status = 'paid'
            elif authorized:
                status = 'auth'
            else:
                status = 'assigned'
            paid_date = to_date(paid_dates.get(order_id)) if paid else False
            auth_date = to_date(auth_dates.get(order_id)) if authorized else False
            assigned_date = to_date(assign_dates.get((lot_id, so.name))) or to_date(so.date_order) or today
            if status == 'paid_auth':
                base = min(d for d in (paid_date, auth_date) if d) if (paid_date or auth_date) else assigned_date
            elif status == 'paid':
                base = paid_date or assigned_date
            elif status == 'auth':
                base = auth_date or assigned_date
            else:
                base = assigned_date
            days = max((today - base).days, 0)
            amount_total = so.amount_total or 0.0
            paid_amount = getattr(so, 'delivery_paid_amount', 0.0) or 0.0
            value = (line.price_unit or 0.0) * (1.0 - (line.discount or 0.0) / 100.0) * (qty or 0.0)
            if so.currency_id and so.currency_id != ccur:
                value = so.currency_id._convert(value, ccur, company, today)
            rows.append({
                'lot_id': lot.id,
                'lot': lot.name,
                'block': getattr(lot, 'x_bloque', '') or '',
                'thickness': getattr(lot, 'x_grosor', '') or '',
                'dims': ('%.2f x %.2f' % (lot.x_ancho or 0.0, lot.x_alto or 0.0)
                         if getattr(lot, 'x_ancho', 0) and getattr(lot, 'x_alto', 0) else ''),
                'product_id': product_id,
                'product': (getattr(line, 'x_mask_name', '') or lot.product_id.display_name),
                'order_id': so.id,
                'order': so.name,
                'customer_id': so.partner_id.id,
                'customer': so.partner_id.display_name,
                'salesperson': so.user_id.name or '',
                'project': (so.x_project_id.name if 'x_project_id' in so._fields and so.x_project_id else ''),
                'qty': round(qty or 0.0, 2),
                'reserved': round(reserved or 0.0, 2),
                'locations': locations or '',
                'value': round(value, 2),
                'status': status,
                'status_label': STATUS_LABELS[status],
                'paid': paid,
                'authorized': authorized,
                'paid_pct': round(paid_amount / amount_total * 100.0, 1) if amount_total else 0.0,
                'paid_amount': round(paid_amount, 2),
                'amount_total': round(amount_total, 2),
                'paid_date': format_date(self.env, paid_date, date_format='dd MMM yyyy') if paid_date else '',
                'auth_date': format_date(self.env, auth_date, date_format='dd MMM yyyy') if auth_date else '',
                'assigned_date': format_date(self.env, assigned_date, date_format='dd MMM yyyy') if assigned_date else '',
                'base_date': format_date(self.env, base, date_format='dd MMM yyyy'),
                'base_iso': fields.Date.to_string(base),
                'days': days,
                'bucket': next(k for k, lo, hi in AGING_BUCKETS if lo <= days <= hi),
            })
        return self._custody_pack(rows, today, ccur)

    @api.model
    def _custody_pack(self, rows, today, ccur):
        rows.sort(key=lambda r: (-r['days'], r['order'], r['lot']))

        def bucket():
            return {'plates': 0, 'qty': 0.0, 'value': 0.0, 'days_sum': 0, 'orders': set(), 'customers': set()}

        totals = bucket()
        by_status = {s: bucket() for s in STATUS_ORDER}
        by_aging = {k: {s: bucket() for s in STATUS_ORDER} for k, _lo, _hi in AGING_BUCKETS}
        by_customer = {}
        by_order = {}
        for r in rows:
            for b in (totals, by_status[r['status']], by_aging[r['bucket']][r['status']]):
                b['plates'] += 1
                b['qty'] += r['qty']
                b['value'] += r['value']
                b['days_sum'] += r['days']
                b['orders'].add(r['order_id'])
                b['customers'].add(r['customer_id'])
            c = by_customer.setdefault(r['customer_id'], dict(bucket(), name=r['customer'], max_days=0))
            c['plates'] += 1; c['qty'] += r['qty']; c['value'] += r['value']; c['days_sum'] += r['days']
            c['orders'].add(r['order_id']); c['max_days'] = max(c['max_days'], r['days'])
            o = by_order.setdefault(r['order_id'], {
                'order_id': r['order_id'], 'order': r['order'], 'customer': r['customer'],
                'salesperson': r['salesperson'], 'project': r['project'], 'status': r['status'],
                'status_label': r['status_label'], 'paid_pct': r['paid_pct'], 'paid_amount': r['paid_amount'],
                'amount_total': r['amount_total'], 'paid_date': r['paid_date'], 'auth_date': r['auth_date'],
                'base_date': r['base_date'], 'base_iso': r['base_iso'], 'days': r['days'],
                'plates': 0, 'qty': 0.0, 'value': 0.0, 'products': set(), 'locations': set(), 'lots': [],
            })
            o['plates'] += 1; o['qty'] += r['qty']; o['value'] += r['value']
            o['products'].add(r['product']); o['locations'].update(x.strip() for x in r['locations'].split('·') if x.strip())
            o['days'] = max(o['days'], r['days'])
            o['lots'].append(r)

        def pack(b, extra=None):
            out = {
                'plates': b['plates'], 'qty': round(b['qty'], 2), 'value': round(b['value'], 2),
                'orders': len(b['orders']), 'customers': len(b['customers']),
                'avg_days': round(b['days_sum'] / b['plates'], 1) if b['plates'] else 0.0,
            }
            if extra:
                out.update(extra)
            return out

        orders_out = []
        for o in sorted(by_order.values(), key=lambda x: (-x['days'], x['order'])):
            o['qty'] = round(o['qty'], 2); o['value'] = round(o['value'], 2)
            o['products'] = sorted(o['products']); o['locations'] = sorted(o['locations'])
            o['product_count'] = len(o['products'])
            orders_out.append(o)
        customers_out = sorted(
            [pack(c, {'id': cid, 'name': c['name'], 'max_days': c['max_days']}) for cid, c in by_customer.items()],
            key=lambda x: (-x['qty'], x['name']))[:12]
        aging_out = []
        for k, lo, hi in AGING_BUCKETS:
            tot = bucket()
            for s in STATUS_ORDER:
                b = by_aging[k][s]
                tot['plates'] += b['plates']
                tot['qty'] += b['qty']
                tot['value'] += b['value']
                tot['days_sum'] += b['days_sum']
                tot['orders'] |= b['orders']
                tot['customers'] |= b['customers']
            aging_out.append({
                'key': k,
                'label': ('%d-%d días' % (lo, hi)) if hi < 10 ** 6 else 'más de %d días' % (lo - 1),
                'by_status': {s: pack(by_aging[k][s]) for s in STATUS_ORDER},
                **pack(tot),
            })
        return {
            'today': format_date(self.env, today, date_format='dd MMM yyyy'),
            'currency_symbol': ccur.symbol or '$',
            'statuses': [{'key': s, 'label': STATUS_LABELS[s], **pack(by_status[s])} for s in STATUS_ORDER],
            'kpis': pack(totals),
            'aging': aging_out,
            'customers': customers_out,
            'orders': orders_out,
            'rows': rows,
        }
