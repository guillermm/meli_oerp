# -*- coding: utf-8 -*-

import logging

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class MeliCampaignRecord(models.Model):

    _name = 'meli.campaign.record'
    _description = u'Registros de Campañas MELI'
    
    campaign_id = fields.Many2one('meli.campaign', u'Campaña', 
        required=True, readonly=True, states={'draft':[('readonly',False)]}, ondelete="restrict")
    pricelist_id = fields.Many2one('product.pricelist', u'Tarifa de Venta',
        required=True, ondelete="restrict",
        readonly=False, states={'done':[('readonly', True)], 'rejected':[('readonly', True)]})
    name = fields.Char(u'Nombre', 
        required=True, readonly=True, states={'draft':[('readonly',False)]})
    description = fields.Text(string=u'Descripcion',
        readonly=True, states={'draft':[('readonly',False)]})
    line_ids = fields.One2many('meli.campaign.record.line', 
        'meli_campaign_id', u'Productos en Oferta', copy=False, auto_join=True,
        readonly=False, states={'done':[('readonly', True)], 'rejected':[('readonly', True)]})
    state = fields.Selection([
        ('draft','Borrador'),
        ('pending_approval','Enviado a Meli/Esperando Aprobacion'),
        ('published','Publicado en MELI'),
        ('approved','Aprobado en MELI'),
        ('done','Campaña Terminada'),
        ('rejected','Cancelado'),
        ], string=u'Estado', index=True, readonly=True, default = u'draft', )
    
    @api.multi
    def action_set_products(self):
        self.ensure_one()
        wizard_model = self.env['wizard.set.products.campaign']
        wizard = wizard_model.create({
            'meli_campaign_id': self.id,
            'action_type': self.env.context.get('action_type') or 'set',
        })
        action = self.env.ref('meli_oerp.action_wizard_set_products_campaign').read()[0]
        action['res_id'] = wizard.id
        return action
    
    @api.multi
    def action_publish_to_meli(self):
        self.ensure_one()
        warning_model = self.env['warning']
        messages = self.line_ids.filtered(lambda x: x.state == 'draft').action_publish_to_meli()
        state = 'published'
        #si algun producto se quedo esperando aprobacion, 
        #el estado general sera esperando aprobacion de Meli
        if self.line_ids.filtered(lambda x: x.state == 'pending_approval'):
            state = 'pending_approval'
        if messages:
            return warning_model.info(title='Ofertas', message=u"\n".join(messages))
        self.state = state
        return True
    
    @api.multi
    def action_done_publish(self):
        self.mapped('line_ids').filtered(lambda x: x.state != 'rejected').write({'state': 'done'})
        self.write({'state': 'done'})
        return True
    
    @api.multi
    def action_cancel_publish(self):
        self.ensure_one()
        warning_model = self.env['warning']
        messages = self.line_ids.filtered(lambda x: x.state != 'rejected').action_unpublish_to_meli()
        if messages:
            return warning_model.info(title='Cancelar Oferta', message=u"\n".join(messages))
        self.write({'state': 'rejected'})
        return True
    
    @api.multi
    def action_recompute_prices(self):
        self.ensure_one()
        #pasar la lista de precios y actualizar los precios
        for line in self.with_context(pricelist=self.pricelist_id.id).line_ids:
            line.write({
                'price_unit': line.product_template_id.list_price,
                'list_price': line.product_template_id.price,
                'meli_price': line.product_template_id.price,
            })
        return True
    
    @api.multi
    def action_update_prices_to_meli(self):
        warning_model = self.env['warning']
        #los nuevos productos publicarlos
        messages = self.mapped('line_ids').filtered(lambda x: x.state == 'draft').action_publish_to_meli()
        #actualizar todas las lineas que esten activas
        messages.extend(self.mapped('line_ids').filtered(lambda x: x.state in ('pending_approval', 'published')).action_update_to_meli())
        if messages:
            return warning_model.info(title='Actualizar Ofertas', message=u"\n".join(messages))
        return True
    
    @api.multi
    def _find_create_campaign_detail(self, response_json):
        campaign_line_model = self.env['meli.campaign.record.line']
        campaign_line = campaign_line_model.browse()
        messages = []
        ProductTemplateModel = self.env['product.template']
        item_id = response_json.get('item_id')
        if not item_id:
            messages.append("No se encuentra un producto con ID: %s" % item_id)
            return campaign_line, messages
        product_template = ProductTemplateModel.search([('meli_id', '=', item_id)], limit=1)
        if not product_template:
            messages.append("No se encuentra un producto con ID: %s" % item_id)
            return campaign_line, messages
        vals = campaign_line_model._prepare_vals_to_update_from_meli(response_json, product_template)
        #buscar una linea de campaña para el producto
        # puede darse el caso que en odoo crean varios registros para la misma campaña
        # es decir 1 registro con productos de 1 categoria especial con un % de descuento
        # y otro registro para otros productos con otro descuento
        # pero al final a meli se suben en la misma campaña
        # asi que en caso de no existir en la oferta actual, 
        # buscar si esta en otra oferta ese producto pero con la misma campaña
        domain = [
            ('product_template_id', '=', product_template.id),
            ('meli_campaign_id', '=', self.id),
        ]
        campaign_line = campaign_line_model.search(domain, limit=1)
        if campaign_line:
            campaign_line.write(vals)
        else:
            domain = [
                ('product_template_id', '=', product_template.id),
                ('meli_campaign_id.campaign_id', '=', self.campaign_id.id),
            ]
            campaign_line = campaign_line_model.search(domain, limit=1)
            if campaign_line:
                messages.append("El producto: %s ID: %s esta en otro registro de campaña: %s ID: %s, se actualizo dicho registro" % 
                                (product_template.name, item_id, campaign_line.meli_campaign_id.name, campaign_line.meli_campaign_id.id))
                campaign_line.write(vals)
            else:
                messages.append("El producto: %s ID: %s No existe en la campaña: %s ID: %s, se creara" % 
                                (product_template.name, item_id, self.name, self.id))
                vals.update({
                    'meli_campaign_id': self.id,
                    'product_template_id': product_template.id,
                })
                campaign_line = campaign_line_model.create(vals)
        return campaign_line, messages
    
    @api.multi
    def _query_iterate_campaign(self, total_downloaded=0, offset=0):
        meli_util_model = self.env['meli.util']
        campaign_line_model = self.env['meli.campaign.record.line']
        campaign_lines = campaign_line_model.browse()
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        message_list = []
        campaign_query = "/users/%s/deals/%s/proposed_items/search" % (company.mercadolibre_seller_id, self.campaign_id.meli_id)
        params = {
            'access_token': meli.access_token,
        }
        if offset:
            params['offset'] = str(offset).strip()
        response = meli.get(campaign_query, params)
        orders_json = response.json()
        if "error" in orders_json:
            _logger.error(orders_json["error"])
            if orders_json["message"] == "invalid_token":
                _logger.error(orders_json["message"])
                message_list.append(orders_json["message"])
            return campaign_lines, message_list
        counter = 0
        total = 0
        if "results" in orders_json:
            total_downloaded += len(orders_json["results"])
        if "paging" in orders_json:
            if "total" in orders_json["paging"]:
                counter = offset + 1
                total = orders_json["paging"]["total"]
                if orders_json["paging"]["total"] == 0:
                    return campaign_lines, message_list
                else: 
                    if total_downloaded < total:
                        offset += orders_json["paging"]["limit"]
                    else:
                        offset = 0
        if "results" in orders_json:
            for response_json in orders_json["results"]:
                _logger.info("Procesando Producto %s de %s", counter, total)
                counter += 1
                campaign_line, msj = self._find_create_campaign_detail(response_json)
                campaign_lines |= campaign_line
                message_list.extend(msj)
        if offset > 0:
            campaign_lines_tmp, message_list_tmp = self._query_iterate_campaign(total_downloaded, offset)
            message_list.extend(message_list_tmp)
            campaign_lines |= campaign_lines_tmp
        return campaign_lines, message_list
    
    @api.multi
    def _action_recompute_state(self):
        self.ensure_one()
        new_state = ''
        # todas las lineas tienen el mismo estado, la cabecera debe tener el mismo estado
        states_lines = self.line_ids.mapped('state')
        for state in ['pending_approval', 'published', 'approved', 'done', 'rejected']:
            if all([line_state == state for line_state in states_lines]):
                new_state = state
                break
        if not new_state:
            if 'done' in states_lines:
                new_state = 'done'
            if 'approved' in states_lines:
                new_state = 'approved'
            elif 'published' in states_lines:
                new_state = 'published'
            elif 'pending_approval' in states_lines:
                new_state = 'pending_approval'
        if new_state and self.state != new_state:
            self.state = new_state
    
    @api.multi
    def action_download_campaign(self):
        self.ensure_one()
        warning_model = self.env['warning']
        campaign_lines, message_list = self._query_iterate_campaign()
        if campaign_lines:
            campaigns = campaign_lines.mapped('meli_campaign_id')
            for campaign in campaigns:
                campaign._action_recompute_state()
        res = True
        if message_list:
            res = warning_model.info(title='Mensajes de informacion', 
                    message="Se obtuvieron los siguientes mensajes en la actualizacion de la Oferta: %s(%s)" % (self.name, self.campaign_id.name), 
                    message_html="<br/>".join(message_list))
        return res
    
    @api.multi
    def unlink(self):
        for campaign in self:
            if campaign.state not in ('draft',):
                raise UserError(u"No puede Eliminar esta Campaña, intente cancelarla")
        res = super(MeliCampaignRecord, self).unlink()
        return res 
    
