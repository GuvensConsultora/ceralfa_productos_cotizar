import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva actions Studio viejas (refuerzo).

    Por qué: las migraciones 2.1-2.3 usaban tabla incorrecta 'ir_actions_server'.
    La 2.4.0 lo corrigió pero puede no haber corrido si el build falló antes.
    Este refuerzo garantiza que la acción ID 1043 quede desactivada.
    """
    cr.execute("""
        UPDATE ir_act_server
        SET active = false
        WHERE state = 'code'
          AND active = true
          AND (code LIKE '%%uom_po_id%%'
               OR code LIKE '%%x_studio_%%')
    """)
    _logger.info(
        "Desactivadas %d server actions Studio obsoletas",
        cr.rowcount,
    )
