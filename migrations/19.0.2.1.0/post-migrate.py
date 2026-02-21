import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva server actions viejas de Studio vinculadas a productos.cotizar.

    Por qué: Las acciones de Studio usan campos x_studio_* y uom_po_id
    que no existen en Odoo 19. Al quedar activas en la DB, aparecen
    en el menú Actions y generan AttributeError al ejecutarse.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Buscar acciones de servidor con código que referencie el modelo viejo
    old_actions = env["ir.actions.server"].search(
        [
            ("state", "=", "code"),
            ("code", "like", "x_productos_a_cotizar"),
        ]
    )
    if old_actions:
        # Desvincular del menú Actions y desactivar
        old_actions.write({"binding_model_id": False})
        _logger.info(
            "Desvinculadas %d server actions Studio viejas: %s",
            len(old_actions),
            old_actions.mapped("name"),
        )
