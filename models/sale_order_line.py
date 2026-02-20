from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Por qué: Toggle en la lista embebida del SO para que el vendedor
    # solicite cotización sin salir del presupuesto. Al activar se crea
    # automáticamente el registro en productos.cotizar.
    solicitar_cotizacion = fields.Boolean(
        string="Soli. coti.",
        default=False,
    )
    # Por qué: Indica visualmente si el item ya tiene precio vigente
    precio_actual = fields.Boolean(
        string="Px actual.",
        default=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Si la línea se crea con el toggle activado, crear solicitud
        for line in lines:
            if line.solicitar_cotizacion and line.product_id:
                line._crear_solicitud_cotizacion()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "solicitar_cotizacion" not in vals:
            return res

        for line in self:
            if vals["solicitar_cotizacion"]:
                # Toggle ON → crear solicitud si no existe una vinculada
                existente = self.env["productos.cotizar"].search(
                    [("sale_line_id", "=", line.id)], limit=1
                )
                if not existente and line.product_id:
                    line._crear_solicitud_cotizacion()
            else:
                # Toggle OFF → eliminar solo si está en estado "nuevo"
                solicitud = self.env["productos.cotizar"].search(
                    [
                        ("sale_line_id", "=", line.id),
                        ("stage", "=", "nuevo"),
                    ]
                )
                solicitud.unlink()
        return res

    def _crear_solicitud_cotizacion(self):
        """Crea registro en productos.cotizar precargando datos de la línea SO.

        Por qué: Centraliza la lógica de creación para reutilizar
        desde create() y write().
        """
        self.ensure_one()
        order = self.order_id
        self.env["productos.cotizar"].create(
            {
                "product_id": self.product_id.id,
                "quantity": self.product_uom_qty,
                "stage": "nuevo",
                "sale_order_id": order.id,
                "sale_line_id": self.id,
                "partner_id": order.partner_id.id,
                "pricelist_id": order.pricelist_id.id,
                "sale_currency_id": order.currency_id.id,
                "user_id": order.user_id.id or self.env.user.id,
                "sale_value_calc": self.price_subtotal,
            }
        )
