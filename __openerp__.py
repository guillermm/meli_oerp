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
    ],
    'data': [
	'views/company_view.xml',
	'views/posting_view.xml',
    'views/product_post.xml',
    'views/product_attribute_view.xml',
    'views/product_view.xml',	
	'views/category_view.xml',
	'views/banner_view.xml',
    'views/warning_view.xml',
    'views/questions_view.xml',
    'views/orders_view.xml',
    ],
    'demo_xml': [],
    'active': False,
    'installable': True,
    'application': True,
}
