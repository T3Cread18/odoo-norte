# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Comiciones(CRM)',
    'version': '1.3',
    
    'description': """
    Esta aplicacion trata de las comiciones de los vendedores en el modulo de CRM entre otros detalles de configuracion
""",
    'depends': ['base','sale','crm', 'web'],

    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/order_view.xml',
        'views/crm_lead.xml',
        'views/accounts_payable_crm.xml',
        'views/account_payment_commission.xml',
       # 'views/account_all.xml',

      
    ],
    'assets': {
        'web.assets_backend': [
            'crm_commissions/static/src/js/*',
        ],
    },

}
