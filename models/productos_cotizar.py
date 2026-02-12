from odoo import models, fields, api, _
from odoo.exceptions import UserError


# Por qué: Selection con group_expand para que kanban muestre todas las columnas
# aunque estén vacías. Patrón estándar Odoo para flujos tipo pipeline.
STAGE_SELECTION = [
    ("borrador", "Borrador"),
    ("solicitado", "Solicitado"),
    ("cotizado", "Cotizado"),
    ("listo", "Listo"),
]


class ProductosCotizar(models.Model):
    _name = "productos.cotizar"
    _description = "Productos a Cotizar"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, date desc, id desc"

    # --- Campos generales ---
    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
    )
    stage = fields.Selection(
        selection=STAGE_SELECTION,
        string="Etapa",
        default="borrador",
        required=True,
        tracking=True,
        group_expand="_group_expand_stage",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgente")],
        string="Prioridad",
        default="0",
    )
    date = fields.Datetime(
        string="Fecha solicitud",
        default=fields.Datetime.now,
    )
    date_start = fields.Date(string="Fecha inicio")
    date_stop = fields.Date(string="Fecha límite")
    date_done = fields.Date(string="Fecha finalización")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        tracking=True,
    )
    quantity = fields.Float(string="Cantidad", default=1.0)
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        tracking=True,
        domain="[('supplier_rank', '>', 0)]",
    )

    # --- Sección compras ---
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda compra",
    )
    exchange_rate = fields.Float(
        string="Tipo de cambio",
        digits=(12, 6),
    )
    lead_time = fields.Integer(string="Plazo entrega (días)")
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Orden de compra",
        readonly=True,
        copy=False,
    )
    purchase_line_id = fields.Many2one(
        "purchase.order.line",
        string="Línea OC",
        readonly=True,
        copy=False,
    )
    purchase_price_initial = fields.Float(
        string="Precio compra inicial",
        digits="Product Price",
    )
    margin = fields.Float(
        string="Margen (%)",
        digits=(5, 2),
    )
    # Por qué: Precio final calculado como precio inicial + margen.
    # Computed stored para poder filtrar/agrupar en vistas.
    purchase_price_final = fields.Float(
        string="Precio compra final",
        digits="Product Price",
        compute="_compute_purchase_price_final",
        store=True,
    )

    # --- Sección ventas ---
    sale_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda venta",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Presupuesto",
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea presupuesto",
        readonly=True,
    )
    sale_value_calc = fields.Float(
        string="Valor venta calculado",
        digits="Product Price",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Lista de precios",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # --- Computed ---

    @api.depends("purchase_price_initial", "margin")
    def _compute_purchase_price_final(self):
        """Precio final = precio inicial * (1 + margen/100)"""
        for rec in self:
            if rec.purchase_price_initial and rec.margin:
                rec.purchase_price_final = rec.purchase_price_initial * (
                    1 + rec.margin / 100
                )
            else:
                rec.purchase_price_final = rec.purchase_price_initial

    # --- group_expand ---
    # Por qué: Kanban necesita mostrar todas las columnas del pipeline
    # aunque no tengan registros. group_expand se llama al agrupar por stage.
    @api.model
    def _group_expand_stage(self, stages, domain):
        return [key for key, _ in STAGE_SELECTION]

    # --- Secuencia ---

    @api.model_create_multi
    def create(self, vals_list):
        """Asigna secuencia automática al crear registros."""
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "productos.cotizar"
                ) or _("Nuevo")
        return super().create(vals_list)

    # --- Acción principal: crear órdenes de compra ---
    # Patrón: Agrupación por (proveedor, moneda) para crear 1 PO por combinación.
    # Esto evita múltiples POs al mismo proveedor cuando hay varias solicitudes.
    def action_create_purchase_orders(self):
        """Crea purchase.order agrupadas por proveedor + moneda.
        Cada solicitud se convierte en una línea de la PO correspondiente.
        """
        # Validar que todas tengan proveedor y moneda
        for rec in self:
            if not rec.supplier_id:
                raise UserError(
                    _("La solicitud '%s' no tiene proveedor asignado.") % rec.name
                )
            if not rec.currency_id:
                raise UserError(
                    _("La solicitud '%s' no tiene moneda de compra.") % rec.name
                )

        # Agrupar por (proveedor, moneda)
        groups = {}
        for rec in self:
            key = (rec.supplier_id.id, rec.currency_id.id)
            groups.setdefault(key, self.browse())
            groups[key] |= rec

        created_orders = self.env["purchase.order"]
        for (supplier_id, currency_id), recs in groups.items():
            # Crear PO
            po = self.env["purchase.order"].create(
                {
                    "partner_id": supplier_id,
                    "currency_id": currency_id,
                }
            )
            # Crear líneas
            for rec in recs:
                pol = self.env["purchase.order.line"].create(
                    {
                        "order_id": po.id,
                        "product_id": rec.product_id.id,
                        "product_qty": rec.quantity,
                        "price_unit": rec.purchase_price_initial or 0.0,
                    }
                )
                # Linkear solicitud → PO y línea
                rec.write(
                    {
                        "purchase_order_id": po.id,
                        "purchase_line_id": pol.id,
                        "stage": "cotizado",
                    }
                )
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
