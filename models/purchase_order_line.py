# Por qué: agrega botón de historial de precios en líneas de compra.
from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def action_ver_historial_precios(self):
        """Abre wizard con últimas 10 operaciones de este producto + proveedor."""
        self.ensure_one()
        return self.env['historial.precios.wizard'].action_open_historial(
            product_id=self.product_id.id,
            partner_id=self.order_id.partner_id.id,
            origin='purchase',
        )
