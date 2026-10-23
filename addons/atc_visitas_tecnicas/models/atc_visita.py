from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .ubicacion import url_mapa

# Estados que solo tienen sentido en instalaciones (se ocultan del kanban de
# visitas) y estados que solo tienen sentido en visitas (se ocultan del de
# instalaciones; 'en_los' lo añade noc_onu_los).
ESTADOS_SOLO_INSTALACION = ("no_realizada", "garantia")
# Estados en los que el contratista tiene trabajo pendiente (portal "Por hacer")
ESTADOS_ABIERTOS_PORTAL = ("pendiente", "asignada", "garantia")
# Días de garantía de una instalación desde su fecha de instalación
PARAM_GARANTIA_DIAS = "atc_visitas_tecnicas.garantia_dias"
# Obligatorios para cerrar una instalación como realizada
CAMPOS_REALIZADA = ("serial_onu", "tecnico_contratista", "precinto")
ESTADOS_SOLO_VISITA = ("en_los",)

# Campos que el contratista puede actualizar desde el portal.
CAMPOS_PORTAL = (
    "fecha_programada", "fecha_instalacion", "tecnico_contratista",
    "serial_onu", "precinto", "potencia_rx", "caja_nap", "puerto_nap",
    "metros_fibra", "observaciones_contratista", "motivo_no_realizada_ids",
    "cliente_latitud", "cliente_longitud", "nap_latitud", "nap_longitud",
)


