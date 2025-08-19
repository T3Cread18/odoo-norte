# -*- coding: utf-8 -*-
# from odoo import http


# class HideOdooBrandInTopRightCorner(http.Controller):
#     @http.route('/hide_odoo_brand_in_top_right_corner/hide_odoo_brand_in_top_right_corner/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hide_odoo_brand_in_top_right_corner/hide_odoo_brand_in_top_right_corner/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('hide_odoo_brand_in_top_right_corner.listing', {
#             'root': '/hide_odoo_brand_in_top_right_corner/hide_odoo_brand_in_top_right_corner',
#             'objects': http.request.env['hide_odoo_brand_in_top_right_corner.hide_odoo_brand_in_top_right_corner'].search([]),
#         })

#     @http.route('/hide_odoo_brand_in_top_right_corner/hide_odoo_brand_in_top_right_corner/objects/<model("hide_odoo_brand_in_top_right_corner.hide_odoo_brand_in_top_right_corner"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hide_odoo_brand_in_top_right_corner.object', {
#             'object': obj
#         })
