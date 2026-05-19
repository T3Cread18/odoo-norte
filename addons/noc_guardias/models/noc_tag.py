from odoo import models, fields


class NocTag(models.Model):
    _name = 'noc.tag'
    _description = 'Etiqueta NOC'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    color = fields.Integer(string='Color', default=0)
