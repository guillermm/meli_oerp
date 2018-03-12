# -*- coding: utf-8 -*-

from odoo import models, api, fields, tools
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

class ProductAttribute(models.Model):

    _inherit = 'product.attribute'
    
    meli_id = fields.Char(u'ID MELI')