# Por qué: agrega botón de historial de precios en líneas de compra
# + campos custom heredados de Studio v17 para vincular con x_productos_a_cotizar.
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Por qué: campos Studio v17 que ya existen en DB — los declaramos
    # para que el ORM los reconozca y podamos usarlos en código Python.
    x_studio_pto_de_vta = fields.Many2one(
        'sale.order', string='Ppto de Venta',
    )
    x_studio_id_linea_or_vta = fields.Integer('ID Línea Orden Vta')
    x_studio_id_prod_a_coti = fields.Integer('ID Producto a Cotizar')

    def action_ver_historial_precios(self):
        """Abre wizard con últimas 10 operaciones de este producto + proveedor."""
        self.ensure_one()
        return self.env['historial.precios.wizard'].action_open_historial(
            product_id=self.product_id.id,
            partner_id=self.order_id.partner_id.id,
            origin='purchase',
        )
