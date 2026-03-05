# Por qué: Modelo custom creado en Studio con 8499 registros + 3 stages.
# Se usa para cotización de productos vinculada a compras/ventas.
# Patrón: mismos nombres de campo → Odoo reutiliza las columnas → datos preservados.
from odoo import fields, models
from odoo.exceptions import UserError


class ProductosACotizarStage(models.Model):
    _name = 'x_productos_a_cotizar_stage'
    _description = 'Productos a cotizar Stages'
    _order = 'x_studio_sequence, id'
    # Por qué: el campo se llama x_name (herencia Studio), sin _rec_name
    # Odoo busca 'name' y muestra el ID en dropdowns/many2one
    _rec_name = 'x_name'

    x_name = fields.Char('Nombre de la etapa', required=True)
    x_studio_sequence = fields.Integer('Secuencia')


class ProductosACotizar(models.Model):
    _name = 'x_productos_a_cotizar'
    _description = 'Productos a cotizar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'x_studio_sequence, id'
    # Por qué: x_name en vez de name (herencia Studio) → sin esto los many2one muestran IDs
    _rec_name = 'x_name'
    # Por qué: el campo de archivado se llama x_active (Studio), no active.
    # Sin _active_name el ORM no filtra archivados automáticamente
    # y active_test=False no tiene efecto.
    _active_name = 'x_active'

    # --- Campos base ---
    x_name = fields.Char('Descripción', required=True)
    x_active = fields.Boolean('Activo', default=True)
    x_color = fields.Integer('Color')
    x_studio_sequence = fields.Integer('Secuencia')
    x_studio_priority = fields.Boolean('Alta prioridad')
    x_studio_notes = fields.Html('Notas')
    x_studio_date = fields.Date('Fecha')
    x_studio_date_start = fields.Datetime('Periodo del proceso')
    x_studio_date_stop = fields.Datetime('Fecha de finalización')
    x_studio_fecha_en_listo = fields.Date('Fecha en listo')

    # --- Stage / Kanban ---
    x_studio_stage_id = fields.Many2one(
        'x_productos_a_cotizar_stage', 'Etapa',
        required=True, ondelete='restrict',
    )
    x_studio_kanban_state = fields.Selection([
        ('draft', 'Cotización'),
        ('sent', 'Cotización Enviada'),
        ('sale', 'Orden de venta'),
        ('cancel', 'Cancelado'),
    ], string='Estado Fact Vta')
    x_studio_selection_field_6bo_1i73jg105 = fields.Selection([
        ('Borrador', 'Cotización'),
        ('Cotización Enviada', 'Cotización Enviada'),
        ('Orden de venta', 'Orden de venta'),
        ('Cancelado', 'Cancelado'),
    ], string='Nuevo Selección')

    # --- Producto ---
    x_studio_producto = fields.Many2one('product.template', 'Producto')
    x_studio_categoria = fields.Many2one('product.category', 'Categoria')
    x_studio_categoria_del_producto = fields.Many2one(
        'product.category', 'Categoria del producto',
        related='x_studio_producto.categ_id', store=True,
    )
    x_studio_cantidad = fields.Float('Cantidad')
    x_studio_margen = fields.Float('Margen')

    # --- Relaciones comerciales ---
    x_studio_cliente = fields.Many2one('res.partner', 'Cliente')
    x_studio_compaia = fields.Many2one('res.company', 'Compañia')
    x_studio_vendedor = fields.Many2one(
        'res.users', 'Vendedor',
        related='x_studio_presupuesto_de_vtas.user_id', store=True,
    )
    x_studio_lista_de_precios = fields.Many2one('product.pricelist', 'Lista de Precios')

    # --- Presupuestos vinculados ---
    x_studio_presupuesto_de_vtas = fields.Many2one('sale.order', 'Ppto Vtas')
    x_studio_ppto_comp = fields.Many2one('purchase.order', 'Presupuesto De Compra')
    x_studio_linea_ppto_vtas = fields.Integer('Linea Ppto Vtas')
    x_studio_linea_ppto_cpras = fields.Integer('Linea Ppto Cpras')

    # --- Montos (monetary con currency_field explícito) ---
    x_studio_currency_id = fields.Many2one('res.currency', 'Div Vtas')
    x_studio_divisa_en_compras = fields.Many2one('res.currency', 'Divisa en Compras')
    x_studio_tipo_de_cambio = fields.Monetary('Tipo de cambio', currency_field='x_studio_currency_id')
    x_studio_val_cpra_final = fields.Monetary('Valor Compra Final', currency_field='x_studio_currency_id')
    x_studio_val_vtas_calc = fields.Monetary('Val Vtas Calc.', currency_field='x_studio_currency_id')
    x_studio_valor_cpra = fields.Monetary('Valor Compra Inicial', currency_field='x_studio_currency_id')

    # --- Entrega ---
    x_studio_plazo_de_entrega = fields.Datetime('Fecha de entrega')
    x_studio_plazo_de_entrega_1 = fields.Integer('Plazo de entrega')

    # =================================================================
    # Acciones (reemplazan automatizaciones Studio v17)
    # =================================================================

    def action_marcar_listo(self):
        """Marca los registros seleccionados como 'Listo'.
        Setea fecha_en_listo = hoy y mueve a la última etapa por secuencia.
        """
        # Por qué: search con order desc + limit 1 = última etapa configurada
        last_stage = self.env['x_productos_a_cotizar_stage'].search(
            [], order='x_studio_sequence desc, id desc', limit=1,
        )
        if not last_stage:
            raise UserError("No hay etapas configuradas. Crear al menos una etapa.")
        self.write({
            'x_studio_fecha_en_listo': fields.Date.today(),
            'x_studio_stage_id': last_stage.id,
        })

    def action_cotizaciones(self):
        """Abre presupuestos vinculados o crea nuevos para los seleccionados.
        - Líneas CON presupuesto → se abren los existentes.
        - Líneas SIN presupuesto → se crea uno por cliente, con las líneas
          como productos del SO.
        """
        with_order = self.filtered('x_studio_presupuesto_de_vtas')
        without_order = self - with_order

        # Por qué: mapped() devuelve recordset de sale.order sin duplicados
        orders = with_order.mapped('x_studio_presupuesto_de_vtas')

        if without_order:
            # Por qué: agrupar por cliente → un SO por partner
            by_client = {}
            for rec in without_order:
                if not rec.x_studio_cliente:
                    continue
                by_client.setdefault(rec.x_studio_cliente.id, [])
                by_client[rec.x_studio_cliente.id].append(rec)

            if not by_client and not orders:
                raise UserError("Las líneas seleccionadas no tienen cliente asignado.")

            SaleOrder = self.env['sale.order']
            SaleOrderLine = self.env['sale.order.line']

            for partner_id, recs in by_client.items():
                order_vals = {'partner_id': partner_id}
                # Por qué: pricelist del primer registro que tenga
                pricelist = next(
                    (r.x_studio_lista_de_precios for r in recs
                     if r.x_studio_lista_de_precios), False,
                )
                if pricelist:
                    order_vals['pricelist_id'] = pricelist.id

                order = SaleOrder.create(order_vals)

                for rec in recs:
                    if rec.x_studio_producto:
                        # Por qué: product_variant_id → variante principal del template
                        product = rec.x_studio_producto.product_variant_id
                        SaleOrderLine.create({
                            'order_id': order.id,
                            'product_id': product.id,
                            'product_uom_qty': rec.x_studio_cantidad or 1.0,
                        })
                    # Vincular el presupuesto creado al registro
                    rec.x_studio_presupuesto_de_vtas = order.id

                orders |= order

        if not orders:
            raise UserError("No hay presupuestos vinculados ni líneas para crear.")

        # Por qué: si es uno solo → abrir form directo; si son varios → lista
        if len(orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': orders.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
            'name': 'Cotizaciones',
        }
