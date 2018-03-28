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
import re
import json
import logging
from datetime import datetime
_logger = logging.getLogger(__name__)

try:
    import csv
except ImportError:
    csv = False
    _logger.error('This module needs csv. Please install csv on your system')

from odoo import fields, osv, models, api, tools
import odoo.addons.decimal_precision as dp

#https://api.mercadolibre.com/questions/search?item_id=MLA508223205

class mercadolibre_orders(models.Model):
    
    _name = "mercadolibre.orders"
    _description = "Pedidos en MercadoLibre"
    _rec_name = 'order_id'
    
    order_id = fields.Char('Order Id')
    sale_order_id = fields.Many2one('sale.order', u'Pedido de Venta',
        copy=False, readonly=True)
    partner_id = fields.Many2one('res.partner', u'Cliente',
        copy=False, readonly=True, ondelete="restrict")
    status = fields.Selection( [
        ("confirmed","Confirmado"), #Initial state of an order, and it has no payment yet.
        ("payment_required","Pago requerido"), #The order needs a payment to become confirmed and show users information.
        ("payment_in_process","Pago en proceso"), #There is a payment related with the order, but it has not accredited yet
        ("paid","Pagado"), #The order has a related payment and it has been accredited.
        ("cancelled","Cancelado"), #The order has not completed by some reason.
    ], string='Order Status')
    status_detail = fields.Text(string='Status detail, in case the order was cancelled.')
    date_created = fields.Date('Creation date')
    date_closed = fields.Date('Closing date')
    order_items = fields.One2many('mercadolibre.order_items','order_id','Order Items' )
    payments = fields.One2many('mercadolibre.payments','order_id','Payments' )
    shipping = fields.Text(string="Shipping")
    total_amount = fields.Char(string='Total amount')
    currency_id = fields.Char(string='Currency')
    buyer =  fields.Many2one( "mercadolibre.buyers","Buyer")
    shipping_id = fields.Char(u'ID de Entrega')
    shipping_name = fields.Char(u'Metodo de Entrega')
    shipping_method_id = fields.Char(u'ID de Metodo de Entrega')
    shipping_cost = fields.Float(u'Costo de Entrega', digits=dp.get_precision('Account'))
    shipping_status = fields.Selection([
        ('to_be_agreed', 'A Convenir(Acuerdo entre comprador y vendedor)'),
        ('pending','Pendiente'),
        ('handling','Pago Recibido/No Despachado'),
        ('ready_to_ship','Listo para Entregar'),
        ('shipped','Enviado'),
        ('delivered','Entregado'),
        ('not_delivered','No Entregado'),
        ('cancelled','cancelled'),
    ], string=u'Estado de Entrega', index=True, readonly=True)
    shipping_substatus = fields.Selection([
        ('ready_to_print','Etiqueta no Impresa'),
        ('printed','Etiqueta Impresa'),
    ], string=u'Estado de Impresion', index=True, readonly=True)
    shipping_mode = fields.Selection([
        ('me2','Mercado Envio'),
    ], string=u'Metodo de envio', readonly=True)
    note = fields.Html(u'Notas', readonly=True, copy=False)
    need_review = fields.Boolean(u'Necesita Revision?', readonly=True, copy=False)

    def billing_info( self, billing_json, context=None ):
        billinginfo = ''
        if 'doc_type' in billing_json:
            if billing_json['doc_type']:
                billinginfo+= billing_json['doc_type']
        if 'doc_number' in billing_json:
            if billing_json['doc_number']:
                billinginfo+= billing_json['doc_number']
        return billinginfo

    def full_phone( self, phone_json, context=None ):
        full_phone = ''
        if 'area_code' in phone_json:
            if phone_json['area_code']:
                full_phone+= phone_json['area_code']
        if 'number' in phone_json:
            if phone_json['number']:
                full_phone+= phone_json['number']
        if 'extension' in phone_json:
            if phone_json['extension']:
                full_phone+= phone_json['extension']
        return full_phone

    def pretty_json( self, ids, data, indent=0, context=None ):
        return json.dumps( data, sort_keys=False, indent=4 )
    
    @api.model
    def prepare_values_shipping(self, meli_shipping_values):
        shipping_values = {}
        if 'id' in meli_shipping_values:
            shipping_values['shipping_id'] = meli_shipping_values['id']
        if 'shipping_option' in meli_shipping_values:
            if 'name' in meli_shipping_values['shipping_option']:
                shipping_values['shipping_name'] = meli_shipping_values['shipping_option']['name']
            if 'shipping_method_id' in meli_shipping_values['shipping_option']:
                shipping_values['shipping_method_id'] = meli_shipping_values['shipping_option']['shipping_method_id']
        if 'cost' in meli_shipping_values:
            shipping_values['shipping_cost'] = meli_shipping_values['cost']
        if 'status' in meli_shipping_values:
            shipping_values['shipping_status'] = meli_shipping_values['status']
        if 'substatus' in meli_shipping_values:
            shipping_values['shipping_substatus'] = meli_shipping_values['substatus']
        if 'shipping_mode' in meli_shipping_values:
            shipping_values['shipping_mode'] = meli_shipping_values['shipping_mode']
        return shipping_values
    
    @api.model
    def _prepare_buyer_vals(self, meli_buyer_vals, document_number):
        buyer_vals = {
            'buyer_id': meli_buyer_vals['id'],
            'nickname': meli_buyer_vals['nickname'],
            'email': meli_buyer_vals['email'],
            'phone': self.full_phone(meli_buyer_vals['phone']),
            'alternative_phone': self.full_phone(meli_buyer_vals['alternative_phone']),
            'first_name': meli_buyer_vals['first_name'],
            'last_name': meli_buyer_vals['last_name'],
            'billing_info': self.billing_info(meli_buyer_vals['billing_info']),
            'document_number': document_number,
        }
        return buyer_vals
    
    @api.model
    def _find_create_buyer(self, meli_buyer_vals, document_number):
        BuyerModel = self.env['mercadolibre.buyers']
        buyer_vals = self._prepare_buyer_vals(meli_buyer_vals, document_number)
        buyer_find = BuyerModel.search([('buyer_id', '=', buyer_vals['buyer_id'])], limit=1)
        if not buyer_find:
            _logger.info("creating buyer: %s", str(buyer_vals))
            buyer_find = BuyerModel.create(buyer_vals)
        return buyer_find
    
    @api.model
    def _prepare_partner_vals(self, meli_buyer_vals, document_number):
        partner_vals = {
            'name': "%s %s" % (meli_buyer_vals['first_name'], meli_buyer_vals['last_name']),
            'street': 'no street',
            'phone': self.full_phone(meli_buyer_vals['phone']),
            'email': meli_buyer_vals['email'],
            'meli_buyer_id': meli_buyer_vals['id'],
            'document_number': document_number,
            'vat': 'CL%s' % document_number,
        }
        partner_vals = self.env['res.partner'].process_fields_meli(partner_vals, meli_buyer_vals['billing_info'].get('doc_type') or 'RUT')
        return partner_vals
    
    @api.model
    def _find_create_partner(self, meli_buyer_vals, document_number):
        partnerModel = self.env['res.partner']
        partner_vals = self._prepare_partner_vals(meli_buyer_vals, document_number)
        partner_find = partnerModel.search([('meli_buyer_id', '=', partner_vals['meli_buyer_id'])], limit=1)
        if not partner_find and document_number:
            partner_find = partnerModel.search([('document_number', '=', document_number)])
        if not partner_find:
            _logger.info("creating partner: %s", str(partner_vals))
            partner_find = partnerModel.create(partner_vals)
        return partner_find

    @api.model
    def _prepare_order_vals(self, meli_order_vals):
        order_vals = {
            'order_id': meli_order_vals["id"],
            'status': meli_order_vals.get("status"),
            'status_detail': meli_order_vals.get("status_detail"),
            'total_amount': meli_order_vals.get("total_amount"),
            'currency_id': meli_order_vals.get("currency_id"),
            'date_created': meli_order_vals.get("date_created"),
            'date_closed': meli_order_vals.get("date_closed"),
        }
        return order_vals
    
    @api.multi
    def _prepare_sale_order_vals(self, pricelist, company):
        sale_order_vals = {
            'company_id': company.id,
            'partner_id': self.partner_id.id,
            'pricelist_id': pricelist.id,
            'meli_order_id': self.id,
            'meli_status': self.status,
            'meli_status_detail': self.status_detail,
            'meli_total_amount': self.total_amount,
            'meli_currency_id': self.currency_id,
            'meli_date_created': self.date_created,
            'meli_date_closed': self.date_closed,
            'meli_shipping': self.shipping,
            'shipping_id': self.shipping_id,
            'shipping_name': self.shipping_name,
            'shipping_method_id': self.shipping_method_id,
            'shipping_cost': self.shipping_cost,
            'shipping_status': self.shipping_status,
            'shipping_substatus': self.shipping_substatus,
            'shipping_mode': self.shipping_mode,
        }
        if company.mercadolibre_sale_team_id:
            sale_order_vals['team_id'] = company.mercadolibre_sale_team_id.id
        warehouse_meli = self.env['stock.warehouse'].sudo().search([('meli_published','=',True), ('company_id','=',company.id)], limit=1)
        if not warehouse_meli:
            warehouse_meli = self.env['stock.warehouse'].sudo().search([('company_id','=',company.id)], limit=1)
        if warehouse_meli:
            sale_order_vals['warehouse_id'] = warehouse_meli.id
        return sale_order_vals
    
    @api.multi
    def _find_create_sale_order(self):
        SaleOrderModel = self.env['sale.order']
        self.ensure_one()
        sale_order = self.sale_order_id
        pricelist = self.env['product.template']._get_pricelist_for_meli()
        company = self.env.user.company_id
        sale_order_vals = self._prepare_sale_order_vals(pricelist, company)
        if (sale_order):
            _logger.info("Updating sale.order: %s", sale_order.id)
            sale_order.write(sale_order_vals)
        else:
            _logger.info("Adding new sale.order: " )
            _logger.info(sale_order_vals)            
            sale_order = SaleOrderModel.create(sale_order_vals)
            self.write({'sale_order_id': sale_order.id})
        for line in self.order_items:
            self._add_sale_order_line(sale_order, line)
        return sale_order
        
    @api.model
    def _find_product(self, meli_order_line_vals):
        ProductTemplateModel = self.env['product.template']
        ProductModel = self.env['product.product']
        product_template = ProductTemplateModel.search([('meli_id', '=', meli_order_line_vals['item']['id'])], limit=1)
        product_find = ProductModel.browse()
        if product_template and product_template.product_variant_ids:
            product_find = product_template.product_variant_ids[0]
        #si hay informacion de variantes, tomar la variante especifica que se haya vendido
        product_variant = ProductModel.browse()
        if meli_order_line_vals['item'].get('variation_id'):
            product_variant = product_template.product_variant_ids.filtered(lambda x: x.meli_id == str(meli_order_line_vals['item'].get('variation_id')))
            if product_variant:
                all_atr_name_meli = []
                for attr in meli_order_line_vals['item'].get('variation_attributes', []):
                    all_atr_name_meli.append(attr['value_name'])
                product_find = product_variant
                variants_names = ", ".join(all_atr_name_meli)
        #en caso de no encontrar la variante especifica por el ID
        #tratar de encontrarla segun los atributos de la variante
        if not product_variant and meli_order_line_vals['item'].get('variation_attributes'):
            all_atr_meli = set()
            all_atr_name_meli = set()
            for attr in meli_order_line_vals['item'].get('variation_attributes'):
                all_atr_meli.add(attr['id'])
                all_atr_name_meli.add(attr['value_name'].lower())
            for product_variant in product_template.product_variant_ids:
                all_atr = set()
                all_atr_name = set()
                for attribute in product_variant.attribute_value_ids:
                    if not attribute.attribute_id.meli_id:
                        continue
                    all_atr.update(set(attribute.attribute_id.meli_id.split(',')))
                    all_atr_name.add(attribute.name.lower())
                if all_atr_meli.intersection(all_atr) and all_atr_name_meli == all_atr_name:
                    product_find = product_variant
                    variants_names = ", ".join(list(all_atr_name_meli))
                    break
        return product_find, variants_names

    @api.model
    def _prepare_order_line_vals(self, order, meli_order_line_vals, posting, product, variants_names):
        order_line_vals = {
            'order_id': order.id,
            'product_id': product.id,
            'order_item_id': meli_order_line_vals['item']['id'],
            'order_item_title': "%s %s" % (meli_order_line_vals['item']['title'], ("(%s)" % variants_names) if variants_names else ''),
            'order_item_category_id': meli_order_line_vals['item']['category_id'],
            'unit_price': meli_order_line_vals['unit_price'],
            'quantity': meli_order_line_vals['quantity'],
            'currency_id': meli_order_line_vals['currency_id']
        }
        return order_line_vals
        
    @api.model
    def _add_order_line(self, order, meli_order_lines, post_related, product_find, variants_names):
        OrderItemModel = self.env['mercadolibre.order_items']
        order_item_vals = self._prepare_order_line_vals(order, meli_order_lines, post_related, product_find, variants_names)
        OrderLine = OrderItemModel.search([
            ('order_item_id', '=', order_item_vals['order_item_id']),
            ('order_id','=',order.id),
        ], limit=1)
        if not OrderLine:
            OrderLine = OrderItemModel.create(order_item_vals)
        else:
            OrderLine.write(order_item_vals)
        return OrderLine
    
    @api.model
    def _prepare_sale_order_line_vals(self, sale_order, meli_order_line):
        sale_order_line_vals = {
            'order_id': sale_order.id,
            'name': meli_order_line.order_item_title,
            'meli_order_item_id': meli_order_line.order_item_id,
            'product_id': meli_order_line.product_id.id,
            'product_uom_qty': meli_order_line.quantity,
            'product_uom': meli_order_line.product_id.uom_id.id,
            'price_unit': meli_order_line.unit_price,
        }
        return sale_order_line_vals
    
    @api.model
    def _add_sale_order_line(self, sale_order, meli_order_line):
        SaleOrderLineModel = self.env['sale.order.line']
        sale_order_line_vals = self._prepare_sale_order_line_vals(sale_order, meli_order_line)
        SaleOrderLine = SaleOrderLineModel.search([
            ('meli_order_item_id', '=', sale_order_line_vals['meli_order_item_id']),
            ('order_id','=',sale_order.id),
        ], limit=1)
        if not SaleOrderLine:
            SaleOrderLine = SaleOrderLineModel.create(sale_order_line_vals)
        else:
            SaleOrderLine.write(sale_order_line_vals)
        return SaleOrderLine
    
    @api.model
    def _prepare_payment_vals(self, order, meli_payment_vals):
        payment_vals = {
            'order_id': order.id,
            'payment_id': meli_payment_vals['id'],
            'transaction_amount': meli_payment_vals.get('transaction_amount') or 0,
            'currency_id': meli_payment_vals.get('currency_id') or '',
            'status': meli_payment_vals.get('status') or '',
            'date_created': meli_payment_vals.get('date_created') or '',
            'date_last_modified': meli_payment_vals.get('date_last_modified') or '',
        }
        return payment_vals
    
    @api.model
    def _add_payment(self, order, meli_payment_vals):
        Payments = self.env['mercadolibre.payments']
        _logger.info(meli_payment_vals)
        payment_vals = self._prepare_payment_vals(order, meli_payment_vals)
        payment = Payments.search([
            ('payment_id', '=', payment_vals['payment_id']),
            ('order_id', '=', order.id),
        ], limit=1)
        if not payment:
            payment = Payments.create(payment_vals)
        else:
            payment.write(payment_vals)
        return payment

    def orders_update_order_json( self, data, context=None ):
        order_json = data["order_json"]
        _logger.info("orders_update_order_json > data: " + str(order_json))
        PartnerModel = self.env['res.partner']
        MeliOrderModel = self.env['mercadolibre.orders']
        PostingModel = self.env['mercadolibre.posting']
        partner = PartnerModel.browse()
        notes = []
        need_review = False
        meli_order = MeliOrderModel.search([('order_id','=',order_json['id'])], limit=1)
        order_vals = self._prepare_order_vals(order_json)
        if 'buyer' in order_json:
            Buyer = order_json['buyer']
            document_number =False
            if Buyer['billing_info'].get('doc_number'):
                document_number = Buyer['billing_info'].get('doc_number')
                document_number = (re.sub('[^1234567890Kk]', '', str(document_number))).zfill(9).upper()
            buyer = self._find_create_buyer(Buyer, document_number)
            partner = self._find_create_partner(Buyer, document_number)
            order_vals['buyer'] = buyer.id
            if not buyer.partner_id:
                buyer.partner_id = partner
        #process base meli_order fields
        if (order_json["shipping"]):
            order_vals['shipping'] = self.pretty_json( id, order_json["shipping"] )
            shipping_values = self.prepare_values_shipping(order_json["shipping"])
            order_vals.update(shipping_values)
            order_vals['partner_id'] = partner.id
        #create or update meli_order
        if (meli_order):
            _logger.info("Updating meli orden: %s", meli_order.id)
            meli_order.write(order_vals)
        else:
            _logger.info("Adding new meli order: %s", str(order_vals))
            meli_order = MeliOrderModel.create(order_vals)
        #update internal fields (items, payments, buyers)
        if 'order_items' in order_json:
            notes = []
            need_review = False
            cn = 0
            for Item in order_json['order_items']:
                cn = cn + 1
                _logger.info(cn)
                _logger.info(Item)
                post_related = PostingModel.search([('meli_id','=',Item['item']['id'])])
                if not post_related:
                    notes.append("*Producto: %s con ID: %s no existe" % (Item['item']['title'], Item['item']['id']))
                    need_review = True
                    continue
                product_find, variants_names = self._find_product(Item)
                if not product_find:
                    notes.append("*Producto: %s con ID: %s no existe" % (Item['item']['title'], Item['item']['id']))
                    need_review = True
                    continue
                self._add_order_line(meli_order, Item, post_related, product_find, variants_names)
        if 'payments' in order_json:
            for meli_payment_vals in order_json['payments']:
                self._add_payment(meli_order, meli_payment_vals)
        meli_order._find_create_sale_order()
        meli_order.write({
            'need_review': need_review,
            'note': "".join(notes),
        })
        return meli_order

    def orders_update_order( self, context=None ):
        meli_util_model = self.env['meli.util']
        #get with an item id
        order = self
        log_msg = 'orders_update_order: %s' % (order.order_id)
        _logger.info(log_msg)
        meli = meli_util_model.get_new_instance()
        response = meli.get("/orders/"+order.order_id, {'access_token':meli.access_token})
        order_json = response.json()
        _logger.info( order_json )
        if "error" in order_json:
            _logger.error( order_json["error"] )
            _logger.error( order_json["message"] )
        else:
            self.orders_update_order_json( {"id": id, "order_json": order_json } )
        return {}

    def orders_query_iterate( self, offset=0, context=None ):
        meli_util_model = self.env['meli.util']
        offset_next = 0
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        orders_query = "/orders/search?seller="+company.mercadolibre_seller_id+"&sort=date_desc"
        if (offset):
            orders_query = orders_query + "&offset="+str(offset).strip()
        response = meli.get( orders_query, {'access_token':meli.access_token})
        orders_json = response.json()
        if "error" in orders_json:
            _logger.error( orders_query )
            _logger.error( orders_json["error"] )
            if (orders_json["message"]=="invalid_token"):
                _logger.error( orders_json["message"] )
            return {}
        _logger.info( orders_json )
        #testing with json:
        if (True==False):
            with open('/home/fabricio/envOdoo8/sources/meli_oerp/orders.json') as json_data:
                _logger.info( json_data )
                orders_json = json.load(json_data)
                _logger.info( orders_json )
        if "paging" in orders_json:
            if "total" in orders_json["paging"]:
                if (orders_json["paging"]["total"]==0):
                    return {}
                else:
                    if (orders_json["paging"]["total"]==orders_json["paging"]["limit"]):
                        offset_next = offset + orders_json["paging"]["limit"]
        if "results" in orders_json:
            for order_json in orders_json["results"]:
                if order_json:
                    _logger.info( order_json )
                    pdata = {"id": False, "order_json": order_json}
                    self.orders_update_order_json( pdata )
        if (offset_next>0):
            self.orders_query_iterate(offset_next)
        return {}

    def orders_query_recent( self ):
        self.orders_query_iterate( 0 )
        return {}
    
    @api.one
    def get_tag_delivery(self):
        self.ensure_one()
        meli_util_model = self.env['meli.util']
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        params = {
            'shipment_ids': self.shipping_id,
            'response_type': 'pdf',
            'access_token':meli.access_token,
        }
        orders_query = "/shipment_labels"
        response = meli.get(orders_query, params)
        return response.content
        
    @api.multi
    def action_print_tag_delivery(self):
        self.ensure_one()
        self.shipping_substatus = 'printed'
        if self.sale_order_id:
            self.sale_order_id.shipping_substatus = 'printed'
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': "Etiqueta de Envio %s.pdf" % (self.shipping_id),
                    'model': self._name,
                    'record_id': self.id,
                    'method': 'get_tag_delivery',
                },
                'target': 'new',
        }
        
    @api.multi
    def _get_payment_journal_for_invoice(self, invoice):
        return self.env['account.journal'].search([('type', 'in', ('cash', 'bank'))], limit=1)
        
    @api.multi
    def _prepare_payment_for_invoice(self, invoice):
        payment_journal = self._get_payment_journal_for_invoice(invoice)
        payment_vals = {
            'payment_type': 'inbound',
            'partner_id': invoice.partner_id.id,
            'partner_type': 'customer',
            'journal_id': payment_journal.id,
            'amount': self.total_amount,
            'payment_method_id': payment_journal.inbound_payment_method_ids.id,
            'invoice_ids': [(6, 0, [invoice.id])],
        }
        return payment_vals
        
    @api.model
    def action_validate_sale_order(self):
        PaymentModel = self.env['account.payment']
        limit_meli = int(self.env['ir.config_parameter'].get_param('meli.order.limit', '100').strip())
        meli_orders = self.search([
            ('status','=', 'paid'),
            ('shipping_status','=', 'ready_to_ship'),
        ], limit=limit_meli)
        message_list = []
        current_document_info = ""
        for meli_order in meli_orders:
            current_document_info = ""
            try:
                #en caso de no tener pedido de venta, crearlo
                sale_order = meli_order.sale_order_id
                if not sale_order:
                    sale_order = meli_order._find_create_sale_order()
                if sale_order.state in ('draft', 'sent'):
                    current_document_info = "Confirmando Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                    _logger.info(current_document_info)
                    sale_order.action_confirm()
                #validar los picking
                for picking in sale_order.picking_ids.filtered(lambda x: x.state not in ('draft', 'cancel', 'done')):
                    current_document_info = "Confirmando y validando picking ID: %s Numero: %s" % (picking.id, picking.name)
                    _logger.info(current_document_info)
                    picking.action_confirm()
                    picking.force_assign()
                    picking.action_done()
                #crear y validar factura
                if not sale_order.invoice_ids:
                    current_document_info = "Creando factura para Pedido de venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                    _logger.info(current_document_info)
                    sale_order.action_invoice_create()
                for invoice in sale_order.invoice_ids.filtered(lambda x: x.state not in ('open', 'paid', 'cancel')):
                    current_document_info = "Confirmando y pagando la factura ID: %s Numero: %s" % (invoice.id, invoice.display_name)
                    _logger.info(current_document_info)
                    invoice.action_invoice_open()
                    #marcar la factura como pagada
                    payment_vals = meli_order._prepare_payment_for_invoice(invoice)
                    payment_id = PaymentModel.create(payment_vals)
                    payment_id.post()
            except Exception, e:
                _logger.error(current_document_info)
                _logger.error(tools.ustr(e))
                message_list.append((current_document_info, tools.ustr(e)))
        if message_list and csv:
            file_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            file_path = os.path.join(file_path, "validar_pedidos_meli_%s.csv" % fields.Datetime.context_timestamp(self, datetime.now()).strftime('%Y_%m_%d_%H_%M_%S'))
            fp = open(file_path,'wb')
            csv_file = csv.writer(fp, quotechar='"', quoting=csv.QUOTE_ALL)
            csv_file.writerow(['Mensaje', 'Detalle'])
            for line in message_list:
                csv_file.writerow([line[0], line[1]])
            fp.close()
        return True

