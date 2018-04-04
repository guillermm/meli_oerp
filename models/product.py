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
import base64
import urllib2
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import csv
except ImportError:
    csv = False
    _logger.error('This module needs csv. Please install csv on your system')

from odoo import models, fields, api
from odoo.tools.translate import _
from odoo import tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF

from ..melisdk.meli import Meli

class ProductTemplate(models.Model):

    _inherit = "product.template"
    
    meli_imagen_id = fields.Char(string='Imagen Id', size=256)
    meli_post_required = fields.Boolean(string='Este producto es publicable en Mercado Libre')
    meli_id = fields.Char( string='Id del item asignado por Meli', readonly=True, copy=False)
    meli_title = fields.Char(string='Nombre del producto en Mercado Libre',size=256)
    meli_description = fields.Text(string='Descripción')
    meli_description_banner_id = fields.Many2one("mercadolibre.banner","Banner")
    meli_category = fields.Many2one("mercadolibre.category","Categoría de MercadoLibre")
    meli_listing_type = fields.Selection([("free","Libre"),("bronze","Bronce"),("silver","Plata"),("gold","Oro"),("gold_premium","Gold Premium"),("gold_special","Gold Special"),("gold_pro","Oro Pro")], string='Tipo de lista')
    meli_buying_mode = fields.Selection( [("buy_it_now","Compre ahora"),("classified","Clasificado")], string='Método de compra')
    meli_price = fields.Char(string='Precio de venta', size=128)
    meli_price_fixed = fields.Boolean(string='Price is fixed')
    meli_currency = fields.Selection([
        ("CLP","Peso Chileno (CLP)"),
        ("USD","Dolares Americanos (USD)")
        ],string='Moneda')
    meli_condition = fields.Selection([ ("new", "Nuevo"), ("used", "Usado"), ("not_specified","No especificado")],'Condición del producto')
    meli_available_quantity = fields.Integer(string='Cantidad disponible')
    meli_warranty = fields.Char(string='Garantía', size=256)
    meli_imagen_logo = fields.Char(string='Imagen Logo', size=256)
    meli_imagen_id = fields.Char(string='Imagen Id', size=256)
    meli_imagen_link = fields.Char(string='Imagen Link', size=256)
    meli_multi_imagen_id = fields.Char(string='Multi Imagen Ids', size=512)
    meli_video = fields.Char( string='Video (id de youtube)', size=256)
    meli_state = fields.Boolean(compute='product_get_meli_update', string="Inicio de sesión requerida", store=False)
    meli_status = fields.Char(compute='product_get_meli_update', size=128, string="Estado del producto en ML", store=False)
    meli_permalink = fields.Char(compute='product_get_meli_update', size=256, string='PermaLink in MercadoLibre', store=False)
    meli_dimensions = fields.Char( string="Dimensiones del producto", size=128)
    meli_pub = fields.Boolean('Meli Publication',help='MELI Product')
    ### Agregar imagen/archivo uno o mas, y la descripcion en HTML...
    # TODO Agregar el banner

    #@api.one
    @api.onchange('list_price') # if these fields are changed, call method
    def check_change_price(self):
        self.meli_price = str(self.list_price)
        
    @api.multi
    def get_product_image(self):
        self.ensure_one()
        return self.image

    def product_meli_get_product( self ):
        meli_util_model = self.env['meli.util']
        #pdb.set_trace()
        _logger.info("product_meli_get_product")
        _logger.info(self)
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance()
        try:
            response = meli.get("/items/"+self.meli_id, {'access_token':meli.access_token})
            #_logger.info(response)
            rjson = response.json()
            _logger.info(rjson)
        except IOError as e:
            print "I/O error({0}): {1}".format(e.errno, e.strerror)
            return {}
        except Exception as ex:
            print "Rare error: %s" % tools.ustr(ex)
            return {}
        des = ''
        desplain = ''
        vid = ''
        if 'error' in rjson:
            return {}
        if 'status' in rjson and rjson['status'] == 'inactive':
            _logger.info("Producto Inactivo: %s %s, no se puede actualizar", rjson.get('id') or '', rjson.get('title') or '')
            return {}
        if "content" in response:
            _logger.info(response.content)
        #    print "product_meli_get_product > response.content: " + response.content
        #TODO: traer la descripcion: con
        #https://api.mercadolibre.com/items/{ITEM_ID}/description?access_token=$ACCESS_TOKEN
        if rjson and rjson['descriptions']:
            response2 = meli.get("/items/"+self.meli_id+"/description", {'access_token':meli.access_token})
            rjson2 = response2.json()
            if 'text' in rjson2:
                des = rjson2['text']
            if 'plain_text' in rjson2:
                desplain = rjson2['plain_text']
            if (len(des)>0):
                desplain = des
        #TODO: verificar q es un video
        if rjson['video_id']:
            vid = ''
        #TODO: traer las imagenes
        #TODO:
        pictures = rjson['pictures']
        if pictures and len(pictures):
            thumbnail_url = pictures[0]['url']
            image = urllib2.urlopen(thumbnail_url).read()
            image_base64 = base64.encodestring(image)
            self.image_medium = image_base64
            #if (len(pictures)>1):
                #complete product images:
                #delete all images...
        #categories
        mlcatid = ""
        www_cat_id = False
        if ('category_id' in rjson):
            category_id = rjson['category_id']
            ml_cat = self.env['mercadolibre.category'].search([('meli_category_id','=',category_id)])
            ml_cat_id = ml_cat.id
            if (ml_cat_id):
                _logger.info("Categoria MELI con ID: %s ya existe!", ml_cat_id)
                mlcatid = ml_cat_id
                www_cat_id = ml_cat.public_category_id
            else:
                _logger.info("Creando Categoria con ID: %s", category_id)
                #https://api.mercadolibre.com/categories/MLA1743
                response_cat = meli.get("/categories/"+str(category_id), {'access_token':meli.access_token})
                rjson_cat = response_cat.json()
                fullname = ""
                if ("path_from_root" in rjson_cat):
                    path_from_root = rjson_cat["path_from_root"]
                    p_id = False
                    #pdb.set_trace()
                    for path in path_from_root:
                        fullname = fullname + "/" + path["name"]
                        if (company.mercadolibre_create_website_categories):
                            www_cats = self.env['product.public.category']
                            if www_cats!=False:
                                www_cat_id = www_cats.search([('name','=',path["name"])], limit=1).id
                                if not www_cat_id:
                                    www_cat_fields = {
                                      'name': path["name"],
                                      #'parent_id': p_id,
                                      #'sequence': 1
                                    }
                                    if p_id:
                                        www_cat_fields['parent_id'] = p_id
                                    www_cat_id = www_cats.create((www_cat_fields)).id
                                    if www_cat_id:
                                        _logger.info("Website Category created:"+fullname)
                                p_id = www_cat_id
                #fullname = fullname + "/" + rjson_cat['name']
                #print "category fullname:" + fullname
                cat_fields = {
                    'name': fullname,
                    'meli_category_id': ''+str(category_id),
                    'public_category_id': 0,
                }
                if www_cat_id:
                    cat_fields['public_category_id'] = www_cat_id
                ml_cat_id = self.env['mercadolibre.category'].create((cat_fields)).id
                if (ml_cat_id):
                    mlcatid = ml_cat_id
        imagen_id = ''
        meli_dim_str = ''
        if ('dimensions' in rjson):
            if (rjson['dimensions']):
                meli_dim_str = rjson['dimensions']
        if ('pictures' in rjson):
            if (len(rjson['pictures'])>0):
                imagen_id = rjson['pictures'][0]['id']
        meli_fields = {
            'name': str(rjson['title'].encode("utf-8")),
            #'name': str(rjson['id']),
            'meli_imagen_id': imagen_id,
            'meli_post_required': True,
            'meli_id': rjson['id'],
            'meli_permalink': rjson['permalink'],
            'meli_title': rjson['title'].encode("utf-8"),
            'meli_description': desplain,
#            'meli_description_banner_id': ,
            'meli_category': mlcatid,
            'meli_listing_type': rjson['listing_type_id'],
            'meli_buying_mode':rjson['buying_mode'],
            'meli_price': str(rjson['price']),
            'meli_price_fixed': True,
            'meli_currency': rjson['currency_id'],
            'meli_condition': rjson['condition'],
            'meli_available_quantity': rjson['available_quantity'],
            'meli_warranty': rjson['warranty'],
##            'meli_imagen_logo': fields.char(string='Imagen Logo', size=256),
##            'meli_imagen_id': fields.char(string='Imagen Id', size=256),
            'meli_imagen_link': rjson['thumbnail'],
##            'meli_multi_imagen_id': fields.char(string='Multi Imagen Ids', size=512),
            'meli_video': str(vid),
            'meli_dimensions': meli_dim_str,
            'list_price': rjson['price']
        }
        #pdb.set_trace()
        if www_cat_id!=False:
            #assign
            self.public_categ_ids = [(4,www_cat_id)]
            #tmpl_fields["public_categ_ids"] = [(4,www_cat_id)]
        self.write( meli_fields )
        if (rjson['available_quantity']>0):
            self.website_published = True
        else:
            self.website_published = False
