from odoo import models, fields, _


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # Por qué: Computed count para el smart button que muestra
    # cuántas solicitudes de productos.cotizar están vinculadas a esta PO.
    cotizar_count = fields.Integer(
        string="Productos a Cotizar",
        compute="_compute_cotizar_count",
    )

    def _compute_cotizar_count(self):
        """Cuenta registros productos.cotizar vinculados a esta PO."""
        for order in self:
            order.cotizar_count = self.env["productos.cotizar"].search_count(
                [("purchase_order_id", "=", order.id)]
            )

    def action_open_productos_cotizar(self):
        """Abre lista de solicitudes vinculadas a esta PO.

        Por qué: Smart button para navegar directamente desde la PO
        a las solicitudes de cotización relacionadas.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Productos a Cotizar"),
            "res_model": "productos.cotizar",
            "domain": [("purchase_order_id", "=", self.id)],
            "view_mode": "list,form",
            "target": "current",
        }

    def action_send_to_productos_cotizar(self):
        """Importa precios de la PO a las solicitudes vinculadas.

        Flujo: Proveedor responde RFQ → Comprador clickea botón →
        precio de cada línea PO se copia a purchase_price_initial +
        margen se autocompleta desde categoría del producto.
        """
        self.ensure_one()
        solicitudes = self.env["productos.cotizar"].search(
            [
                ("purchase_order_id", "=", self.id),
                ("stage", "=", "en_progreso"),
            ]
        )
        solicitudes.action_import_purchase_price()
