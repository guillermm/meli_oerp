# -*- coding: utf-8 -*-

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

class WizardPrintTagDelivery(models.TransientModel):

    _name = 'wizard.print.tag.delivery'
    _description = u'Asistente para imprimir etiqueta de entrega(MELI)'
    
    meli_order_ids = fields.Many2many('mercadolibre.orders', 
        'wizard_print_tag_delivery_meli_orders_rel', 'wizard_id', 'meli_order_id', u'Pedidos Meli',)
    
    @api.one
    def get_tag_delivery_pdf(self):
        self.ensure_one()
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        params = {
            'shipment_ids': ",".join(self.meli_order_ids.mapped('shipping_id')),
            'response_type': 'pdf',
            'access_token':meli.access_token,
        }
        orders_query = "/shipment_labels"
        response = meli.get(orders_query, params)
        return response.content