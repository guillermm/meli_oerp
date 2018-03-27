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

import re
import json
import logging

from odoo import fields, osv, models, api
import odoo.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)

#https://api.mercadolibre.com/questions/search?item_id=MLA508223205

class ResPartner(models.Model):
    
    _inherit = "res.partner"

    meli_buyer_id = fields.Char('Meli Buyer Id')
    
    @api.model
    def process_fields_meli(self, values, doc_type):
        return values

class mercadolibre_orders(models.Model):
    
    _name = "mercadolibre.orders"
    _description = "Pedidos en MercadoLibre"
    _rec_name = 'order_id'

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

    def orders_update_order_json( self, data, context=None ):
        _logger.info("orders_update_order_json > data: " + str(data) )
        oid = data["id"]
        order_json = data["order_json"]
        #print "data:" + str(data)
        #_logger.info("orders_update_order_json > data[id]: " + oid + " order_json:" + order_json )
        company = self.env.user.company_id
        saleorder_obj = self.env['sale.order']
        saleorderline_obj = self.env['sale.order.line']
        product_obj = self.env['product.template']
        pricelist_obj = self.env['product.pricelist']
        respartner_obj = self.env['res.partner']
        plistids = pricelist_obj.search([
            ('currency_id','=','CLP'),
            ('website_id','!=',False),
            ], limit=1)
        plistid = None
        if plistids:
            plistid = plistids
        order_obj = self.env['mercadolibre.orders']
        buyers_obj = self.env['mercadolibre.buyers']
        posting_obj = self.env['mercadolibre.posting']
        order_items_obj = self.env['mercadolibre.order_items']
        payments_obj = self.env['mercadolibre.payments']
        order = self.browse()
        sorder = saleorder_obj.browse()
        # if id is defined, we are updating existing one
        if (oid):
            order = order_obj.browse(oid )
            ##sorder = order_obj.browse(
            sorder = saleorder_obj.browse(oid )
        else:
        #we search for existing order with same order_id => "id"
            order_s = order_obj.search([ ('order_id','=',order_json['id']) ] )
            if (order_s):
                order = order_s
            #    order = order_obj.browse(order_s[0] )

            if order.sale_order_id:
                sorder = order.sale_order_id
            if not sorder and order:
                sorder = saleorder_obj.search([('meli_order_id','=',order.id)])
        order_fields = {
            'order_id': '%i' % (order_json["id"]),
            'status': order_json["status"],
            'status_detail': order_json["status_detail"] or '' ,
            'total_amount': order_json["total_amount"],
            'currency_id': order_json["currency_id"],
            'date_created': order_json["date_created"] or '',
            'date_closed': order_json["date_closed"] or '',
        }
        #print "order:" + str(order)
        if 'buyer' in order_json:
            Buyer = order_json['buyer']
            meli_buyer_fields = {
                'name': Buyer['first_name']+' '+Buyer['last_name'],
                'street': 'no street',
                'phone': self.full_phone( Buyer['phone']),
                'email': Buyer['email'],
                'meli_buyer_id': Buyer['id'],
            }
            buyer_fields = {
                'buyer_id': Buyer['id'],
                'nickname': Buyer['nickname'],
                'email': Buyer['email'],
                'phone': self.full_phone( Buyer['phone']),
                'alternative_phone': self.full_phone( Buyer['alternative_phone']),
                'first_name': Buyer['first_name'],
                'last_name': Buyer['last_name'],
                'billing_info': self.billing_info(Buyer['billing_info']),
            }
            document_number =False
            if Buyer['billing_info'].get('doc_number'):
                document_number = Buyer['billing_info'].get('doc_number')
                document_number = (re.sub('[^1234567890Kk]', '', str(document_number))).zfill(9).upper()
                vat = 'CL%s' % document_number
                document_number = '%s.%s.%s-%s' % (
                    document_number[0:2], document_number[2:5],
                    document_number[5:8], document_number[-1])
                buyer_fields['document_number'] = document_number
                meli_buyer_fields['document_number'] = document_number
                meli_buyer_fields['vat'] = vat
                meli_buyer_fields = respartner_obj.process_fields_meli(meli_buyer_fields, Buyer['billing_info'].get('doc_type') or 'RUT')
            buyer_ids = buyers_obj.search([  ('buyer_id','=',buyer_fields['buyer_id'] ) ] )
            buyer_id = 0
            if not buyer_ids:
                print "creating buyer:" + str(buyer_fields)
                buyer_id = buyers_obj.create(( buyer_fields ))
            else:
                if (buyer_ids):
                    buyer_id = buyer_ids
                #if (len(buyer_ids)>0):
                #      buyer_id = buyer_ids[0]

            partner_ids = respartner_obj.search([('meli_buyer_id', '=', buyer_fields['buyer_id'])])
            partner_id = 0
            if not partner_ids and document_number:
                partner_ids = respartner_obj.search([('document_number', '=', document_number)])
            if not partner_ids:
                #print "creating partner:" + str(meli_buyer_fields)
                partner_id = respartner_obj.create(( meli_buyer_fields ))
            else:
                partner_id = partner_ids
                #if (len(partner_ids)>0):
                #    partner_id = partner_ids[0]
            if buyer_id and partner_id and not buyer_id.partner_id:
                buyer_id.partner_id = partner_id
            if order:
                return_id = order.write({'buyer':buyer_id.id})
            else:
                partner_id.write((meli_buyer_fields))
        if (len(partner_ids)>0):
            partner_id = partner_ids[0]
        #process base order fields
        meli_order_fields = {
            'partner_id': partner_id.id,
            'pricelist_id': plistid.id,
            'meli_status': order_json["status"],
            'meli_status_detail': order_json["status_detail"] or '' ,
            'meli_total_amount': order_json["total_amount"],
            'meli_currency_id': order_json["currency_id"],
            'meli_date_created': order_json["date_created"] or '',
            'meli_date_closed': order_json["date_closed"] or '',
        }
        if (order_json["shipping"]):
            order_fields['shipping'] = self.pretty_json( id, order_json["shipping"] )
            meli_order_fields['meli_shipping'] = self.pretty_json( id, order_json["shipping"] )
            shipping_values = self.prepare_values_shipping(order_json["shipping"])
            order_fields.update(shipping_values)
            meli_order_fields.update(shipping_values)
        #create or update order
        if (order and order.id):
            _logger.info("Updating order: %s" % (order.id))
            order.write( order_fields )
        else:
            _logger.info("Adding new order: " )
            _logger.info(order_fields)
            print "creating order:" + str(order_fields)
            order = order_obj.create( (order_fields))

        meli_order_fields['meli_order_id'] = order.id
        if (sorder and sorder.id):
            _logger.info("Updating sale.order: %s" % (sorder.id))
            sorder.write( meli_order_fields )
        else:
            _logger.info("Adding new sale.order: " )
            _logger.info(meli_order_fields)
            #print "creating sale order:" + str(meli_order_fields)
            sorder = saleorder_obj.create((meli_order_fields))
        order.write({'sale_order_id': sorder.id})
        #check error
        if not order:
            _logger.error("Error adding order. " )
            print "Error adding order"
            return {}
        #check error
        if not sorder:
            _logger.error("Error adding sale.order. " )
            print "Error adding sale.order"
            return {}
        #update internal fields (items, payments, buyers)
        if 'order_items' in order_json:
            items = order_json['order_items']
            _logger.info( items )
            print "order items" + str(items)
            cn = 0
            for Item in items:
                cn = cn + 1
                _logger.info(cn)
                _logger.info(Item )
                product_related = product_obj.search([('meli_id','=',Item['item']['id'])], limit=1)
                post_related = posting_obj.search([('meli_id','=',Item['item']['id'])])
                post_related_obj = ''
                product_related_obj = ''
                product_related_obj_id = False
                if len(post_related):
                    post_related_obj = post_related
                    _logger.info( post_related_obj )
                    #if (post_related[0]):
                    #    post_related_obj = post_related[0]
                else:
                    return {}
                variants_names = ""
                if len(product_related):
                    product_related_obj = product_related.product_variant_ids[0]
                    #si hay informacion de variantes, tomar la variante especifica que se haya vendido
                    product_variant = False
                    if Item['item'].get('variation_id'):
                        product_variant = product_related.product_variant_ids.filtered(lambda x: x.meli_id == str(Item['item'].get('variation_id')))
                        if product_variant:
                            all_atr_name_meli = []
                            for attr in Item['item'].get('variation_attributes', []):
                                all_atr_name_meli.append(attr['value_name'])
                            product_related_obj = product_variant
                            variants_names = ", ".join(all_atr_name_meli)
                    if not product_variant and Item['item'].get('variation_attributes'):
                        all_atr_meli = set()
                        all_atr_name_meli = set()
                        for attr in Item['item'].get('variation_attributes'):
                            all_atr_meli.add(attr['id'])
                            all_atr_name_meli.add(attr['value_name'].lower())
                        for product_variant in product_related.product_variant_ids:
                            all_atr = set()
                            all_atr_name = set()
                            for attribute in product_variant.attribute_value_ids:
                                if not attribute.attribute_id.meli_id:
                                    continue
                                all_atr.update(set(attribute.attribute_id.meli_id.split(',')))
                                all_atr_name.add(attribute.name.lower())
                            if all_atr_meli.intersection(all_atr) and all_atr_name_meli == all_atr_name:
                                product_related_obj = product_variant
                                variants_names = ", ".join(list(all_atr_name_meli))
                                break
                    _logger.info( product_related_obj )
                    #if (product_related[0]):
                    #    product_related_obj_id = product_related[0]
                    #    product_related_obj = product_obj.browse( product_related_obj_id)
                    #    _logger.info("product_related:")
                    #    _logger.info( product_related_obj )
                else:
                    return {}
                order_item_fields = {
                    'order_id': order.id,
                    'posting_id': post_related_obj.id,
                    'order_item_id': Item['item']['id'],
                    'order_item_title': "%s %s" % (Item['item']['title'], ("(%s)" % variants_names) if variants_names else ''),
                    'order_item_category_id': Item['item']['category_id'],
                    'unit_price': Item['unit_price'],
                    'quantity': Item['quantity'],
                    'currency_id': Item['currency_id']
                }
                order_item_ids = order_items_obj.search( [('order_item_id','=',order_item_fields['order_item_id']),('order_id','=',order.id)] )
                _logger.info( order_item_fields )
                if not order_item_ids:
                    #print "order_item_fields: " + str(order_item_fields)
                    order_item_ids = order_items_obj.create( ( order_item_fields ))
                else:
                    order_item_ids.write( ( order_item_fields ) )
                saleorderline_item_fields = {
                    'company_id': company.id,
                    'order_id': sorder.id,
                    'meli_order_item_id': Item['item']['id'],
                    'price_unit': float(Item['unit_price']),
#                    'price_total': float(Item['unit_price']) * float(Item['quantity']),
                    'product_id': product_related_obj.id,
                    'product_uom_qty': Item['quantity'],
                    'product_uom': product_related_obj.uom_id.id,
                    'name': "%s %s" % (Item['item']['title'], ("(%s)" % variants_names) if variants_names else ''),
#                    'customer_lead': float(0)
                }
                saleorderline_item_ids = saleorderline_obj.search( [('meli_order_item_id','=',saleorderline_item_fields['meli_order_item_id']),('order_id','=',sorder.id)] )
                _logger.info( saleorderline_item_fields )
                if not saleorderline_item_ids:
                    #print "saleorderline_item_fields: " + str(saleorderline_item_fields)
                    saleorderline_item_ids = saleorderline_obj.create( ( saleorderline_item_fields ))
                else:
                    saleorderline_item_ids.write( ( saleorderline_item_fields ) )
        if 'payments' in order_json:
            payments = order_json['payments']
            _logger.info( payments )
            cn = 0
            for Payment in payments:
                cn = cn + 1
                _logger.info(cn)
                _logger.info(Payment )
                payment_fields = {
                    'order_id': order.id,
                    'payment_id': Payment['id'],
                    'transaction_amount': Payment['transaction_amount'] or '',
                    'currency_id': Payment['currency_id'] or '',
                    'status': Payment['status'] or '',
                    'date_created': Payment['date_created'] or '',
                    'date_last_modified': Payment['date_last_modified'] or '',
                }
                payment_ids = payments_obj.search( [  ('payment_id','=',payment_fields['payment_id']),
                                                            ('order_id','=',order.id ) ] )
                if not payment_ids:
                    payment_ids = payments_obj.create( ( payment_fields ))
                else:
                    payment_ids.write( ( payment_fields ) )
        if order:
            return_id = self.env['mercadolibre.orders'].update
        return {}

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
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': "Etiqueta de Envio %s.pdf" % (self.shipping_id),
                    'model': self._name,
                    'record_id': self.id,
                    'method': 'get_tag_delivery',
                },
                'target': 'new',
        }

    order_id = fields.Char('Order Id')
    sale_order_id = fields.Many2one('sale.order', u'Pedido de Venta',
        copy=False, readonly=True)
    status = fields.Selection( [
        #Initial state of an order, and it has no payment yet.
                                        ("confirmed","Confirmado"),
        #The order needs a payment to become confirmed and show users information.
                                      ("payment_required","Pago requerido"),
        #There is a payment related with the order, but it has not accredited yet
                                    ("payment_in_process","Pago en proceso"),
        #The order has a related payment and it has been accredited.
                                    ("paid","Pagado"),
        #The order has not completed by some reason.
                                    ("cancelled","Cancelado")], string='Order Status')

    status_detail = fields.Text(string='Status detail, in case the order was cancelled.')
    date_created = fields.Date('Creation date')
    date_closed = fields.Date('Closing date')
    order_items = fields.One2many('mercadolibre.order_items','order_id','Order Items' )
    payments = fields.One2many('mercadolibre.payments','order_id','Payments' )
    shipping = fields.Text(string="Shipping")
    total_amount = fields.Char(string='Total amount')
    currency_id = fields.Char(string='Currency')
    buyer =  fields.Many2one( "mercadolibre.buyers","Buyer")
    seller = fields.Text( string='Seller' )
    shipping_id = fields.Char(u'ID de Entrega')
    shipping_name = fields.Char(u'Metodo de Entrega')
    shipping_method_id = fields.Char(u'ID de Metodo de Entrega')
    shipping_cost = fields.Float(u'Costo de Entrega', digits=dp.get_precision('Account'))
    shipping_status = fields.Selection([
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

class MercadolibreOrderItems(models.Model):
    
    _name = "mercadolibre.order_items"
    _description = "Producto pedido en MercadoLibre"

    posting_id = fields.Many2one("mercadolibre.posting","Posting")
    order_id = fields.Many2one("mercadolibre.orders","Order")
    order_item_id = fields.Char('Item Id')
    order_item_title = fields.Char('Item Title')
    order_item_category_id = fields.Char('Item Category Id')
    unit_price = fields.Char(string='Unit price')
    quantity = fields.Integer(string='Quantity')
    #       'total_price': fields.char(string='Total price'),
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
