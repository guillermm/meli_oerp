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

from odoo import fields, osv, models

#https://api.mercadolibre.com/questions/search?item_id=MLA508223205

class MercadolibreQuestions(models.Model):
	
	_name = "mercadolibre.questions"
	_description = "Preguntas en MercadoLibre"
	_rec_name = 'question_id'

	posting_id = fields.Many2one("mercadolibre.posting","Posting")
	question_id = fields.Char('Question Id')
	date_created = fields.Datetime('Creation date')
	item_id = fields.Char(string="Item ID",size=255)
	seller_id = fields.Char(string="Seller ID",size=255)
	text = fields.Text("Question Text")
	status = fields.Selection([
		("UNANSWERED","Question is not answered yet."),
		("ANSWERED","Question was answered."),
		("CLOSED_UNANSWERED","The item is closed and the question was never answered."),
		("UNDER_REVIEW","The item is under review and the question too."),
		("BANNED","The item was banned")
		], string='Question Status')
	answer_date_created = fields.Datetime('Answer creation date')
	answer_status = fields.Selection([
		("ACTIVE","Active"),
		("DISABLED","Disabled"),
		("BANNED","Banned")
		], string='Answer Status')
	answer_text = fields.Text("Answer Text")
