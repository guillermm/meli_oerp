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
import json
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
_logger = logging.getLogger(__name__)

try:
    import csv
except ImportError:
    csv = False
    _logger.error('This module needs csv. Please install csv on your system')

from odoo import fields, osv, models, api, tools
import odoo.addons.decimal_precision as dp
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF

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
    date_created = fields.Datetime('Creation date')
    date_closed = fields.Datetime('Closing date')
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
        ('not_verified','No Verificado'),
        ('cancelled','cancelled'),
        ('closed','Cerrado'),
        ('error','Error'),
        ('active','Activo'),
        ('not_specified','No especificado'),
        ('stale_ready_to_ship','A Punto de Enviar'),
        ('stale_shipped','Enviado'),
    ], string=u'Estado de Entrega', index=True, readonly=True)
    shipping_substatus = fields.Selection([
        #subestados de pending
        ('cost_exceeded','Costo Exedido'),
        ('under_review','Bajo Revision'),
        ('reviewed','Revisado'),
        ('fraudulent','Fraudulento'),
        ('waiting_for_payment','Esperando pago se acredite'),
        ('shipment_paid','Costo de envio pagado'),
        #subestados de handling
        ('regenerating','Regenerado'),
        ('waiting_for_label_generation','Esperando Impresion de etiqueta'),
        ('invoice_pending','Facturacion Pendiente'),
        ('waiting_for_return_confirmation','Esperando Confirmacion de devolucion'),
        ('return_confirmed','Devolucion Confirmada'),
        ('manufacturing','Fabricado'),
        #subestados de ready_to_ship
        ('ready_to_print','Etiqueta no Impresa'),
        ('printed','Etiqueta Impresa'),
        ('in_pickup_list','En Lista de Entrega'),
        ('ready_for_pkl_creation','Listo para crear PKL'),
        ('ready_for_pickup','Listo para Entrega en tienda'),
        ('ready_for_dropoff','Listo para dropoff'),
        ('picked_up','Retirado en tienda'),
        ('stale','A Punto de enviar'),
        ('dropped_off','Caido'),
        ('in_hub','En Centro'),
        ('measures_ready','Medidas listas'),
        ('waiting_for_carrier_authorization','Esperando aprobacion de courrier'),
        ('authorized_by_carrier','Aprobado por Courrier'),
        ('in_packing_list','En lista de empaque'),
        ('in_plp','En PLP'),
        ('in_warehouse','En Bodega'),
        ('ready_to_pack','Listo para empacar'),
        #subestados de shipped
        ('delayed','Retrasado'),
        ('waiting_for_withdrawal','Esperando Retirada'),
        ('contact_with_carrier_required','Se requiere contacto con el transportista'),
        ('receiver_absent','Receptor ausente'),
        ('reclaimed','Reclamado'),
        ('not_localized','No localizado'),
        ('forwarded_to_third','Enviado a Tercero'),
        ('soon_deliver','Pronto a entregar'),
        ('refused_delivery','Entrega rechazada'),
        ('bad_address','Mala direccion'),
        ('negative_feedback','No enviado por malos conmentarios del comprador'),
        ('need_review','Necesita revision'),
        ('operator_intervention','Necesita intervencion del operador'),
        ('claimed_me','Reclamo del vendedor'),
        ('retained','Paquete Retenido'),
        #subestados de delivered
        ('damaged','Dañado'),
        ('fulfilled_feedback','Cumplido por los comentarios del comprador'),
        ('no_action_taken','Ninguna acción tomada por el comprador'),
        ('double_refund','Doble Reembolso'),
        #subestados de not_delivered
        ('returning_to_sender','Returning to sender'),
        ('stolen','Robado'),
        ('returned','Devuelto'),
        ('confiscated','Confiscado'),
        ('to_review','Envio Cerrado'),
        ('destroyed','Destruido'),
        ('lost','Perdido'),
        ('cancelled_measurement_exceeded','Cancelado por exeso de medidas'),
        ('returned_to_hub','Devuelto al centro'),
        ('returned_to_agency','Devuelto a agencia'),
        ('picked_up_for_return','Devuelto para regocer en local'),
        ('returning_to_warehouse','Devolviendo a Almacen'),
        ('returned_to_warehouse','Devuelto a Almacen'),
        #subestados de cancelled
        ('recovered','Recuperado'),
        ('label_expired','Etiqueta Expirada'),
        ('cancelled_manually','Cancelado manualmente'),
        ('fraudulent','Cancelado fraudulento'),
        ('return_expired','Devuelto por expiracion'),
        ('return_session_expired','Sesion de devolucion expirada'),
        ('unfulfillable','Imposible de llenar'),
    ], string=u'Estado de Impresion/Entrega', index=True, readonly=True)
    shipping_mode = fields.Selection([
        ('me2','Mercado Envio'),
    ], string=u'Metodo de envio', readonly=True)
    note = fields.Html(u'Notas', readonly=True, copy=False)
    need_review = fields.Boolean(u'Necesita Revision?', readonly=True, copy=False)
    need_credit_note = fields.Boolean(u'Necesita Nota de Credito?', readonly=True, copy=False)

    def billing_info( self, billing_json, context=None ):
        billinginfo = ''
        if 'doc_type' in billing_json:
            if billing_json['doc_type']:
                billinginfo+= billing_json['doc_type']
        if 'doc_number' in billing_json:
            if billing_json['doc_number']:
                billinginfo+= billing_json['doc_number']
        return billinginfo

    def _pre_process_document_number(self, document_number):
        '''
        En algunos paises sera necesario validar o procesar el RUT/RUC o documento tributario del cliente
        antes de crear el cliente, sobreescribir esta funcion de ser necesario
        '''
        return document_number
    
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
        }
        #pasar el vat con codigo de pais incluido
        if self.env.user.company_id.country_id:
            partner_vals['vat'] = '%s%s' % (self.env.user.company_id.country_id.code, document_number)
        return partner_vals
    
    @api.model
    def _find_create_partner(self, meli_buyer_vals, document_number):
        partnerModel = self.env['res.partner']
        partner_vals = self._prepare_partner_vals(meli_buyer_vals, document_number)
        partner_find = partnerModel.search([('meli_buyer_id', '=', partner_vals['meli_buyer_id'])], limit=1)
        if not partner_find:
            partner_find = partnerModel.create(partner_vals)
        return partner_find

    @api.model
    def _prepare_order_vals(self, meli_order_vals):
        meli_util = self.env['meli.util']
        order_vals = {
            'order_id': meli_order_vals["id"],
            'status': meli_order_vals.get("status"),
            'status_detail': meli_order_vals.get("status_detail"),
            'total_amount': meli_order_vals.get("total_amount"),
            'currency_id': meli_order_vals.get("currency_id"),
            'date_created': meli_util.convert_to_datetime(meli_order_vals.get("date_created")).strftime(DTF),
            'date_closed': meli_util.convert_to_datetime(meli_order_vals.get("date_closed")).strftime(DTF),
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
            'shipping_mode': self.shipping_mode,
        }
        if company.mercadolibre_sale_team_id:
            sale_order_vals['team_id'] = company.mercadolibre_sale_team_id.id
        warehouse_meli = self.env['stock.warehouse'].sudo().search([
            ('meli_published','=',True), 
            ('company_id','=',company.id),
            ], order="meli_sequence", limit=1)
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
            if self.shipping_substatus == 'printed':
                _logger.info("No se modifica sale.order: %s, esta lista para ser validada y etiqueta impresa", sale_order.id)
            elif sale_order.state not in ('sale', 'done', 'cancel'):
                _logger.info("Updating sale.order: %s", sale_order.id)
                sale_order.write(sale_order_vals)
        else:
            _logger.info("Adding new sale.order: " )
            sale_order = SaleOrderModel.create(sale_order_vals)
            self.write({'sale_order_id': sale_order.id})
        for line in self.order_items:
            self._add_sale_order_line(sale_order, line)
        #si el pedido esta pagado y listo para enviar, confirmar el pedido de venta y crear el picking
        message_list = []
        if self.status == 'paid' and self.shipping_status == 'ready_to_ship':
            current_document_info = ""
            try:
                if sale_order.state in ('draft', 'sent'):
                    current_document_info = "Confirmando Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                    _logger.info(current_document_info)
                    #cambiar el almacen de donde tomar los productos
                    #de ser necesario(cuando no haya stock en un almacen usar el siguiente)
                    warehouse = self._get_warehouse_to_order(sale_order)
                    if sale_order.warehouse_id != warehouse:
                        current_document_info = "Cambiando almacen a Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                        more_info = "Almacen anterior: %s, nuevo almacen: %s" % (sale_order.warehouse_id.name, warehouse.name)
                        message_list.append((current_document_info, more_info))
                        sale_order.write({'warehouse_id': warehouse.id})
                        sale_order.message_post(body="Cambiando almacen por falta de stock %s" % more_info)
                    sale_order.action_confirm()
                #validar los picking
                for picking in sale_order.picking_ids.filtered(lambda x: x.state not in ('draft', 'cancel', 'done')):
                    current_document_info = "Confirmando y validando picking ID: %s Numero: %s" % (picking.id, picking.name)
                    _logger.info(current_document_info)
                    picking.action_confirm()
                    picking.force_assign()
                    picking.action_done()
            except Exception, e:
                _logger.error(tools.ustr(e))
                message_list.append((current_document_info, tools.ustr(e)))
        return sale_order, message_list
        
    @api.model
    def _find_product(self, meli_order_line_vals):
        ProductTemplateModel = self.env['product.template']
        ProductModel = self.env['product.product']
        product_template = ProductTemplateModel.search([('meli_id', '=', meli_order_line_vals['item']['id'])], limit=1)
        product_find = ProductModel.browse()
        variants_names = ""
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
    def _prepare_order_line_vals(self, order, meli_order_line_vals, product, variants_names):
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
    def _add_order_line(self, order, meli_order_lines, product_find, variants_names):
        OrderItemModel = self.env['mercadolibre.order_items']
        order_item_vals = self._prepare_order_line_vals(order, meli_order_lines, product_find, variants_names)
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
        meli_util = self.env['meli.util']
        payment_vals = {
            'order_id': order.id,
            'payment_id': meli_payment_vals['id'],
            'transaction_amount': meli_payment_vals.get('transaction_amount') or 0,
            'currency_id': meli_payment_vals.get('currency_id') or '',
            'status': meli_payment_vals.get('status') or '',
            'date_created': meli_util.convert_to_datetime(meli_payment_vals.get('date_created')).strftime(DTF),
            'date_last_modified': meli_util.convert_to_datetime(meli_payment_vals.get('date_last_modified')).strftime(DTF),
        }
        return payment_vals
    
    @api.model
    def _add_payment(self, order, meli_payment_vals):
        Payments = self.env['mercadolibre.payments']
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
        PartnerModel = self.env['res.partner']
        MeliOrderModel = self.env['mercadolibre.orders']
        partner = PartnerModel.browse()
        notes = []
        send_mail = False
        need_review = False
        meli_order = MeliOrderModel.search([('order_id','=',order_json['id'])], limit=1)
        try:
            order_vals = self._prepare_order_vals(order_json)
            if 'buyer' in order_json:
                Buyer = order_json['buyer']
                document_number =False
                if Buyer['billing_info'].get('doc_number'):
                    document_number = Buyer['billing_info'].get('doc_number')
                    document_number = self._pre_process_document_number(document_number)
                if not document_number:
                    msj = "*Cliente: %s %s con ID: %s no tiene Informacion tributaria(RUT, Tipo de documento)" % \
                        (Buyer.get('first_name'), Buyer.get('last_name'), Buyer.get('id'))
                    notes.append(("ERROR Creando Cliente", msj))
                    need_review = True
                    _logger.error(msj)
                    return meli_order, notes, send_mail
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
                if meli_order.status == 'paid':
                    send_mail = True
            #update internal fields (items, payments, buyers)
            if 'order_items' in order_json:
                notes = []
                need_review = False
                for Item in order_json['order_items']:
                    product_find, variants_names = self._find_product(Item)
                    if not product_find:
                        _logger.error("ERROR Buscando Producto: %s con ID: %s no exist", Item['item']['title'], Item['item']['id'])
                        notes.append(("ERROR Buscando producto", "*Producto: %s con ID: %s no existe" % (Item['item']['title'], Item['item']['id'])))
                        need_review = True
                        continue
                    self._add_order_line(meli_order, Item, product_find, variants_names)
            if 'payments' in order_json:
                for meli_payment_vals in order_json['payments']:
                    self._add_payment(meli_order, meli_payment_vals)
            if meli_order.order_items:
                sale_order, message_list = meli_order._find_create_sale_order()
                notes.extend(message_list)
                meli_order.write({
                    'need_review': need_review,
                    'note': "".join([msj[1] for msj in notes]),
                })
            else:
                meli_order.write({
                    'need_review': need_review,
                    'note': "".join([msj[1] for msj in notes]),
                })
        except Exception, e:
            _logger.error(tools.ustr(e))
            notes.append(("Error descargando Pedido", tools.ustr(e)))
        return meli_order, notes, send_mail

    def orders_update_order( self, context=None ):
        meli_util_model = self.env['meli.util']
        #get with an item id
        order = self
        log_msg = 'orders_update_order: %s' % (order.order_id)
        _logger.info(log_msg)
        meli = meli_util_model.get_new_instance()
        response = meli.get("/orders/"+order.order_id, {'access_token':meli.access_token})
        order_json = response.json()
        if "error" in order_json:
            _logger.error( order_json["error"] )
            _logger.error( order_json["message"] )
        else:
            self.orders_update_order_json( {"id": id, "order_json": order_json } )
        return {}

    def orders_query_iterate(self, total_downloaded=0, offset=0, filter_by="paid"):
        meli_util_model = self.env['meli.util']
        meli_order_sent_by_mail = self.browse()
        meli_days_last_synchro = self.env['ir.config_parameter'].get_param('meli_days_synchro', 5)
        try:
            meli_days_last_synchro = int(meli_days_last_synchro)
        except:
            meli_days_last_synchro = 5
        #solo filtrar las ventas desde los ultimos N dias configurados(5 dias atras por defecto)
        filter_date_from = fields.Date.from_string(fields.Date.context_today(self)) - relativedelta(days=meli_days_last_synchro)
        company = self.env.user.company_id
        meli = meli_util_model.get_new_instance(company)
        message_list = []
        orders_query = "/orders/search"
        params = {
            'access_token': meli.access_token,
            'seller': company.mercadolibre_seller_id,
            'sort': 'date_asc',
            'order.date_created.from': '%sT00:00:00.000-00:00' % (filter_date_from.strftime(DF)),
        }
        if filter_by:
            params['order.status'] = filter_by
        if offset:
            params['offset'] = str(offset).strip()
        response = meli.get(orders_query, params)
        orders_json = response.json()
        if "error" in orders_json:
            _logger.error( orders_json["error"] )
            if (orders_json["message"]=="invalid_token"):
                _logger.error( orders_json["message"] )
            return message_list
        counter = 0
        total = 0
        if "results" in orders_json:
            total_downloaded += len(orders_json["results"])
        if "paging" in orders_json:
            if "total" in orders_json["paging"]:
                counter = offset + 1
                total = orders_json["paging"]["total"]
                if (orders_json["paging"]["total"]==0):
                    return message_list
                else: 
                    if total_downloaded < total:
                        offset += orders_json["paging"]["limit"]
                    else:
                        offset = 0
        if "results" in orders_json:
            for order_json in orders_json["results"]:
                if order_json:
                    _logger.info("Procesando Pedido %s de %s", counter, total)
                    counter += 1
                    pdata = {"id": False, "order_json": order_json}
                    if self._is_order_cancelled(order_json):
                        meli_order, msj = self._action_cancel_order(pdata)
                        message_list.extend(msj)
                    else:
                        meli_order, msj, send_mail = self.orders_update_order_json(pdata)
                        if send_mail and meli_order:
                            meli_order_sent_by_mail |= meli_order 
                        message_list.extend(msj)
        if meli_order_sent_by_mail:
            template_mail = self.env.ref('meli_oerp.et_new_meli_order', False)
            for meli_order in meli_order_sent_by_mail:
                template_mail.send_mail(meli_order.id, force_send=True)
        if (offset>0):
            message_list.extend(self.orders_query_iterate(total_downloaded, offset, filter_by))
        return message_list

    def orders_query_recent(self):
        res = self.orders_query_iterate()
        return res
    
    @api.model
    def _is_order_cancelled(self, order_json):
        #se considera un pedido cancelado cuando:
        #*estado = confirmed y no hay pagos O los pagos esten en estado returned,
        #o el estado sea explicito cancelled, invalid
        is_order_cancelled = False
        if order_json.get('status') in ['cancelled', 'invalid']:
            is_order_cancelled = True
        elif order_json.get('status') == 'confirmed':
            has_payments = False
            has_refund = False
            for payment in order_json.get('payments'):
                if payment.get('status') == 'approved':
                    has_payments = True
                elif payment.get('status') == 'refunded':
                    has_refund = True
            if not has_payments:
                is_order_cancelled = True
            elif has_refund:
                is_order_cancelled = True
        return is_order_cancelled
    
    @api.model
    def _action_cancel_order(self, data):
        order_json = data["order_json"]
        message_list = []
        current_document_info = ""
        meli_order = self.search([
            ('order_id','=',order_json['id']),
            ('status', '!=', 'cancelled'),
            #no traer los q necesitan NC, xq no se cancelan a nivel de estado en el ERP pero estan anulados en meli
            ('need_credit_note', '=', False),
        ], limit=1)
        #puede que un pedido cancelado nunca se haya creado en el sistema
        #crearlo para estadisticas
        if not meli_order:
            current_document_info = "Pedido de MELI: %s esta anulado pero no existe en ERP, se creara para estadisticas" % (order_json['id'])
            _logger.info(current_document_info)
            meli_order, msj, send_mail = self.orders_update_order_json(data)
            message_list.extend(msj)
        if meli_order and meli_order.sale_order_id:
            sale_order = meli_order.sale_order_id
            need_credit_note = False
            sent_mail_cancel = False
            #si el pedido de venta ya esta cancelado, no hacer nada
            #caso contrario, enviar a cancelar el picking y el pedido de venta
            if sale_order.state != 'cancel':
                current_document_info = "Anulando Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                _logger.info(current_document_info)
                #si el pedido de venta ya tiene factura, no cancelar el pedido, se debe hacer nota de credito manualmente
                if sale_order.invoice_ids:
                    need_credit_note = True
                    template_mail = self.env.ref('meli_oerp.et_meli_order_need_cn', False)
                    if template_mail:
                        template_mail.send_mail(meli_order.id, force_send=True)
                    _logger.info("Pedido Facturado, debe emitir Nota de Credito")
                    message_list.append((current_document_info, "Pedido Facturado, debe emitir Nota de Credito"))
                else:
                    try:
                        for picking in sale_order.picking_ids:
                            picking.action_cancel()
                        sale_order.action_cancel()
                        sent_mail_cancel = True
                        _logger.info("Cancelado con exito el Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name))
                    except Exception, e:
                        _logger.error(current_document_info)
                        _logger.error(tools.ustr(e))
                        message_list.append((current_document_info, tools.ustr(e)))
            if meli_order.status != 'cancelled':
                current_document_info = "Anulando Pedido de Venta MELI ID: %s Numero: %s" % (meli_order.id, meli_order.order_id)
                _logger.info(current_document_info)
                try:
                    #actualizar los pagos para q se marquen como rechazado/devueltos, etc
                    for payment in order_json.get('payments'):
                        self._add_payment(meli_order, payment)
                    if need_credit_note:
                        meli_order.write({'need_credit_note': need_credit_note})
                    else:
                        meli_order.write({'status': 'cancelled'})
                        sent_mail_cancel = True
                    _logger.info("Cancelado con exito el Pedido de Venta MELI ID: %s Numero: %s" % (meli_order.id, meli_order.order_id))
                except Exception, e:
                    _logger.error(current_document_info)
                    _logger.error(tools.ustr(e))
                    message_list.append((current_document_info, tools.ustr(e)))
            if sent_mail_cancel:
                template_mail = self.env.ref('meli_oerp.et_meli_order_cancelled', False)
                if template_mail:
                    template_mail.send_mail(meli_order.id, force_send=True)
        return meli_order, message_list
    
    @api.model
    def action_cancel_orders(self):
        #ordenes en estado confirmed sin pagos aprobados meli las considera canceladas
        message_list = self.orders_query_iterate(filter_by='confirmed')
        message_list.extend(self.orders_query_iterate(filter_by='cancelled'))
        message_list.extend(self.orders_query_iterate(filter_by='invalid'))
        if message_list and csv:
            file_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            if not os.path.exists(file_path):
                os.makedirs(file_path)
            file_path = os.path.join(file_path, "cancelar_pedidos_meli_%s.csv" % fields.Datetime.context_timestamp(self, datetime.now()).strftime('%Y_%m_%d_%H_%M_%S'))
            fp = open(file_path,'wb')
            csv_file = csv.writer(fp, quotechar='"', quoting=csv.QUOTE_ALL)
            csv_file.writerow(['Mensaje', 'Detalle'])
            for line in message_list:
                csv_file.writerow([line[0], line[1]])
            fp.close()
        return True
        
    @api.multi
    def action_print_tag_delivery(self):
        wizard_model = self.env['wizard.print.tag.delivery']
        wizard = wizard_model.create({'meli_order_ids': [(6, 0, self.ids)]})
        self.write({'shipping_substatus': 'printed'})
        if len(self.ids) > 1:
            file_name = "Etiquetas de Envio %s.pdf" % (fields.Datetime.to_string(fields.Datetime.context_timestamp(self, datetime.now())))
        else:
            file_name = "Etiqueta de Envio %s.pdf" % (self.shipping_id)
        return {'type': 'ir.actions.act_url',
                'url': '/download/saveas?model=%(model)s&record_id=%(record_id)s&method=%(method)s&filename=%(filename)s' % {
                    'filename': file_name,
                    'model': wizard_model._name,
                    'record_id': wizard.id,
                    'method': 'get_tag_delivery_pdf',
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
            'payment_date': self.date_closed,
        }
        return payment_vals
    
    @api.multi
    def _get_next_warehouse_to_order(self, warehouse):
        """
        Devolver el siguiente almacen disponible para meli
        segun el orden de prioridad de meli configurada en cada almacen
        """
        return self.env['stock.warehouse'].search([
            ('meli_published', '=', True),
            ('company_id','=', warehouse.company_id.id),
            ('meli_sequence', '>', warehouse.meli_sequence),
            ('id', '!=', warehouse.id),
            ], order="meli_sequence", limit=1)
        
    @api.multi
    def _get_warehouse_to_order(self, sale_order):
        """
        Cuando hay multiples almacenes de los cuales se envia el stock a meli
        debemos ir dando de baja al stock segun se va vendiendo en meli,
        pero respetando un orden de tiendas, es decir
        primero dar de baja a todo el stock de una tienda, luego que no hay stock en esa tienda
        dar de baja a la siguiente tienda(segun el orden de las tiendas)
        Es un algoritmo que se puede mejorar si MELI pasara el ID de la tienda de la cual se esta vendiendo
        pero no existe ese dato en meli
        por ello tendremos que asumir la tienda mediante prioridades
        y basandonos en una regla de meli que un pedido de venta SIEMPRE es por 1 producto
        nunca va a haber mas de 1 producto en el carrito de compras de meli
        """
        ProductModel = self.env['product.product']
        new_warehouse = sale_order.warehouse_id
        next_warehouse = sale_order.warehouse_id
        lines_to_check = sale_order.order_line.filtered(lambda x: x.product_id and x.product_id.type in ('product', 'consu'))
        for line in lines_to_check:
            while next_warehouse:
                product = ProductModel.with_context(warehouse=next_warehouse.id).browse(line.product_id.id)
                if product.qty_available <= 0:
                    next_warehouse = self._get_next_warehouse_to_order(next_warehouse)
                else:
                    new_warehouse = next_warehouse
                    break
        return new_warehouse
        
    @api.model
    def action_validate_sale_order(self):
        PaymentModel = self.env['account.payment']
        meli_days_last_synchro = self.env['ir.config_parameter'].get_param('meli_days_synchro', 5)
        try:
            meli_days_last_synchro = int(meli_days_last_synchro)
        except:
            meli_days_last_synchro = 5
        #solo filtrar las ventas desde los ultimos N dias configurados(5 dias atras por defecto)
        filter_date_from = fields.Date.from_string(fields.Date.context_today(self)) - relativedelta(days=meli_days_last_synchro)
        limit_meli = int(self.env['ir.config_parameter'].get_param('meli.order.limit', '100').strip())
        meli_orders = self.search([
            ('status','=', 'paid'),
            ('shipping_status','=', 'ready_to_ship'),
            ('shipping_substatus','=', 'printed'),
            ('date_created', '>=', filter_date_from.strftime(DF)),
        ], limit=limit_meli)
        message_list = []
        current_document_info = ""
        for meli_order in meli_orders:
            current_document_info = ""
            try:
                #si por alguna razon no se crearon lineas(xq el ID de Meli no existe en el producto)
                #y no hay lineas, no hacer nada
                if not meli_order.order_items:
                    continue
                #en caso de no tener pedido de venta, crearlo
                sale_order = meli_order.sale_order_id
                if not sale_order:
                    sale_order, message_list_so = meli_order._find_create_sale_order()
                    message_list.extend(message_list_so)
                #cuando el pedido de venta es cancelado en MELI
                #el estado del pago sera refunded
                #asi que esas no validarlas, y en su lugar cancelarlas
                #tambien existen pedidos con un pago cancelado y uno aprobado
                #esos pedidos deben validarse, xq x alguna razon se anulo el primer pago
                #pero el siguiente pago se realizo
                if not meli_order.payments.filtered(lambda x: x.status == 'approved'):
                    current_document_info = "Anulando Pedido de Venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                    message_list.append((current_document_info, ""))
                    _logger.info(current_document_info)
                    sale_order.action_cancel()
                    meli_order.write({'status': 'cancelled'})
                    continue
                #crear y validar factura
                if not sale_order.invoice_ids and sale_order.state not in ('draft', 'cancel'):
                    current_document_info = "Creando factura para Pedido de venta ID: %s Numero: %s" % (sale_order.id, sale_order.name)
                    _logger.info(current_document_info)
                    sale_order.action_invoice_create()
                for invoice in sale_order.invoice_ids.filtered(lambda x: x.state not in ('paid', 'cancel')):
                    if invoice.state == 'draft':
                        current_document_info = "Confirmando la factura ID: %s Numero: %s" % (invoice.id, invoice.display_name)
                        _logger.info(current_document_info)
                        invoice.action_invoice_open()
                    if invoice.state == 'open': 
                        #marcar la factura como pagada
                        current_document_info = "Pagando la factura ID: %s Numero: %s" % (invoice.id, invoice.display_name)
                        _logger.info(current_document_info)
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
    
    @api.multi
    def get_signup_url_meli(self):
        self.ensure_one()
        return self.partner_id.with_context(signup_valid=True, signup_force_type_in_url='login')._get_signup_url_for_action(
            action=self.env.ref('meli_oerp.action_meli_orders_tree').id,
            model=self._name,
            view_type='tree')[self.partner_id.id]

class MercadolibreOrderItems(models.Model):
    
    _name = "mercadolibre.order_items"
    _description = "Producto pedido en MercadoLibre"

    order_id = fields.Many2one("mercadolibre.orders","Order", ondelete="cascade")
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

    order_id = fields.Many2one("mercadolibre.orders","Order", ondelete="cascade")
    payment_id = fields.Char('Payment Id')
    transaction_amount = fields.Char('Transaction Amount')
    currency_id = fields.Char(string='Currency')
    status = fields.Char(string='Payment Status')
    date_created = fields.Datetime('Creation date')
    date_last_modified = fields.Datetime('Modification date')

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
