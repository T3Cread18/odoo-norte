from odoo import api, fields, models


class AtcFranquicia(models.Model):
    """Franquicia (sede) de la empresa. Es un nivel por encima de la zona:
    una franquicia agrupa varias zonas. En el reporte del sistema viene en
    la columna FRANQUICIA (ARAURE, ACARIGUA, VILLA ARAURE...)."""
    _name = "atc.franquicia"
    _description = "Franquicia (sede)"
    _order = "name"

    name = fields.Char(string="Franquicia", required=True)
    code = fields.Char(string="Código")
    zona_ids = fields.One2many(
        "atc.zona", "franquicia_id", string="Zonas",
        help="Zonas que atiende esta franquicia.")
    zona_count = fields.Integer(string="N° zonas", compute="_compute_zona_count")
    active = fields.Boolean(default=True)

    _name_unico = models.Constraint(
        "UNIQUE(name)", "Ya existe una franquicia con ese nombre.")

    @api.depends("zona_ids")
    def _compute_zona_count(self):
        for f in self:
            f.zona_count = len(f.zona_ids)
