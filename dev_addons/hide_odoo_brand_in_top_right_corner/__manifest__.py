# -*- coding: utf-8 -*-
{
    'name': "Hide Odoo Brand In Top Right Corner",
    'summary': """
        Remove *Documentation*, *Support*, *My Odoo.com account* from the top right corner
    """,
    'description': """
        Remove *Documentation*, *Support*, *My Odoo.com account* from the top right corner
    """,
    'author': "DERICK TEMFACK",
    'maintainer': "DERICK TEMFACK",
    'website': "https://temfack.com",
    'category': 'Customizations',
    'version': '14.0.1',
    'depends': ['base'],
    'assets': {
        'web.assets_backend': [
            'hide_odoo_brand_in_top_right_corner/static/src/js/extended_user_menu.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
