import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva server actions de Studio que usan campos obsoletos.

    Por qué: la migración 2.2.0 solo desvinculó (binding_model_id = NULL)
    pero la acción seguía activa y podía dispararse desde botones o
    ir.actions.server ID directo. Ahora se desactiva completamente.

    Patrón: SQL directo porque el ORM no está disponible en migraciones.
    """
    # Por qué: ir_act_server es el _table real de ir.actions.server en Odoo
    # (NO ir_actions_server — ese nombre no existe y las migraciones previas fallaban silenciosamente)
    cr.execute("""
        UPDATE ir_act_server
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
