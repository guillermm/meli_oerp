# -*- coding: utf-8 -*-

import logging

from odoo import fields, osv, models
from odoo.tools.translate import _
#CHANGE WARNING_MODULE with your module name
WARNING_MODULE = 'meli_oerp'
WARNING_TYPES = [('warning','Warning'),('info','Information'),('error','Error')]

_logger = logging.getLogger(__name__)

class warning(models.TransientModel):
    
    _name = 'warning'
    _description = 'warning'
    _req_name = 'title'
    
    type = fields.Selection(WARNING_TYPES, string='Type', readonly=True)
    title = fields.Char(string="Title", size=100, readonly=True)
    message = fields.Text(string="Message", readonly=True)
    message_html = fields.Html(string="Message HTML", readonly=True)

    def _get_view_id(self ):
        """Get the view id
        @return: view id, or False if no view found
        """
        res = self.env['ir.model.data'].get_object_reference( WARNING_MODULE, 'warning_form')
        return res and res[1] or False

    def _message(self, id):
        #pdb.set_trace()
        message = self.browse( id)
        message_type = [t[1]for t in WARNING_TYPES if message.type == t[0]][0]
        #print '%s: %s' % (_(message_type), _(message.title))
        res = {
            'name': '%s: %s' % (_(message_type), _(message.title)),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': self._get_view_id(),
            'res_model': 'warning',
            'domain': [],
            #'context': context,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': message.id
        }
        return res

    def warning(self, title, message, message_html=''):
        msj_logger = "Mensaje: %s" % message
        if message_html:
            msj_logger += "Mas Informacion: %s" % message_html
        _logger.warn(msj_logger)
        id = self.create( {'title': title, 'message': message, 'message_html': message_html, 'type': 'warning'}).id
        res = self._message( id )
        return res

    def info(self, title, message, message_html=''):
        msj_logger = "Mensaje: %s" % message
        if message_html:
            msj_logger += "Mas Informacion: %s" % message_html
        _logger.info(msj_logger)
        id = self.create( {'title': title, 'message': message, 'message_html': message_html, 'type': 'info'}).id
        res = self._message( id )
        return res

    def error(self, title, message, message_html=''):
        msj_logger = "Mensaje: %s" % message
        if message_html:
            msj_logger += "Mas Informacion: %s" % message_html
        _logger.error(msj_logger)
        id = self.create( {'title': title, 'message': message, 'message_html': message_html, 'type': 'error'}).id
        res = self._message( id)
        return res