class AtcVisita(models.Model):
    _name = "atc.visita"
    _description = "Orden ATC (Visita / Instalación)"
    _inherit = ["portal.mixin", "mail.thread", "mail.activity.mixin"]
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
    franquicia_id = fields.Many2one(
        "atc.franquicia", string="Franquicia", index=True, tracking=True,
        compute="_compute_franquicia_id", store=True, readonly=False,
        precompute=True,
        help="Franquicia (sede) de la orden. Si la zona pertenece a una "
             "franquicia se toma de ahí; si no, viene del reporte importado.")
    zona_id = fields.Many2one(
        "atc.zona", string="Zona", index=True, tracking=True)
    vgt_id = fields.Many2one(
        "atc.vgt", string="VGT / Proyecto autorizado", index=True,
        tracking=True,
        help="Proyecto VGT autorizado asociado a esta orden. Puedes elegir "
             "cualquier VGT; si aún no está enlazada a una zona, se enlazará "
             "automáticamente a la zona de esta orden al guardar.")
    vgt_zona_ids = fields.Many2many(
        "atc.zona", related="vgt_id.zona_ids", string="Zonas de la VGT")
    tag_ids = fields.Many2many("atc.visita.tag", string="Etiquetas")
    direccion = fields.Char(string="Dirección de la visita", tracking=True)
    descripcion = fields.Html(string="Descripción")
    fecha = fields.Date(
        string="Fecha de la visita", default=fields.Date.context_today,
        tracking=True)
    estado = fields.Selection(
        selection=[("pendiente", "Pendiente"),
                   ("asignada", "Asignada"),
                   ("garantia", "Visita por garantía"),
                   ("realizada", "Realizada"),
                   ("no_realizada", "No realizada")],
        string="Estado", default="pendiente", index=True,
        tracking=True, group_expand="_group_expand_estado")
    garantia_hasta = fields.Date(
        string="Garantía hasta", compute="_compute_garantia_hasta",
        help="Fin de la garantía de la instalación (fecha de instalación + "
             "días de garantía).")
    garantia_desde = fields.Datetime(
        string="En garantía desde", copy=False,
        help="Cuándo la instalación pasó a 'Visita por garantía'.")
    garantia_motivo = fields.Char(string="Motivo de la garantía", copy=False)
    garantia_automatica = fields.Boolean(
        copy=False,
        help="La puso en garantía el sistema (ruptura de la ONU): se cierra "
             "sola si el cliente se recupera.")
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

    # --------------------------------------------------------------
    # Instalaciones por contratista
    # --------------------------------------------------------------
    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista", index=True, tracking=True,
        help="Contratista externo responsable de la instalación. Sus "
             "usuarios de portal la ven y la actualizan en /my/instalaciones.")
    vendedor_id = fields.Many2one(
        "atc.vendedor", string="Vendedor", index=True, tracking=True,
        help="Vendedor que hizo la venta (columna VENDEDOR del reporte). Sus "
             "usuarios de portal siguen el estado en /my/ventas.")
    tipo_servicio_id = fields.Many2one(
        "atc.tipo.servicio", string="Tipo de servicio", tracking=True)
    telefono_movil = fields.Char(string="Teléfono móvil")
    telefono_fijo = fields.Char(string="Teléfono fijo")
    fecha_asignacion = fields.Date(
        string="Fecha de asignación", index=True, tracking=True,
        help="Día en que la instalación se entregó al contratista. "
             "La antigüedad se cuenta desde aquí.")
    fecha_programada = fields.Date(
        string="Fecha programada", tracking=True,
        help="Fecha en que el contratista acordó con el cliente ir a instalar.")
    fecha_instalacion = fields.Date(
        string="Fecha de instalación", tracking=True)
    dias_pendiente = fields.Integer(
        string="Antigüedad (días)", compute="_compute_dias_pendiente",
        help="Días desde la asignación hasta hoy, o hasta la fecha de "
             "instalación si ya se cerró.")
    dias_instalacion = fields.Integer(
        string="Días para instalar", compute="_compute_dias_instalacion",
        store=True, aggregator="avg",
        help="Días que tardó el contratista desde la asignación hasta la "
             "instalación (solo órdenes realizadas).")
    tecnico_contratista = fields.Char(
        string="Técnico del contratista", tracking=True,
        help="Nombre del técnico de la contratista que hizo el trabajo.")
    serial_onu = fields.Char(string="Serial ONU / equipo", tracking=True)
    precinto = fields.Char(string="Nº de precinto", tracking=True)
    potencia_rx = fields.Float(
        string="Potencia RX (dBm)", digits=(4, 2), tracking=True)
    caja_nap = fields.Char(string="Caja NAP", tracking=True)
    puerto_nap = fields.Char(string="Puerto NAP", tracking=True)
    metros_fibra = fields.Integer(string="Metros de fibra", tracking=True)
    cliente_latitud = fields.Float(
        string="Latitud cliente", digits=(10, 7), tracking=True)
    cliente_longitud = fields.Float(
        string="Longitud cliente", digits=(10, 7), tracking=True)
    cliente_mapa_url = fields.Char(
        string="Ubicación del cliente", compute="_compute_mapa_url")
    nap_latitud = fields.Float(
        string="Latitud caja NAP", digits=(10, 7), tracking=True)
    nap_longitud = fields.Float(
        string="Longitud caja NAP", digits=(10, 7), tracking=True)
    nap_mapa_url = fields.Char(
        string="Ubicación de la caja NAP", compute="_compute_mapa_url")
    observaciones_contratista = fields.Text(
        string="Observaciones del contratista")
    motivo_no_realizada_ids = fields.Many2many(
        "atc.motivo.no.realizada", string="Motivo (no realizada)",
        tracking=True,
        help="Por qué no se pudo realizar la orden. Si eliges 'Otro', "
             "explícalo en las observaciones.")
    fecha_no_realizada = fields.Datetime(
        string="No realizada el", readonly=True, copy=False,
        help="Cuándo se marcó como no realizada por última vez. Al importar "
             "el reporte, la orden solo se reabre si allí aparece asignada "
             "después de esta fecha.")

    def _compute_access_url(self):
        super()._compute_access_url()
        for v in self:
            v.access_url = "/my/instalaciones/%s" % v.id

    @api.depends("cliente_latitud", "cliente_longitud",
                 "nap_latitud", "nap_longitud")
    def _compute_mapa_url(self):
        for v in self:
            v.cliente_mapa_url = url_mapa(v.cliente_latitud, v.cliente_longitud)
            v.nap_mapa_url = url_mapa(v.nap_latitud, v.nap_longitud)

    @api.depends("fecha_asignacion", "fecha_instalacion")
    def _compute_dias_pendiente(self):
        hoy = fields.Date.context_today(self)
        for v in self:
            if not v.fecha_asignacion:
                v.dias_pendiente = 0
                continue
            fin = v.fecha_instalacion or hoy
            v.dias_pendiente = max((fin - v.fecha_asignacion).days, 0)

    @api.depends("fecha_asignacion", "fecha_instalacion", "estado")
    def _compute_dias_instalacion(self):
        for v in self:
            if v.estado == "realizada" and v.fecha_asignacion \
                    and v.fecha_instalacion:
                v.dias_instalacion = max(
                    (v.fecha_instalacion - v.fecha_asignacion).days, 0)
            else:
                v.dias_instalacion = 0

    @api.model
    def _garantia_dias(self):
        try:
            return int(self.env["ir.config_parameter"].sudo().get_param(PARAM_GARANTIA_DIAS) or 30)
        except (TypeError, ValueError):
            return 30

    @api.depends("fecha_instalacion", "tipo_orden")
    def _compute_garantia_hasta(self):
        dias = self._garantia_dias()
        for v in self:
            v.garantia_hasta = v.fecha_instalacion + timedelta(days=dias) \
                if v.tipo_orden == "instalacion" and v.fecha_instalacion else False

    @api.model
    def _dominio_en_garantia(self):
        """Instalaciones realizadas dentro del periodo de garantía, o ya en
        visita por garantía."""
        desde = fields.Date.context_today(self) - timedelta(days=self._garantia_dias())
        return [("tipo_orden", "=", "instalacion"), "|",
                ("estado", "=", "garantia"),
                "&", ("estado", "=", "realizada"), ("fecha_instalacion", ">=", desde)]

    def _pasar_a_garantia(self, motivo, automatica=True):
        """Reabre la instalación como 'Visita por garantía' para su contratista."""
        for v in self:
            v.write({"estado": "garantia", "garantia_desde": fields.Datetime.now(),
                     "garantia_motivo": motivo, "garantia_automatica": automatica})
            v.message_post(body=self.env._(
                "Visita por garantía (instalada el %(fecha)s, garantía hasta el "
                "%(hasta)s): %(motivo)s",
                fecha=v.fecha_instalacion, hasta=v.garantia_hasta, motivo=motivo),
                subtype_xmlid="mail.mt_comment")

    def action_garantia_atendida(self):
        self.write({"estado": "realizada"})

    @api.model
    def _group_expand_estado(self, estados, domain):
        """Columnas del kanban según el menú: las instalaciones no muestran
        'En LOS' y las visitas no muestran 'No realizada' (salvo que haya
        órdenes en ese estado)."""
        todos = self._fields["estado"].get_values(self.env)
        tipo = self.env.context.get("default_tipo_orden")
        if tipo == "instalacion":
            ocultos = ESTADOS_SOLO_VISITA
        elif tipo == "visita":
            ocultos = ESTADOS_SOLO_INSTALACION
        else:
            ocultos = ()
        return [e for e in todos if e not in ocultos or e in estados]

    @api.depends("nombre", "cliente_id", "fecha", "tipo_orden")
    def _compute_name(self):
        for v in self:
            if v.name:
                continue
            etiqueta = "Instalación" if v.tipo_orden == "instalacion" else "Visita"
            base = v.nombre or (v.cliente_id.name if v.cliente_id else etiqueta)
            v.name = "%s — %s" % (base, v.fecha) if v.fecha else base

    @api.depends("zona_id")
    def _compute_franquicia_id(self):
        # Una zona sin franquicia no borra la que ya tiene la orden
        for v in self:
            v.franquicia_id = v.zona_id.franquicia_id or v.franquicia_id

    @api.onchange("vgt_id")
    def _onchange_vgt_id(self):
        # Si la orden no tiene zona y la VGT pertenece a una sola, se hereda.
        if self.vgt_id and not self.zona_id \
                and len(self.vgt_id.zona_ids) == 1:
            self.zona_id = self.vgt_id.zona_ids

    def _autoenlazar_vgt_zona(self):
        """Enlaza la VGT de la orden a su zona, solo si la VGT aún no está
        enlazada a ninguna zona (las ya enlazadas no se tocan)."""
        for v in self:
            if v.vgt_id and v.zona_id and not v.vgt_id.zona_ids:
                v.vgt_id.sudo().write({"zona_ids": [(4, v.zona_id.id)]})

    @api.constrains("estado", "tecnico_asignado_ids", "contratista_id")
    def _check_asignada_tecnico(self):
        for v in self:
            if v.estado == "asignada" and not v.tecnico_asignado_ids \
                    and not v.contratista_id:
                raise ValidationError(self.env._(
                    "No puedes pasar la orden a 'Asignada' sin al menos un "
                    "técnico en 'Asignado a' o un contratista. Usa el botón "
                    "'Asignar técnico'."))

    @api.constrains("cedula", "tipo_orden")
    def _check_cedula_visita(self):
        # Solo salta al crear o al cambiar la cédula: las visitas antiguas sin
        # cédula se pueden seguir editando. Las órdenes que genera el cron de
        # LOS (estado 'en_los') pueden venir sin cédula de SmartOLT.
        for v in self:
            if v.tipo_orden == "visita" and v.estado != "en_los" \
                    and not (v.cedula or "").strip():
                raise ValidationError(self.env._(
                    "La cédula del cliente es obligatoria en las visitas "
                    "técnicas."))

    @api.ondelete(at_uninstall=False)
    def _unlink_solo_visitas(self):
        """El rol ATC puede borrar visitas técnicas. Las instalaciones (vienen
        del Excel de contratistas) y las órdenes en LOS (el cron las volvería
        a crear) solo las borra un administrador."""
        if self.env.is_superuser() or self.env.user.has_group("base.group_system"):
            return
        if any(v.tipo_orden != "visita" or v.estado == "en_los" for v in self):
            raise UserError(self.env._(
                "Solo puedes borrar visitas técnicas. Las instalaciones y las "
                "órdenes en LOS las borra un administrador (puedes archivarlas)."))

    @api.constrains("estado", "motivo_no_realizada_ids")
    def _check_motivo_no_realizada(self):
        for v in self:
            if v.estado == "no_realizada" and not v.motivo_no_realizada_ids:
                raise ValidationError(self.env._(
                    "Indica el motivo por el que la orden no se realizó."))

    @api.constrains("estado", "serial_onu", "tecnico_contratista", "precinto")
    def _check_datos_instalacion_realizada(self):
        """Una instalación no se cierra como realizada sin serial de la ONU,
        técnico que instala y precinto (portal, formulario y kanban). El
        autocierre de una garantía (cliente recuperado) no se bloquea."""
        if self.env.context.get("atc_cierre_automatico"):
            return
        for v in self:
            if v.tipo_orden != "instalacion" or v.estado != "realizada":
                continue
            faltan = [v._fields[c].string for c in CAMPOS_REALIZADA
                      if not (v[c] or "").strip()]
            if faltan:
                raise ValidationError(self.env._(
                    "Para marcar la instalación como realizada falta: %(campos)s.",
                    campos=", ".join(faltan)))

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
            # Entregar la orden a un contratista la deja asignada.
            if vals.get("contratista_id") \
                    and vals.get("estado", "pendiente") == "pendiente":
                vals["estado"] = "asignada"
                vals.setdefault("fecha_asignacion",
                                fields.Date.context_today(self))
        visitas = super().create(vals_list)
        visitas._autoenlazar_vgt_zona()
        return visitas

    def write(self, vals):
        if (vals.get("cedula") or vals.get("nombre")) \
                and not vals.get("cliente_id") and len(self) == 1 \
                and not self.cliente_id:
            self._resolve_partner(vals, current=self)
        hoy = fields.Date.context_today(self)
        # Entregar una orden pendiente a un contratista la deja asignada.
        por_asignar = self.browse()
        if vals.get("contratista_id") and "estado" not in vals:
            por_asignar = self.filtered(lambda v: v.estado == "pendiente")
        if vals.get("estado") and vals["estado"] != "garantia":
            # Sale de garantía: queda el historial en el chatter
            vals = dict(vals, garantia_desde=False, garantia_motivo=False,
                        garantia_automatica=False)
        if vals.get("estado") == "no_realizada":
            vals = dict(vals, fecha_no_realizada=fields.Datetime.now())
        por_fechar = self.browse()
        if vals.get("estado") == "realizada" and "fecha_instalacion" not in vals:
            por_fechar = self.filtered(
                lambda v: v.tipo_orden == "instalacion"
                and not v.fecha_instalacion)
        res = super().write(vals)
        if por_asignar:
            sin_fecha = por_asignar.filtered(lambda v: not v.fecha_asignacion)
            super(AtcVisita, por_asignar).write({"estado": "asignada"})
            if sin_fecha:
                super(AtcVisita, sin_fecha).write({"fecha_asignacion": hoy})
        if por_fechar:
            super(AtcVisita, por_fechar).write({"fecha_instalacion": hoy})
        if "vgt_id" in vals or "zona_id" in vals:
            self._autoenlazar_vgt_zona()
        return res

    # --------------------------------------------------------------
    # Actualización desde el portal del contratista
    # --------------------------------------------------------------
    def _portal_puede_editar(self):
        self.ensure_one()
        return self.tipo_orden == "instalacion" \
            and self.estado in ESTADOS_ABIERTOS_PORTAL

    def _portal_actualizar(self, vals, accion=None):
        """Aplica los cambios enviados por el contratista. Solo escribe los
        campos de CAMPOS_PORTAL y solo mientras la orden siga abierta; el
        llamador ya verificó que la orden pertenece al contratista."""
        self.ensure_one()
        if not self._portal_puede_editar():
            raise ValidationError(self.env._(
                "Esta instalación ya está cerrada; pide a ATC que la reabra "
                "si necesitas corregir algo."))
        datos = {k: v for k, v in vals.items() if k in CAMPOS_PORTAL}
        if self.estado == "garantia" and accion in ("realizada", "no_realizada"):
            raise ValidationError(self.env._(
                "Esta orden es una visita por garantía: usa \"Garantía atendida\"."))
        if accion == "garantia_atendida":
            if self.estado != "garantia":
                raise ValidationError(self.env._("Esta orden no está en garantía."))
            datos["estado"] = "realizada"
        elif accion == "realizada":
            datos["estado"] = "realizada"
            if not datos.get("fecha_instalacion"):
                datos["fecha_instalacion"] = fields.Date.context_today(self)
        elif accion == "no_realizada":
            motivos = datos.get("motivo_no_realizada_ids")
            if motivos is None:
                motivos = self.motivo_no_realizada_ids.ids
            else:
                motivos = motivos[0][2]
            if not motivos:
                raise ValidationError(self.env._(
                    "Indica el motivo por el que la instalación no se realizó."))
            datos["estado"] = "no_realizada"
        self.write(datos)

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
                "default_contratista_id": self.contratista_id.id,
                "default_es_instalacion": self.tipo_orden == "instalacion",
            },
        }

    # --------------------------------------------------------------
    # Botones de estado
    # --------------------------------------------------------------
    def action_marcar_realizada(self):
        self.write({"estado": "realizada"})

    def action_marcar_pendiente(self):
        # Al reabrir, si ya tiene a quién está asignada vuelve a 'Asignada'.
        asignadas = self.filtered(
            lambda v: v.contratista_id or v.tecnico_asignado_ids)
        asignadas.write({"estado": "asignada"})
        (self - asignadas).write({"estado": "pendiente"})
