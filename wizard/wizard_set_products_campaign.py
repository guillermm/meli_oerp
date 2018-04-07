# -*- coding: utf-8 -*-

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

class WizardSetProductsCampaign(models.TransientModel):

    _name = 'wizard.set.products.campaign'
    _description = u'Asistente para configurar productos en campañas meli'
    
    meli_campaign_id = fields.Many2one('meli.campaign.record', u'Registro de Campaña', required=True)
    action_type = fields.Selection([
        ('add','Agregar Productos'),
        ('remove','Quitar Productos'),
        ('set','Configurar Productos'),
        ], string=u'Accion a realizar', required=True)
    product_template_ids = fields.Many2many('product.template', 
        'wizard_set_products_campaign_product_template_rel', 'wizard_id', 'product_template_id', u'Productos')
    
    @api.multi
    def action_set_products(self):
        campaign_line_model = self.env['meli.campaign.record.line']
        if self.action_type == 'set':
            self.meli_campaign_id.line_ids.filtered(lambda x: x.state == 'draft').unlink()
        if self.action_type in ['add', 'set']:
            for product in self.with_context(pricelist=self.meli_campaign_id.pricelist_id.id).product_template_ids:
                campaign_line_model.create({
                    'meli_campaign_id': self.meli_campaign_id.id,
                    'product_template_id': product.id,
                    'price_unit': product.list_price,
                    'list_price': product.price,
                    'meli_price': product.price,
                    })
        
        elif self.action_type == 'remove':
            lines_unpublish = self.meli_campaign_id.line_ids.filtered(lambda x: x.product_template_id in self.product_template_ids)
            if lines_unpublish:
                #cuando el producto esta en borrador eliminarlo
                #caso contrario no eliminarlo, 
                #xq una vez publicado meli no deja subir otra vez el mismo producto en la misma campaña
                lines_to_remove = lines_unpublish.filtered(lambda x: x.state == 'draft')
                lines_unpublish.action_unpublish_to_meli()
                if lines_to_remove:
                    lines_to_remove.unlink()
        return {'type': 'ir.actions.act_window_close'}