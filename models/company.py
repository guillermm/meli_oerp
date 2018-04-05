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

import os
import logging
import requests
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import csv
except ImportError:
    csv = False
    _logger.error('This module needs csv. Please install csv on your system')

from odoo import fields, osv, models, api
from odoo.tools.translate import _
from odoo import tools

from .meli_oerp_config import REDIRECT_URI

class ResCompany(models.Model):
    
    _name = "res.company"
    _inherit = "res.company"

    @api.multi
    def get_meli_state(self):
        # recoger el estado y devolver True o False (meli)
        #False if logged ok
        #True if need login
        _logger.info('company get_meli_state() ')
        company = self.env.user.company_id
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance(company)
        ACCESS_TOKEN = company.mercadolibre_access_token
        REFRESH_TOKEN = company.mercadolibre_refresh_token
        ML_state = False
        message = "Login to ML needed in Odoo."
        #pdb.set_trace()

        try:
            _logger.info("access_token:"+str(ACCESS_TOKEN))
            response = meli.get("/users/"+company.mercadolibre_seller_id, {'access_token':meli.access_token} )
            _logger.info("response.content:"+str(response.content))
            rjson = response.json()
            #response = meli.get("/users/")
            if "error" in rjson:
                ML_state = True
                if rjson["error"]=="not_found":
                    ML_state = True
                if "message" in rjson:
                    message = rjson["message"]
                    if (rjson["message"]=="expired_token" or rjson["message"]=="invalid_token"):
                        ML_state = True
                        try:
                            refresh = meli.get_refresh_token()
                            _logger.info("need to refresh:"+str(refresh))
                            if (refresh):
                                ACCESS_TOKEN = meli.access_token
                                REFRESH_TOKEN = meli.refresh_token
                                company.write({'mercadolibre_access_token': ACCESS_TOKEN, 'mercadolibre_refresh_token': REFRESH_TOKEN, 'mercadolibre_code': '' } )
                                ML_state = False
                        except Exception as e:
                            _logger.error(e)
            if ACCESS_TOKEN=='' or ACCESS_TOKEN==False:
                ML_state = True
        except requests.exceptions.ConnectionError as e:
            #raise osv.except_osv( _('MELI WARNING'), _('NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, and Secret Key and try again'))
            ML_state = True
            error_msg = 'MELI WARNING: NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, and Secret Key and try again '
            _logger.error(error_msg)
        except Exception as ex:
            #raise osv.except_osv( _('MELI WARNING'), _('NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, and Secret Key and try again'))
            ML_state = True
            error_msg = 'MELI WARNING: NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, Vendor ID and Secret Key and try again'
            _logger.error(error_msg)
            _logger.error(tools.ustr(ex))
