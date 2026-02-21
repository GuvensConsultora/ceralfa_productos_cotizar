import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva actions Studio viejas y desvíncula nuestras actions del menú.

    Por qué: las migraciones 2.1.0 y 2.2.0 usaban tabla 'ir_actions_server'
    que NO existe — la tabla real es 'ir_act_server'. Por eso nunca
    desactivaron la acción Studio ID 1043 que sigue causando errores.
    """
    # 1. Desactivar actions Studio con código que referencia campos obsoletos
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

    # 2. Desvincular nuestras 3 server actions del menú Actions
    # Por qué: ahora se usan botones en <header> de la list view
    cr.execute("""
        UPDATE ir_act_server
        SET binding_model_id = NULL
        WHERE state = 'code'
          AND binding_model_id IS NOT NULL
          AND code IN (
              'records.action_create_purchase_orders()',
              'records.action_import_purchase_price()',
              'records.action_boton_listo()'
          )
    """)
    _logger.info(
        "Desvinculadas %d server actions propias del menú Actions",
        cr.rowcount,
    )
