from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AtcFranquicia(models.Model):
    """Franquicia (sede) de la empresa. Igual que en TotalNet hay dos niveles:
    franquicia padre (columna ZONA del reporte, hoy siempre ACARIGUA) y
    franquicias hijas (columna FRANQUICIA: ACARIGUA, ARAURE, OSPINO...).
    Las órdenes y los clientes van a una hija; a un usuario se le pueden dar
    hijas sueltas o el padre (ve todas sus hijas). La hija agrupa varias zonas."""
    _name = "atc.franquicia"
    _description = "Franquicia (sede)"
    _order = "parent_path, name"
    _parent_store = True

    name = fields.Char(string="Franquicia", required=True)
    code = fields.Char(string="Código")
    parent_id = fields.Many2one(
        "atc.franquicia", string="Franquicia padre", index=True, ondelete="restrict",
        help="En TotalNet, la columna ZONA del reporte.")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("atc.franquicia", "parent_id", string="Franquicias hijas")
    zona_ids = fields.One2many(
        "atc.zona", "franquicia_id", string="Zonas",
        help="Zonas que atiende esta franquicia.")
    zona_count = fields.Integer(string="N° zonas", compute="_compute_zona_count")
    active = fields.Boolean(default=True)

    _name_unico = models.Constraint(
        "UNIQUE NULLS NOT DISTINCT(name, parent_id)",
        "Ya existe una franquicia con ese nombre bajo la misma franquicia padre.")

    @api.depends("zona_ids")
    def _compute_zona_count(self):
        for f in self:
            f.zona_count = len(f.zona_ids)

    @api.depends("name", "child_ids")
    def _compute_display_name(self):
        # El padre se llama igual que una hija (ACARIGUA): se distingue en pantalla
        for f in self:
            f.display_name = (self.env._("%s (padre)", f.name)
                              if f.child_ids else f.name)

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if self._has_cycle():
            raise ValidationError(self.env._("Una franquicia no puede ser padre de sí misma."))

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if any(v.get("parent_id") for v in vals_list):
            self.env.registry.clear_cache()   # ver res.users.write
        return res

    def write(self, vals):
        res = super().write(vals)
        if "parent_id" in vals:
            self.env.registry.clear_cache()   # ver res.users.write
        return res

    @api.model
    def _buscar_hija(self, name):
        """Franquicia hija por nombre (sin distinguir mayúsculas). Si no existe
        se crea, colgando del padre si solo hay uno."""
        Franquicia = self.with_context(active_test=False)
        rec = Franquicia.search([("name", "=ilike", name), ("child_ids", "=", False)], limit=1) \
            or Franquicia.search([("name", "=ilike", name)], limit=1)
        if not rec:
            padres = Franquicia.search([("child_ids", "!=", False), ("parent_id", "=", False)])
            rec = Franquicia.create({"name": name,
                                     "parent_id": padres.id if len(padres) == 1 else False})
        elif not rec.active:
            rec.active = True
        return rec
