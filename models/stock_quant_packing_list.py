# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class StockQuantPackingList(models.Model):
    _inherit = "stock.quant"

    # -------------------------------------------------------------------------
    # HELPERS GENERALES
    # -------------------------------------------------------------------------

    @api.model
    def _iv_model_available(self, model_name):
        try:
            return model_name in self.env.registry.models
        except Exception:
            return False

    @api.model
    def _iv_safe_value(self, record, field_name, default=False):
        if not record or not record.exists():
            return default

        if field_name not in record._fields:
            return default

        return record[field_name] or default

    @api.model
    def _iv_first_value(self, records_and_fields, default=""):
        """
        Devuelve el primer valor disponible revisando varios records/campos.

        Uso principal:
        - En Inventario Visual muchos campos vienen desde stock.quant.
        - En otros flujos viven en stock.lot.
        - Esta función evita que el PL falle solo porque el dato no vive
          exactamente en el modelo esperado.
        """
        for record, field_names in records_and_fields:
            if not record or not record.exists():
                continue

            for field_name in field_names:
                if field_name not in record._fields:
                    continue

                value = record[field_name]
                if value:
                    return value

        return default

    @api.model
    def _iv_normalize_text(self, value):
        if not value:
            return ""

        return str(value).strip()

    @api.model
    def _iv_normalize_for_compare(self, value):
        if not value:
            return ""

        return (
            str(value)
            .strip()
            .upper()
            .replace(" ", "")
            .replace("-", "")
            .replace("_", "")
        )

    # -------------------------------------------------------------------------
    # RESOLUCIÓN DE EMBARQUE / PACKING
    # -------------------------------------------------------------------------

    @api.model
    def _iv_resolve_shipment_from_row(self, row):
        """
        Resuelve el embarque supplier.shipment desde un renglón de PL.
        """
        if not row or not row.exists():
            return False

        # 1. Campo related/directo shipment_id en el row
        if "shipment_id" in row._fields and row.shipment_id:
            return row.shipment_id

        # 2. A través del packing
        packing = row.packing_id if "packing_id" in row._fields else False
        if packing and packing.exists():
            if "shipment_id" in packing._fields and packing.shipment_id:
                return packing.shipment_id

        # 3. A través del contenedor
        if "container_id" in row._fields and row.container_id:
            container = row.container_id
            if "shipment_id" in container._fields and container.shipment_id:
                return container.shipment_id

        return False

    @api.model
    def _iv_make_packing_info_from_row(self, row):
        """
        Devuelve información navegable desde supplier.shipment.packing.row.

        Regla:
        - La columna se llama Packing List.
        - Si existe embarque, el frontend abre supplier.shipment.
        - Si no existe embarque, puede abrir supplier.shipment.packing.
        """
        if not row or not row.exists():
            return {}

        packing = row.packing_id if "packing_id" in row._fields else False
        shipment = self._iv_resolve_shipment_from_row(row)

        container_name = ""

        if "container_id" in row._fields and row.container_id:
            container = row.container_id
            if "container_number" in container._fields:
                container_name = container.container_number or container.display_name
            else:
                container_name = container.display_name

        packing_name = ""
        if packing:
            packing_name = (
                packing.packing_number
                if "packing_number" in packing._fields and packing.packing_number
                else packing.display_name
            )

        shipment_name = ""
        if shipment:
            shipment_name = shipment.name or shipment.display_name

        info = {
            "packing_row_id": row.id,
            "packing_id": packing.id if packing else False,
            "packing_name": packing_name,
            "shipment_id": shipment.id if shipment else False,
            "shipment_name": shipment_name,
            "container_name": container_name,
        }

        _logger.info(
            "[Inventario Visual][PL] Row encontrado | row=%s | packing=%s | shipment=%s",
            row.id,
            info["packing_id"],
            info["shipment_id"],
        )

        return info

    @api.model
    def _iv_make_packing_info_from_shipment(self, shipment, packing=False, container_name=""):
        """
        Fallback cuando se encuentra el embarque, aunque no se encuentre
        el renglón exacto del Packing List.
        """
        if not shipment or not shipment.exists():
            return {}

        if not packing and "packing_ids" in shipment._fields and shipment.packing_ids:
            packing = shipment.packing_ids[:1]

        packing_name = ""
        if packing:
            packing_name = (
                packing.packing_number
                if "packing_number" in packing._fields and packing.packing_number
                else packing.display_name
            )

        return {
            "packing_row_id": False,
            "packing_id": packing.id if packing else False,
            "packing_name": packing_name,
            "shipment_id": shipment.id,
            "shipment_name": shipment.name or shipment.display_name,
            "container_name": container_name or "",
        }

    # -------------------------------------------------------------------------
    # RESOLUCIÓN POR TORRE DE CONTROL / TRÁNSITO
    # -------------------------------------------------------------------------

    @api.model
    def _iv_get_transit_line_for_quant(self, quant):
        """
        Resuelve stock.transit.line de forma robusta.

        Prioridad:
        1. quant.transit_line_id, si existe.
        2. stock.transit.line.quant_id.
        3. stock.transit.line por lote + producto.
        """
        if (
            not quant
            or not quant.exists()
            or not self._iv_model_available("stock.transit.line")
        ):
            return False

        if "transit_line_id" in quant._fields and quant.transit_line_id:
            return quant.transit_line_id.sudo()

        TransitLine = self.env["stock.transit.line"].sudo()

        try:
            if "quant_id" in TransitLine._fields:
                transit_line = TransitLine.search([
                    ("quant_id", "=", quant.id),
                ], order="id desc", limit=1)

                if transit_line:
                    return transit_line
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual][PL] Error buscando transit line por quant %s: %s",
                quant.id,
                exc,
            )

        if quant.lot_id and quant.product_id:
            try:
                transit_line = TransitLine.search([
                    ("lot_id", "=", quant.lot_id.id),
                    ("product_id", "=", quant.product_id.id),
                ], order="id desc", limit=1)

                if transit_line:
                    return transit_line
            except Exception as exc:
                _logger.warning(
                    "[Inventario Visual][PL] Error buscando transit line por lote/producto quant %s: %s",
                    quant.id,
                    exc,
                )

        return False

    @api.model
    def _iv_get_voyage_for_quant(self, quant):
        """
        Resuelve stock.transit.voyage desde el quant.

        Prioridad:
        1. quant.transit_voyage_id
        2. quant.transit_line_id.voyage_id
        3. stock.transit.line encontrada por quant/lote/producto
        """
        if not quant or not quant.exists():
            return False

        if "transit_voyage_id" in quant._fields and quant.transit_voyage_id:
            return quant.transit_voyage_id.sudo()

        transit_line = self._iv_get_transit_line_for_quant(quant)
        if transit_line and "voyage_id" in transit_line._fields and transit_line.voyage_id:
            return transit_line.voyage_id.sudo()

        return False

    @api.model
    def _iv_find_shipment_from_voyage(self, voyage):
        if (
            not voyage
            or not voyage.exists()
            or not self._iv_model_available("supplier.shipment")
        ):
            return False

        Shipment = self.env["supplier.shipment"].sudo()

        if "voyage_id" not in Shipment._fields:
            return False

        try:
            shipment = Shipment.search([
                ("voyage_id", "=", voyage.id),
            ], order="id desc", limit=1)

            if shipment:
                return shipment
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual][PL] Error buscando supplier.shipment por voyage %s: %s",
                voyage.id,
                exc,
            )

        return False

    @api.model
    def _iv_find_shipment_from_transit_for_quant(self, quant):
        """
        Fallback principal:
        quant -> transit line / voyage -> supplier.shipment.
        """
        if not quant or not quant.exists():
            return False

        voyage = self._iv_get_voyage_for_quant(quant)
        if not voyage:
            return False

        return self._iv_find_shipment_from_voyage(voyage)

    @api.model
    def _iv_find_shipment_from_picking_for_quant(self, quant):
        """
        Fallback adicional:
        busca movimientos del lote que provengan de un picking
        con supplier_shipment_id.
        """
        if (
            not quant
            or not quant.exists()
            or not quant.lot_id
            or not quant.product_id
            or not self._iv_model_available("stock.move.line")
        ):
            return False

        MoveLine = self.env["stock.move.line"].sudo()

        try:
            move_lines = MoveLine.search([
                ("lot_id", "=", quant.lot_id.id),
                ("product_id", "=", quant.product_id.id),
                ("picking_id", "!=", False),
            ], order="id desc", limit=30)
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual][PL] Error buscando move lines para quant %s: %s",
                quant.id,
                exc,
            )
            return False

        for ml in move_lines:
            picking = ml.picking_id
            if (
                picking
                and "supplier_shipment_id" in picking._fields
                and picking.supplier_shipment_id
            ):
                return picking.supplier_shipment_id.sudo()

        return False

    # -------------------------------------------------------------------------
    # RESOLUCIÓN POR RENGÓN DE PACKING LIST
    # -------------------------------------------------------------------------

    @api.model
    def _iv_get_quant_matching_values(self, quant):
        """
        Junta valores desde quant y lot.

        Importante:
        En tu vista, bloque/atado/pedimento/contenedor/ref proveedor suelen venir
        del quant. Si buscamos solo en lot, has_packing_list puede quedar false.
        """
        lot = quant.lot_id if quant and quant.exists() else False

        numero_placa = self._iv_first_value([
            (quant, ["x_numero_placa", "numero_placa"]),
            (lot, ["x_numero_placa", "numero_placa"]),
        ])

        ref_proveedor = self._iv_first_value([
            (quant, ["x_referencia_proveedor", "referencia_proveedor", "ref_proveedor"]),
            (lot, ["x_referencia_proveedor", "referencia_proveedor", "ref_proveedor"]),
        ])

        bloque = self._iv_first_value([
            (quant, ["x_bloque", "bloque"]),
            (lot, ["x_bloque", "bloque"]),
        ])

        atado = self._iv_first_value([
            (quant, ["x_atado", "atado"]),
            (lot, ["x_atado", "atado"]),
        ])

        pedimento = self._iv_first_value([
            (quant, ["x_pedimento", "pedimento"]),
            (lot, ["x_pedimento", "pedimento"]),
        ])

        contenedor = self._iv_first_value([
            (quant, ["x_contenedor", "contenedor", "container_number"]),
            (lot, ["x_contenedor", "contenedor", "container_number"]),
        ])

        return {
            "numero_placa": self._iv_normalize_text(numero_placa),
            "ref_proveedor": self._iv_normalize_text(ref_proveedor),
            "bloque": self._iv_normalize_text(bloque),
            "atado": self._iv_normalize_text(atado),
            "pedimento": self._iv_normalize_text(pedimento),
            "contenedor": self._iv_normalize_text(contenedor),
        }

    @api.model
    def _iv_add_domain_if_fields_exist(self, domains, Row, base_domain, additions):
        """
        Agrega un dominio candidato solo si todos los campos existen.
        """
        for field_name, operator, value in additions:
            if "." not in field_name and field_name not in Row._fields:
                return

            if not value:
                return

        domains.append(base_domain + [
            (field_name, operator, value)
            for field_name, operator, value in additions
        ])

    @api.model
    def _iv_find_packing_row_for_quant(self, quant, shipment=False):
        """
        Busca un renglón de Packing List asociado al lote/producto del quant.

        Mejora clave:
        - Primero intenta scoped por shipment si ya se resolvió el embarque.
        - Usa datos del quant y del lot.
        - Si no encuentra row, el flujo todavía puede devolver el shipment como fallback.
        """
        if (
            not quant
            or not quant.exists()
            or not quant.product_id
            or not self._iv_model_available("supplier.shipment.packing.row")
        ):
            return False

        Row = self.env["supplier.shipment.packing.row"].sudo()
        values = self._iv_get_quant_matching_values(quant)

        base_domains = [
            [("product_id", "=", quant.product_id.id)],
        ]

        if shipment and shipment.exists() and "shipment_id" in Row._fields:
            base_domains.insert(0, [
                ("product_id", "=", quant.product_id.id),
                ("shipment_id", "=", shipment.id),
            ])

        candidate_domains = []

        for base_domain in base_domains:
            # 1. Número de placa exacto
            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [("numero_placa", "=", values["numero_placa"])],
            )

            # 2. Referencia proveedor exacta
            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [("ref_proveedor", "=", values["ref_proveedor"])],
            )

            # 3. Bloque + atado
            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [
                    ("bloque", "=", values["bloque"]),
                    ("atado", "=", values["atado"]),
                ],
            )

            # 4. Pedimento + bloque
            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [
                    ("pedimento", "=", values["pedimento"]),
                    ("bloque", "=", values["bloque"]),
                ],
            )

            # 5. Contenedor + bloque
            if "container_id" in Row._fields:
                self._iv_add_domain_if_fields_exist(
                    candidate_domains,
                    Row,
                    base_domain,
                    [
                        ("container_id.container_number", "=", values["contenedor"]),
                        ("bloque", "=", values["bloque"]),
                    ],
                )

            # 6. Búsquedas flexibles
            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [("numero_placa", "ilike", values["numero_placa"])],
            )

            self._iv_add_domain_if_fields_exist(
                candidate_domains,
                Row,
                base_domain,
                [("ref_proveedor", "ilike", values["ref_proveedor"])],
            )

        seen_domains = set()

        for domain in candidate_domains:
            domain_key = repr(domain)
            if domain_key in seen_domains:
                continue
            seen_domains.add(domain_key)

            try:
                row = Row.search(domain, order="id desc", limit=1)
                if row:
                    _logger.info(
                        "[Inventario Visual][PL] Row resuelto para quant %s con dominio %s",
                        quant.id,
                        domain,
                    )
                    return row
            except Exception as exc:
                _logger.warning(
                    "[Inventario Visual][PL] Error buscando row para quant %s con dominio %s: %s",
                    quant.id,
                    domain,
                    exc,
                )

        return False

    # -------------------------------------------------------------------------
    # PUNTO ÚNICO PARA FRONTEND
    # -------------------------------------------------------------------------

    @api.model
    def _iv_get_packing_list_info_for_quant(self, quant):
        """
        Punto único de resolución para frontend.

        Prioridad:
        1. Resolver shipment desde tránsito/voyage.
        2. Buscar row exacto del PL, scoped por shipment si existe.
        3. Si hay row, devolver row + packing + shipment.
        4. Si no hay row pero sí shipment, devolver shipment + primer PL.
        5. Fallback por picking.supplier_shipment_id.
        """
        if not quant or not quant.exists():
            return {}

        shipment = (
            self._iv_find_shipment_from_transit_for_quant(quant)
            or self._iv_find_shipment_from_picking_for_quant(quant)
        )

        row = self._iv_find_packing_row_for_quant(quant, shipment=shipment)
        if row:
            info = self._iv_make_packing_info_from_row(row)

            # Si el row no trae shipment, completamos con fallback.
            if info and not info.get("shipment_id") and shipment:
                info["shipment_id"] = shipment.id
                info["shipment_name"] = shipment.name or shipment.display_name

            return info

        if shipment:
            values = self._iv_get_quant_matching_values(quant)
            return self._iv_make_packing_info_from_shipment(
                shipment,
                container_name=values.get("contenedor") or "",
            )

        return {}

    # -------------------------------------------------------------------------
    # OVERRIDE SEGURO: AGREGA CAMPOS AL RESULTADO ACTUAL
    # -------------------------------------------------------------------------

    @api.model
    def get_quant_details(self, quant_ids=None):
        """
        Extiende la respuesta existente de Inventario Visual sin duplicar
        toda la lógica de stock_quant_transit_visibility.
        """
        result = super().get_quant_details(quant_ids=quant_ids)

        if not result:
            return result

        quant_ids_from_result = [
            item.get("id")
            for item in result
            if item.get("id")
        ]

        quants_by_id = {
            quant.id: quant
            for quant in self.sudo().browse(quant_ids_from_result).exists()
        }

        for item in result:
            quant = quants_by_id.get(item.get("id"))

            packing_info = self._iv_get_packing_list_info_for_quant(quant) if quant else {}

            item["packing_list_id"] = packing_info.get("packing_id") or False
            item["packing_list_name"] = packing_info.get("packing_name") or ""
            item["packing_row_id"] = packing_info.get("packing_row_id") or False
            item["packing_shipment_id"] = packing_info.get("shipment_id") or False
            item["packing_shipment_name"] = packing_info.get("shipment_name") or ""
            item["packing_container_name"] = packing_info.get("container_name") or ""
            item["has_packing_list"] = bool(
                item["packing_list_id"]
                or item["packing_shipment_id"]
                or item["packing_row_id"]
            )

            _logger.info(
                "[Inventario Visual][PL] quant=%s | has=%s | shipment=%s | packing=%s | row=%s",
                item.get("id"),
                item["has_packing_list"],
                item["packing_shipment_id"],
                item["packing_list_id"],
                item["packing_row_id"],
            )

        return result