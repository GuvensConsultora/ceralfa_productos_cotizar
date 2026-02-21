import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva server actions de Studio que usan campos obsoletos.

    Por qué: la migración 2.2.0 solo desvinculó (binding_model_id = NULL)
    pero la acción seguía activa y podía dispararse desde botones o
    ir.actions.server ID directo. Ahora se desactiva completamente.

    Patrón: SQL directo porque el ORM no está disponible en migraciones.
    """
    # Desactivar acciones cuyo código Python referencia campos removidos
    # en Odoo 19 (uom_po_id) o campos Studio del modelo viejo (x_studio_*)
    cr.execute("""
        UPDATE ir_actions_server
        SET active = false
        WHERE state = 'code'
          AND active = true
          AND (code LIKE '%%uom_po_id%%'
               OR code LIKE '%%x_studio_%%')
    """)
    _logger.info(
        "Desactivadas %d server actions Studio obsoletas (uom_po_id / x_studio_)",
        cr.rowcount,
    )
