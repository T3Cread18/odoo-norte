from odoo import fields, models


class AtcVisitaTag(models.Model):
    _name = "atc.visita.tag"
    _description = "Etiqueta de Visita Técnica"
    _order = "name"

    name = fields.Char(string="Etiqueta", required=True)
    color = fields.Integer(string="Color")
    active = fields.Boolean(default=True)
