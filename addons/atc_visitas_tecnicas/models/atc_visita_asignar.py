from odoo import fields, models
from odoo.exceptions import ValidationError


class AtcVisitaAsignar(models.TransientModel):
    _name = "atc.visita.asignar"
    _description = "Asignar técnicos a la visita"

    visita_id = fields.Many2one(
        "atc.visita", string="Visita", required=True, ondelete="cascade")
    es_instalacion = fields.Boolean()
    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista",
        help="Para instalaciones: contratista externo que la hará.")
    tecnico_asignado_ids = fields.Many2many(
        "hr.employee", string="Asignar a")
    vehiculo_id = fields.Many2one(
        "fleet.vehicle", string="Vehículo utilizado")

    def action_asignar(self):
        self.ensure_one()
        if not self.tecnico_asignado_ids and not self.contratista_id:
            raise ValidationError(self.env._(
                "Selecciona al menos un técnico o un contratista para "
                "asignar la orden."))
        vals = {
            "tecnico_asignado_ids": [(6, 0, self.tecnico_asignado_ids.ids)],
            "vehiculo_id": self.vehiculo_id.id,
            "contratista_id": self.contratista_id.id,
            "estado": "asignada",
        }
        if self.contratista_id and not self.visita_id.fecha_asignacion:
            vals["fecha_asignacion"] = fields.Date.context_today(self)
        self.visita_id.write(vals)
        return {"type": "ir.actions.act_window_close"}
