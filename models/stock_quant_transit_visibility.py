# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class StockQuantTransitVisibility(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _iv_has_transit_publication_fields(self):
        return (
            "transit_inventory_published" in self._fields
            and "transit_inventory_state" in self._fields
        )

    @api.model
    def _iv_get_transit_state(self, quant):
        """
        Estado comercial usado exclusivamente para tránsito.

        hidden:
            No debe aparecer en Inventario Visual.

        available:
            Aparece como T. Available.

        committed:
            Aparece como T. Committed.
        """
        if quant.location_id.usage != "transit":
            return False

        if not self._iv_has_transit_publication_fields():
            return "hidden"

        if not quant.transit_inventory_published:
            return "hidden"

        if quant.transit_inventory_state in ("available", "committed"):
            return quant.transit_inventory_state

        return "hidden"

    @api.model
    def _iv_get_transit_line(self, quant):
        if "transit_line_id" in quant._fields and quant.transit_line_id:
            return quant.transit_line_id

        if "stock.transit.line" not in self.env.registry.models:
            return False

        return self.env["stock.transit.line"].sudo().search([
            ("quant_id", "=", quant.id),
        ], limit=1)

    @api.model
    def get_inventory_grouped_by_product(self, filters=None):
        if not filters:
            return {"products": [], "missing_lots": []}

        domain = [
            ("quantity", ">", 0),
            ("location_id.usage", "in", ["internal", "transit"]),
        ]

        search_lot_names = []

        if filters.get("product_name"):
            domain.append(("product_id", "ilike", filters["product_name"]))

        if filters.get("almacen_id"):
            almacen = self.env["stock.warehouse"].browse(int(filters["almacen_id"]))
            if almacen.view_location_id:
                domain.append(("location_id", "child_of", almacen.view_location_id.id))

        if filters.get("ubicacion_id"):
            domain.append(("location_id", "child_of", int(filters["ubicacion_id"])))

        if filters.get("tipo"):
            domain.append(("x_tipo", "=", filters["tipo"]))

        if filters.get("marca"):
            domain.append(("product_id.product_tmpl_id.x_marca", "ilike", filters["marca"]))

        if filters.get("color"):
            domain.append(("product_id.product_tmpl_id.x_color", "ilike", filters["color"]))

        if filters.get("categoria_name"):
            all_cats = self.env["product.category"].search([
                ("name", "ilike", filters["categoria_name"])
            ])
            parent_ids = set(
                self.env["product.category"].search([
                    ("parent_id", "!=", False)
                ]).mapped("parent_id").ids
            )
            leaf_cat_ids = [cat.id for cat in all_cats if cat.id not in parent_ids]
            if leaf_cat_ids:
                domain.append(("product_id.categ_id", "in", leaf_cat_ids))

        if filters.get("grupo"):
            grupo_search = filters["grupo"]
            field = self._fields.get("x_grupo")
            if field and hasattr(field, "comodel_name"):
                related_model = self.env[field.comodel_name]
                matching_records = related_model.search([("name", "ilike", grupo_search)])
                if matching_records:
                    domain.append(("x_grupo", "in", matching_records.ids))
                else:
                    domain.append(("id", "=", 0))

        if filters.get("acabado"):
            domain.append(("x_acabado", "=", filters["acabado"]))

        if filters.get("color"):
            domain.append(("x_color", "ilike", filters["color"]))

        if filters.get("grosor"):
            try:
                grosor_val = float(filters["grosor"])
                domain.append(("x_grosor", ">=", grosor_val - 0.001))
                domain.append(("x_grosor", "<=", grosor_val + 0.001))
            except (ValueError, TypeError):
                pass

        if filters.get("numero_serie"):
            raw_input = filters["numero_serie"]
            search_lot_names = [name.strip() for name in raw_input.split(",") if name.strip()]
            if search_lot_names:
                if len(search_lot_names) == 1:
                    domain.append(("lot_id.name", "ilike", search_lot_names[0]))
                else:
                    lot_domain = ["|"] * (len(search_lot_names) - 1)
                    for name in search_lot_names:
                        lot_domain.append(("lot_id.name", "ilike", name))
                    domain.extend(lot_domain)

        if filters.get("bloque"):
            domain.append(("x_bloque", "ilike", filters["bloque"]))

        if filters.get("pedimento"):
            pedimento_normalized = filters["pedimento"].replace(" ", "").replace("-", "")
            quants_con_pedimento = self.search([
                ("x_pedimento", "!=", False),
                ("quantity", ">", 0),
            ])
            matching_quant_ids = [
                q.id for q in quants_con_pedimento
                if q.x_pedimento and q.x_pedimento.replace(" ", "").replace("-", "") == pedimento_normalized
            ]
            if matching_quant_ids:
                domain.append(("id", "in", matching_quant_ids))
            else:
                domain.append(("id", "=", 0))

        if filters.get("contenedor"):
            domain.append(("x_contenedor", "ilike", filters["contenedor"]))

        if filters.get("atado"):
            domain.append(("x_atado", "ilike", filters["atado"]))

        if filters.get("alto_min"):
            try:
                domain.append(("x_alto", ">=", float(filters["alto_min"])))
            except (ValueError, TypeError):
                pass

        if filters.get("ancho_min"):
            try:
                domain.append(("x_ancho", ">=", float(filters["ancho_min"])))
            except (ValueError, TypeError):
                pass

        quants = self.search(domain)

        # Filtro: cantidad mínima por bloque
        if filters.get("cantidad_min_bloque"):
            try:
                min_bloque = float(filters["cantidad_min_bloque"])
            except (ValueError, TypeError):
                min_bloque = 0.0

            if min_bloque > 0 and quants:
                bloque_totals = {}
                for q in quants:
                    bloque_val = q.x_bloque if hasattr(q, "x_bloque") else ""
                    if not bloque_val:
                        continue
                    key = (q.product_id.id, bloque_val)
                    bloque_totals[key] = bloque_totals.get(key, 0.0) + q.quantity

                valid_keys = {k for k, total in bloque_totals.items() if total >= min_bloque}

                quants = quants.filtered(lambda q: (
                    q.x_bloque
                    and (q.product_id.id, q.x_bloque) in valid_keys
                ))

        product_groups = {}

        visible_quants = self.env["stock.quant"]

        for quant in quants:
            usage = quant.location_id.usage
            is_transit = usage == "transit"

            if is_transit:
                transit_state = self._iv_get_transit_state(quant)
                if transit_state == "hidden":
                    continue

            visible_quants |= quant

            product_id = quant.product_id.id

            if product_id not in product_groups:
                tipo_display = ""
                if hasattr(quant, "x_tipo") and quant.x_tipo:
                    try:
                        field = quant._fields.get("x_tipo")
                        if field:
                            selection = field.selection
                            if callable(selection):
                                selection = selection(quant)
                            tipo_dict = dict(selection)
                            tipo_display = tipo_dict.get(quant.x_tipo, "")
                    except Exception:
                        tipo_display = ""

                product_groups[product_id] = {
                    "product_id": product_id,
                    "product_name": quant.product_id.display_name,
                    "product_code": quant.product_id.default_code or "",
                    "categ_name": quant.product_id.categ_id.display_name,
                    "tipo": tipo_display,
                    "quant_ids": [],
                    "stock_qty": 0.0,
                    "stock_plates": 0,
                    "hold_qty": 0.0,
                    "hold_plates": 0,
                    "committed_qty": 0.0,
                    "committed_plates": 0,
                    "available_qty": 0.0,
                    "available_plates": 0,
                    "transit_qty": 0.0,
                    "transit_plates": 0,
                    "transit_hold_qty": 0.0,
                    "transit_hold_plates": 0,
                    "transit_committed_qty": 0.0,
                    "transit_committed_plates": 0,
                    "transit_available_qty": 0.0,
                    "transit_available_plates": 0,
                    "color": quant.x_color if hasattr(quant, "x_color") else "",
                }

            product_groups[product_id]["quant_ids"].append(quant.id)

            qty = quant.quantity
            reserved = quant.reserved_quantity
            available = qty - reserved
            has_hold = hasattr(quant, "x_tiene_hold") and quant.x_tiene_hold

            if is_transit:
                transit_state = self._iv_get_transit_state(quant)

                product_groups[product_id]["transit_qty"] += qty
                product_groups[product_id]["transit_plates"] += 1

                if transit_state == "committed":
                    product_groups[product_id]["transit_committed_qty"] += qty
                    product_groups[product_id]["transit_committed_plates"] += 1

                elif transit_state == "available":
                    product_groups[product_id]["transit_available_qty"] += qty
                    product_groups[product_id]["transit_available_plates"] += 1

                continue

            product_groups[product_id]["stock_qty"] += qty
            product_groups[product_id]["stock_plates"] += 1

            if has_hold:
                product_groups[product_id]["hold_qty"] += qty
                product_groups[product_id]["hold_plates"] += 1

            if reserved > 0:
                product_groups[product_id]["committed_qty"] += reserved
                product_groups[product_id]["committed_plates"] += 1

            if not has_hold and available > 0:
                product_groups[product_id]["available_qty"] += available
                product_groups[product_id]["available_plates"] += 1

        missing_lots = []
        if search_lot_names:
            found_lot_names = set(visible_quants.mapped("lot_id.name"))
            for search_term in search_lot_names:
                if not any(
                    search_term.lower() in lot_name.lower()
                    for lot_name in found_lot_names
                    if lot_name
                ):
                    missing_lots.append(search_term)
            missing_lots.sort()

        if filters.get("price_min") or filters.get("price_max"):
            product_groups = self._filter_products_by_price(product_groups, filters)

        return {
            "products": list(product_groups.values()),
            "missing_lots": missing_lots,
        }

    @api.model
    def get_quant_details(self, quant_ids=None):
        if not quant_ids:
            return []

        quants = self.browse(quant_ids)
        result = []

        is_sales_user = (
            self.env.user.has_group("sales_team.group_sale_salesman")
            or self.env.user.has_group("sales_team.group_sale_salesman_all_leads")
            or self.env.user.has_group("sales_team.group_sale_manager")
        )

        for quant in quants:
            usage = quant.location_id.usage
            is_transit = usage == "transit"
            transit_state = self._iv_get_transit_state(quant) if is_transit else False

            if is_transit and transit_state == "hidden":
                continue

            tipo_display = ""
            if hasattr(quant, "x_tipo") and quant.x_tipo:
                try:
                    field = quant._fields.get("x_tipo")
                    if field:
                        selection = field.selection
                        if callable(selection):
                            selection = selection(quant)
                        tipo_dict = dict(selection)
                        tipo_display = tipo_dict.get(quant.x_tipo, "")
                except Exception:
                    tipo_display = ""

            transit_line = self._iv_get_transit_line(quant) if is_transit else False

            detail = {
                "id": quant.id,
                "lot_id": quant.lot_id.id if quant.lot_id else False,
                "lot_name": quant.lot_id.name if quant.lot_id else "",
                "location_id": quant.location_id.id,
                "location_name": quant.location_id.name,
                "location_usage": quant.location_id.usage,
                "quantity": quant.quantity,
                "reserved_quantity": quant.reserved_quantity,
                "grosor": quant.x_grosor if hasattr(quant, "x_grosor") else False,
                "alto": quant.x_alto if hasattr(quant, "x_alto") else False,
                "ancho": quant.x_ancho if hasattr(quant, "x_ancho") else False,
                "color": quant.x_color if hasattr(quant, "x_color") else "",
                "tipo": tipo_display,
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
                "cantidad_fotos": 0,
                "detalles_placa": quant.x_detalles_placa if hasattr(quant, "x_detalles_placa") else "",
                "tiene_hold": False,
                "hold_info": None,
                "en_orden_venta": False,
                "sale_order_ids": [],
                "transit_inventory_state": transit_state or "",
                "transit_inventory_published": bool(
                    self._iv_has_transit_publication_fields()
                    and getattr(quant, "transit_inventory_published", False)
                ),
            }

            if quant.lot_id and hasattr(quant.lot_id, "x_fotografia_ids"):
                detail["cantidad_fotos"] = len(quant.lot_id.x_fotografia_ids)

            if is_transit:
                if transit_state == "committed":
                    detail["en_orden_venta"] = True
                    if transit_line and transit_line.order_id:
                        detail["sale_order_ids"] = [transit_line.order_id.id]
                result.append(detail)
                continue

            detail["tiene_hold"] = quant.x_tiene_hold if hasattr(quant, "x_tiene_hold") else False

            if (
                detail["tiene_hold"]
                and is_sales_user
                and hasattr(quant, "x_hold_activo_id")
                and quant.x_hold_activo_id
            ):
                hold = quant.x_hold_activo_id
                detail["hold_info"] = {
                    "id": hold.id,
                    "partner_name": hold.partner_id.name if hold.partner_id else "",
                    "proyecto_nombre": hold.project_id.name if hasattr(hold, "project_id") and hold.project_id else "",
                    "arquitecto_nombre": hold.arquitecto_id.name if hasattr(hold, "arquitecto_id") and hold.arquitecto_id else "",
                    "vendedor_nombre": hold.user_id.name if hold.user_id else "",
                    "fecha_inicio": hold.fecha_inicio.strftime("%Y-%m-%d") if hasattr(hold, "fecha_inicio") and hold.fecha_inicio else "",
                    "fecha_expiracion": hold.fecha_expiracion.strftime("%Y-%m-%d") if hasattr(hold, "fecha_expiracion") and hold.fecha_expiracion else "",
                    "notas": hold.notas if hasattr(hold, "notas") else "",
                }

            if quant.lot_id:
                move_lines_with_lot = self.env["stock.move.line"].sudo().search([
                    ("lot_id", "=", quant.lot_id.id),
                    ("state", "=", "assigned"),
                    ("location_id", "=", quant.location_id.id),
                    ("move_id.sale_line_id", "!=", False),
                ])

                sale_order_ids = set()
                for move_line in move_lines_with_lot:
                    sale_order = move_line.move_id.sale_line_id.order_id
                    if sale_order.state in ["sale", "done"]:
                        sale_order_ids.add(sale_order.id)

                if sale_order_ids:
                    detail["en_orden_venta"] = True
                    detail["sale_order_ids"] = list(sale_order_ids)

            result.append(detail)

        return result