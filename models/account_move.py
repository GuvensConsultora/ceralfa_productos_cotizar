from odoo import models, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    # Por qué: En Odoo 19 purchase_id es store=False (campo helper para auto-completar).
    # Pero el ORM lo registra en el árbol de triggers: cuando se crean purchase.order.line,
    # modified() intenta buscar account.move WHERE purchase_id IN (...) → falla porque
    # no hay columna en DB. Forzar store=True crea la columna y elimina el ValueError.
    # Tip: Este es un bug conocido de Odoo 19 (purchase_id not stored pero en trigger tree)
    purchase_id = fields.Many2one(store=True)
