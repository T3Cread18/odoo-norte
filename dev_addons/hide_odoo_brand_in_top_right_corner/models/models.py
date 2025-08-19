# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class hide_odoo_brand_in_top_right_corner(models.Model):
#     _name = 'hide_odoo_brand_in_top_right_corner.hide_odoo_brand_in_top_right_corner'
#     _description = 'hide_odoo_brand_in_top_right_corner.hide_odoo_brand_in_top_right_corner'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
