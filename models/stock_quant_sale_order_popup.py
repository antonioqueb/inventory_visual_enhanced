# -*- coding: utf-8 -*-
from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class StockQuantSaleOrderPopup(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _iv_format_date_value(self, value):
        if not value:
            return ""

        try:
            if hasattr(value, "date"):
                return value.date().strftime("%Y-%m-%d")
            if hasattr(value, "strftime"):
                return value.strftime("%Y-%m-%d")
        except Exception:
            pass

        return str(value)

    @api.model
    def _iv_get_first_existing_field_value(self, record, field_names):
        if not record or not record.exists():
            return False

        for field_name in field_names:
            if field_name in record._fields:
                value = record[field_name]
                if value:
                    return value

        return False

    @api.model
    def _iv_get_tipo_display(self, quant):
        if not quant or not quant.exists():
            return ""

        if not hasattr(quant, "x_tipo") or not quant.x_tipo:
            return ""

        try:
            field = quant._fields.get("x_tipo")
            if not field:
                return quant.x_tipo or ""

            selection = field.selection
            if callable(selection):
                selection = selection(quant)

            return dict(selection).get(quant.x_tipo, quant.x_tipo)
        except Exception:
            return quant.x_tipo or ""

    @api.model
    def _iv_shorten_location_name(self, location):
        """
        Convierte:
            SOM/Existencias/G/Linea G-16 -> G/Linea G-16
            S/Existencias/G/Linea G16    -> G/Linea G16
            Existencias/G/Linea G16      -> G/Linea G16
        """
        if not location:
            return ""

        raw = location.complete_name or location.display_name or location.name or ""
        raw = raw.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
        parts = [p.strip() for p in raw.split("/") if p.strip()]

        if not parts:
            return raw

        lowered = [p.lower() for p in parts]

        for marker in ("existencias", "stock"):
            if marker in lowered:
                idx = lowered.index(marker)
                remaining = parts[idx + 1:]
                if remaining:
                    return "/".join(remaining)

        if len(parts) >= 3 and parts[0].lower() in ("s", "som"):
            return "/".join(parts[2:])

        return "/".join(parts)

    @api.model
    def _iv_get_quant_sale_popup_context(self, quant_id=False):
        if not quant_id:
            return {}

        quant = self.sudo().browse(int(quant_id))
        if not quant.exists():
            return {}

        is_transit = quant.location_id.usage == "transit"

        eta_value = False
        eta_source = ""

        if is_transit:
            transit_line = False

            try:
                if hasattr(self, "_iv_get_transit_line"):
                    transit_line = self._iv_get_transit_line(quant)
            except Exception as exc:
                _logger.warning(
                    "[Inventario Visual] No se pudo resolver transit_line para quant %s: %s",
                    quant.id,
                    exc,
                )
                transit_line = False

            eta_fields = [
                "eta",
                "eta_date",
                "date_eta",
                "fecha_eta",
                "expected_arrival_date",
                "estimated_arrival_date",
                "arrival_date",
                "scheduled_date",
                "date_expected",
                "expected_date",
            ]

            if transit_line:
                eta_value = self._iv_get_first_existing_field_value(transit_line, eta_fields)
                if eta_value:
                    eta_source = "Tránsito"

            if not eta_value:
                eta_value = self._iv_get_first_existing_field_value(quant, eta_fields)
                if eta_value:
                    eta_source = "Inventario"

        alto = quant.x_alto if hasattr(quant, "x_alto") else False
        ancho = quant.x_ancho if hasattr(quant, "x_ancho") else False
        grosor = quant.x_grosor if hasattr(quant, "x_grosor") else False

        dimensions = ""
        if grosor and alto and ancho:
            dimensions = f"{grosor} cm · {alto} m × {ancho} m"
        elif alto and ancho:
            dimensions = f"{alto} m × {ancho} m"
        elif grosor:
            dimensions = f"{grosor} cm"

        location_name = quant.location_id.complete_name or quant.location_id.display_name or quant.location_id.name or ""
        location_short = self._iv_shorten_location_name(quant.location_id)

        return {
            "quant_id": quant.id,
            "lot_id": quant.lot_id.id if quant.lot_id else False,
            "lot_name": quant.lot_id.name if quant.lot_id else "",
            "product_id": quant.product_id.id if quant.product_id else False,
            "product_name": quant.product_id.display_name if quant.product_id else "",
            "product_code": quant.product_id.default_code or "",
            "location_name": location_name,
            "location_short": location_short,
            "location_usage": quant.location_id.usage or "",
            "is_transit": is_transit,
            "quantity": quant.quantity or 0.0,
            "reserved_quantity": quant.reserved_quantity or 0.0,
            "available_quantity": (quant.quantity or 0.0) - (quant.reserved_quantity or 0.0),
            "dimensions": dimensions,
            "tipo": self._iv_get_tipo_display(quant),
            "color": quant.x_color if hasattr(quant, "x_color") else "",
            "bloque": quant.x_bloque if hasattr(quant, "x_bloque") else "",
            "atado": quant.x_atado if hasattr(quant, "x_atado") else "",
            "pedimento": quant.x_pedimento if hasattr(quant, "x_pedimento") else "",
            "contenedor": quant.x_contenedor if hasattr(quant, "x_contenedor") else "",
            "referencia_proveedor": quant.x_referencia_proveedor if hasattr(quant, "x_referencia_proveedor") else "",
            "numero_placa": (
                quant.lot_id.x_numero_placa
                if quant.lot_id and hasattr(quant.lot_id, "x_numero_placa")
                else ""
            ),
            "eta": self._iv_format_date_value(eta_value) if eta_value else "",
            "eta_source": eta_source,
        }

    @api.model
    def _iv_convert_invoice_amount_to_order_currency(self, invoice, amount, order):
        if not amount:
            return 0.0

        if invoice.currency_id == order.currency_id:
            return amount

        date = invoice.invoice_date or invoice.date or fields.Date.context_today(self)

        return invoice.currency_id._convert(
            amount,
            order.currency_id,
            order.company_id,
            date,
        )

    @api.model
    def _iv_get_sale_order_payment_info(self, order):
        amount_total = order.amount_total or 0.0
        amount_paid = 0.0
        invoiced_total = 0.0
        residual_total = 0.0
        invoice_count = 0

        try:
            invoices = self.env["account.move"]

            if "invoice_ids" in order._fields:
                invoices = order.invoice_ids.sudo().filtered(
                    lambda inv: (
                        inv.state == "posted"
                        and inv.move_type in ("out_invoice", "out_refund")
                    )
                )

            invoice_count = len(invoices)

            for invoice in invoices:
                sign = -1.0 if invoice.move_type == "out_refund" else 1.0

                invoice_total = self._iv_convert_invoice_amount_to_order_currency(
                    invoice,
                    invoice.amount_total or 0.0,
                    order,
                )
                invoice_residual = self._iv_convert_invoice_amount_to_order_currency(
                    invoice,
                    invoice.amount_residual or 0.0,
                    order,
                )

                invoiced_total += sign * invoice_total
                residual_total += sign * invoice_residual

            amount_paid = max(invoiced_total - residual_total, 0.0)

            if amount_total > 0:
                amount_paid = min(amount_paid, amount_total)

        except Exception as exc:
            _logger.warning(
                "[Inventario Visual] No se pudo calcular pago de la orden %s: %s",
                order.name,
                exc,
            )
            amount_paid = 0.0

        amount_pending = max(amount_total - amount_paid, 0.0)
        payment_percentage = (amount_paid / amount_total * 100.0) if amount_total else 0.0

        if amount_total and (payment_percentage >= 99.99 or amount_pending <= 0.01):
            payment_status = "paid"
            payment_label = "Pagada"
            has_payment = True
        elif amount_paid > 0:
            payment_status = "partial"
            payment_label = "Pago parcial"
            has_payment = True
        else:
            payment_status = "no_payment"
            payment_label = "Sin pago"
            has_payment = False

        return {
            "has_payment": has_payment,
            "payment_status": payment_status,
            "payment_label": payment_label,
            "payment_percentage": payment_percentage,
            "amount_paid": amount_paid,
            "amount_pending": amount_pending,
            "invoice_count": invoice_count,
        }

    @api.model
    def get_sale_order_info(self, sale_order_ids, quant_id=False):
        lot_info = self._iv_get_quant_sale_popup_context(quant_id)

        if not sale_order_ids:
            return {
                "count": 0,
                "orders": [],
                "lot_info": lot_info,
            }

        orders = self.env["sale.order"].sudo().browse(sale_order_ids).exists()
        result = []

        for order in orders:
            payment_info = self._iv_get_sale_order_payment_info(order)

            result.append({
                "id": order.id,
                "name": order.name,
                "partner_name": order.partner_id.name if order.partner_id else "",
                "user_name": order.user_id.name if order.user_id else "",
                "date_order": order.date_order.strftime("%Y-%m-%d") if order.date_order else "",
                "commitment_date": order.commitment_date.strftime("%Y-%m-%d") if order.commitment_date else "",
                "amount_total": order.amount_total or 0.0,
                "amount_paid": payment_info["amount_paid"],
                "amount_pending": payment_info["amount_pending"],
                "payment_percentage": payment_info["payment_percentage"],
                "payment_status": payment_info["payment_status"],
                "payment_label": payment_info["payment_label"],
                "has_payment": payment_info["has_payment"],
                "invoice_count": payment_info["invoice_count"],
                "currency_symbol": order.currency_id.symbol or "",
                "currency_name": order.currency_id.name or "",
            })

        return {
            "count": len(result),
            "orders": result,
            "lot_info": lot_info,
        }