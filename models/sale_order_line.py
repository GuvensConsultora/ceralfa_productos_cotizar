# Por qué: Reimplementa el toggle "Pedir Cotización" que existía en Studio v17.
# Al guardar el presupuesto, crea/archiva registros en x_productos_a_cotizar
# vinculados a cada línea del SO.
# Patrón: herencia de modelo + override create/write para sync automático.
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_pedir_cotizacion = fields.Boolean('Pedir Cotización', default=False)

    # -----------------------------------------------------------------
    # CRUD overrides — sincronizan x_productos_a_cotizar con el toggle
    # -----------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Por qué: solo sync líneas que vienen con toggle activo
        lines.filtered('x_pedir_cotizacion')._sync_productos_a_cotizar()
        return lines

    def write(self, vals):
        res = super().write(vals)
        # Por qué: si cambió el toggle o campos que afectan al registro vinculado,
        # re-sincronizar para crear/archivar/actualizar según corresponda.
        trigger_fields = {
            'x_pedir_cotizacion', 'product_id', 'product_uom_qty',
            'price_subtotal', 'name',
        }
        if trigger_fields & set(vals):
            self._sync_productos_a_cotizar()
        return res

    # -----------------------------------------------------------------
    # Lógica de sincronización
    # -----------------------------------------------------------------

    def _sync_productos_a_cotizar(self):
        """Crea, reactiva o archiva registros en x_productos_a_cotizar
        según el estado del toggle x_pedir_cotizacion en cada línea.
        """
        Cotizar = self.env['x_productos_a_cotizar'].sudo()

        for line in self:
            # Por qué: búsqueda con active_test=False para encontrar archivados también
            existing = Cotizar.with_context(active_test=False).search([
                ('x_studio_presupuesto_de_vtas', '=', line.order_id.id),
                ('x_studio_linea_ppto_vtas', '=', line.id),
            ], limit=1)

            if line.x_pedir_cotizacion:
                if existing:
                    # Por qué: si estaba archivado, reactivar sin duplicar
                    if not existing.x_active:
                        existing.x_active = True
                else:
                    # Por qué: crear nuevo registro con mapeo de campos SO line → cotizar
                    Cotizar.create(line._prepare_producto_a_cotizar_vals())
            else:
                # Por qué: toggle desactivado → archivar si existía activo
                if existing and existing.x_active:
                    existing.x_active = False

    def _prepare_producto_a_cotizar_vals(self):
        """Prepara el dict de valores para crear un x_productos_a_cotizar
        desde una línea de presupuesto de venta.
        """
        self.ensure_one()
        # Por qué: primera etapa por secuencia = estado inicial del workflow
        first_stage = self.env['x_productos_a_cotizar_stage'].search(
            [], order='x_studio_sequence, id', limit=1,
        )
        return {
            'x_name': self.name or (self.product_id.name if self.product_id else ''),
            'x_studio_producto': self.product_id.product_tmpl_id.id if self.product_id else False,
            'x_studio_cantidad': self.product_uom_qty,
            'x_studio_cliente': self.order_id.partner_id.id,
            'x_studio_presupuesto_de_vtas': self.order_id.id,
            'x_studio_linea_ppto_vtas': self.id,
            'x_studio_stage_id': first_stage.id if first_stage else False,
            'x_studio_kanban_state': 'draft',
            'x_studio_currency_id': self.order_id.currency_id.id,
            'x_studio_val_vtas_calc': self.price_subtotal,
            'x_studio_date': fields.Date.today(),
        }
