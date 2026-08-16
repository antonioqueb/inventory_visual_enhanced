# -*- coding: utf-8 -*-
"""Qué NO ve el usuario de inventario en la app nativa de Inventario.

El vendedor necesita 'usuario de inventario' (stock.group_stock_user) para
consultar existencias — y con ese grupo Odoo le abre de más: la sección de
Información general, toda Operaciones y el menú de Lotes bajo Productos.
Son pantallas de almacén; el vendedor no tiene nada que hacer ahí.

POR QUÉ POR NOMBRE Y NO POR XML ID
----------------------------------
Son menús de CORE. Sus XML ID cambian entre builds (ver la regla
xpath-builds-enterprise: el 19.0 de GitHub no es el build desplegado), y
apuntarle a un id equivocado restringe el menú equivocado. El nombre, en
cambio, es exactamente lo que el usuario ve en pantalla y es lo que pidió
esconder. Se busca SOLO dentro del árbol de Inventario, comparando sin
acentos ni mayúsculas.

CÓMO SE RESTRINGE
-----------------
El grupo se REEMPLAZA por 'Administrador de inventario'
(stock.group_stock_manager), que implica al de usuario: el almacén sigue
viendo todo y el usuario raso deja de verlo. Sumar un grupo no serviría —
en Odoo los grupos de un menú son un OR, así que dejar el de usuario ahí
lo seguiría mostrando.

Corre como <function> en cada actualización del módulo: si alguien
actualiza 'stock' y core repone sus grupos, la siguiente pasada lo vuelve
a cerrar. Todo lo que toca (y lo que NO encuentra) queda en el log.
"""
import logging
import unicodedata

from odoo import api, models

_logger = logging.getLogger(__name__)

# Secciones de la app Inventario que el usuario raso NO debe ver. Se busca
# en TODO el árbol de Inventario, no solo en los hijos directos: la primera
# versión miraba únicamente el primer nivel y por eso no encontraba nada.
#
# Cada entrada es una tupla de alias del MISMO menú: el nombre depende del
# idioma y del build, y con un solo nombre se falla en silencio.
_HIDE = {
    'Información general': (
        'informacion general', 'informacion gral', 'general',
        'vista general', 'resumen', 'panorama general', 'overview',
    ),
    'Operaciones': (
        'operaciones', 'operacion', 'operations',
    ),
    'Productos': (
        'productos', 'producto', 'products',
    ),
    # Se deja aunque 'Productos' ya lo tape: si en este build el menú de
    # lotes cuelga de otro lado, igual queda cerrado.
    'Lotes': (
        'lotes', 'numeros de serie', 'lotes/numeros de serie',
        'lotes / numeros de serie', 'lots', 'lots/serial numbers',
    ),
}


def _norm(text):
    """minúsculas, sin acentos y con espacios colapsados."""
    txt = (text or '').strip().lower()
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(c for c in txt if not unicodedata.combining(c))
    return ' '.join(txt.split())


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _som_menu_groups_field(self):
        """Odoo 19 anda moviendo los m2m a res.groups (ir.ui.view y las
        acciones YA perdieron groups_id). Se detecta el nombre real en vez
        de asumirlo: escribir un campo inexistente aborta el -u entero."""
        for fname in ('groups_id', 'group_ids'):
            if fname in self._fields:
                return fname
        return None

    @api.model
    def _som_apply_inventory_menu_policy(self):
        gfield = self._som_menu_groups_field()
        if not gfield:
            _logger.error(
                '[inventory_visual_enhanced] ir.ui.menu no tiene campo de '
                'grupos conocido; la política de menús NO se aplicó.')
            return False

        manager = self.env.ref('stock.group_stock_manager',
                               raise_if_not_found=False)
        root = self.env.ref('stock.menu_stock_root', raise_if_not_found=False)
        if not manager or not root:
            _logger.error(
                '[inventory_visual_enhanced] Falta stock.group_stock_manager '
                'o stock.menu_stock_root; la política de menús NO se aplicó.')
            return False

        # sudo(): los menús son datos de configuración y esto corre en la
        # instalación/actualización del módulo.
        Menu = self.sudo()
        # TODO el árbol de Inventario, a cualquier profundidad. Mirar solo
        # los hijos directos fue el error de la primera versión: si el menú
        # cuelga un nivel más abajo, no se encontraba y fallaba callado.
        arbol = Menu.search([('id', 'child_of', root.id), ('id', '!=', root.id)])

        objetivos = Menu.browse()
        encontrados = set()
        for menu in arbol:
            nombre = _norm(menu.name)
            for etiqueta, alias in _HIDE.items():
                if nombre in alias:
                    objetivos |= menu
                    encontrados.add(etiqueta)
                    break

        for menu in objetivos:
            antes = ', '.join(menu[gfield].mapped('name')) or '(sin grupos)'
            if menu[gfield].ids == manager.ids:
                _logger.info(
                    '[inventory_visual_enhanced] Menú "%s" ya estaba '
                    'restringido.', menu.name)
                continue
            menu.write({gfield: [(6, 0, manager.ids)]})
            _logger.info(
                '[inventory_visual_enhanced] Menú "%s" restringido a '
                'Administrador de inventario (antes: %s).', menu.name, antes)

        faltantes = [e for e in _HIDE if e not in encontrados]

        # El árbol COMPLETO va al log siempre, no solo cuando falla. Sin
        # esto, un menú renombrado (o traducido distinto) deja la política
        # sin efecto y no hay forma de saber por qué: el log da los nombres
        # reales para corregir la lista de alias en un minuto.
        _logger.info(
            '[inventory_visual_enhanced] ─── Árbol de Inventario tal como '
            'está en ESTA base (%s menús) ───', len(arbol))
        for menu in arbol.sorted(key=lambda m: m.complete_name or ''):
            grupos = ', '.join(menu[gfield].mapped('name')) or '(sin grupos)'
            marca = '  <<< RESTRINGIDO' if menu in objetivos else ''
            _logger.info('[inventory_visual_enhanced]   %-58s [%s]%s',
                         menu.complete_name or menu.name, grupos, marca)

        if faltantes:
            _logger.warning(
                '[inventory_visual_enhanced] NO se encontró: %s. Se llaman '
                'distinto en esta base — busca el nombre real en el árbol de '
                'arriba y agrégalo a _HIDE en ir_ui_menu_policy.py.',
                ', '.join(faltantes))

        # El árbol de menús va en caché: sin esto el usuario los sigue
        # viendo hasta que reinicie la sesión. El nombre del método cambió
        # entre versiones — se prueba el que exista, no se asume.
        for meth in ('clear_cache', 'clear_caches'):
            fn = getattr(self.env.registry, meth, None)
            if callable(fn):
                fn()
                break
        return True
