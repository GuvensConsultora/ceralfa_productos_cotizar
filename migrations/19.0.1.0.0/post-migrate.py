"""Post-migración: copia datos de x_productos_a_cotizar (Studio) al nuevo modelo.

Por qué: El modelo Studio x_productos_a_cotizar tiene datos históricos que
deben preservarse. Esta migración mapea columnas x_studio_* a los campos
del nuevo modelo productos_cotizar.

IMPORTANTE: Verificar nombres reales de columnas en DB staging antes de deploy.
Los nombres x_studio_* pueden variar según la configuración de Studio.
"""
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Mapeo: columna Studio → campo nuevo modelo
# Tip: Ajustar este mapeo según las columnas reales de la tabla Studio en la DB
COLUMN_MAP = {
    "x_name": "name",
    "x_studio_priority": "priority",
    "x_studio_stage_id": None,  # Se mapea aparte (Studio usa stage_id como Many2one)
    "x_studio_product_id": "product_id",
    "x_studio_quantity": "quantity",
    "x_studio_supplier_id": "supplier_id",
    "x_studio_currency_id": "currency_id",
    "x_studio_exchange_rate": "exchange_rate",
    "x_studio_lead_time": "lead_time",
    "x_studio_purchase_price": "purchase_price_initial",
    "x_studio_margin": "margin",
    "x_studio_sale_order_id": "sale_order_id",
    "x_studio_sale_line_id": "sale_line_id",
    "x_studio_partner_id": "partner_id",
    "x_studio_pricelist_id": "pricelist_id",
    "x_studio_user_id": "user_id",
    "x_studio_date": "date",
    "x_studio_date_start": "date_start",
    "x_studio_date_stop": "date_stop",
    "x_studio_date_done": "date_done",
    "x_studio_sale_currency_id": "sale_currency_id",
    "x_studio_sale_value": "sale_value_calc",
}

# Mapeo de stages Studio (texto o id) → selection del nuevo modelo
STAGE_MAP = {
    "borrador": "borrador",
    "solicitado": "solicitado",
    "cotizado": "cotizado",
    "listo": "listo",
    # Agregar variantes si Studio usa nombres diferentes
    "draft": "borrador",
    "requested": "solicitado",
    "quoted": "cotizado",
    "done": "listo",
}


def migrate(cr, version):
    """Migra registros de x_productos_a_cotizar a productos_cotizar."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Verificar si la tabla Studio existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'x_productos_a_cotizar'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "Tabla x_productos_a_cotizar no encontrada. "
            "Saltando migración de datos."
        )
        return

    # Obtener columnas reales de la tabla Studio
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'x_productos_a_cotizar'
    """)
    existing_columns = {row[0] for row in cr.fetchall()}
    _logger.info(
        "Columnas encontradas en x_productos_a_cotizar: %s",
        existing_columns,
    )

    # Filtrar solo columnas que existen en la tabla
    valid_mappings = {}
    for studio_col, new_col in COLUMN_MAP.items():
        if studio_col in existing_columns and new_col:
            valid_mappings[studio_col] = new_col

    if not valid_mappings:
        _logger.warning(
            "No se encontraron columnas mapeables en x_productos_a_cotizar. "
            "Verificar COLUMN_MAP."
        )
        return

    # Leer registros Studio
    studio_cols = ", ".join(valid_mappings.keys())
    cr.execute(f"SELECT id, {studio_cols} FROM x_productos_a_cotizar")
    rows = cr.fetchall()
    col_names = ["id"] + list(valid_mappings.keys())

    migrated = 0
    for row in rows:
        record = dict(zip(col_names, row))
        vals = {}
        for studio_col, new_col in valid_mappings.items():
            value = record.get(studio_col)
            if value is not None:
                vals[new_col] = value

        # Mapear stage si existe
        if "x_studio_stage_id" in existing_columns:
            stage_val = record.get("x_studio_stage_id")
            if stage_val:
                # Studio puede guardar stage como texto o como id de x_studio_stage
                vals["stage"] = STAGE_MAP.get(str(stage_val).lower(), "borrador")

        if vals:
            try:
                env["productos.cotizar"].create(vals)
                migrated += 1
            except Exception as e:
                _logger.warning(
                    "Error migrando registro Studio id=%s: %s",
                    record["id"],
                    e,
                )

    _logger.info(
        "Migración completada: %d/%d registros migrados de "
        "x_productos_a_cotizar a productos.cotizar",
        migrated,
        len(rows),
    )
