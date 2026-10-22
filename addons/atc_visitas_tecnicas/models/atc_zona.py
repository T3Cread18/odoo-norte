from odoo import api, fields, models


class AtcZona(models.Model):
    _name = "atc.zona"
    _description = "Zona de Visita Técnica"
    _order = "name"

    name = fields.Char(string="Zona", required=True)
    code = fields.Char(string="Código")
    franquicia_id = fields.Many2one(
        "atc.franquicia", string="Franquicia", index=True,
        help="Franquicia (sede) a la que pertenece la zona. Las órdenes de "
             "esta zona toman esta franquicia.")
    vgt_ids = fields.Many2many(
        "atc.vgt", "atc_zona_vgt_rel", "zona_id", "vgt_id",
        string="VGT / Proyectos autorizados",
        help="Proyectos VGT que pertenecen a esta zona.")
    vgt_count = fields.Integer(
        string="N° VGT", compute="_compute_vgt_count")
    active = fields.Boolean(default=True)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("franquicia_id"):
            # Las órdenes de la zona que aún no tienen franquicia la toman
            self.env["atc.visita"].with_context(active_test=False).search([
                ("zona_id", "in", self.ids), ("franquicia_id", "=", False),
            ]).write({"franquicia_id": vals["franquicia_id"]})
        return res

    @api.depends("vgt_ids")
    def _compute_vgt_count(self):
        for z in self:
            z.vgt_count = len(z.vgt_ids)
