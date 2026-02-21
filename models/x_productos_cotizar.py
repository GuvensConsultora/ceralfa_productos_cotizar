from odoo import models


class XProductosACotizar(models.Model):
    """Herencia sobre el modelo Studio para agregar acción 'Cotizar'.

    Por qué: el modelo Studio x_productos_a_cotizar sigue en uso.
    La acción vieja (ir.actions.server ID 1043) usaba uom_po_id que no
    existe en Odoo 19. Este método reemplaza esa lógica rota.
    """

    _inherit = "x_productos_a_cotizar"

    def action_cotizar(self):
        """Crea purchase.order agrupadas por moneda y compañía.

        Por qué: replica la lógica del server action Studio viejo,
        pero sin uom_po_id (removido en Odoo 19) ni campos obsoletos.
        Se usa uom_id del producto en su lugar.
        """
        if not self:
            return

        # Agrupar por (moneda, compañía) como hacía la acción Studio original
        groups = {}
        for rec in self:
            key = (
                rec.x_studio_currency_id.id or self.env.company.currency_id.id,
                rec.x_studio_compaia.id if rec.x_studio_compaia else self.env.company.partner_id.id,
            )
            groups.setdefault(key, self.browse())
            groups[key] |= rec

        created_orders = self.env["purchase.order"]

        for (currency_id, company_id), recs in groups.items():
            # Fecha de entrega: la más temprana del grupo
            primer_entrega = min(recs, key=lambda r: r.x_studio_date_stop or r.create_date)

            po = self.env["purchase.order"].create({
                "partner_id": company_id,
                "currency_id": currency_id,
                "company_id": company_id,
                "date_order": primer_entrega.x_studio_date_stop,
            })

            for rec in recs:
                product = self.env["product.template"].browse(rec.x_studio_producto.id)
                self.env["purchase.order.line"].create({
                    "order_id": po.id,
                    "product_id": product.product_variant_id.id,
                    "product_qty": rec.x_studio_cantidad,
                    "price_unit": product.standard_price,
                    # Por qué: uom_po_id fue removido en Odoo 19, se usa uom_id
                    "product_uom": product.uom_id.id,
                    "name": rec.x_name,
                    "date_planned": primer_entrega.x_studio_date_stop,
                })

            # Actualizar referencias en los registros originales
            for po_line in po.order_line:
                # Buscar el registro que matchea por nombre
                matching = recs.filtered(lambda r: r.x_name == po_line.name)
                if matching:
                    matching[0].write({
                        "x_studio_ppto_comp": po.id,
                        "x_studio_linea_ppto_cpras": po_line.id,
                        "x_studio_stage_id": 2,  # En progreso
                    })

            created_orders |= po

        # Retornar acción para ver las POs creadas
        if len(created_orders) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "purchase.order",
                "res_id": created_orders.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "domain": [("id", "in", created_orders.ids)],
            "view_mode": "list,form",
            "target": "current",
        }
