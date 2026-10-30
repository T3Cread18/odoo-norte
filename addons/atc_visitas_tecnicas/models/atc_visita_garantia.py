from odoo import api, fields, models

RESULTADOS = [("abierta", "Abierta"),
              ("atendida", "Atendida"),
              ("recuperada", "Cliente recuperado (cierre automático)"),
              ("cambio_estado", "Salió de garantía sin atenderla")]


class AtcVisitaGarantia(models.Model):
    """Una fila por cada vez que una instalación pasa a 'Visita por garantía'.
    La orden borra garantia_desde/motivo al salir de garantía: aquí queda el
    historial. Lo crean y cierran los hooks de atc.visita (create/write)."""
    _name = "atc.visita.garantia"
    _description = "Historial de visitas por garantía"
    _order = "fecha_inicio desc, id desc"
    _rec_name = "visita_id"

    visita_id = fields.Many2one(
        "atc.visita", string="Instalación", required=True,
        ondelete="cascade", index=True)
    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista", index=True,
        help="Contratista de la instalación cuando se abrió la garantía.")
    nombre = fields.Char(related="visita_id.nombre", string="Cliente")
    cedula = fields.Char(related="visita_id.cedula", string="Cédula")
    fecha_instalacion = fields.Date(
        related="visita_id.fecha_instalacion", string="Instalada el")
    fecha_inicio = fields.Datetime(
        string="Abierta el", required=True, default=fields.Datetime.now)
    motivo = fields.Char(string="Motivo")
    automatica = fields.Boolean(
        string="Automática", help="La abrió el sistema (ruptura de la ONU).")
    fecha_cierre = fields.Datetime(string="Cerrada el")
    cerrada_por_id = fields.Many2one("res.users", string="Cerrada por")
    resultado = fields.Selection(
        RESULTADOS, string="Resultado", default="abierta", required=True,
        index=True)
    duracion_horas = fields.Float(
        string="Duración (h)", digits=(10, 1),
        compute="_compute_duracion_horas", store=True)

    @api.depends("fecha_inicio", "fecha_cierre")
    def _compute_duracion_horas(self):
        for g in self:
            g.duracion_horas = (g.fecha_cierre - g.fecha_inicio).total_seconds() / 3600 \
                if g.fecha_inicio and g.fecha_cierre else 0.0
