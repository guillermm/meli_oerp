# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import json
import logging

from odoo import fields, osv, models, _
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

from ..melisdk.meli import Meli

class ProductPost(models.TransientModel):
    
    _name = "mercadolibre.product.post"
    _description = "Wizard de Product Posting en MercadoLibre"

    type = fields.Selection([('post','Alta'),('put','Editado'),('delete','Borrado')], string='Tipo de operación' )
    posting_date = fields.Date('Fecha del posting')
    #'company_id': fields.many2one('res.company',string='Company'),
    #'mercadolibre_state': fields.related( 'res.company', 'mercadolibre_state', string="State" )

    def pretty_json( self, data ):
        return json.dumps( data, sort_keys=False, indent=4 )

    def product_post(self, context):
        #pdb.set_trace()
        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.template']
        #user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        #user_obj.company_id.meli_login()
        #company = user_obj.company_id
        #company = self.pool.get('res.company').browse(cr,uid,1)
        REDIRECT_URI = company.mercadolibre_redirect_uri
        CLIENT_ID = company.mercadolibre_client_id
        CLIENT_SECRET = company.mercadolibre_secret_key
        ACCESS_TOKEN = company.mercadolibre_access_token
        if not ACCESS_TOKEN:
            meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
            url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
            return {
	            "type": "ir.actions.act_url",
	            "url": url_login_meli,
	            "target": "new",
            }
        res = {}
        for product_id in product_ids:
            product = product_obj.browse(product_id)
            #import pdb;pdb.set_trace();
            #Alta
            if (product.meli_pub and not product.meli_id):
                res = product.product_post()
            #Actualiza
            elif (product.meli_pub and product.meli_id):
                res = product.product_update_to_meli()
            #Pausa
            elif (not product.meli_pub and product.meli_id):
                res = product.product_meli_status_pause()
            if 'name' in res:
                return res
        return res
