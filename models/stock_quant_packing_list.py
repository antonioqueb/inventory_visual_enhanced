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
    def _iv_resolve_shipment_from_row(self, row):
        """
        Resuelve el embarque (supplier.shipment) desde un renglón
        de packing list, intentando todos los caminos posibles.
        """
        if not row or not row.exists():
            return False

        # 1. Campo directo shipment_id en el row
        if "shipment_id" in row._fields and row.shipment_id:
            return row.shipment_id

        # 2. A través del packing
        packing = row.packing_id if "packing_id" in row._fields else False
        if packing and packing.exists():
            if "shipment_id" in packing._fields and packing.shipment_id:
                return packing.shipment_id

        # 3. A través del container
        if "container_id" in row._fields and row.container_id:
            container = row.container_id
            if "shipment_id" in container._fields and container.shipment_id:
                return container.shipment_id

        return False

    @api.model
    def _iv_make_packing_info_from_row(self, row):
        """
        Devuelve la información navegable del Packing List / Embarque
        desde un renglón de supplier.shipment.packing.row.

        Regla solicitada:
        - La columna se llama Packing List.
        - El hipervínculo debe llevar al Embarque, no solo al renglón.
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

        info = {
            "packing_row_id": row.id,
            "packing_id": packing.id if packing else False,
            "packing_name": (
                packing.packing_number
                if packing and "packing_number" in packing._fields and packing.packing_number
                else (packing.display_name if packing else "")
            ),
            "shipment_id": shipment.id if shipment else False,
            "shipment_name": shipment.name if shipment else "",
            "container_name": container_name,
        }

        _logger.debug(
            "[Inventario Visual] Packing info desde row %s: shipment_id=%s, packing_id=%s",
            row.id, info["shipment_id"], info["packing_id"]
        )

        return info

    @api.model
    def _iv_make_packing_info_from_shipment(self, shipment, packing=False):
        """
        Fallback cuando se logra llegar al embarque, pero no al renglón exacto.
        """
        if not shipment or not shipment.exists():
            return {}

        if not packing and "packing_ids" in shipment._fields and shipment.packing_ids:
            packing = shipment.packing_ids[:1]

        return {
            "packing_row_id": False,
            "packing_id": packing.id if packing else False,
            "packing_name": (
                packing.packing_number
                if packing and "packing_number" in packing._fields and packing.packing_number
                else (packing.display_name if packing else "")
            ),
            "shipment_id": shipment.id,
            "shipment_name": shipment.name or shipment.display_name,
            "container_name": "",
        }

    # -------------------------------------------------------------------------
    # RESOLUCIÓN POR RENGÓN DE PACKING LIST
    # -------------------------------------------------------------------------

    @api.model
    def _iv_find_packing_row_for_quant(self, quant):
        """
        Busca un renglón de Packing List asociado al lote/producto del quant.
        """
        if (
            not quant
            or not quant.exists()
            or not quant.lot_id
            or not quant.product_id
            or not self._iv_model_available("supplier.shipment.packing.row")
        ):
            return False

        lot = quant.lot_id
        Row = self.env["supplier.shipment.packing.row"].sudo()

        base_domain = [
            ("product_id", "=", quant.product_id.id),
        ]

        candidate_domains = []

        numero_placa = self._iv_safe_value(lot, "x_numero_placa", "")
        ref_proveedor = self._iv_safe_value(lot, "x_referencia_proveedor", "")
        bloque = self._iv_safe_value(lot, "x_bloque", "")
        atado = self._iv_safe_value(lot, "x_atado", "")
        pedimento = self._iv_safe_value(lot, "x_pedimento", "")

        if numero_placa and "numero_placa" in Row._fields:
            candidate_domains.append(base_domain + [
                ("numero_placa", "=", numero_placa),
            ])

        if ref_proveedor and "ref_proveedor" in Row._fields:
            candidate_domains.append(base_domain + [
                ("ref_proveedor", "=", ref_proveedor),
            ])

        if bloque and atado and "bloque" in Row._fields and "atado" in Row._fields:
            candidate_domains.append(base_domain + [
                ("bloque", "=", bloque),
                ("atado", "=", atado),
            ])

        if pedimento and bloque and "pedimento" in Row._fields and "bloque" in Row._fields:
            candidate_domains.append(base_domain + [
                ("pedimento", "=", pedimento),
                ("bloque", "=", bloque),
            ])

        if numero_placa and "numero_placa" in Row._fields:
            candidate_domains.append(base_domain + [
                ("numero_placa", "ilike", numero_placa),
            ])

        if ref_proveedor and "ref_proveedor" in Row._fields:
            candidate_domains.append(base_domain + [
                ("ref_proveedor", "ilike", ref_proveedor),
            ])

        for domain in candidate_domains:
            try:
                row = Row.search(domain, order="id desc", limit=1)
                if row:
                    return row
            except Exception as exc:
                _logger.warning(
                    "[Inventario Visual] Error buscando Packing Row para quant %s con dominio %s: %s",
                    quant.id,
                    domain,
                    exc,
                )

        return False

    # -------------------------------------------------------------------------
    # RESOLUCIÓN POR TRÁNSITO / EMBARQUE / PICKING
    # -------------------------------------------------------------------------

    @api.model
    def _iv_find_shipment_from_transit_for_quant(self, quant):
        """
        Fallback: si el lote tuvo línea en Torre de Control, intenta llegar
        al viaje y de ahí al embarque del proveedor.
        """
        if (
            not quant
            or not quant.exists()
            or not quant.lot_id
            or not quant.product_id
            or not self._iv_model_available("stock.transit.line")
            or not self._iv_model_available("supplier.shipment")
        ):
            return False

        TransitLine = self.env["stock.transit.line"].sudo()
        Shipment = self.env["supplier.shipment"].sudo()

        transit_line = False

        try:
            transit_line = TransitLine.search([
                ("lot_id", "=", quant.lot_id.id),
                ("product_id", "=", quant.product_id.id),
            ], order="id desc", limit=1)
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual] Error buscando stock.transit.line para quant %s: %s",
                quant.id,
                exc,
            )
            transit_line = False

        if not transit_line:
            return False

        voyage = transit_line.voyage_id if "voyage_id" in transit_line._fields else False

        if not voyage:
            return False

        try:
            shipment = Shipment.search([
                ("voyage_id", "=", voyage.id),
            ], order="id desc", limit=1)

            if shipment:
                return shipment
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual] Error buscando supplier.shipment por voyage %s: %s",
                voyage.id,
                exc,
            )

        return False

    @api.model
    def _iv_find_shipment_from_picking_for_quant(self, quant):
        """
        Fallback adicional: busca movimientos del lote que provengan de un picking
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
            move_line = MoveLine.search([
                ("lot_id", "=", quant.lot_id.id),
                ("product_id", "=", quant.product_id.id),
                ("picking_id", "!=", False),
            ], order="id desc", limit=20)
        except Exception as exc:
            _logger.warning(
                "[Inventario Visual] Error buscando stock.move.line para packing shipment quant %s: %s",
                quant.id,
                exc,
            )
            return False

        for ml in move_line:
            picking = ml.picking_id
            if (
                picking
                and "supplier_shipment_id" in picking._fields
                and picking.supplier_shipment_id
            ):
                return picking.supplier_shipment_id

        return False

    @api.model
    def _iv_get_packing_list_info_for_quant(self, quant):
        """
        Punto único de resolución para frontend.

        Prioridad:
        1. Renglón exacto del Packing List.
        2. Si el row no devolvió shipment, intentar resolverlo por tránsito.
        3. Embarque por stock.transit.line/voyage.
        4. Embarque por picking.supplier_shipment_id.
        """
        if not quant or not quant.exists() or not quant.lot_id:
            return {}

        row = self._iv_find_packing_row_for_quant(quant)
        if row:
            info = self._iv_make_packing_info_from_row(row)

            # Si tenemos row pero NO shipment_id, intentamos completar con fallbacks
            if info and not info.get("shipment_id"):
                shipment = (
                    self._iv_find_shipment_from_transit_for_quant(quant)
                    or self._iv_find_shipment_from_picking_for_quant(quant)
                )
                if shipment:
                    info["shipment_id"] = shipment.id
                    info["shipment_name"] = shipment.name or shipment.display_name

            return info

        shipment = self._iv_find_shipment_from_transit_for_quant(quant)
        if shipment:
            return self._iv_make_packing_info_from_shipment(shipment)

        shipment = self._iv_find_shipment_from_picking_for_quant(quant)
        if shipment:
            return self._iv_make_packing_info_from_shipment(shipment)

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

        return result