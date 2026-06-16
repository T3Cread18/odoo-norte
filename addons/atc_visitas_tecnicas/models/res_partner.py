from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    cedula = fields.Char(string="Cédula", index=True,
                         help="Cédula de identidad del cliente.")