class MeliCampaignRecordLine(models.Model):

    _name = 'meli.campaign.record.line'
    _description = u'Productos o Ofertar en Campañas'
    
    meli_campaign_id = fields.Many2one('meli.campaign.record', 
        u'Registro de Campaña', ondelete="cascade", auto_join=True)
    product_template_id = fields.Many2one('product.template', 
        u'Plantilla de Producto', ondelete="restrict", auto_join=True)
    price_unit = fields.Float(u'Precio Unitario', digits=dp.get_precision('Product Price'))
    list_price = fields.Float(u'Precio Unitario(Tarifa)', digits=dp.get_precision('Product Price'))
    meli_price = fields.Float(u'Precio Unitario(MELI)', digits=dp.get_precision('Product Price'))
    declared_free_shipping = fields.Boolean(u'Envio Gratis?')
    declared_oro_premium_full = fields.Boolean(u'Premium?')
    declared_stock = fields.Float(u'Stock Declarado', digits=dp.get_precision('Product Unit of Measure'))
    review_reasons_ids = fields.One2many('meli.campaign.record.review.reason', 
        'meli_campaign_line_id', u'Razones de Revision', readonly=True, copy=False, auto_join=True)
    state = fields.Selection([
        ('draft','Borrador'),
        ('pending_approval', 'Enviado a Meli/Esperando Aprobacion'),
        ('published','Publicado en MELI'),
        ('approved','Aprobado en MELI'),
        ('done','Campaña Terminada'),
        ('rejected','Cancelado'),
        ], string=u'Estado', default = u'draft')
    
    @api.multi
    def _prepare_vals_to_publish(self):
        post_data = {
            'deal_price': self.meli_price,
            'regular_price': self.price_unit,
            'declared_free_shipping': self.declared_free_shipping,
            'declared_oro_premium_full': self.declared_oro_premium_full,
        }
        return post_data
    
    @api.multi
    def _prepare_vals_to_update_from_meli(self, response_json, product_template):
        vals = {
            'meli_price': response_json.get('deal_price'),
            'list_price': response_json.get('deal_price'),
            'price_unit': response_json.get('regular_price'),
            'declared_free_shipping': response_json.get('declared_free_shipping'),
            'declared_oro_premium_full': response_json.get('declared_oro_premium_full'),
            'state': response_json.get('status'),
        }
        return vals
    
    @api.multi
    def action_publish_to_meli(self):
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance()
        params = {'access_token': meli.access_token}
        messages = []
        msj = ""
        for line in self:
            post_data = line._prepare_vals_to_publish()
            post_data['item_id'] = line.product_template_id.meli_id
            url = "/users/%s/deals/%s/proposed_items" % (company.mercadolibre_seller_id, line.meli_campaign_id.campaign_id.meli_id)
            response = meli.post(url, post_data, params)
            rjson = response.json()
            if rjson.get('error'):
                msj = rjson.get('message') or "Error Publicando Oferta"
                messages.append("%s. Producto ID: %s" % (msj, line.product_template_id.meli_id))
                continue
            vals_line = {
                'state':  rjson.get('status'),
            }
            review_reason = []
            for review in rjson.get('review_reasons', []):
                review_reason.append((0, 0, {
                    'reason_type': review.get('reason_type', ''),
                    'reason_requisite': (review.get('requisite') or {}).get('name', ''),
                    'message_key': review.get('message_key', ''),
                    }))
            if review_reason:
                vals_line['review_reasons_ids'] = [(5, 0)] + review_reason
            if vals_line:
                line.write(vals_line)
        return messages
    
    @api.multi
    def action_unpublish_to_meli(self):
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance()
        params = {'access_token': meli.access_token}
        messages = []
        #los productos publicados en meli enviar a cancelarlos
        #los que no han sido publicados, solo cambiarle el estado
        lines_unpublish = self.filtered(lambda x: x.state in ('pending_approval', 'published', 'done'))
        lines_cancel = self - lines_unpublish
        if lines_cancel:
            lines_cancel.write({'state': 'rejected'})
        for line in lines_unpublish:
            url = "/users/%s/deals/%s/proposed_items/%s" % (company.mercadolibre_seller_id, line.meli_campaign_id.campaign_id.meli_id, line.product_template_id.meli_id)
            response = meli.delete(url, params)
            rjson = response.json()
            if rjson.get('error'):
                msj = rjson.get('message') or "Error Eliminando Oferta"
                messages.append("%s. Producto ID: %s" % (msj, line.product_template_id.meli_id))
                continue
            vals_line = {
                'state':  rjson.get('status'),
            }
            if vals_line:
                line.write(vals_line)
        return messages
    
    @api.multi
    def action_update_to_meli(self):
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance()
        params = {'access_token': meli.access_token}
        messages = []
        for line in self:
            post_data = line._prepare_vals_to_publish()
            url = "/users/%s/deals/%s/proposed_items/%s" % (company.mercadolibre_seller_id, line.meli_campaign_id.campaign_id.meli_id, line.product_template_id.meli_id)
            response = meli.put(url, post_data, params)
            rjson = response.json()
            if rjson.get('error'):
                msj = rjson.get('message') or "Error Actualizando Oferta"
                messages.append("%s. Producto ID: %s" % (msj, line.product_template_id.meli_id))
                continue
        return messages
    
    @api.multi
    def name_get(self):
        res = []
        for element in self:
            name = u"%s %s" % (element.meli_campaign_id.display_name or '', element.product_template_id.display_name)
            res.append((element.id, name))
        return res
    
class MeliCampaignRecordRevisionReason(models.Model):

    _name = 'meli.campaign.record.review.reason'
    _description = u'Razones de Revision en Ofertas'
    
    meli_campaign_line_id = fields.Many2one('meli.campaign.record.line', 
        u'Producto en Oferta', ondelete="cascade", auto_join=True)
    reason_type = fields.Char(u'Tipo de Razon')
    reason_requisite = fields.Char(u'Requisito')
    message_key = fields.Char(u'Mensaje')
    
