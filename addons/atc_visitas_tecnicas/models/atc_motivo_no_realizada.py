from odoo import fields, models


class AtcMotivoNoRealizada(models.Model):
    _name = "atc.motivo.no.realizada"
    _description = "Motivo por el que una orden no se realizó"
    _order = "sequence, name"

    name = fields.Char(string="Motivo", required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string="Color")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "unique(name)", "Ya existe un motivo con ese nombre.")
