# -*- coding: utf-8 -*-
##############################################################################
#
#       Pere Ramon Erro Mas <pereerro@tecnoba.com> All Rights Reserved.
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'MercadoLibre Publisher',
    'version': '0.1',
    'author': 'Moldeo Interactive',
    'website': 'http://business.moldeo.coop',
    "category": "Sales",
    "depends": [
        'base', 
        'product',
        'sale',
        'stock',
        'website_sale',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/parameters_data.xml',
        'data/cron_jobs.xml',
        'data/email_template_data.xml',
        'data/action_server_data.xml',
        'wizard/wizard_set_products_campaign_view.xml',
        'views/company_view.xml',
        'views/posting_view.xml',
        'views/product_post.xml',
        'views/product_attribute_view.xml',
        'views/product_image_view.xml',
        'views/product_view.xml',	
        'views/stock_warehouse_view.xml',
        'views/category_view.xml',
        'views/banner_view.xml',
        'views/warning_view.xml',
        'views/questions_view.xml',
        'views/orders_view.xml',
        'views/meli_campaign_view.xml',
        'views/meli_campaign_record_view.xml',
        'views/sale_order_view.xml',
        'views/res_partner_view.xml',
    ],
    'demo_xml': [],
    'active': False,
    'installable': True,
    'application': True,
}
