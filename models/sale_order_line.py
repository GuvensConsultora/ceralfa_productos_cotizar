from odoo import models, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def action_solicitar_cotizacion(self):
        """Crea un registro en productos.cotizar desde la línea de venta.

        Por qué: Los vendedores necesitan solicitar cotizaciones al área de
        compras directamente desde el presupuesto, sin salir del flujo de ventas.
        Se pre-carga toda la info disponible de la línea + orden.
        """
        self.ensure_one()
        order = self.order_id
        vals = {
            "product_id": self.product_id.id,
            "quantity": self.product_uom_qty,
            "stage": "solicitado",
            # Datos de venta
            "sale_order_id": order.id,
            "sale_line_id": self.id,
            "partner_id": order.partner_id.id,
            "pricelist_id": order.pricelist_id.id,
            "sale_currency_id": order.currency_id.id,
            "user_id": order.user_id.id or self.env.user.id,
            "sale_value_calc": self.price_subtotal,
        }
        solicitud = self.env["productos.cotizar"].create(vals)

        # Retornar form de la solicitud creada
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitud de Cotización"),
            "res_model": "productos.cotizar",
            "res_id": solicitud.id,
            "view_mode": "form",
            "target": "current",
        }
