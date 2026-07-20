from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AtcVisita(models.Model):
    _name = "atc.visita"
    _description = "Orden ATC (Visita / Instalación)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha desc, id desc"

    name = fields.Char(
        string="Referencia", compute="_compute_name", store=True,
        readonly=False)
    tipo_orden = fields.Selection(
        selection=[("visita", "Visita Técnica"),
                   ("instalacion", "Instalación")],
        string="Tipo de orden", default="visita", required=True,
        index=True, tracking=True)
    cedula = fields.Char(string="Cédula", tracking=True)
    nombre = fields.Char(string="Nombre del cliente", tracking=True)
    cliente_id = fields.Many2one(
        "res.partner", string="Cliente ISP", index=True, tracking=True)
    zona_id = fields.Many2one(
        "atc.zona", string="Zona", index=True, tracking=True)
    tag_ids = fields.Many2many("atc.visita.tag", string="Etiquetas")
    direccion = fields.Char(string="Dirección de la visita", tracking=True)
    descripcion = fields.Html(string="Descripción")
    fecha = fields.Date(
        string="Fecha de la visita", default=fields.Date.context_today,
        tracking=True)
    estado = fields.Selection(
        selection=[("pendiente", "Pendiente"),
                   ("asignada", "Asignada"),
                   ("realizada", "Realizada")],
        string="Estado", default="pendiente", index=True,
        tracking=True, group_expand=True)
    tecnico_asignado_ids = fields.Many2many(
        "hr.employee", "atc_visita_tecnico_rel", "visita_id", "employee_id",
        string="Asignado a", tracking=True,
        help="Técnicos (empleados) asignados a la orden. Puede ser más de uno.")
    vehiculo_id = fields.Many2one(
        "fleet.vehicle", string="Vehículo utilizado", tracking=True,
        help="Vehículo usado para la orden.")
    tecnico_id = fields.Many2one(
        "res.users", string="Atendido por",
        default=lambda self: self.env.user, tracking=True,
        help="Usuario que efectivamente atendió la orden.")
    active = fields.Boolean(default=True)

    @api.depends("nombre", "cliente_id", "fecha", "tipo_orden")
    def _compute_name(self):
        for v in self:
            if v.name:
                continue
            etiqueta = "Instalación" if v.tipo_orden == "instalacion" else "Visita"
            base = v.nombre or (v.cliente_id.name if v.cliente_id else etiqueta)
            v.name = "%s — %s" % (base, v.fecha) if v.fecha else base

    @api.constrains("estado", "tecnico_asignado_ids")
    def _check_asignada_tecnico(self):
        for v in self:
            if v.estado == "asignada" and not v.tecnico_asignado_ids:
                raise ValidationError(self.env._(
                    "No puedes pasar la orden a 'Asignada' sin al menos un "
                    "técnico en 'Asignado a'. Usa el botón 'Asignar técnico'."))

    # --------------------------------------------------------------
    # Autocompletado cliente <-> cédula / nombre
    # --------------------------------------------------------------
    @api.onchange("cedula")
    def _onchange_cedula(self):
        cedula = (self.cedula or "").strip()
        if cedula:
            partner = self.env["res.partner"].search(
                [("cedula", "=", cedula)], limit=1)
            if partner:
                self.cliente_id = partner
                self.nombre = partner.name
            else:
                self.cliente_id = False

    @api.onchange("nombre")
    def _onchange_nombre(self):
        nombre = (self.nombre or "").strip()
        if not nombre:
            return
        partner = self.env["res.partner"].search(
            [("name", "=", nombre)], limit=1)
        if partner:
            self.cliente_id = partner
        elif not self.cedula:
            self.cliente_id = False

    @api.onchange("cliente_id")
    def _onchange_cliente_id(self):
        if self.cliente_id:
            self.cedula = self.cliente_id.cedula
            self.nombre = self.cliente_id.name

    def _resolve_partner(self, vals, current=None):
        if vals.get("cliente_id"):
            return
        cedula = (vals.get("cedula") or "").strip()
        nombre = (vals.get("nombre")
                  or (current and current.nombre) or "").strip()
        if not cedula and not nombre:
            return
        Partner = self.env["res.partner"].sudo()
        partner = False
        if cedula:
            partner = Partner.search([("cedula", "=", cedula)], limit=1)
        if not partner and nombre:
            partner = Partner.search([("name", "=", nombre)], limit=1)
        if not partner:
            if not nombre:
                return
            partner = Partner.create(
                {"name": nombre, "cedula": cedula or False})
        vals["cliente_id"] = partner.id
        if not vals.get("nombre"):
            vals["nombre"] = partner.name
        if not vals.get("cedula") and partner.cedula:
            vals["cedula"] = partner.cedula

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._resolve_partner(vals)
        return super().create(vals_list)

    def write(self, vals):
        if (vals.get("cedula") or vals.get("nombre")) \
                and not vals.get("cliente_id") and len(self) == 1 \
                and not self.cliente_id:
            self._resolve_partner(vals, current=self)
        return super().write(vals)

    # --------------------------------------------------------------
    # Asignación de técnico (abre el wizard)
    # --------------------------------------------------------------
    def action_abrir_asignar(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Asignar técnico"),
            "res_model": "atc.visita.asignar",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visita_id": self.id,
                "default_tecnico_asignado_ids": [
                    (6, 0, self.tecnico_asignado_ids.ids)],
                "default_vehiculo_id": self.vehiculo_id.id,
            },
        }

    # --------------------------------------------------------------
    # Botones de estado
    # --------------------------------------------------------------
    def action_marcar_realizada(self):
        self.write({"estado": "realizada"})

    def action_marcar_pendiente(self):
        self.write({"estado": "pendiente"})
