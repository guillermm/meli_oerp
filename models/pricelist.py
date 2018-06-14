# -*- coding: utf-8 -*-

from odoo import models, api, fields, tools
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

class ProductPricelist(models.Model):

    _inherit = 'product.pricelist'
    
    @api.multi
    def unlink(self):
        # enviar a marcar los productos para que se actualicen en meli
        for pricelist in self:
            for pricelist_item in pricelist.item_ids:
                pricelist_item._handle_products_to_meli()
        return super(ProductPricelist, self).unlink()

    
class ProductPricelistItem(models.Model):

    _inherit = 'product.pricelist.item'
    
    @api.model
    def _get_fields_trigger(self):
        fields_triggers = [
            'applied_on', 
            'compute_price',
            'date_start',
            'date_end',
            'price_discount',
            'percent_price',
            'price_surcharge',
            'fixed_price',
            'base_pricelist_id',
            'categ_id',
            'product_tmpl_id',
            'product_id',
        ]
        return fields_triggers
    
    @api.multi
    def _get_all_product_ids(self):
        products = self.env['product.template'].browse()
        # listas de precios globales, enviar a actualizar todos los productos de meli
        if self.applied_on == '3_global':
            products = self.env['product.template'].search([('meli_pub', '=', True)])
        # listas de precios nasadas en categorias, enviar a actualizar todos los productos de meli que pertenecen a dicha categoria
        elif self.applied_on == '2_product_category' and self.categ_id:
            products = self.env['product.template'].search([('categ_id', '=', self.categ_id.id), ('meli_pub', '=', True)])
        # basadas en plantilla de productos, devolver la propia plantilla
        elif self.applied_on == '1_product' and self.product_tmpl_id:
            if self.product_tmpl_id.meli_pub:
                products = self.product_tmpl_id
        # basadas en variante de producto, devolver la plantilla de esa variante
        elif self.applied_on == '0_product_variant' and self.product_id:
            if self.product_id.product_tmpl_id.meli_pub:
                products = self.product_id.product_tmpl_id
        return products
    
    @api.multi
    def _handle_products_to_meli(self):
        # verificar si la lista de precios puede alterar el precio de los productos
        # en descuentos o recargos
        need_update_products = False
        if self.compute_price == 'fixed' and self.fixed_price != 0:
            need_update_products = True
        elif self.compute_price == 'percentage' and self.percent_price != 0:
            need_update_products = True
        elif self.compute_price == 'formula':
            if self.base == 'pricelist' and self.base_pricelist_id:
                need_update_products = True
            elif self.base != 'pricelist' and (self.price_discount != 0 or self.price_surcharge != 0):
                need_update_products = True
        if need_update_products:
            #marcar como un producto que necesita actualizarse en meli
            products_update_meli = self._get_all_product_ids()
            if products_update_meli:
                products_update_meli._mark_to_update_meli()
        return True
    
    @api.model
    def create(self, vals):
        new_rec = super(ProductPricelistItem, self).create(vals)
        if set(vals.keys()).intersection(set(self._get_fields_trigger())):
            new_rec._handle_products_to_meli()
        return new_rec
    
    @api.multi
    def write(self, vals):
        res = super(ProductPricelistItem, self).write(vals)
        # cuando un campo cambia y afecta el calculo de precios,
        # enviar a marcar los productos para que se actualicen en meli
        if set(vals.keys()).intersection(self._get_fields_trigger()):
            for pricelist in self:
                pricelist._handle_products_to_meli()
        return res
    
    @api.multi
    def unlink(self):
        # enviar a marcar los productos para que se actualicen en meli
        for pricelist in self:
            pricelist._handle_products_to_meli()
        return super(ProductPricelistItem, self).unlink()
    