#{"id":"MLA639109219","site_id":"MLA","title":"Disco Vinilo Queen - Rock - A Kind Of Magic","subtitle":null,"seller_id":171329758,"category_id":"MLA2038","official_store_id":null,"price":31,"base_price":31,"original_price":null,"currency_id":"ARS","initial_quantity":5,"available_quantity":5,"sold_quantity":0,"buying_mode":"buy_it_now","listing_type_id":"free","start_time":"2016-10-17T20:36:22.000Z","stop_time":"2016-12-16T20:36:22.000Z","end_time":"2016-12-16T20:36:22.000Z","expiration_time":null,"condition":"used","permalink":"http://articulo.mercadolibre.com.ar/MLA-639109219-disco-vinilo-queen-rock-a-kind-of-magic-_JM","thumbnail":"http://mla-s1-p.mlstatic.com/256905-MLA25108641321_102016-I.jpg","secure_thumbnail":"https://mla-s1-p.mlstatic.com/256905-MLA25108641321_102016-I.jpg","pictures":[{"id":"256905-MLA25108641321_102016","url":"http://mla-s1-p.mlstatic.com/256905-MLA25108641321_102016-O.jpg","secure_url":"https://mla-s1-p.mlstatic.com/256905-MLA25108641321_102016-O.jpg","size":"500x400","max_size":"960x768","quality":""},{"id":"185215-MLA25150338489_112016","url":"http://www.mercadolibre.com/jm/img?s=STC&v=O&f=proccesing_image_es.jpg","secure_url":"https://www.mercadolibre.com/jm/img?s=STC&v=O&f=proccesing_image_es.jpg","size":"500x500","max_size":"500x500","quality":""}],"video_id":null,"descriptions":[{"id":"MLA639109219-1196717922"}],"accepts_mercadopago":true,"non_mercado_pago_payment_methods":[],"shipping":{"mode":"not_specified","local_pick_up":false,"free_shipping":false,"methods":[],"dimensions":null,"tags":[]},"international_delivery_mode":"none","seller_address":{"id":193196973,"comment":"3B","address_line":"Billinghurst 1711","zip_code":"1425","city":{"id":"TUxBQlBBTDI1MTVa","name":"Palermo"},"state":{"id":"AR-C","name":"Capital Federal"},"country":{"id":"AR","name":"Argentina"},"latitude":-34.5906131,"longitude":-58.4101982,"search_location":{"neighborhood":{"id":"TUxBQlBBTDI1MTVa","name":"Palermo"},"city":{"id":"TUxBQ0NBUGZlZG1sYQ","name":"Capital Federal"},"state":{"id":"TUxBUENBUGw3M2E1","name":"Capital Federal"}}},"seller_contact":null,"location":{},"geolocation":{"latitude":-34.5906131,"longitude":-58.4101982},"coverage_areas":[],"attributes":[],"warnings":[],"listing_source":"","variations":[],"status":"active","sub_status":[],"tags":[],"warranty":null,"catalog_product_id":null,"domain_id":null,"seller_custom_field":null,"parent_item_id":null,"differential_pricing":null,"deal_ids":[],"automatic_relist":false,"date_created":"2016-10-17T20:36:22.000Z","last_updated":"2016-11-07T21:38:10.000Z"}
        posting_fields = {'posting_date': str(datetime.now()),'meli_id':rjson['id'],'product_id':self.product_variant_ids[0].id,'name': 'Post (ML): ' + self.meli_title }
        posting_id = self.env['mercadolibre.posting'].search([('meli_id','=',rjson['id'])]).id
        if not posting_id:
            posting = self.env['mercadolibre.posting'].create((posting_fields))
            posting_id = posting.id
            if (posting):
                posting.posting_query_questions()
        return {}

    def product_meli_login(self ):
        company = self.env.user.company_id
        REDIRECT_URI = company.mercadolibre_redirect_uri
        CLIENT_ID = company.mercadolibre_client_id
        CLIENT_SECRET = company.mercadolibre_secret_key
        meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
        url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
        #url_login_oerp = "/meli_login"
        return {
	        "type": "ir.actions.act_url",
	        "url": url_login_meli,
	        "target": "new",
        }

    def product_meli_status_close(self):
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        response = meli.put("/items/"+self.meli_id, { 'status': 'closed' }, {'access_token':meli.access_token})
        #print "product_meli_status_close: " + response.content
        return {}

    def product_meli_status_pause( self ):
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        response = meli.put("/items/"+self.meli_id, { 'status': 'paused' }, {'access_token':meli.access_token})
        #print "product_meli_status_pause: " + response.content
        return {}

    def product_meli_status_active( self ):
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        response = meli.put("/items/"+self.meli_id, { 'status': 'active' }, {'access_token':meli.access_token})
        #print "product_meli_status_active: " + response.content
        return {}

    def product_meli_delete( self ):
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        product = self
        if product.meli_status!='closed':
            self.product_meli_status_close()
        response = meli.put("/items/"+product.meli_id, { 'deleted': 'true' }, {'access_token':meli.access_token})
        #print "product_meli_delete: " + response.content
        rjson = response.json()
        ML_status = rjson.get("status")
        if "error" in rjson:
            ML_status = rjson["error"]
        if "sub_status" in rjson:
            if len(rjson["sub_status"]) and rjson["sub_status"][0]=='deleted':
                product.write({ 'meli_id': '' })
                product.product_variant_ids.write({ 'meli_id': '' })
        return {}

    def product_meli_upload_image( self ):
        meli_util_model = self.env['meli.util']
        warningobj = self.env['warning']
        meli = meli_util_model.get_new_instance()
        product = self
        product_image = product.get_product_image()
        if not product_image:
            return warningobj.info( title='MELI WARNING', message="Debe cargar una imagen de base en el producto.", message_html="" )
        # print "product_meli_upload_image"
        #print "product_meli_upload_image: " + response.content
        imagebin = base64.b64decode(product_image)