class MercadolibreOrderItems(models.Model):
    
    _name = "mercadolibre.order_items"
    _description = "Producto pedido en MercadoLibre"

    order_id = fields.Many2one("mercadolibre.orders","Order")
    product_id = fields.Many2one('product.product', u'Producto', ondelete="restrict", index=True)
    order_item_id = fields.Char('Item Id')
    order_item_title = fields.Char('Item Title')
    order_item_category_id = fields.Char('Item Category Id')
    unit_price = fields.Char(string='Unit price')
    quantity = fields.Integer(string='Quantity')
    currency_id = fields.Char(string='Currency')

class MercadolibrePayments(models.Model):
    
    _name = "mercadolibre.payments"
    _description = "Pagos en MercadoLibre"

    order_id = fields.Many2one("mercadolibre.orders","Order")
    payment_id = fields.Char('Payment Id')
    transaction_amount = fields.Char('Transaction Amount')
    currency_id = fields.Char(string='Currency')
    status = fields.Char(string='Payment Status')
    date_created = fields.Date('Creation date')
    date_last_modified = fields.Date('Modification date')

class MercadolibreBuyers(models.Model):
    
    _name = "mercadolibre.buyers"
    _description = "Compradores en MercadoLibre"

    buyer_id = fields.Char(string='Buyer ID')
    nickname = fields.Char(string='Nickname')
    email = fields.Char(string='Email')
    phone = fields.Char( string='Phone')
    alternative_phone = fields.Char( string='Alternative Phone')
    first_name = fields.Char( string='First Name')
    last_name = fields.Char( string='Last Name')
    billing_info = fields.Char( string='Billing Info')
    document_number = fields.Char(u'Numero de Documento')
    partner_id = fields.Many2one('res.partner', u'Empresa')
    
    @api.multi
    def name_get(self):
        res = []
        for buyer in self:
            name = u"%s %s" % (buyer.first_name or '', buyer.last_name or '')
            res.append((buyer.id, name))
        return res

class MercadolibreOrdersUpdate(models.TransientModel):
    
    _name = "mercadolibre.orders.update"
    _description = "Update Order"

    def order_update(self, context):
        orders_ids = context['active_ids']
        orders_obj = self.env['mercadolibre.orders']
        for order_id in orders_ids:
            _logger.info("order_update: %s " % (order_id) )
            order = orders_obj.browse( order_id)
            order.orders_update_order()
        return {}
