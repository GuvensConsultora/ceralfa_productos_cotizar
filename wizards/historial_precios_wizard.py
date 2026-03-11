# Por qué: wizard TransientModel que muestra las últimas 10 operaciones
# de un producto con un partner (cliente o proveedor).
# Se abre desde un botón en las líneas de presupuesto de venta o compra.
# Incluye TODOS los estados (cotización, confirmada, cancelada) para dar
# visibilidad completa del historial de negociación.
from odoo import api, fields, models

# Por qué: mapeo centralizado de state técnico → label legible.
# Evita hardcodear strings en _compute_lines y facilita mantenimiento.
SALE_STATE_LABELS = {
    'draft': 'Cotización',
    'sent': 'Cotización enviada',
    'sale': 'Orden de venta',
    'done': 'Bloqueada',
    'cancel': 'Cancelado',
}
PURCHASE_STATE_LABELS = {
    'draft': 'Solicitud de cotización',
    'sent': 'Solicitud enviada',
    'purchase': 'Orden de compra',
    'done': 'Bloqueada',
    'cancel': 'Cancelado',
}


class HistorialPreciosWizard(models.TransientModel):
    _name = 'historial.precios.wizard'
    _description = 'Historial de precios por producto y partner'

    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente / Proveedor', readonly=True)
    origin = fields.Selection([
        ('sale', 'Ventas'),
        ('purchase', 'Compras'),
    ], string='Origen', readonly=True)
    # Por qué: 2 secciones separadas — mismo cliente (top 3) vs todos (top 10).
    # Permite al vendedor comparar el precio que le dimos a ESTE cliente
    # contra el precio general del mercado.
    line_ids = fields.One2many(
        'historial.precios.wizard.line', 'wizard_id',
        string='Últimas 3 cotizaciones a este cliente',
        domain=[('section', '=', 'partner')],
    )
    line_all_ids = fields.One2many(
        'historial.precios.wizard.line', 'wizard_id',
        string='Últimas 10 cotizaciones a cualquier cliente',
        domain=[('section', '=', 'all')],
    )

    @api.model
    def action_open_historial(self, product_id, partner_id, origin):
        """Crea el wizard y lo abre con las líneas históricas."""
        wizard = self.create({
            'product_id': product_id,
            'partner_id': partner_id,
            'origin': origin,
        })
        wizard._compute_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Historial de precios',
            'res_model': 'historial.precios.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _compute_lines(self):
        """Carga 2 secciones:
        - partner: últimas 3 veces que se cotizó al MISMO cliente
        - all: últimas 10 veces que se cotizó a CUALQUIER cliente (todos los estados)
        """
        self.ensure_one()
        LineWiz = self.env['historial.precios.wizard.line']

        if self.origin == 'sale':
            self._fill_sale_lines(LineWiz)
        else:
            self._fill_purchase_lines(LineWiz)

    def _fill_sale_lines(self, LineWiz):
        """Llena ambas secciones para ventas."""
        SOLine = self.env['sale.order.line']

        # --- Sección 1: últimas 3 al MISMO cliente ---
        partner_lines = SOLine.search([
            ('product_id', '=', self.product_id.id),
            ('order_id.partner_id', '=', self.partner_id.id),
        ], order='create_date desc', limit=3)
        for line in partner_lines:
            LineWiz.create(self._prepare_sale_line_vals(line, 'partner'))

        # --- Sección 2: últimas 10 a CUALQUIER cliente ---
        all_lines = SOLine.search([
            ('product_id', '=', self.product_id.id),
        ], order='create_date desc', limit=10)
        for line in all_lines:
            LineWiz.create(self._prepare_sale_line_vals(line, 'all'))

    def _fill_purchase_lines(self, LineWiz):
        """Llena ambas secciones para compras."""
        POLine = self.env['purchase.order.line']

        # --- Sección 1: últimas 3 al MISMO proveedor ---
        partner_lines = POLine.search([
            ('product_id', '=', self.product_id.id),
            ('order_id.partner_id', '=', self.partner_id.id),
        ], order='create_date desc', limit=3)
        for line in partner_lines:
            LineWiz.create(self._prepare_purchase_line_vals(line, 'partner'))

        # --- Sección 2: últimas 10 a CUALQUIER proveedor ---
        all_lines = POLine.search([
            ('product_id', '=', self.product_id.id),
        ], order='create_date desc', limit=10)
        for line in all_lines:
            LineWiz.create(self._prepare_purchase_line_vals(line, 'all'))

    def _prepare_sale_line_vals(self, line, section):
        """Prepara vals para una línea de venta."""
        return {
            'wizard_id': self.id,
            'section': section,
            'order_name': line.order_id.name,
            'date': line.order_id.date_order,
            'partner_name': line.order_id.partner_id.name,
            'product_name': line.product_id.display_name,
            'quantity': line.product_uom_qty,
            'price_unit': line.price_unit,
            'price_total': line.price_subtotal,
            'currency_id': line.currency_id.id,
            'order_state': SALE_STATE_LABELS.get(
                line.order_id.state, line.order_id.state),
        }

    def _prepare_purchase_line_vals(self, line, section):
        """Prepara vals para una línea de compra."""
        return {
            'wizard_id': self.id,
            'section': section,
            'order_name': line.order_id.name,
            'date': line.order_id.date_order,
            'partner_name': line.order_id.partner_id.name,
            'product_name': line.product_id.display_name,
            'quantity': line.product_qty,
            'price_unit': line.price_unit,
            'price_total': line.price_subtotal,
            'currency_id': line.currency_id.id,
            'order_state': PURCHASE_STATE_LABELS.get(
                line.order_id.state, line.order_id.state),
        }


class HistorialPreciosWizardLine(models.TransientModel):
    _name = 'historial.precios.wizard.line'
    _description = 'Línea de historial de precios'

    wizard_id = fields.Many2one('historial.precios.wizard', ondelete='cascade')
    # Por qué: section discrimina a qué lista pertenece la línea.
    # 'partner' = mismo cliente (top 3), 'all' = cualquier cliente (top 10).
    section = fields.Selection([
        ('partner', 'Mismo cliente'),
        ('all', 'Todos'),
    ])
    order_name = fields.Char('Nro Cotización')
    date = fields.Datetime('Fecha')
    # Por qué: en la sección "todos" se necesita ver a qué cliente se cotizó.
    partner_name = fields.Char('Cliente')
    product_name = fields.Char('Producto')
    quantity = fields.Float('Cantidad')
    price_unit = fields.Monetary('Precio unitario', currency_field='currency_id')
    price_total = fields.Monetary('Precio total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    order_state = fields.Char('Estado')
