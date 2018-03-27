# -*- coding: utf-8 -*-

from odoo import fields, osv, models, api
import odoo.addons.decimal_precision as dp

class SaleOrder(models.Model):
    
    _inherit = "sale.order"

    meli_order_id = fields.Many2one('mercadolibre.orders', u'Meli Order Id', 
        copy=False, readonly=True)
    meli_status = fields.Selection( [
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

    meli_status_detail = fields.Text(string='Status detail, in case the order was cancelled.')
    meli_date_created = fields.Date('Creation date')
    meli_date_closed = fields.Date('Closing date')

#        'meli_order_items': fields.one2many('mercadolibre.order_items','order_id','Order Items' ),
#        'meli_payments': fields.one2many('mercadolibre.payments','order_id','Payments' ),
    meli_shipping = fields.Text(string="Shipping")
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
    meli_total_amount = fields.Char(string='Total amount')
    meli_currency_id = fields.Char(string='Currency')
#        'buyer': fields.many2one( "mercadolibre.buyers","Buyer"),
#       'meli_seller': fields.text( string='Seller' ),

class SaleOrderLine(models.Model):
    
    _inherit = "sale.order.line"

    meli_order_item_id = fields.Char('Meli Order Item Id')