#       print "data:image/png;base64,"+imageb64
#       files = [ ('images', ('image_medium', imagebin, "image/png")) ]
        files = { 'file': ('image.jpg', imagebin, "image/jpeg"), }
        #print  files
        response = meli.upload("/pictures", files, { 'access_token': meli.access_token } )
        # print response.content
        rjson = response.json()
        if ("error" in rjson):
            raise UserError('No se pudo cargar la imagen en MELI! Error: %s , Mensaje: %s, Status: %s' % ( rjson["error"], rjson["message"],rjson["status"],))
            return { 'status': 'error', 'message': 'not uploaded'}
        _logger.info( rjson )
        if ("id" in rjson):
            #guardar id
            product.write( { "meli_imagen_id": rjson["id"], "meli_imagen_link": rjson["variations"][0]["url"] })
            #asociar imagen a producto
            if product.meli_id:
                response = meli.post("/items/"+product.meli_id+"/pictures", { 'id': rjson["id"] }, { 'access_token': meli.access_token } )
        return { 'status': 'success', 'message': 'uploaded and assigned' }

    def product_meli_upload_multi_images( self  ):
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        product = self
        if not product.product_image_ids:
            return { 'status': 'error', 'message': 'no images to upload' }
        image_ids = []
        c = 0
        #loop over images
        for product_image in product.product_image_ids:
            if (product_image.image):
                if product_image.meli_id:
                    image_ids+= [{'id': product_image.meli_id}]
                    _logger.info("Imagen ya tenia ID de MELI, se usara ese ID: %s", product_image.meli_id)
                    continue
                imagebin = base64.b64decode( product_image.image )
                #files = { 'file': ('image.png', imagebin, "image/png"), }
                files = { 'file': ('image.jpg', imagebin, "image/jpeg"), }
                response = meli.upload("/pictures", files, { 'access_token': meli.access_token } )
                print "meli upload:" + response.content
                rjson = response.json()
                if ("error" in rjson):
                    raise UserError(_('No se pudo cargar la imagen en MELI! Error: %s , Mensaje: %s, Status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
                    #return { 'status': 'error', 'message': 'not uploaded'}
                else:
                    product_image.write({'meli_id': rjson['id']})
                    image_ids+= [ { 'id': rjson['id'] }]
                    c = c + 1
                    print "image_ids:" + str(image_ids)
        product.write( { "meli_multi_imagen_id": "%s" % (image_ids) } )
        return image_ids

    @api.onchange('meli_description_banner_id',)
    def product_on_change_meli_banner(self):
        #solo para saber si ya habia una descripcion completada
        product = self
        banner = self.meli_description_banner_id
        #banner.description
        _logger.info( banner.description )
        result = ""
        if (banner.description!="" and banner.description!=False and product.meli_imagen_link!=""):
            imgtag = "<img style='width: 420px; height: auto;' src='%s'/>" % ( product.meli_imagen_link )
            result = banner.description.replace( "[IMAGEN_PRODUCTO]", imgtag )
            if (result):
                _logger.info( "result: %s" % (result) )
            else:
                result = banner.description
        return { 'value': { 'meli_description' : result } }

    @api.one
    def product_get_meli_update(self):
        self.ensure_one()
        #pdb.set_trace()
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        product = self
        ACCESS_TOKEN = company.mercadolibre_access_token
        ML_status = "unknown"
        ML_permalink = ""
        ML_state = False
        if not ACCESS_TOKEN or not product.meli_pub:
            ML_status = "unknown"
            ML_permalink = ""
            ML_state = True
        else:
            meli = meli_util_model.get_new_instance(company)
            if product.meli_id:
                response = meli.get("/items/"+product.meli_id, {'access_token':meli.access_token} )
                rjson = response.json()
                
                rjson = response.json()
                if "status" in rjson:
                    ML_status = rjson["status"]
                if "permalink" in rjson:
                    ML_permalink = rjson["permalink"]
                if "error" in rjson:
                    ML_status = rjson["error"]
                    ML_permalink = ""
                if "sub_status" in rjson:
                    if len(rjson["sub_status"]) and rjson["sub_status"][0]=='deleted':
                        product.write({ 'meli_id': '' })
        self.meli_status = ML_status
        self.meli_permalink = ML_permalink
        self.meli_state = ML_state
        
    @api.multi
    def set_meli_fields_aditionals(self, vals):
        self.ensure_one()
        return vals
    
    @api.multi
    def validate_fields_meli(self):
        self.ensure_one()
        errors = []
        fields_required = [
            'meli_category', 
            'meli_listing_type',
            'meli_buying_mode',
            'meli_currency',
            'meli_condition',
        ]
        for field_name in fields_required:
            if not field_name in self._fields:
                continue
            if not self[field_name]:
                errors.append("<li>%s</li>" % self._fields[field_name].string)
        if errors:
            errors.insert(0, "<ul>")
            errors.append("</ul>")
        return errors

    def product_post(self):
        meli_util_model = self.env['meli.util']
        message_list = []
        return_message_list = self.env.context.get('return_message_list')
        message_text, message_description = "", ""
        pricelist = self._get_pricelist_for_meli()
        product = self.with_context(pricelist=pricelist.id)
        company = self.env.user.company_id
        warningobj = self.env['warning']
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
        meli = meli_util_model.get_new_instance(company)
        # print product.meli_category.meli_category_id
        if not product.meli_title:
            # print 'Assigning title: product.meli_title: %s name: %s' % (product.meli_title, product.name)
            product.meli_title = product.get_title_for_meli()
        if not product.meli_price:
            # print 'Assigning price: product.meli_price: %s standard_price: %s' % (product.meli_price, product.standard_price)
            product.meli_price = int(product.price)
        errors = self.validate_fields_meli()
        if errors:
            message_text = "Por favor configure los siguientes campos en el producto: %s." % product.display_name
            message_description = "".join(errors)
            message_list.append((message_text, message_description))
            if return_message_list:
                return message_list
            return warningobj.info(title='ERRORES AL SUBIR PUBLICACION', message=message_text, message_html=message_description)
        #publicando imagen cargada en OpenERP
        product_image = product.get_product_image()
        if not product_image:
            message_text = "Debe cargar una imagen de base en el producto: %s." % product.display_name
            message_description = ""
            message_list.append((message_text, message_description))
            if return_message_list:
                return message_list
            return warningobj.info( title='MELI WARNING', message=message_text, message_html=message_description)
        elif not product.meli_imagen_id:
            # print "try uploading image..."
            resim = product.product_meli_upload_image()
            if "status" in resim:
                if (resim["status"]=="error" or resim["status"]=="warning"):
                    error_msg = 'MELI: mensaje de error:   ', resim
                    message_text = error_msg
                    message_description = ""
                    message_list.append((message_text, message_description))
                    _logger.error(error_msg)
        #publicando multiples imagenes
        multi_images_ids = {}
        if (product.product_image_ids):
            # print 'website_multi_images presente:   ', product.images
            #recorrer las imagenes y publicarlas
            multi_images_ids = product.product_meli_upload_multi_images()
        qty_available = self._get_meli_quantity_available()
        body = {
            "title": product.meli_title or '',
            "description": {
                "plain_text": product.meli_description or '',
            },
            "category_id": product.meli_category.meli_category_id or '0',
            "listing_type_id": product.meli_listing_type or '0',
            "buying_mode": product.meli_buying_mode or '',
            "price": int(product.price),
            "currency_id": product.meli_currency  or 'CLP',
            "condition": product.meli_condition  or '',
            "available_quantity": max([qty_available, 1]),
            "warranty": product.meli_warranty or '',
            #"pictures": [ { 'source': product.meli_imagen_logo} ] ,
            "video_id": product.meli_video  or '',
            "shipping": {
               "mode": "me2",
               "local_pick_up": False,
               "free_shipping": False,
               "free_methods": []
            }
        }
        bodydescription = {
            "plain_text": product.meli_description or '',
        }
        #ID de COLOR = 83000
        #ID de TALLA = 73003
        variations = []
        variant_without_stock = []
        variant_with_stock = {}
        for product_variant in self.product_variant_ids:
            variation_data = {}
            attribute_combinations = []
            atribute_values = []
            for attribute in product_variant.attribute_value_ids:
                if not attribute.attribute_id.meli_id:
                    continue
                attribute_meli = False
                #si el atributo no existe en la categoria no agregarlo xq no dejara hacer la publicacion
                for attrib_meli_id in attribute.attribute_id.meli_id.split(','):
                    attribute_meli = self.meli_category.find_attribute(attrib_meli_id)
                    if attribute_meli:
                        break
                if not attribute_meli:
                    continue
                atribute_values.append(attribute.id)
                attribute_combinations.append({
                    'id': attribute_meli.code,
                    'value_name': attribute.name,
                })
            if not attribute_combinations:
                continue
            qty_available = self._get_meli_quantity_available_variant(product_variant)
            #los productos que no tengan stock, despues de publicarlos se deben modificar para pasarles el stock 0
            #ya que al subirlos por primera vez no se puede publicar con stock 0
            if qty_available <= 0:
                variant_without_stock.append(product_variant.id)
            else:
                variant_with_stock[product_variant.id] = qty_available
            variation_data['available_quantity'] = max([qty_available, 1])
            variation_data['price'] = int(product_variant.price or product.price)
            variation_data['attribute_combinations'] = attribute_combinations
            variation_data['picture_ids'] = self._get_meli_image_variants(atribute_values)
            variations.append(variation_data)
        body['variations'] = variations
        body = self.set_meli_fields_aditionals(body)
        #modificando datos si ya existe el producto en MLA
        if (product.meli_id):
            body = {
                "title": product.meli_title or '',
                #"description": product.meli_description or '',
                #"category_id": product.meli_category.meli_category_id,
                #"listing_type_id": product.meli_listing_type,
                "buying_mode": product.meli_buying_mode or '',
                #"currency_id": product.meli_currency,
                "condition": product.meli_condition or '',
                "warranty": product.meli_warranty or '',
                "pictures": [],
                #"pictures": [ { 'source': product.meli_imagen_logo} ] ,
                "video_id": product.meli_video or '',
            }
        #si la compañia tiene ID de tienda oficial, pasarla a los productos
        if company.mercadolibre_official_store_id:
            body['official_store_id'] = company.mercadolibre_official_store_id
        #asignando imagen de logo (por source)
        #if product.meli_imagen_logo:
        if product.meli_imagen_id:
            body.setdefault('pictures', []).append({'id': product.meli_imagen_id})
            if (multi_images_ids):
                body.setdefault('pictures', []).extend(multi_images_ids)
            if product.meli_imagen_logo:
                body.setdefault('pictures', []).append({'source': product.meli_imagen_logo})
        #else:
        #    return warningobj.info(title='MELI WARNING', message="Debe completar el campo 'Imagen_Logo' con un url", message_html="")

        #check fields
        if product.meli_description==False:
            message_text = "Debe completar el campo 'description' (en html), Producto: %s" % product.display_name
            message_description = ""
            message_list.append((message_text, message_description))
            if return_message_list:
                return message_list
            return warningobj.info(title='MELI WARNING', message=message_text, message_html=message_description)
        #put for editing, post for creating
        _logger.info(body)
        if product.meli_id:
            response = meli.put("/items/"+product.meli_id, body, {'access_token':meli.access_token})
            resdescription = meli.put("/items/"+product.meli_id+"/description", bodydescription, {'access_token':meli.access_token})
            rjsondes = resdescription.json()
            _logger.info(rjsondes)
        else:
            response = meli.post("/items", body, {'access_token':meli.access_token})
        #check response
        # print response.content
        rjson = response.json()
        _logger.info(rjson)
        #check error
        if "error" in rjson:
            #print "Error received: %s " % rjson["error"]
            error_msg = 'MELI: mensaje de error:  %s , mensaje: %s, status: %s, cause: %s ' % (rjson["error"], rjson["message"], rjson["status"], rjson["cause"])
            _logger.error(error_msg)
            missing_fields = error_msg
            #expired token
            if "message" in rjson and (rjson["message"]=='invalid_token' or rjson["message"]=="expired_token"):
                meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
                url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
                #print "url_login_meli:", url_login_meli
                #raise osv.except_osv( _('MELI WARNING'), _('INVALID TOKEN or EXPIRED TOKEN (must login, go to Edit Company and login):  error: %s, message: %s, status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
                message_text = "Debe iniciar sesión en MELI.  "
                message_description = ""
                message_list.append((message_text, message_description))
                if return_message_list:
                    return message_list
                return warningobj.info( title='MELI WARNING', message=message_text, message_html="")
            else:
                #Any other errors
                message_text = "Completar todos los campos! Producto: %s" % product.display_name
                message_description = "<br><br>"+missing_fields
                message_list.append((message_text, message_description))
                if return_message_list:
                    return message_list
                return warningobj.info( title='MELI WARNING', message=message_text, message_html=message_description)
        #last modifications if response is OK
        if "id" in rjson:
            product.write( { 'meli_id': rjson["id"]} )
            #pasar el id de cada variante
            if rjson.get('variations', []):
                self._set_meli_id_from_variants(rjson.get('variations', []))
            if variant_without_stock:
                body_stock = {}
                for product_variant in self.product_variant_ids:
                    if product_variant.meli_id:
                        if product_variant.id in variant_without_stock:
                            body_stock.setdefault('variations', []).append({
                                'id': product_variant.meli_id,
                                'available_quantity': 0, 
                            })
                        elif product_variant.id in variant_with_stock:
                            body_stock.setdefault('variations', []).append({
                                'id': product_variant.meli_id,
                                'available_quantity': variant_with_stock[product_variant.id], 
                            })
                if body_stock:
                    response = meli.put("/items/"+product.meli_id, body_stock, {'access_token':meli.access_token})
        posting_fields = {'posting_date': str(datetime.now()),'meli_id':rjson['id'],'product_id':product.product_variant_ids[0].id,'name': 'Post: ' + product.meli_title }
        posting_id = self.env['mercadolibre.posting'].search( [('meli_id','=',rjson['id'])]).id
        if not posting_id:
            posting_id = self.env['mercadolibre.posting'].create((posting_fields)).id
        if return_message_list:
            return message_list
        return {}
    
    def product_update_to_meli(self):
        meli_util_model = self.env['meli.util']
        message_list = []
        return_message_list = self.env.context.get('return_message_list')
        message_text, message_description = "", ""
        pricelist = self._get_pricelist_for_meli()
        product = self.with_context(pricelist=pricelist.id)
        company = self.env.user.company_id
        warningobj = self.env['warning']
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
        meli = meli_util_model.get_new_instance(company)
        #publicando multiples imagenes
        multi_images_ids = {}
        if (product.product_image_ids):
            # print 'website_multi_images presente:   ', product.images
            #recorrer las imagenes y publicarlas
            multi_images_ids = product.product_meli_upload_multi_images()
        qty_available = self._get_meli_quantity_available()
        product.write({'meli_title': product.get_title_for_meli()})
        body = {
            "title": product.meli_title,
            "warranty": product.meli_warranty or '',
            "video_id": product.meli_video  or '',
        }
        if len(self.product_variant_ids) <= 1:
            body.update({
                "price": int(product.price),
                "available_quantity": max([qty_available, 1]),
            })
        #ID de COLOR = 83000
        #ID de TALLA = 73003
        variations = []
        variant_without_stock = []
        variant_with_stock = {}
        for product_variant in self.product_variant_ids:
            variation_data = {}
            attribute_combinations = []
            atribute_values = []
            for attribute in product_variant.attribute_value_ids:
                if not attribute.attribute_id.meli_id:
                    continue
                attribute_meli = False
                #si el atributo no existe en la categoria no agregarlo xq no dejara hacer la publicacion
                for attrib_meli_id in attribute.attribute_id.meli_id.split(','):
                    attribute_meli = self.meli_category.find_attribute(attrib_meli_id)
                    if attribute_meli:
                        break
                if not attribute_meli:
                    continue
                atribute_values.append(attribute.id)
                attribute_combinations.append({
                    'id': attribute_meli.code,
                    'value_name': attribute.name,
                })
            if not attribute_combinations:
                continue
            qty_available = self._get_meli_quantity_available_variant(product_variant)
            #los productos que no tengan stock, despues de publicarlos se deben modificar para pasarles el stock 0
            #ya que al subirlos por primera vez no se puede publicar con stock 0
            if qty_available <= 0:
                variant_without_stock.append(product_variant.id)
            else:
                variant_with_stock[product_variant.id] = qty_available
            variation_data['available_quantity'] = max([qty_available, 1])
            variation_data['price'] = int(product_variant.price or product.price)
            variation_data['attribute_combinations'] = attribute_combinations
            variation_data['picture_ids'] = self._get_meli_image_variants(atribute_values)
            if product_variant.meli_id:
                variation_data['id'] = product_variant.meli_id
            variations.append(variation_data)
        body['variations'] = variations
        body = self.set_meli_fields_aditionals(body)
        #si la compañia tiene ID de tienda oficial, pasarla a los productos
        if company.mercadolibre_official_store_id:
            body['official_store_id'] = company.mercadolibre_official_store_id
        #asignando imagen de logo (por source)
        #if product.meli_imagen_logo:
        if product.meli_imagen_id:
            body.setdefault('pictures', []).append({'id': product.meli_imagen_id})
            if (multi_images_ids):
                body.setdefault('pictures', []).extend(multi_images_ids)
            if product.meli_imagen_logo:
                body.setdefault('pictures', []).append({'source': product.meli_imagen_logo})
        rjson = {}
        if product.meli_id:
            response = meli.put("/items/"+product.meli_id, body, {'access_token':meli.access_token})
            rjson = response.json()
            _logger.info(rjson)
        #check error
        if "error" in rjson:
            #print "Error received: %s " % rjson["error"]
            error_msg = 'MELI: mensaje de error:  %s , mensaje: %s, status: %s, cause: %s ' % (rjson["error"], rjson["message"], rjson["status"], rjson["cause"])
            _logger.error(error_msg)
            missing_fields = error_msg
            #expired token
            if "message" in rjson and (rjson["message"]=='invalid_token' or rjson["message"]=="expired_token"):
                meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
                url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
                #print "url_login_meli:", url_login_meli
                #raise osv.except_osv( _('MELI WARNING'), _('INVALID TOKEN or EXPIRED TOKEN (must login, go to Edit Company and login):  error: %s, message: %s, status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
                message_text = "Debe iniciar sesión en MELI.  "
                message_description = ""
                message_list.append((message_text, message_description))
                if return_message_list:
                    return message_list
                return warningobj.info( title='MELI WARNING', message=message_text, message_html="")
            else:
                #Any other errors
                message_text = "Completar todos los campos! Producto: %s" % product.display_name
                message_description = "<br><br>"+missing_fields
                message_list.append((message_text, message_description))
                if return_message_list:
                    return message_list
                return warningobj.info( title='MELI WARNING', message=message_text, message_html=message_description)
        #last modifications if response is OK
        if "id" in rjson:
            #pasar el id de cada variante
            if rjson.get('variations', []):
                self._set_meli_id_from_variants(rjson.get('variations', []))
            if variant_without_stock:
                body_stock = {}
                for product_variant in self.product_variant_ids:
                    if product_variant.meli_id:
                        if product_variant.id in variant_without_stock:
                            body_stock.setdefault('variations', []).append({
                                'id': product_variant.meli_id,
                                'available_quantity': 0, 
                            })
                        elif product_variant.id in variant_with_stock:
                            body_stock.setdefault('variations', []).append({
                                'id': product_variant.meli_id,
                                'available_quantity': variant_with_stock[product_variant.id], 
                            })
                if body_stock:
                    response = meli.put("/items/"+product.meli_id, body_stock, {'access_token':meli.access_token})
        if return_message_list:
            return message_list
        return {}
    
    @api.multi
    def get_title_for_meli(self):
        return self.name
    
    @api.multi
    def get_title_for_category_predictor(self):
        return self.name

    @api.multi
    def get_price_for_category_predictor(self):
        pricelist = self._get_pricelist_for_meli()
        return int(self.with_context(pricelist=pricelist.id).price)
    
    @api.multi
    def action_category_predictor(self):
        self.ensure_one()
        warning_model = self.env['warning']
        meli_categ, rjson = self._get_meli_category_from_predictor()
        if meli_categ:
            self.meli_category = meli_categ.id
            return warning_model.info( title='MELI WARNING', message="CATEGORY PREDICTOR", message_html="Categoria sugerida: %s" % meli_categ.name)
        return warning_model.info( title='MELI WARNING', message="CATEGORY PREDICTOR", message_html=rjson)
    
    @api.multi
    def _get_meli_category_from_predictor(self):
        self.ensure_one()
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        vals = [{
            'title': self.get_title_for_category_predictor(),
            'price': self.get_price_for_category_predictor(),
        }]
        _logger.info(vals)
        response = meli.post("/sites/MLC/category_predictor/predict", vals)
        rjson = response.json()
        _logger.info(rjson)
        meli_categ = False
        if rjson and isinstance(rjson, list):
            if "id" in rjson[0]:
                meli_categ = self.env['mercadolibre.category'].import_category(rjson[0]['id'])
        return meli_categ, rjson
    
    @api.model
    def _get_pricelist_for_meli(self):
        pricelist = self.env.user.company_id.meli_pricelist_id
        if not pricelist:
            pricelist = self.env['product.pricelist'].search([
                ('currency_id','=','CLP'),
                ('website_id','!=',False),
            ], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].search([], limit=1)
        return pricelist
    
    @api.multi
    def action_sincronice_product_data_ml(self):
        #Completar los datos por un valor por defecto para los campos que esten vacios
        vals = {}
        meli_listing_type = self.env['ir.config_parameter'].get_param('meli_listing_type', 'gold_special').strip()
        meli_condition = self.env['ir.config_parameter'].get_param('meli_condition', 'new').strip()
        pricelist = self._get_pricelist_for_meli()
        for template in self.with_context(pricelist=pricelist.id):
            vals = {}
            if not template.meli_title:
                vals['meli_title'] = template.get_title_for_meli()
            if not template.meli_listing_type:
                vals['meli_listing_type'] = meli_listing_type
            #en modo libre solo se permite 1 cantidad de stock, cuando se use otra lista tomar el stock real
            vals['meli_available_quantity'] = template._get_meli_quantity_available()
            if not template.meli_buying_mode:
                vals['meli_buying_mode'] = 'buy_it_now'
            if not template.meli_price:
                vals['meli_price'] = int(template.price)
            if not template.meli_currency:
                vals['meli_currency'] = 'CLP'
            if not template.meli_condition:
                vals['meli_condition'] = meli_condition
            if not template.meli_description:
                vals['meli_description'] = template._get_description_sale()
            if not template.meli_category:
                meli_category, json = template._get_meli_category_from_predictor()
                if meli_category:
                    vals['meli_category'] = meli_category.id
            if vals:
                template.write(vals)
        return True
    
    @api.multi
    def _get_description_sale(self):
        self.ensure_one()
        return self.description_sale or ''
    
    @api.multi
    def _get_meli_image_variants(self, atribute_values):
        picture_ids = []
        if (not atribute_values or len(self.product_image_ids)<=1) and self.meli_imagen_id:
            picture_ids.append(self.meli_imagen_id)
        for product_image in self.product_image_ids:
            if not product_image.meli_id:
                continue
            if atribute_values and product_image.product_attribute_id:
                if product_image.product_attribute_id.id in atribute_values:
                    picture_ids.append(product_image.meli_id)
            else:
                picture_ids.append(product_image.meli_id)
        return picture_ids
    
    @api.multi
    def _get_meli_quantity_available(self):
        qty_available = 0
        warehouse_website = self.env['stock.warehouse'].sudo().search([('meli_published','=',True)])
        if not warehouse_website:
            qty_available = self.meli_available_quantity
            return qty_available 
        for ware in warehouse_website:
            stock_data = self.with_context(warehouse=ware.id)._compute_quantities_dict()
            qty_available += stock_data.get(self.id).get('qty_available')
        return qty_available
    
    @api.model
    def _get_meli_quantity_available_variant(self, variant):
        qty_available = 0
        warehouse_website = self.env['stock.warehouse'].sudo().search([('meli_published','=',True)])
        if not warehouse_website:
            qty_available = self.meli_available_quantity
            return qty_available
        for ware in warehouse_website:
            stock_data = variant.with_context(warehouse=ware.id)._compute_quantities_dict(lot_id=False, owner_id=False, package_id=False)
            qty_available += stock_data.get(variant.id).get('qty_available')
        return qty_available
    
    @api.multi
    def _set_meli_id_from_variants(self, variation_list):
        #si hay informacion de variantes, tomar la variante especifica que se haya vendido
        for variant in variation_list:
            all_atr_meli = set()
            all_atr_name_meli = set()
            for attr in variant.get('attribute_combinations', []):
                all_atr_meli.add(attr['id'])
                all_atr_name_meli.add(attr['value_name'].lower())
            for product_variant in self.product_variant_ids:
                all_atr = set()
                all_atr_name = set()
                for attribute in product_variant.attribute_value_ids:
                    if not attribute.attribute_id.meli_id:
                        continue
                    all_atr.update(set(attribute.attribute_id.meli_id.split(',')))
                    all_atr_name.add(attribute.name.lower())
                if all_atr_meli.intersection(all_atr) and all_atr_name_meli == all_atr_name:
                    product_variant.write({'meli_id': variant['id']})
                    break

    @api.model
    def action_send_products_to_meli(self):
        limit_meli = int(self.env['ir.config_parameter'].get_param('meli.product.limit', '1000').strip())
        products = self.with_context(return_message_list=True).search([
            ('meli_pub','=',True),
            ('meli_id','=',False),
            ], limit=limit_meli)
        products.action_sincronice_product_data_ml()
        message_list = []
        message = []
        for product in products:
            message = product.product_post()
            if isinstance(message, list):
                message_list.extend(message)
        if message_list and csv:
            file_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            file_path = os.path.join(file_path, "subir_productos_meli_%s.csv" % fields.Datetime.context_timestamp(self, datetime.now()).strftime('%Y_%m_%d_%H_%M_%S'))
            fp = open(file_path,'wb')
            csv_file = csv.writer(fp, quotechar='"', quoting=csv.QUOTE_ALL)
            csv_file.writerow(['Mensaje', 'Detalle'])
            for line in message_list:
                csv_file.writerow([line[0], line[1]])
            fp.close()
        return True
    
    @api.model
    def action_update_products_to_meli(self):
        limit_meli = int(self.env['ir.config_parameter'].get_param('meli.product.limit', '1000').strip())
        products = self.with_context(return_message_list=True).search([
            ('meli_pub','=',True),
            ('meli_id','!=',False),
            ], limit=limit_meli)
        message_list = []
        message = []
        for product in products:
            message = product.product_update_to_meli()
            if isinstance(message, list):
                message_list.extend(message)
        if message_list and csv:
            file_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            file_path = os.path.join(file_path, "actualizar_productos_meli_%s.csv" % fields.Datetime.context_timestamp(self, datetime.now()).strftime('%Y_%m_%d_%H_%M_%S'))
            fp = open(file_path,'wb')
            csv_file = csv.writer(fp, quotechar='"', quoting=csv.QUOTE_ALL)
            csv_file.writerow(['Mensaje', 'Detalle'])
            for line in message_list:
                csv_file.writerow([line[0], line[1]])
            fp.close()
        return True
    
class ProductProduct(models.Model):

    _inherit = "product.product"
    
    meli_id = fields.Char( string='Id del item asignado por Meli', readonly=True, copy=False)
    