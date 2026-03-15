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

    def action_esperando_precio(self):
        """Marca los registros como 'Cotización cargada, esperando precio'.
        Por qué: estado intermedio entre borrador y listo — el comprador ya cargó
                 la cotización pero aún no tiene respuesta de precio del proveedor.
        """
        self.write({'x_studio_kanban_state': 'sent'})

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

    def action_crear_cotizacion_compra(self):
        """Crea solicitudes de cotización de COMPRA agrupadas por moneda + compañía.
        Por qué: reemplaza la acción de servidor Studio v17 (ID 1043) que usaba
        uom_po_id (removido en Odoo 19).
        Patrón: agrupar registros → un PO por (currency, company) → vincular back.
        """
        if not self:
            raise UserError("Seleccione al menos un registro.")

        # Por qué: segunda etapa = "en proceso de cotización"
        second_stage = self.env['x_productos_a_cotizar_stage'].search(
            [], order='x_studio_sequence, id', limit=2,
        )
        target_stage = second_stage[-1] if len(second_stage) >= 2 else second_stage[:1]

        PurchaseOrder = self.env['purchase.order']
        created_orders = PurchaseOrder

        # --- Agrupar por (moneda, compañía) ---
        groups = {}
        for rec in self:
            key = (rec.x_studio_currency_id.id or False, rec.x_studio_compaia.id or False)
            groups.setdefault(key, self.browse())
            groups[key] |= rec

        for (currency_id, company_id), recs in groups.items():
            if not company_id:
                continue

            # Por qué: fecha de entrega más temprana del grupo como fecha de orden
            recs_with_date = recs.filtered('x_studio_date_stop')
            date_order = min(recs_with_date.mapped('x_studio_date_stop')) if recs_with_date else fields.Datetime.now()

            # Por qué: res.company → partner_id para tener el res.partner correcto del proveedor
            company = self.env['res.company'].browse(company_id)

            order_vals = {
                'partner_id': company.partner_id.id,
                'currency_id': currency_id,
                'company_id': company_id,
                'date_order': date_order,
                'order_line': [],
            }

            for rec in recs:
                if not rec.x_studio_producto:
                    continue
                product = rec.x_studio_producto.product_variant_id
                order_vals['order_line'].append((0, 0, {
                    'product_id': product.id,
                    'product_qty': rec.x_studio_cantidad or 1.0,
                    'price_unit': rec.x_studio_producto.standard_price,
                    # Por qué: uom_po_id no existe en v19, usamos uom_id del producto
                    'product_uom': rec.x_studio_producto.uom_id.id,
                    'name': rec.x_name,
                    'date_planned': date_order,
                    # Campos de vinculación con venta y producto a cotizar
                    'x_studio_pto_de_vta': rec.x_studio_presupuesto_de_vtas.id,
                    'x_studio_id_linea_or_vta': rec.x_studio_linea_ppto_vtas,
                    'x_studio_id_prod_a_coti': rec.id,
                }))

            if not order_vals['order_line']:
                continue

            po = PurchaseOrder.create(order_vals)
            created_orders |= po

            # Por qué: vincular el PO y sus líneas back al registro de productos a cotizar
            for po_line in po.order_line:
                cotizar_rec = self.browse(po_line.x_studio_id_prod_a_coti)
                if cotizar_rec:
                    cotizar_rec.write({
                        'x_studio_ppto_comp': po.id,
                        'x_studio_linea_ppto_cpras': po_line.id,
                    })

            # Mover a la etapa de "en cotización"
            if target_stage:
                recs.write({'x_studio_stage_id': target_stage.id})

        if not created_orders:
            raise UserError("No se pudieron crear cotizaciones. Verifique que los registros tengan producto y compañía.")

        # Por qué: si es una sola PO → abrir form; si son varias → lista
        if len(created_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'res_id': created_orders.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_orders.ids)],
            'name': 'Cotizaciones de Compra',
        }

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
