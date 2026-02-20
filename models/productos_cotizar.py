from odoo import models, fields, api, _
from odoo.exceptions import UserError


# Por qué: 3 estados según flujo real del cliente:
# Nuevo → En progreso (RFQ creada) → Listo (precio devuelto al SO)
STAGE_SELECTION = [
    ("nuevo", "Nuevo"),
    ("en_progreso", "En progreso"),
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
        default="nuevo",
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
        string="Fecha",
        default=fields.Datetime.now,
    )
    # Por qué: Datetime en vez de Date porque el cliente necesita ver timestamps con hora
    date_start = fields.Datetime(string="Periodo inicio")
    date_stop = fields.Datetime(string="Periodo fin")
    date_done = fields.Date(string="Fecha en listo")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        tracking=True,
    )
    # Por qué: Categoría del producto, related stored para filtrar/agrupar en vistas
    category_id = fields.Many2one(
        "product.category",
        related="product_id.categ_id",
        store=True,
        string="Categoría",
    )
    # Por qué: No usar related con product.name porque en Odoo 19 es tipo
    # Translated (incompatible con Char). Se usa compute en su lugar.
    description = fields.Char(
        string="Descripción",
        compute="_compute_description",
    )

    @api.depends("product_id")
    def _compute_description(self):
        for rec in self:
            rec.description = rec.product_id.name or ""
    quantity = fields.Float(string="Cantidad", default=1.0)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
    )

    # --- Sección compras ---
    currency_id = fields.Many2one(
        "res.currency",
        string="Divisa Compra",
    )
    exchange_rate = fields.Float(
        string="Tipo de cambio",
        digits=(12, 6),
    )
    lead_time = fields.Integer(string="Plazo entrega (días)")
    date_delivery = fields.Date(string="Fecha entrega")
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Presupuesto Compra",
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
        string="Valor Compra Inicial",
        digits="Product Price",
    )
    # Por qué: Margen es multiplicador directo, no porcentaje.
    # Ej: 1.20 = precio * 1.20 (+20%)
    margin = fields.Float(
        string="Margen",
        digits=(5, 2),
    )
    # Por qué: Precio final = precio inicial * margen (multiplicador directo)
    # Computed stored para poder filtrar/agrupar en vistas.
    purchase_price_final = fields.Float(
        string="Valor Compra Final",
        digits="Product Price",
        compute="_compute_purchase_price_final",
        store=True,
    )

    # --- Sección ventas ---
    sale_currency_id = fields.Many2one(
        "res.currency",
        string="Divisa Venta",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Presupuesto Ventas",
        readonly=True,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea presupuesto",
        readonly=True,
    )
    sale_value_calc = fields.Float(
        string="Val Vtas Calc",
        digits="Product Price",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Lista de Precios",
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
        """Precio final = precio inicial * margen (multiplicador directo).

        Por qué: El cliente usa margen como multiplicador (1.20 = +20%),
        no como porcentaje aditivo.
        """
        for rec in self:
            if rec.purchase_price_initial and rec.margin:
                rec.purchase_price_final = rec.purchase_price_initial * rec.margin
            else:
                rec.purchase_price_final = rec.purchase_price_initial

    # --- group_expand ---
    # Por qué: Kanban/lista agrupada necesita mostrar todas las columnas
    # del pipeline aunque estén vacías.
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

    # --- Acción: crear RFQ agrupadas por moneda ---
    # Por qué: El comprador selecciona items en "Nuevo" y desde Actions crea RFQs.
    # Se usa la empresa propia como vendor temporal; el comprador cambia el proveedor
    # manualmente en el form de la RFQ.
    def action_create_purchase_orders(self):
        """Crea purchase.order agrupadas por moneda.

        Flujo: Vendedor tilda toggle → Comprador selecciona items Nuevo →
        Actions → Crear cotizaciones → Se crean RFQ con empresa propia como
        vendor temporal → Estado pasa a "en_progreso".
        """
        # Filtrar solo registros en estado "nuevo"
        recs_nuevo = self.filtered(lambda r: r.stage == "nuevo")
        if not recs_nuevo:
            raise UserError(
                _("Solo se pueden crear cotizaciones para registros en estado 'Nuevo'.")
            )

        # Agrupar por moneda (el vendor se asigna después manualmente)
        groups = {}
        company_partner = self.env.company.partner_id
        for rec in recs_nuevo:
            currency = rec.currency_id or self.env.company.currency_id
            groups.setdefault(currency.id, self.browse())
            groups[currency.id] |= rec

        created_orders = self.env["purchase.order"]
        for currency_id, recs in groups.items():
            # Por qué: Se usa la empresa propia como partner temporal.
            # El comprador cambia el proveedor en el form de la RFQ.
            po = self.env["purchase.order"].create(
                {
                    "partner_id": company_partner.id,
                    "currency_id": currency_id,
                }
            )
            for rec in recs:
                pol = self.env["purchase.order.line"].create(
                    {
                        "order_id": po.id,
                        "product_id": rec.product_id.id,
                        "product_qty": rec.quantity,
                        "price_unit": rec.purchase_price_initial or 0.0,
                    }
                )
                rec.write(
                    {
                        "purchase_order_id": po.id,
                        "purchase_line_id": pol.id,
                        "stage": "en_progreso",
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

    # --- Acción: importar precio de la PO line ---
    def action_import_purchase_price(self):
        """Lee precio de la línea de PO vinculada y lo copia a purchase_price_initial.

        Por qué: Después de que el proveedor responde la RFQ, el comprador
        importa el precio sin tipear manualmente.
        """
        for rec in self:
            if rec.stage != "en_progreso":
                continue
            if not rec.purchase_line_id:
                continue
            price = rec.purchase_line_id.price_unit
            if price > 0.0:
                rec.purchase_price_initial = price

    # --- Acción: Botón Listo ---
    def action_boton_listo(self):
        """Calcula precio de venta y lo devuelve a la línea del presupuesto.

        Flujo: purchase_price_initial * margin → sale_value_calc →
        sale_line_id.price_unit. Estado pasa a "listo".
        """
        for rec in self:
            if rec.stage != "en_progreso":
                continue
            if not rec.margin:
                raise UserError(
                    _("La solicitud '%s' no tiene margen asignado.") % rec.name
                )
            # Calcular valor venta = precio compra * margen (multiplicador)
            sale_value = rec.purchase_price_initial * rec.margin
            vals = {
                "sale_value_calc": sale_value,
                "stage": "listo",
                "date_done": fields.Date.today(),
            }
            rec.write(vals)
            # Devolver precio a la línea del presupuesto de venta
            if rec.sale_line_id:
                rec.sale_line_id.price_unit = sale_value
