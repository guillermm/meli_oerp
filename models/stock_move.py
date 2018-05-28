# -*- coding: utf-8 -*-

from odoo import models, api, fields, tools
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

class StockMove(models.Model):

    _inherit = 'stock.move'
    
    @api.multi
    def action_done(self):
        res = super(StockMove, self).action_done()
        products_meli = self.mapped('product_id').mapped('product_tmpl_id').filtered('meli_pub')
        if products_meli:
            products_meli._mark_to_update_meli()
        return res
    
    @api.multi
    def action_cancel(self):
        res = super(StockMove, self).action_cancel()
        products_meli = self.mapped('product_id').mapped('product_tmpl_id').filtered('meli_pub')
        if products_meli:
            products_meli._mark_to_update_meli()
        return res