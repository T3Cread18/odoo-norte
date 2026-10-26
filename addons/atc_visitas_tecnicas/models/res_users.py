from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    atc_franquicia_ids = fields.Many2many(
        "atc.franquicia", "atc_franquicia_res_users_rel", "user_id", "franquicia_id",
        string="Franquicias ATC",
        help="Franquicias cuyas órdenes ATC puede ver este usuario (rol ATC). "
             "Vacío = todas. Los NOC Responsable ven siempre todas.")

    def write(self, vals):
        res = super().write(vals)
        if "atc_franquicia_ids" in vals:
            # las reglas (ir.rule) cachean su dominio por usuario: sin esto el cambio
            # no se aplicaría hasta reiniciar Odoo
            self.env.registry.clear_cache()
        return res
