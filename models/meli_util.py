# -*- coding: utf-8 -*-

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

from .meli_oerp_config import REDIRECT_URI
from ..melisdk.meli import Meli

class MeliUtil(models.AbstractModel):

    _name = 'meli.util'
    _description = u'Utilidades para Mercado Libre'
    
    @api.model
    def get_new_instance(self, company=None):
        if not company:
            company = self.env.user.company_id
        CLIENT_ID = company.mercadolibre_client_id
        CLIENT_SECRET = company.mercadolibre_secret_key
        ACCESS_TOKEN = company.mercadolibre_access_token
        REFRESH_TOKEN = company.mercadolibre_refresh_token
        meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET, access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN)
        return meli
    
    @api.model
    def get_url_meli_login(self, meli):
        url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
        return {
            "type": "ir.actions.act_url",
            "url": url_login_meli,
            "target": "self",
        }