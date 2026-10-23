from odoo import api, fields, models

ESTADOS_EN_PROCESO = ("pendiente", "asignada")


class AtcVendedor(models.Model):
    _name = "atc.vendedor"
    _description = "Vendedor (ventas de instalaciones)"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(
        string="Vendedor", required=True, tracking=True,
        help="Nombre tal como aparece en la columna VENDEDOR del reporte de "
             "órdenes (se usa para enlazar al importar).")
    cedula = fields.Char(string="Cédula / RIF", tracking=True)
    telefono = fields.Char(string="Teléfono", tracking=True)
    email = fields.Char(string="Correo", tracking=True)
    user_ids = fields.Many2many(
        "res.users", "atc_vendedor_user_rel", "vendedor_id", "user_id",
        string="Usuarios de portal",
        domain=[("share", "=", True)],
        help="Usuarios de portal que ven el estado de las ventas de este "
             "vendedor en /my/ventas (solo lectura).")
    venta_ids = fields.One2many(
        "atc.visita", "vendedor_id", string="Ventas")
    en_proceso_count = fields.Integer(
        string="En proceso", compute="_compute_contadores")
    realizadas_count = fields.Integer(
        string="Instaladas", compute="_compute_contadores")
    no_realizadas_count = fields.Integer(
        string="No instaladas", compute="_compute_contadores")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        "unique(name)", "Ya existe un vendedor con ese nombre.")

    @api.depends("venta_ids.estado")
    def _compute_contadores(self):
        for v in self:
            estados = v.venta_ids.mapped("estado")
            v.en_proceso_count = sum(e in ESTADOS_EN_PROCESO for e in estados)
            v.realizadas_count = sum(
                e in ("realizada", "garantia") for e in estados)
            v.no_realizadas_count = estados.count("no_realizada")

    def action_ver_ventas(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "atc_visitas_tecnicas.action_atc_instalacion")
        action["domain"] = [("tipo_orden", "=", "instalacion"),
                            ("vendedor_id", "=", self.id)]
        action["context"] = {"default_tipo_orden": "instalacion",
                             "default_vendedor_id": self.id}
        return action
