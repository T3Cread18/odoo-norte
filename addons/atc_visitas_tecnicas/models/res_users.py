from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    atc_franquicia_ids = fields.Many2many(
        "atc.franquicia", "atc_franquicia_res_users_rel", "user_id", "franquicia_id",
        string="Franquicias ATC",
        help="Franquicias cuyas órdenes ATC puede ver este usuario (roles ATC y NOC Usuario). "
             "Un padre incluye todas sus hijas. Vacío = todas. Los NOC Responsable ven siempre todas.")
    atc_franquicia_todas_ids = fields.Many2many(
        "atc.franquicia", string="Franquicias ATC (con hijas)",
        compute="_compute_atc_franquicia_todas_ids", compute_sudo=True,
        help="Las franquicias del usuario más sus hijas. Lo usan las reglas de acceso.")

    @api.depends("atc_franquicia_ids")
    def _compute_atc_franquicia_todas_ids(self):
        Franquicia = self.env["atc.franquicia"].with_context(active_test=False)
        for u in self:
            u.atc_franquicia_todas_ids = Franquicia.search(
                [("id", "child_of", u.atc_franquicia_ids.ids)]) if u.atc_franquicia_ids else False

    def write(self, vals):
        res = super().write(vals)
        if "atc_franquicia_ids" in vals:
            # las reglas (ir.rule) cachean su dominio por usuario: sin esto el cambio
            # no se aplicaría hasta reiniciar Odoo
            self.env.registry.clear_cache()
        return res
