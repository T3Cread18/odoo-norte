from odoo import fields, models
from odoo.exceptions import ValidationError


class AtcVisitaAsignar(models.TransientModel):
    _name = "atc.visita.asignar"
    _description = "Asignar técnicos a la visita"

    visita_id = fields.Many2one(
        "atc.visita", string="Visita", required=True, ondelete="cascade")
    tecnico_asignado_ids = fields.Many2many(
        "hr.employee", string="Asignar a")
    vehiculo_id = fields.Many2one(
        "fleet.vehicle", string="Vehículo utilizado")

    def action_asignar(self):
        self.ensure_one()
        if not self.tecnico_asignado_ids:
            raise ValidationError(self.env._(
                "Selecciona al menos un técnico para asignar la visita."))
        self.visita_id.write({
            "tecnico_asignado_ids": [(6, 0, self.tecnico_asignado_ids.ids)],
            "vehiculo_id": self.vehiculo_id.id,
            "estado": "asignada",
        })
        return {"type": "ir.actions.act_window_close"}
