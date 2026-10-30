from odoo import api, fields, models


def formato_duracion(segundos):
    """'3 d 4 h', '5 h 12 min' o '12 min'."""
    minutos = max(int(segundos // 60), 0)
    dias, minutos = divmod(minutos, 1440)
    horas, minutos = divmod(minutos, 60)
    if dias:
        return "%d d %d h" % (dias, horas)
    if horas:
        return "%d h %d min" % (horas, minutos)
    return "%d min" % minutos


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
    garantia_hasta = fields.Date(
        related="visita_id.garantia_hasta", string="Garantía hasta")
    dias_restantes = fields.Integer(
        string="Días de garantía restantes", compute="_compute_dias_restantes",
        help="Días que le quedan al periodo de garantía de la instalación "
             "(negativo: ya venció).")
    tiempo_abierta = fields.Char(
        string="Tiempo en garantía", compute="_compute_tiempo_abierta",
        help="Cuánto lleva abierta (o cuánto duró, si ya se cerró).")
    # Datos de la orden para la ficha
    estado_orden = fields.Selection(related="visita_id.estado", string="Estado de la orden")
    franquicia_id = fields.Many2one(related="visita_id.franquicia_id")
    direccion = fields.Char(related="visita_id.direccion")
    telefono_movil = fields.Char(related="visita_id.telefono_movil")
    telefono_fijo = fields.Char(related="visita_id.telefono_fijo")
    tipo_servicio_id = fields.Many2one(related="visita_id.tipo_servicio_id")
    tecnico_contratista = fields.Char(related="visita_id.tecnico_contratista")
    serial_onu = fields.Char(related="visita_id.serial_onu")
    precinto = fields.Char(related="visita_id.precinto")
    potencia_rx = fields.Float(related="visita_id.potencia_rx")
    caja_nap = fields.Char(related="visita_id.caja_nap")
    puerto_nap = fields.Char(related="visita_id.puerto_nap")
    cliente_mapa_url = fields.Char(related="visita_id.cliente_mapa_url")
    nap_mapa_url = fields.Char(related="visita_id.nap_mapa_url")
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

    @api.depends("garantia_hasta")
    def _compute_dias_restantes(self):
        hoy = fields.Date.context_today(self)
        for g in self:
            g.dias_restantes = (g.garantia_hasta - hoy).days if g.garantia_hasta else 0

    @api.depends("fecha_inicio", "fecha_cierre")
    def _compute_tiempo_abierta(self):
        ahora = fields.Datetime.now()
        for g in self:
            g.tiempo_abierta = formato_duracion(
                ((g.fecha_cierre or ahora) - g.fecha_inicio).total_seconds()) \
                if g.fecha_inicio else False

    def action_abrir_orden(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "atc.visita",
                "res_id": self.visita_id.id, "view_mode": "form",
                "views": [(self.env.ref("atc_visitas_tecnicas.view_atc_visita_form").id, "form")]}

    @api.depends("fecha_inicio", "fecha_cierre")
    def _compute_duracion_horas(self):
        for g in self:
            g.duracion_horas = (g.fecha_cierre - g.fecha_inicio).total_seconds() / 3600 \
                if g.fecha_inicio and g.fecha_cierre else 0.0
