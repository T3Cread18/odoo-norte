from odoo import api, fields, models

ESTADOS_ABIERTOS = ("pendiente", "asignada")


class AtcContratista(models.Model):
    _name = "atc.contratista"
    _description = "Contratista de instalaciones"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(
        string="Contratista", required=True, tracking=True,
        help="Nombre tal como aparece en la columna TECNICO del reporte de "
             "órdenes pendientes (se usa para enlazar al importar).")
    rif = fields.Char(string="RIF / Cédula", tracking=True)
    telefono = fields.Char(string="Teléfono", tracking=True)
    email = fields.Char(string="Correo", tracking=True)
    user_ids = fields.Many2many(
        "res.users", "atc_contratista_user_rel", "contratista_id", "user_id",
        string="Usuarios de portal",
        domain=[("share", "=", True)],
        help="Usuarios de portal que ven y actualizan las instalaciones "
             "de este contratista en /my/instalaciones.")
    instalacion_ids = fields.One2many(
        "atc.visita", "contratista_id", string="Instalaciones")
    pendientes_count = fields.Integer(
        string="Abiertas", compute="_compute_contadores")
    vencidas_count = fields.Integer(
        string="Con más de 7 días", compute="_compute_contadores")
    realizadas_count = fields.Integer(
        string="Realizadas", compute="_compute_contadores")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "unique(name)", "Ya existe un contratista con ese nombre.")

    @api.depends("instalacion_ids.estado", "instalacion_ids.fecha_asignacion")
    def _compute_contadores(self):
        limite = fields.Date.add(fields.Date.context_today(self), days=-7)
        for c in self:
            abiertas = c.instalacion_ids.filtered(
                lambda v: v.estado in ESTADOS_ABIERTOS)
            c.pendientes_count = len(abiertas)
            c.vencidas_count = len(abiertas.filtered(
                lambda v: v.fecha_asignacion and v.fecha_asignacion < limite))
            c.realizadas_count = len(c.instalacion_ids.filtered(
                lambda v: v.estado == "realizada"))

    def action_ver_instalaciones(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "atc_visitas_tecnicas.action_atc_instalacion")
        action["domain"] = [("tipo_orden", "=", "instalacion"),
                            ("contratista_id", "=", self.id)]
        action["context"] = {"default_tipo_orden": "instalacion",
                             "default_contratista_id": self.id}
        return action


class AtcTipoServicio(models.Model):
    _name = "atc.tipo.servicio"
    _description = "Tipo de servicio a instalar"
    _order = "name"

    name = fields.Char(string="Tipo de servicio", required=True)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "unique(name)", "Ya existe un tipo de servicio con ese nombre.")
