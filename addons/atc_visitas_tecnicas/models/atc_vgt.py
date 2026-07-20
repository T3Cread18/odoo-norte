from odoo import api, fields, models


class AtcVgt(models.Model):
    _name = "atc.vgt"
    _description = "Proyecto VGT autorizado"
    _order = "codigo"
    _rec_name = "codigo"

    codigo = fields.Char(string="Código VGT", required=True, index=True)
    nombre = fields.Char(string="Nombre del proyecto")
    estado = fields.Char(string="Estado")
    municipio = fields.Char(string="Municipio")
    region = fields.Selection(
        selection=[("andes", "ANDES"),
                   ("general", "GENERAL NACIONAL")],
        string="Región")
    cantidad_postes = fields.Integer(string="Postes supervisados")
    fecha_autorizacion = fields.Date(string="Fecha de autorización")
    zona_ids = fields.Many2many(
        "atc.zona", "atc_zona_vgt_rel", "vgt_id", "zona_id",
        string="Zonas",
        help="Zonas ATC que cubre este proyecto VGT.")
    active = fields.Boolean(default=True)

    _codigo_uniq = models.Constraint(
        "unique(codigo)",
        "Ya existe una VGT con ese código.")

    @api.depends("codigo", "nombre")
    def _compute_display_name(self):
        for v in self:
            if v.codigo and v.nombre:
                v.display_name = "%s — %s" % (v.codigo, v.nombre)
            else:
                v.display_name = v.codigo or v.nombre or ""
