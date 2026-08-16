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

# Menús colgados DIRECTAMENTE de Inventario que el usuario raso no debe ver.
_HIDE_TOP = ('informacion general', 'operaciones')

# Dentro de 'Productos': el submenú de lotes/números de serie.
_PRODUCTS_MENU = 'productos'
_HIDE_UNDER_PRODUCTS = ('lotes', 'numeros de serie', 'lotes/numeros de serie')


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
        hijos = Menu.search([('parent_id', '=', root.id)])

        objetivos = Menu.browse()
        faltantes = list(_HIDE_TOP)

        for menu in hijos:
            nombre = _norm(menu.name)
            if nombre in _HIDE_TOP:
                objetivos |= menu
                if nombre in faltantes:
                    faltantes.remove(nombre)
            elif nombre == _PRODUCTS_MENU:
                lotes = Menu.search([('parent_id', '=', menu.id)]).filtered(
                    lambda m: _norm(m.name) in _HIDE_UNDER_PRODUCTS)
                if lotes:
                    objetivos |= lotes
                else:
                    faltantes.append('%s > lotes' % _PRODUCTS_MENU)

        for menu in objetivos:
            antes = ', '.join(menu[gfield].mapped('name')) or '(sin grupos)'
            if menu[gfield].ids == manager.ids:
                continue
            menu.write({gfield: [(6, 0, manager.ids)]})
            _logger.info(
                '[inventory_visual_enhanced] Menú "%s" restringido a '
                'Administrador de inventario (antes: %s).', menu.name, antes)

        if faltantes:
            _logger.warning(
                '[inventory_visual_enhanced] No se encontraron estos menús '
                'bajo Inventario (¿los renombraron?): %s. Revisar a mano.',
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
