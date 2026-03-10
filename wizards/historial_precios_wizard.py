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
    line_ids = fields.One2many(
        'historial.precios.wizard.line', 'wizard_id',
        string='Historial',
    )

    @api.model
    def action_open_historial(self, product_id, partner_id, origin):
        """Crea el wizard y lo abre con las últimas 10 líneas."""
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
        """Busca las últimas 10 líneas históricas según origen (venta/compra).
        Incluye todos los estados para dar visibilidad completa."""
        self.ensure_one()
        LineWiz = self.env['historial.precios.wizard.line']

        if self.origin == 'sale':
            # Por qué: incluir TODOS los estados (draft, sent, sale, done, cancel)
            # para que el vendedor vea el historial completo de negociación.
            lines = self.env['sale.order.line'].search([
                ('product_id', '=', self.product_id.id),
                ('order_id.partner_id', '=', self.partner_id.id),
            ], order='create_date desc', limit=10)
            for line in lines:
                LineWiz.create({
                    'wizard_id': self.id,
                    'order_name': line.order_id.name,
                    'date': line.order_id.date_order,
                    'product_name': line.product_id.display_name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'price_total': line.price_subtotal,
                    'currency_id': line.currency_id.id,
                    # Por qué: traducir el state técnico a un label legible
                    'order_state': SALE_STATE_LABELS.get(
                        line.order_id.state, line.order_id.state),
                })
        else:
            # Por qué: misma lógica para compras, sin filtro de estado.
            lines = self.env['purchase.order.line'].search([
                ('product_id', '=', self.product_id.id),
                ('order_id.partner_id', '=', self.partner_id.id),
            ], order='create_date desc', limit=10)
            for line in lines:
                LineWiz.create({
                    'wizard_id': self.id,
                    'order_name': line.order_id.name,
                    'date': line.order_id.date_order,
                    'product_name': line.product_id.display_name,
                    'quantity': line.product_qty,
                    'price_unit': line.price_unit,
                    'price_total': line.price_subtotal,
                    'currency_id': line.currency_id.id,
                    'order_state': PURCHASE_STATE_LABELS.get(
                        line.order_id.state, line.order_id.state),
                })


class HistorialPreciosWizardLine(models.TransientModel):
    _name = 'historial.precios.wizard.line'
    _description = 'Línea de historial de precios'

    wizard_id = fields.Many2one('historial.precios.wizard', ondelete='cascade')
    order_name = fields.Char('Nro Cotización')
    date = fields.Datetime('Fecha')
    product_name = fields.Char('Producto')
    quantity = fields.Float('Cantidad')
    price_unit = fields.Monetary('Precio unitario', currency_field='currency_id')
    price_total = fields.Monetary('Precio total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    # Por qué: mostrar el estado del presupuesto/orden para que el vendedor
    # distinga entre cotizaciones, órdenes confirmadas y canceladas.
    order_state = fields.Char('Estado')
