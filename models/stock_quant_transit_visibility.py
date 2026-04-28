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
    def _iv_format_date_value(self, value):
        """
        Formatea fechas / datetimes para enviarlas al frontend como YYYY-MM-DD.

        Mantiene fallback seguro por si el valor ya viene como string.
        """
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
        """
        Busca el primer campo existente con valor en un record cualquiera.

        Se usa para ETA porque el campo puede vivir en distintos modelos
        o llamarse diferente según el módulo de tránsito.
        """
        if not record or not record.exists():
            return False

        for field_name in field_names:
            if field_name in record._fields:
                value = record[field_name]
                if value:
                    return value

        return False

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
    def _iv_get_eta_for_transit_quant(self, quant):
        """
        Obtiene ETA únicamente para quants en tránsito.

        Prioridad:
        1. Línea de tránsito vinculada al quant.
        2. Quant directamente.

        Si tu campo real de ETA tiene otro nombre, agrégalo a eta_fields.
        """
        if not quant or not quant.exists() or quant.location_id.usage != "transit":
            return "", ""

        eta_fields = [
            "eta",
            "eta_date",
            "date_eta",
            "fecha_eta",
            "eta_produccion",
            "eta_production",
            "production_eta",
            "production_eta_date",
            "fecha_eta_produccion",
            "expected_arrival_date",
            "estimated_arrival_date",
            "arrival_date",
            "scheduled_date",
            "date_expected",
            "expected_date",
        ]

        transit_line = self._iv_get_transit_line(quant)
        eta_value = self._iv_get_first_existing_field_value(transit_line, eta_fields)

        if eta_value:
            return self._iv_format_date_value(eta_value), "Tránsito"

        eta_value = self._iv_get_first_existing_field_value(quant, eta_fields)

        if eta_value:
            return self._iv_format_date_value(eta_value), "Inventario"

        return "", ""

    # -------------------------------------------------------------------------
    # DETECCIÓN NORMAL DE SO PARA INVENTARIO INTERNO
    # -------------------------------------------------------------------------

    @api.model
    def _iv_resolve_sale_orders_from_move_line(self, move_line):
        """
        Resuelve la SO origen de una línea operativa pendiente.

        Cubre:
        - move_id.sale_line_id.order_id
        - picking.sale_id, si existe
        - procurement group de la SO
        - origin del picking/move, cuando contiene la referencia de la SO

        Solo se usa para inventario interno normal. No se usa en tránsito.
        """
        SaleOrder = self.env["sale.order"].sudo()
        orders = SaleOrder

        if not move_line or not move_line.exists():
            return orders

        move = move_line.move_id
        picking = move_line.picking_id

        # 1) Ruta normal: stock.move -> sale.order.line -> sale.order
        if move and "sale_line_id" in move._fields and move.sale_line_id:
            orders |= move.sale_line_id.order_id

        # 2) Compatibilidad: picking.sale_id si existe
        if picking and "sale_id" in picking._fields and picking.sale_id:
            orders |= picking.sale_id

        # 3) Procurement group
        group = False

        if move and "group_id" in move._fields and move.group_id:
            group = move.group_id
        elif picking and "group_id" in picking._fields and picking.group_id:
            group = picking.group_id

        if group:
            if "procurement_group_id" in SaleOrder._fields:
                orders |= SaleOrder.search([
                    ("procurement_group_id", "=", group.id),
                    ("state", "in", ["sale", "done"]),
                ], limit=20)
            elif "group_id" in SaleOrder._fields:
                orders |= SaleOrder.search([
                    ("group_id", "=", group.id),
                    ("state", "in", ["sale", "done"]),
                ], limit=20)

        # 4) Origin fallback
        origin = ""

        if picking and picking.origin:
            origin = picking.origin
        elif move and "origin" in move._fields and move.origin:
            origin = move.origin

        if origin:
            refs = [
                ref.strip()
                for ref in origin.replace(";", ",").split(",")
                if ref.strip()
            ]

            if refs:
                orders |= SaleOrder.search([
                    ("name", "in", refs),
                    ("state", "in", ["sale", "done"]),
                ], limit=20)

        return orders.filtered(lambda order: order.state in ("sale", "done"))

    @api.model
    def _iv_get_normal_sale_order_ids_for_quant(self, quant):
        """
        Detecta si un quant interno normal está comprometido con una SO.

        Importante:
        - NO aplica a tránsito.
        - NO cambia la lógica de T. Available / T. Committed.
        - Sirve para que la columna E muestre el signo $ verde en Inventario Visual.

        Casos cubiertos:
        1. Lote en picking/entrega asignada o pendiente con sale_line_id.
        2. Lote seleccionado en sale.order.line.lot_ids antes de remisión.
        """
        sale_order_ids = set()

        if (
            not quant
            or not quant.exists()
            or not quant.lot_id
            or not quant.product_id
            or quant.location_id.usage != "internal"
        ):
            return []

        # ---------------------------------------------------------------------
        # 1) Detección logística:
        #    Picking / operación pendiente con lote asignado.
        #
        #    En rutas multi-step puede ser internal, no necesariamente outgoing.
        #    Por eso NO filtramos picking_type_code.
        # ---------------------------------------------------------------------
        move_lines_with_lot = self.env["stock.move.line"].sudo().search([
            ("lot_id", "=", quant.lot_id.id),
            ("product_id", "=", quant.product_id.id),
            ("location_id", "=", quant.location_id.id),
            ("state", "not in", ["done", "cancel"]),
            ("move_id.state", "not in", ["done", "cancel"]),
        ], order="id desc")

        for move_line in move_lines_with_lot:
            orders = self._iv_resolve_sale_orders_from_move_line(move_line)
            sale_order_ids.update(orders.ids)

        # ---------------------------------------------------------------------
        # 2) Detección comercial:
        #    El lote ya está seleccionado en la línea de venta, pero todavía
        #    puede no existir move_line asignada.
        #
        #    Esto cubre la etapa previa a remisión.
        # ---------------------------------------------------------------------
        SaleLine = self.env["sale.order.line"].sudo()

        if "lot_ids" in SaleLine._fields:
            sale_lines = SaleLine.search([
                ("order_id.state", "in", ["sale", "done"]),
                ("display_type", "=", False),
                ("product_id", "=", quant.product_id.id),
                ("lot_ids", "in", [quant.lot_id.id]),
            ])

            for sale_line in sale_lines:
                if not sale_line.order_id:
                    continue

                # Si existe qty_delivered, solo consideramos líneas con pendiente.
                if "qty_delivered" in sale_line._fields:
                    if (sale_line.product_uom_qty or 0.0) <= (sale_line.qty_delivered or 0.0):
                        continue

                sale_order_ids.add(sale_line.order_id.id)

        return sorted(sale_order_ids)

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

            # -----------------------------------------------------------------
            # Inventario interno normal
            # -----------------------------------------------------------------
            normal_sale_order_ids = self._iv_get_normal_sale_order_ids_for_quant(quant)

            is_committed_by_stock = reserved > 0
            is_committed_by_sale = bool(normal_sale_order_ids)

            product_groups[product_id]["stock_qty"] += qty
            product_groups[product_id]["stock_plates"] += 1

            if has_hold:
                product_groups[product_id]["hold_qty"] += qty
                product_groups[product_id]["hold_plates"] += 1

            if is_committed_by_stock or is_committed_by_sale:
                committed_qty = reserved if reserved > 0 else qty
                product_groups[product_id]["committed_qty"] += committed_qty
                product_groups[product_id]["committed_plates"] += 1

            if not has_hold and not is_committed_by_sale and available > 0:
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

            eta_value = ""
            eta_source = ""

            if is_transit:
                eta_value, eta_source = self._iv_get_eta_for_transit_quant(quant)

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
                "is_transit": is_transit,
                "eta": eta_value,
                "eta_source": eta_source,
            }

            if quant.lot_id and hasattr(quant.lot_id, "x_fotografia_ids"):
                detail["cantidad_fotos"] = len(quant.lot_id.x_fotografia_ids)

            # -----------------------------------------------------------------
            # TRÁNSITO: NO SE TOCA LA LÓGICA ACTUAL.
            # Solo se agregan campos informativos para frontend:
            # - is_transit
            # - eta
            # - eta_source
            # -----------------------------------------------------------------
            if is_transit:
                if transit_state == "committed":
                    detail["en_orden_venta"] = True
                    if transit_line and transit_line.order_id:
                        detail["sale_order_ids"] = [transit_line.order_id.id]

                result.append(detail)
                continue

            # -----------------------------------------------------------------
            # INVENTARIO INTERNO NORMAL
            # -----------------------------------------------------------------
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

            sale_order_ids = self._iv_get_normal_sale_order_ids_for_quant(quant)

            if sale_order_ids:
                detail["en_orden_venta"] = True
                detail["sale_order_ids"] = sale_order_ids

            result.append(detail)

        return result