#        except requests.exceptions.HTTPError as e:
#            print "And you get an HTTPError:", e.message
        if ML_state:
            ACCESS_TOKEN = ''
            REFRESH_TOKEN = ''
            company.write({'mercadolibre_access_token': ACCESS_TOKEN, 'mercadolibre_refresh_token': REFRESH_TOKEN, 'mercadolibre_code': '' } )

            if (company.mercadolibre_refresh_token and company.mercadolibre_cron_mail):
                # we put the job_exception in context to be able to print it inside
                # the email template
                context = {
                    'job_exception': message,
                    'dbname': self._cr.dbname,
                }
                _logger.debug(
                    "Sending scheduler error email with context=%s", context)
                self.env['mail.template'].browse(
                    company.mercadolibre_cron_mail.id
                ).with_context(context).sudo().send_mail( (company.id), force_send=True)
        #FIX: esta funcion es de un campo calculado
        #pero erroneamente se usa en una tarea cron, por lo que no se pasa el recordset sino vario
        #asi que verificar que exxista algo para hacer el write
        if self:
            self.mercadolibre_state = ML_state

    mercadolibre_client_id = fields.Char(string='Client ID para ingresar a MercadoLibre',size=128)
    mercadolibre_secret_key = fields.Char(string='Secret Key para ingresar a MercadoLibre',size=128)
    mercadolibre_redirect_uri = fields.Char( string='Redirect uri (https://myserver/meli_login)',size=1024)
    mercadolibre_access_token = fields.Char( string='Access Token',size=256)
    mercadolibre_refresh_token = fields.Char( string='Refresh Token', size=256)
    mercadolibre_code = fields.Char( string='Code', size=256)
    mercadolibre_seller_id = fields.Char( string='Vendedor Id', size=256)
    mercadolibre_official_store_id = fields.Char( string='ID de Tienda Oficial', size=256)
    mercadolibre_state = fields.Boolean( compute=get_meli_state, string="Se requiere Iniciar Sesión con MLA", store=False )
    mercadolibre_category_import = fields.Char( string='Category Code to Import', size=256)
    mercadolibre_recursive_import = fields.Boolean( string='Import all categories (recursiveness)', size=256)
    mercadolibre_sale_team_id = fields.Many2one('crm.team', u'Equipo de Ventas por defecto')

    mercadolibre_cron_refresh = fields.Boolean(string='Cron Refresh')
    mercadolibre_cron_mail = fields.Many2one(
        comodel_name="mail.template",
        string="Cron Error E-mail Template",
        help="Select the email template that will be sent when "
        "cron refresh fails.")
    mercadolibre_cron_get_orders = fields.Boolean(string='Cron Get Orders')
    mercadolibre_cron_get_questions = fields.Boolean(string='Cron Get Questions')
    mercadolibre_cron_get_update_products = fields.Boolean(string='Cron Update Products')
    mercadolibre_create_website_categories = fields.Boolean(string='Create Website Categories')
    mercadolibre_validate_attributes_categories = fields.Boolean(string='Exigir Categorias con Atributos(Talla/Color)')
    meli_pricelist_id = fields.Many2one('product.pricelist', u'Tarifa de Venta para MELI')

    #'mercadolibre_login': fields.selection( [ ("unknown", "Desconocida"), ("logged","Abierta"), ("not logged","Cerrada")],string='Estado de la sesión'), )

    @api.multi
    def	meli_logout(self):
        _logger.info('company.meli_logout() ')
        self.ensure_one()
        company = self.env.user.company_id
        ACCESS_TOKEN = ''
        REFRESH_TOKEN = ''
        company.write({'mercadolibre_access_token': ACCESS_TOKEN, 'mercadolibre_refresh_token': REFRESH_TOKEN, 'mercadolibre_code': '' } )
        url_logout_meli = '/web?debug=#view_type=kanban&model=product.template&action=150'
        print url_logout_meli
        return {
            "type": "ir.actions.act_url",
            "url": url_logout_meli,
            "target": "new",
        }

    @api.multi
    def meli_login(self):
        _logger.info('company.meli_login() ')
        self.ensure_one()
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        return meli_util_model.get_url_meli_login(meli)

    @api.multi
    def meli_query_orders(self):
        _logger.info('company.meli_query_orders() ')
        orders_obj = self.env['mercadolibre.orders']
        result = orders_obj.orders_query_recent()
        return result

    @api.multi
    def meli_query_products(self):
        _logger.info('company.meli_query_products() ')
        self.product_meli_get_products()
        return {}

    def product_meli_get_products( self ):
        _logger.info('company.product_meli_get_products() ')
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
        #url_login_oerp = "/meli_login"
        results = []
        response = meli.get("/users/"+company.mercadolibre_seller_id+"/items/search", {'access_token':meli.access_token,'offset': 0 })
        #response = meli.get("/sites/MLA/search?seller_id="+company.mercadolibre_seller_id+"&limit=0", {'access_token':meli.access_token})
        rjson = response.json()
        _logger.info(rjson)
        if 'error' in rjson:
            if rjson['message']=='invalid_token' or rjson['message']=='expired_token':
                ACCESS_TOKEN = ''
                REFRESH_TOKEN = ''
                company.write({'mercadolibre_access_token': ACCESS_TOKEN, 'mercadolibre_refresh_token': REFRESH_TOKEN, 'mercadolibre_code': '' } )
            return {
            "type": "ir.actions.act_url",
            "url": url_login_meli,
            "target": "new",}
        if 'results' in rjson:
            results = rjson['results']
        #download?
        if (rjson['paging']['total']>rjson['paging']['limit']):
            pages = rjson['paging']['total']/rjson['paging']['limit']
            ioff = rjson['paging']['limit']
            condition_last_off = False
            while (condition_last_off!=True):
                response = meli.get("/users/"+company.mercadolibre_seller_id+"/items/search", {'access_token':meli.access_token,'offset': ioff })
                rjson2 = response.json()
                if 'error' in rjson2:
                    if rjson2['message']=='invalid_token' or rjson2['message']=='expired_token':
                        ACCESS_TOKEN = ''
                        REFRESH_TOKEN = ''
                        company.write({'mercadolibre_access_token': ACCESS_TOKEN, 'mercadolibre_refresh_token': REFRESH_TOKEN, 'mercadolibre_code': '' } )
                    condition = True
                    return {
                    "type": "ir.actions.act_url",
                    "url": url_login_meli,
                    "target": "new",}
                else:
                    results += rjson2['results']
                    ioff+= rjson['paging']['limit']
                    condition_last_off = ( ioff>=rjson['paging']['total'])
        _logger.info( rjson )
        _logger.info( "("+str(rjson['paging']['total'])+") products to check...")
        iitem = 0
        if (results):
            for item_id in results:
                print item_id
                iitem+= 1
                _logger.info( item_id + "("+str(iitem)+"/"+str(rjson['paging']['total'])+")" )
                posting_id = self.env['product.template'].search([('meli_id','=',item_id)])
                response = meli.get("/items/"+item_id, {'access_token':meli.access_token})
                rjson3 = response.json()
                if (posting_id):
                    _logger.info( "Item already in database: " + str(posting_id[0]) )
                    #print "Item already in database: " + str(posting_id[0])
                else:
                    #idcreated = self.pool.get('product.product').create(cr,uid,{ 'name': rjson3['title'], 'meli_id': rjson3['id'] })
                    if 'id' in rjson3:
                        prod_fields = {
                            'name': rjson3['id'],
                            'description': rjson3['title'].encode("utf-8"),
                            'meli_id': rjson3['id']
                        }
                        prod_fields['default_code'] = rjson3['id']
                        productcreated = self.env['product.template'].create((prod_fields))
                        if (productcreated):
                            _logger.info( "product created: " + str(productcreated) + " >> meli_id:" + str(rjson3['id']) + "-" + str( rjson3['title'].encode("utf-8")) )
                            #pdb.set_trace()
                            _logger.info(productcreated)
                            productcreated.product_meli_get_product()
                        else:
                            _logger.info( "product couldnt be created")
                    else:
                        _logger.info( "product error: " + str(rjson3) )
        return {}

    @api.multi
    def meli_update_products(self):
        _logger.info('company.meli_update_products() ')
        self.product_meli_update_products()
        return {}

    def product_meli_update_products( self ):
        _logger.info('company.product_meli_update_products() ')
        #buscar productos que hayan sido publicados en ML
        #para actualizarlos masivamente 
        products = self.env['product.template'].search([
            ('meli_pub','=',True),
            ('meli_id','!=',False),
        ])
        if products:
            for product in products:
                _logger.info("Product to update: %s", product.id)
                #_logger.info( "Product to update name: " + str(obj.name)  )
                #obj.product_meli_get_product()
                #import pdb; pdb.set_trace()
                #print "Product " + obj.name
                product.product_meli_get_product()
        return {}

    def meli_import_categories(self, context=None ):
        company = self.env.user.company_id
        category_model = self.env['mercadolibre.category']
        CATEGORY_ROOT = company.mercadolibre_category_import
        result = category_model.import_all_categories(category_root=CATEGORY_ROOT )
        return {}

    @api.model
    def action_sincronice_meli_data(self):
        company = self.env.user.company_id
        if (company.mercadolibre_cron_get_orders):
            _logger.info("obteniendo Pedidos desde Meli")
            message_list = self.meli_query_orders()
            if message_list and csv:
                file_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
                if not os.path.exists(file_path):
                    os.makedirs(file_path)
                file_path = os.path.join(file_path, "crear_pedidos_meli_%s.csv" % fields.Datetime.context_timestamp(self, datetime.now()).strftime('%Y_%m_%d_%H_%M_%S'))
                fp = open(file_path,'wb')
                csv_file = csv.writer(fp, quotechar='"', quoting=csv.QUOTE_ALL)
                csv_file.writerow(['Mensaje', 'Detalle'])
                for line in message_list:
                    csv_file.writerow([line[0], line[1]])
                fp.close()
        return True
    
    @api.multi
    def action_get_all_campaign(self):
        meli_util_model = self.env['meli.util']
        campaign_model = self.env['meli.campaign']
        self.ensure_one()
        meli = meli_util_model.get_new_instance(self)
        params = {'access_token': meli.access_token}
        response = meli.get("/users/%s/deals/search" % self.mercadolibre_seller_id, params)
        rjson = response.json()
        campaign_recs = campaign_model.browse()
        if 'error' in rjson:
            _logger.error('ERROR al obtener campañas de MELI: %s', rjson.get('message', ''))
        for campaign in rjson.get('results', []):
            campaign_recs |= campaign_model.find_create(campaign)
        action = True
        if campaign_recs:
            action = self.env.ref('meli_oerp.meli_campaign_action').read()[0]
            if len(campaign_recs) > 1:
                action['domain'] = [('id', 'in', campaign_recs.ids)]
            else:
                action['views'] = [(self.env.ref('meli_oerp.meli_campaign_form_view').id, 'form')]
                action['res_id'] = campaign_recs.ids[0]
        return action
    