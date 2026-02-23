# Por qué: Modelo custom creado en Studio con 8499 registros + 3 stages.
# Se usa para cotización de productos vinculada a compras/ventas.
# Patrón: mismos nombres de campo → Odoo reutiliza las columnas → datos preservados.
from odoo import fields, models


class ProductosACotizarStage(models.Model):
    _name = 'x_productos_a_cotizar_stage'
    _description = 'Productos a cotizar Stages'
    _order = 'x_studio_sequence, id'

    x_name = fields.Char('Nombre de la etapa', required=True)
    x_studio_sequence = fields.Integer('Secuencia')


class ProductosACotizar(models.Model):
    _name = 'x_productos_a_cotizar'
    _description = 'Productos a cotizar'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'x_studio_sequence, id'

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
