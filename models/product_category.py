from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = "product.category"

    # Por qué: Margen por defecto de la categoría se usa para autocompletar
    # el campo margin en productos.cotizar al importar precio de compra.
    # Patrón: multiplicador directo (1.20 = +20%), consistente con productos.cotizar.
    margin_default = fields.Float(
        string="Margen por defecto",
        digits=(5, 2),
        help="Multiplicador directo. Ej: 1.20 = +20%",
    )
