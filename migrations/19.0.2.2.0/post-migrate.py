import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Desactiva server actions viejas de Studio que referencian x_studio_*.

    Por qué: SQL directo porque el ORM puede fallar si el modelo
    referenciado (x_productos_a_cotizar) ya no existe en ir.model.
    Se desvinculan del menú Actions para que no aparezcan más.
    """
    # Desvincular acciones con código que use campos x_studio_
    # (cubre tanto x_productos_a_cotizar como cualquier otra acción Studio huérfana)
    cr.execute("""
        UPDATE ir_actions_server
        SET binding_model_id = NULL
        WHERE state = 'code'
          AND binding_model_id IS NOT NULL
          AND (code LIKE '%%x_productos_a_cotizar%%'
               OR code LIKE '%%x_studio_%%')
    """)
    _logger.info(
        "Desvinculadas %d server actions Studio viejas",
        cr.rowcount,
    )
