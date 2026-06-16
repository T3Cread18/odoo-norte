from odoo import fields, models


class AtcZona(models.Model):
    _name = "atc.zona"
    _description = "Zona de Visita Técnica"
    _order = "name"

    name = fields.Char(string="Zona", required=True)
    code = fields.Char(string="Código")
    active = fields.Boolean(default=True)
