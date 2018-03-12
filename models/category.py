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

import logging

from odoo import fields, osv, models, api

_logger = logging.getLogger(__name__)

class MercadolibreCategoryAttributeValue(models.Model):

    _name = 'mercadolibre.category.attribute.value'
    _description = u'Opciones de atributos'
    
    name = fields.Char(string=u'Nombre')
    code = fields.Char(string=u'ID MELI')
    
    @api.model
    def find_or_create(self, name, code):
        value_find = self.search([
            ('name','=', name),
            ('code','=', code),
        ], limit=1)
        if not value_find:
            value_find = self.create({
                'name': name,
                'code': code,
            })
        return value_find
    
class MercadolibreCategoryAttribute(models.Model):

    _name = 'mercadolibre.category.attribute'
    _description = u'mercadolibre.category.attribute'
    
    name = fields.Char(string=u'Nombre')
    code = fields.Char(string=u'ID MELI')
    attribute_type = fields.Selection([
        ('string','Texto Libre'),
        ('number','Numeros'),
        ('number_unit','Unidad de Medida'),
        ('list','Lista de Opciones'),
        ('boolean','Si/No'),
        ], string=u'Tipo de Atributo')
    value_ids = fields.Many2many('mercadolibre.category.attribute.value', 'mercadolibre_category_attribute_value_rel', 
        'attribute_id', 'value_id', u'Valores de Atributo')
    
    @api.model
    def find_or_create(self, name, code, attribute_type, value_list=None):
        if not value_list:
            value_list = []
        value_model = self.env['mercadolibre.category.attribute.value']
        attribute_find = self.search([
            ('name','=', name),
            ('code','=', code),
            ('attribute_type','=', attribute_type),
        ], limit=1)
        if not attribute_find:
            value_ids = []
            for value in value_list:
                value_find = value_model.find_or_create(value.get('name') or 'SN', value.get('id') or 'SC',)
                value_ids.append(value_find.id)
            attribute_find = self.create({
                'name': name,
                'code': code,
                'attribute_type': attribute_type,
                'value_ids': [(6, 0, value_ids)],
            })
        return attribute_find
    
class MercadolibreCategory(models.Model):
    _name = "mercadolibre.category"
    _description = "Categories of MercadoLibre"

    name = fields.Char('Name')
    meli_category_id = fields.Char('Category Id')
    public_category_id = fields.Integer('Public Category Id')
    listing_allowed = fields.Boolean(u'Permitido Postear productos?')
    attribute_ids = fields.Many2many('mercadolibre.category.attribute', 'mercadolibre_category_attribute_rel', 
        'category_id', 'attribute_id', u'Atributos')

    @api.multi
    def find_attribute(self, attribute_code):
        self.ensure_one()
        attribute = self.attribute_ids.filtered(lambda x: x.code == attribute_code)
        return attribute
        
    def import_category(self, category_id):
        attribute_model = self.env['mercadolibre.category.attribute']
        meli_util_model = self.env['meli.util']
        meli = meli_util_model.get_new_instance()
        meli_categ = self.browse()
        if not category_id:
            return meli_categ
        meli_categ = self.search([('meli_category_id','=',category_id)], limit=1)
        if (meli_categ):
            _logger.info("category exists! %s ID: %s" % (category_id, meli_categ.id))
            return meli_categ
        else:
            _logger.info("Creating category: %s" % (category_id))
            #https://api.mercadolibre.com/categories/MLA1743
            response_cat = meli.get("/categories/%s" % (category_id), {'access_token':meli.access_token})
            rjson_cat = response_cat.json()
            _logger.info("category:" + str(rjson_cat))
            fullname = ""
            if ("path_from_root" in rjson_cat):
                path_from_root = rjson_cat["path_from_root"]
                for path in path_from_root:
                    fullname = fullname + "/" + path["name"]

            #fullname = fullname + "/" + rjson_cat['name']
            #print "category fullname:" + str(fullname)
            _logger.info(fullname)
            response_attributes = meli.get("/categories/%s/attributes" % (category_id), {'access_token':meli.access_token})
            attributes_json = response_attributes.json()
            attribute_ids = []
            for attribute in attributes_json:
                attribute = attribute_model.find_or_create(attribute.get('name') or 'SN',
                                                           attribute.get('id') or 'SC', 
                                                           attribute.get('value_type') or 'string', 
                                                           attribute.get('values') or attribute.get('allowed_units') or [])
                attribute_ids.append(attribute.id)
            cat_fields = {
                'name': fullname,
                'meli_category_id': ''+str(category_id),
                'listing_allowed': rjson_cat.get('settings', {}).get('listing_allowed') or False,
                'attribute_ids': [(6, 0, attribute_ids)],
                }
            meli_categ = self.create((cat_fields))
            return meli_categ


    def import_all_categories(self, category_root ):
        warning_model = self.env['warning']
        category_model = self.env['mercadolibre.category']
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance()
        RECURSIVE_IMPORT = company.mercadolibre_recursive_import
        if (category_root):
            response = meli.get("/categories/"+str(category_root), {'access_token':meli.access_token} )
            print "response.content:", response.content
            rjson = response.json()
            if ("name" in rjson):
                # en el html deberia ir el link  para chequear on line esa categoría corresponde a sus productos.
                warning_model.info( title='MELI WARNING', message="Preparando importación de todas las categorías en "+str(category_root), message_html=response )
                if ("children_categories" in rjson):
                    #empezamos a iterar categorias
                    for child in rjson["children_categories"]:
                        ml_cat_id = child["id"]
                        if (ml_cat_id):
                            category_model.import_category(category_id=ml_cat_id)
                            if (RECURSIVE_IMPORT):
                                category_model.import_all_categories(category_root=ml_cat_id)
