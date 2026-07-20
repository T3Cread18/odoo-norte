from odoo import api, fields, models


class AtcZona(models.Model):
    _name = "atc.zona"
    _description = "Zona de Visita Técnica"
    _order = "name"

    name = fields.Char(string="Zona", required=True)
    code = fields.Char(string="Código")
    vgt_ids = fields.Many2many(
        "atc.vgt", "atc_zona_vgt_rel", "zona_id", "vgt_id",
        string="VGT / Proyectos autorizados",
        help="Proyectos VGT que pertenecen a esta zona.")
    vgt_count = fields.Integer(
        string="N° VGT", compute="_compute_vgt_count")
    active = fields.Boolean(default=True)

    @api.depends("vgt_ids")
    def _compute_vgt_count(self):
        for z in self:
            z.vgt_count = len(z.vgt_ids)
