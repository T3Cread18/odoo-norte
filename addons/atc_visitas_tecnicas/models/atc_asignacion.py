"""Asistente de asignación de instalaciones.

ATC sube el export de contratos por asignar de TotalNet y el asistente:
clasifica las filas, agrupa los sectores en zonas (diccionario que se aprende),
deja elegir contratista por zona y criterios, propone un plan editable y, al
confirmar, crea o actualiza las órdenes. La asignación queda en Odoo: ATC la
registra luego a mano en TotalNet (casilla «En TotalNet» de cada línea).
"""
import json
import logging
import math
import re

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..wizard.atc_instalacion_import import (
    SIN_DATO, _limpiar, _norm, leer_fecha,
)

_logger = logging.getLogger(__name__)

ABIERTAS_ODOO = ("pendiente", "asignada")
# Carga actual de un contratista: también cuentan las visitas por garantía
CARGA_ACTUAL = ("pendiente", "asignada", "garantia")
SIN_SECTOR = "SIN SECTOR"
ALIAS_PAGO = ("FECHA PAGO", "FECHA DE PAGO")
ALIAS_ORDEN = ("NRO ORDEN", "N ORDEN", "NUMERO ORDEN", "ORDEN")

PREFIJOS_SECTOR = {
    "URB", "URBANIZACION", "BARRIO", "BO", "SECTOR", "AV", "AVENIDA",
    "RESIDENCIAS", "CONJUNTO", "CASERIO",
}
# Desde estas palabras, lo que sigue es detalle dentro del sector
CORTES_SECTOR = {"SECTOR", "VEREDA", "ETAPA", "CALLE", "MANZANA"}
ROMANOS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}


def clave_sector(texto):
    """Sector normalizado (mayúsculas, sin acentos ni signos)."""
    return re.sub(r"[^A-Z0-9]+", " ", _norm(texto)).strip() or SIN_SECTOR


def base_sector(texto):
    """Nombre de fondo de un sector, para reconocer variantes del mismo:
    «URB. BELLA VISTA II» -> «BELLA VISTA»; «BARRIO LA GONZALO SECTOR 4
    VEREDA 9» -> «LA GONZALO»; «DURIGUA 4» y «DURIGUA CENTRO» -> «DURIGUA»."""
    clave = clave_sector(texto)
    if clave == SIN_SECTOR:
        return clave
    palabras = clave.split()
    # «SECTOR 4» se queda como está: sin el prefijo solo quedaría un número
    while len(palabras) > 1 and palabras[0] in PREFIJOS_SECTOR \
            and not palabras[1].isdigit():
        palabras.pop(0)
    for i, palabra in enumerate(palabras):
        if i and palabra in CORTES_SECTOR:
            palabras = palabras[:i]
            break
    while len(palabras) > 1 and (
            palabras[-1] in ROMANOS or palabras[-1].isdigit()
            or palabras[-1] == "CENTRO"):
        palabras.pop()
    return " ".join(palabras)


class AtcZonaSector(models.Model):
    """Diccionario: a qué zona pertenece cada sector del export."""
    _name = "atc.zona.sector"
    _description = "Sector del export y su zona"
    _order = "clave"

    clave = fields.Char(string="Sector", required=True, index=True)
    franquicia_id = fields.Many2one(
        "atc.franquicia", string="Franquicia", ondelete="cascade")
    zona_id = fields.Many2one(
        "atc.zona", string="Zona", required=True, ondelete="cascade", index=True)

    _sector_unico = models.Constraint(
        "UNIQUE NULLS NOT DISTINCT(clave, franquicia_id)",
        "Ese sector ya tiene zona en esa franquicia.")


class AtcAsignacionLote(models.Model):
    _name = "atc.asignacion.lote"
    _description = "Lote de asignación de instalaciones"
    _order = "id desc"

    name = fields.Char(
        string="Lote", required=True,
        default=lambda self: self.env._(
            "Asignación %s",
            fields.Date.context_today(self).strftime("%d/%m/%Y")))
    state = fields.Selection([
        ("archivo", "Archivo"),
        ("sectores", "Sectores"),
        ("zonas", "Zonas y criterios"),
        ("plan", "Plan"),
        ("confirmado", "Confirmado"),
    ], string="Paso", default="archivo", required=True, readonly=True)
    archivo = fields.Binary(
        string="Export de TotalNet (.xlsx, .xls o .csv)", attachment=True)
    nombre_archivo = fields.Char(string="Archivo")
    fecha_reporte = fields.Date(
        string="Fecha del reporte", required=True,
        default=fields.Date.context_today)

    respetar_propias = fields.Boolean(
        string="Venta propia va a su contratista", default=True,
        help="La venta cuyo vendedor es un contratista queda con ese contratista.")
    equidad = fields.Selection([
        ("abiertas", "Equitativo contando las órdenes que ya tiene abiertas"),
        ("lote", "Equitativo solo en este lote"),
        ("no", "Sin reparto automático"),
    ], string="Equidad", default="abiertas", required=True,
        help="Cómo repartir las zonas sin contratista elegido. Sin reparto "
             "automático, esas órdenes quedan para asignarlas a mano en el plan.")
    dividir_zonas = fields.Boolean(
        string="Dividir una zona si rompe el equilibrio", default=False,
        help="Desactivado, cada zona va entera a un solo contratista.")

    linea_ids = fields.One2many(
        "atc.asignacion.linea", "lote_id", string="Órdenes del plan",
        domain=[("incluida", "=", True)])
    excluida_ids = fields.One2many(
        "atc.asignacion.linea", "lote_id", string="Fuera del plan",
        domain=[("incluida", "=", False)])
    sector_ids = fields.One2many(
        "atc.asignacion.sector", "lote_id", string="Sectores")
    zona_ids = fields.One2many(
        "atc.asignacion.zona", "lote_id", string="Zonas")
    contratista_ids = fields.One2many(
        "atc.asignacion.contratista", "lote_id", string="Contratistas")

    total_filas = fields.Integer(string="Filas del archivo", readonly=True)
    otras_franquicias = fields.Integer(
        string="Filas de otras franquicias", readonly=True)
    avisos = fields.Text(string="Avisos del archivo", readonly=True)
    resultado = fields.Text(string="Resultado", readonly=True)
    confirmado_por_id = fields.Many2one(
        "res.users", string="Confirmado por", readonly=True)
    fecha_confirmado = fields.Datetime(string="Confirmado el", readonly=True)

    por_asignar_count = fields.Integer(
        string="Órdenes en el plan", compute="_compute_contadores")
    sin_contratista_count = fields.Integer(
        string="Sin contratista", compute="_compute_contadores")
    sin_totalnet_count = fields.Integer(
        string="Faltan en TotalNet", compute="_compute_contadores")
    resumen = fields.Html(
        string="Resumen", compute="_compute_resumen", sanitize=False)

    @api.depends("linea_ids.contratista_id", "linea_ids.en_totalnet",
                 "linea_ids.resultado")
    def _compute_contadores(self):
        for lote in self:
            lineas = lote.linea_ids
            lote.por_asignar_count = len(lineas)
            lote.sin_contratista_count = len(
                lineas.filtered(lambda l: not l.contratista_id))
            lote.sin_totalnet_count = len(lineas.filtered(
                lambda l: l.contratista_id and not l.en_totalnet
                and l.resultado in ("creada", "actualizada")))

    @api.depends("total_filas", "otras_franquicias", "avisos", "state",
                 "linea_ids.contratista_id", "excluida_ids.exclusion")
    def _compute_resumen(self):
        for lote in self:
            if lote.state == "archivo":
                lote.resumen = False
                continue
            _ = lote.env._
            etiquetas = dict(lote.env["atc.asignacion.linea"]._fields[
                "exclusion"]._description_selection(lote.env))
            fuera = {}
            for linea in lote.excluida_ids:
                fuera[linea.exclusion] = fuera.get(linea.exclusion, 0) + 1
            items = Markup("").join(
                Markup("<li>%s: <b>%s</b></li>") % (etiquetas.get(k, k), n)
                for k, n in sorted(fuera.items(), key=lambda t: -t[1]))
            if lote.otras_franquicias:
                items += Markup("<li>%s: <b>%s</b></li>") % (
                    _("De franquicias que no atiendes (no se cargan)"),
                    lote.otras_franquicias)
            html = Markup(
                '<div class="alert alert-info" role="alert">'
                "%s: <b>%s</b> · %s: <b>%s</b>") % (
                _("Filas del archivo"), lote.total_filas,
                _("En el plan"), lote.por_asignar_count)
            if lote.sin_contratista_count and lote.state in ("plan", "confirmado"):
                html += Markup(" · %s: <b>%s</b>") % (
                    _("Sin contratista (quedarán pendientes)"),
                    lote.sin_contratista_count)
            if lote.state == "confirmado":
                html += Markup(" · %s: <b>%s</b>") % (
                    _("Faltan por registrar en TotalNet"),
                    lote.sin_totalnet_count)
            if items:
                html += Markup("<div>%s</div><ul class='mb-0'>%s</ul>") % (
                    _("Fuera del plan (ver pestaña «Fuera del plan»):"), items)
            html += Markup("</div>")
            if lote.avisos:
                html += Markup(
                    '<div class="alert alert-warning" role="alert"><ul class="mb-0">%s</ul></div>'
                ) % Markup("").join(
                    Markup("<li>%s</li>") % a for a in lote.avisos.split("\n"))
            lote.resumen = html

    @api.ondelete(at_uninstall=False)
    def _unlink_solo_sin_confirmar(self):
        if any(lote.state == "confirmado" for lote in self):
            raise UserError(self.env._(
                "Un lote confirmado no se puede borrar: es el registro de la asignación."))

    def _reabrir(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _exigir_paso(self, *pasos):
        self.ensure_one()
        if self.state not in pasos:
            raise UserError(self.env._(
                "El lote cambió de paso: recarga la página."))

    # ------------------------------------------------------------------
    # Paso 1: analizar el archivo
    # ------------------------------------------------------------------
    def _limpiar_analisis(self):
        self.linea_ids.unlink()
        self.excluida_ids.unlink()
        self.sector_ids.unlink()
        self.zona_ids.unlink()
        self.contratista_ids.unlink()

    def action_analizar(self):
        self._exigir_paso("archivo")
        if not self.archivo:
            raise UserError(self.env._("Debes adjuntar el export de TotalNet."))
        importador = self.env["atc.instalacion.import"].create({
            "archivo": self.archivo,
            "nombre_archivo": self.nombre_archivo,
            "fecha_reporte": self.fecha_reporte,
        })
        importador._cargar()
        self._limpiar_analisis()
        self._crear_lineas(importador)
        self._crear_sectores()
        self._crear_contratistas()
        importador.unlink()
        self.state = "sectores"
        return self._reabrir()

    def _crear_lineas(self, imp):
        mapeo = imp._mapeo()
        filas = imp._filas(mapeo)
        if not filas:
            raise UserError(self.env._("No hay filas con cédula o nombre."))
        con_error, avisos = imp._revisar(mapeo, filas, avisar_sin_contratista=False)
        cuerpo = json.loads(imp.datos or "[]")
        primera = imp.fila_encabezado + 1
        col_pago = col_orden = None
        for columna in imp.linea_ids:
            titulo = _norm(columna.columna)
            if titulo in ALIAS_PAGO:
                col_pago = columna.indice
            elif titulo in ALIAS_ORDEN and col_orden is None:
                col_orden = columna.indice
        if col_pago is None:
            avisos.append(self.env._(
                "El archivo no trae la columna FECHA PAGO: no se pudo dejar fuera "
                "las órdenes sin fecha de pago."))

        # Se consulta con sudo: un cliente puede tener una orden en otra
        # franquicia que este usuario no ve, y no debe duplicarse.
        Visita = self.env["atc.visita"].sudo().with_context(active_test=False)
        cedulas = list({f["cedula"] for _n, f in filas if f["cedula"]})
        abiertas, cerradas = {}, {}
        for v in Visita.search([("tipo_orden", "=", "instalacion"),
                                ("cedula", "in", cedulas)], order="id desc"):
            if v.active and v.estado in ABIERTAS_ODOO:
                abiertas.setdefault(v.cedula, v)
            else:
                cerradas.setdefault(v.cedula, v)

        franquicias_usuario = self.env.user.atc_franquicia_todas_ids \
            if self.env.user.atc_franquicia_ids else None
        Franquicia = self.env["atc.franquicia"].with_context(active_test=False)
        cache_franquicia = {}
        vistas = set()
        vals_list = []
        otras = 0
        for n, fila in filas:
            crudo = cuerpo[n - primera]

            def celda(indice):
                val = crudo[indice] if indice is not None and indice < len(crudo) else None
                return None if _norm(val) in SIN_DATO else val

            nombre_f = fila["franquicia"]
            clave_f = _norm(nombre_f)
            if clave_f and clave_f not in cache_franquicia:
                cache_franquicia[clave_f] = Franquicia.search(
                    [("name", "=ilike", nombre_f), ("child_ids", "=", False)], limit=1)
            franquicia = cache_franquicia.get(clave_f, Franquicia)
            if franquicias_usuario is not None and franquicia \
                    and franquicia not in franquicias_usuario:
                otras += 1
                continue

            pago_txt = celda(col_pago) if col_pago is not None else None
            vals = {
                "lote_id": self.id,
                "fila": n,
                "nro_orden": _limpiar(celda(col_orden)),
                "cedula": fila["cedula"],
                "nombre": fila["nombre"],
                "telefono_movil": fila["telefono_movil"] or False,
                "telefono_fijo": fila["telefono_fijo"] or False,
                "direccion": fila["direccion"],
                "sector": fila["zona"] or SIN_SECTOR,
                "franquicia_nombre": nombre_f,
                "franquicia_id": franquicia.id,
                "vendedor": fila["vendedor"],
                "tipo_servicio": fila["tipo_servicio"],
                "antiguedad": fila["antiguedad"] or 0,
                "fecha_pago": leer_fecha(pago_txt),
            }
            vals.update(self._clasificar(
                n, fila, con_error, vistas, abiertas, cerradas,
                sin_pago=col_pago is not None and not _limpiar(pago_txt)))
            vals_list.append(vals)
        self.env["atc.asignacion.linea"].create(vals_list)
        self.write({
            "total_filas": len(filas),
            "otras_franquicias": otras,
            "avisos": "\n".join(avisos) or False,
        })

    def _clasificar(self, n, fila, con_error, vistas, abiertas, cerradas, sin_pago):
        """Decide si la fila entra al plan. Devuelve los valores de la línea."""
        _ = self.env._
        cedula = fila["cedula"]

        def fuera(motivo, detalle=False):
            return {"incluida": False, "exclusion": motivo,
                    "exclusion_detalle": detalle}

        if n in con_error:
            return fuera("error", "; ".join(con_error[n]))
        if fila["estatus"] != "abierta":
            return fuera("estatus", fila["estatus"].upper())
        if cedula and cedula in vistas:
            return fuera("repetida")
        if cedula:
            vistas.add(cedula)
        abierta = abiertas.get(cedula) if cedula else None
        if abierta and abierta.contratista_id:
            return fuera("asignada_odoo", abierta.contratista_id.name)
        if not abierta:
            cerrada = cerradas.get(cedula) if cedula else None
            if cerrada and cerrada.active and cerrada.estado == "no_realizada":
                return fuera("no_realizada", _(
                    "%(c)s: %(m)s",
                    c=cerrada.contratista_id.name or "—",
                    m=", ".join(cerrada.motivo_no_realizada_ids.mapped("name")) or "—"))
            if cerrada:
                estados = dict(cerrada._fields["estado"]._description_selection(self.env))
                return fuera("cerrada", _(
                    "%(e)s%(a)s (%(c)s)", e=estados.get(cerrada.estado, cerrada.estado),
                    a="" if cerrada.active else _(", archivada"),
                    c=cerrada.contratista_id.name or "—"))
        if fila["contratista"]:
            return fuera("tecnico_sistema", fila["contratista"])
        if sin_pago:
            return fuera("sin_pago")
        return {"incluida": True, "visita_id": abierta.id if abierta else False}

    # ------------------------------------------------------------------
    # Paso 2: sectores
    # ------------------------------------------------------------------
    def _crear_sectores(self):
        grupos = {}
        for linea in self.linea_ids:
            clave = (linea.franquicia_id.id, clave_sector(linea.sector))
            grupos.setdefault(clave, self.env["atc.asignacion.linea"])
            grupos[clave] |= linea
        Dic = self.env["atc.zona.sector"]
        dic_exacto, dic_base = {}, {}
        for fila in Dic.search([]):
            dic_exacto[(fila.franquicia_id.id, fila.clave)] = fila.zona_id
            dic_base.setdefault(
                (fila.franquicia_id.id, base_sector(fila.clave)), fila.zona_id)
        zonas = self.env["atc.zona"].search([])
        vals_list = []
        for (franquicia_id, clave), lineas in grupos.items():
            zona, origen = dic_exacto.get((franquicia_id, clave)), "conocido"
            if not zona:
                zona = dic_base.get((franquicia_id, base_sector(clave))) \
                    or self._zona_parecida(clave, franquicia_id, zonas)
                origen = "sugerida" if zona else "sin_zona"
            vals_list.append({
                "lote_id": self.id,
                "clave": clave,
                "franquicia_id": franquicia_id,
                "zona_id": zona.id if zona else False,
                "origen": origen,
                "ordenes": len(lineas),
            })
        self.env["atc.asignacion.sector"].create(vals_list)

    def _zona_parecida(self, clave, franquicia_id, zonas):
        """Zona existente con el mismo nombre de fondo que el sector, o cuyo
        nombre (de dos palabras o más) es el inicio del sector: «RIO ACARIGUA
        ARENERA» -> RIO ACARIGUA. Un nombre de una palabra no basta: «ARAURE»
        no debe atraer a «QUEBRADITA DE ARAURE» ni a «ARAURE NORTE»."""
        base = base_sector(clave)
        mejor = None
        for zona in zonas:
            if zona.franquicia_id and zona.franquicia_id.id != franquicia_id:
                continue
            nombre = clave_sector(zona.name)
            if nombre in (clave, base):
                return zona
            if len(nombre.split()) >= 2 and base.startswith(nombre + " ") \
                    and (not mejor or len(nombre) > len(clave_sector(mejor.name))):
                mejor = zona
        return mejor

    def _crear_contratistas(self):
        Visita = self.env["atc.visita"].sudo()
        grupos = Visita._read_group(
            [("tipo_orden", "=", "instalacion"),
             ("estado", "in", CARGA_ACTUAL),
             ("contratista_id", "!=", False)],
            ["contratista_id"], ["__count"])
        abiertas = {c.id: n for c, n in grupos}
        self.env["atc.asignacion.contratista"].create([{
            "lote_id": self.id,
            "contratista_id": c.id,
            "abiertas": abiertas.get(c.id, 0),
        } for c in self.env["atc.contratista"].search([])])

    def action_volver_archivo(self):
        self._exigir_paso("sectores")
        self._limpiar_analisis()
        self.write({"state": "archivo", "avisos": False, "total_filas": 0,
                    "otras_franquicias": 0})
        return self._reabrir()

    def action_agrupar(self):
        """Guarda los sectores en el diccionario y arma las zonas del lote."""
        self._exigir_paso("sectores")
        self._guardar_diccionario()
        por_sector = {(s.franquicia_id.id, s.clave): s for s in self.sector_ids}
        previas = {z.clave: z.contratista_id for z in self.zona_ids}
        self.zona_ids.unlink()
        grupos = {}
        for linea in self.linea_ids:
            clave = clave_sector(linea.sector)
            sector = por_sector.get((linea.franquicia_id.id, clave))
            zona = sector.zona_id if sector else self.env["atc.zona"]
            if zona:
                grupo = "z%s" % zona.id
                nombre = zona.name
            else:
                base = base_sector(clave)
                grupo = "s%s:%s" % (linea.franquicia_id.id or 0, base)
                nombre = base
            linea.write({"zona_id": zona.id, "grupo_clave": grupo,
                         "grupo_nombre": nombre})
            datos = grupos.setdefault(grupo, {
                "nombre": nombre, "zona": zona,
                "lineas": self.env["atc.asignacion.linea"]})
            datos["lineas"] |= linea
        contratistas = self.env["atc.contratista"].search([])
        nombres = {_norm(c.name) for c in contratistas}
        vals_list = []
        for grupo, datos in grupos.items():
            lineas = datos["lineas"]
            sugerido = previas.get(grupo) or datos["zona"].contratista_sugerido_id
            vals_list.append({
                "lote_id": self.id,
                "clave": grupo,
                "nombre": datos["nombre"],
                "zona_id": datos["zona"].id,
                "contratista_id": sugerido.id if sugerido and sugerido.active else False,
                "franquicias": ", ".join(sorted(set(lineas.mapped("franquicia_nombre")))),
                "sectores": ", ".join(sorted({clave_sector(l.sector) for l in lineas})),
                "ordenes": len(lineas),
                "propias": len(lineas.filtered(lambda l: _norm(l.vendedor) in nombres)),
                "antiguedad_max": max(lineas.mapped("antiguedad") or [0]),
            })
        self.env["atc.asignacion.zona"].create(vals_list)
        self.state = "zonas"
        return self._reabrir()

    def _guardar_diccionario(self):
        Dic = self.env["atc.zona.sector"]
        for sector in self.sector_ids:
            fila = Dic.search([("clave", "=", sector.clave),
                               ("franquicia_id", "=", sector.franquicia_id.id)], limit=1)
            if sector.clave == SIN_SECTOR:
                continue
            if sector.zona_id and fila:
                if fila.zona_id != sector.zona_id:
                    fila.zona_id = sector.zona_id
            elif sector.zona_id:
                Dic.create({"clave": sector.clave,
                            "franquicia_id": sector.franquicia_id.id,
                            "zona_id": sector.zona_id.id})
            elif fila:
                # ATC le quitó la zona: deja de saberse
                fila.unlink()

    # ------------------------------------------------------------------
    # Paso 3: plan
    # ------------------------------------------------------------------
    def action_volver_sectores(self):
        self._exigir_paso("zonas")
        self.state = "sectores"
        return self._reabrir()

    def action_generar_plan(self):
        self._exigir_paso("zonas")
        self._generar_plan()
        self.state = "plan"
        return self._reabrir()

    def action_recalcular(self):
        self._exigir_paso("plan")
        self._generar_plan()
        return self._reabrir()

    def action_recalcular_desde_cero(self):
        self._exigir_paso("plan")
        self.linea_ids.with_context(atc_plan=True).write({"motivo": False})
        self._generar_plan()
        return self._reabrir()

    def action_volver_zonas(self):
        self._exigir_paso("plan")
        self.state = "zonas"
        return self._reabrir()

    def _generar_plan(self):
        """Reparte el lote. Orden: cambios manuales, venta propia, zona con
        contratista elegido y, según la equidad, el resto de las zonas (la más
        grande primero, al contratista con menos carga)."""
        self.ensure_one()
        Linea = self.env["atc.asignacion.linea"].with_context(atc_plan=True)
        participan = self.contratista_ids.filtered("participa").contratista_id
        if not participan:
            raise UserError(self.env._("Elige al menos un contratista que participe."))
        lineas = Linea.browse(self.linea_ids.ids)
        manuales = lineas.filtered(lambda l: l.motivo == "manual" and l.contratista_id)
        pendientes = lineas - manuales
        pendientes.write({"contratista_id": False, "motivo": False})

        carga = {c.id: 0 for c in participan}
        if self.equidad == "abiertas":
            for fila in self.contratista_ids.filtered("participa"):
                carga[fila.contratista_id.id] = fila.abiertas
        for linea in manuales:
            if linea.contratista_id.id in carga:
                carga[linea.contratista_id.id] += 1

        def asignar(lote_lineas, contratista, motivo):
            lote_lineas.write({"contratista_id": contratista.id, "motivo": motivo})
            carga[contratista.id] += len(lote_lineas)

        if self.respetar_propias:
            por_nombre = {_norm(c.name): c for c in participan}
            for linea in pendientes:
                contratista = por_nombre.get(_norm(linea.vendedor))
                if contratista:
                    asignar(linea, contratista, "propia")
        resto = pendientes.filtered(lambda l: not l.contratista_id)

        for zona in self.zona_ids.filtered(
                lambda z: z.contratista_id and z.contratista_id in participan):
            de_zona = resto.filtered(lambda l: l.grupo_clave == zona.clave)
            if de_zona:
                asignar(de_zona, zona.contratista_id, "zona")
        resto = resto.filtered(lambda l: not l.contratista_id)
        if self.equidad != "no":
            self._repartir(resto, participan, carga, asignar)

    def _repartir(self, lineas, participan, carga, asignar):
        if not lineas:
            return
        grupos = {}
        for linea in lineas.sorted(lambda l: (-l.antiguedad, l.id)):
            grupos.setdefault(linea.grupo_clave, lineas.browse())
            grupos[linea.grupo_clave] |= linea
        tope = math.ceil((sum(carga.values()) + len(lineas)) / len(participan))
        orden = sorted(grupos.items(), key=lambda t: (-len(t[1]), t[0]))
        nombre = {c.id: c.name for c in participan}
        for _grupo, grupo_lineas in orden:
            restantes = grupo_lineas
            while restantes:
                cid = min(carga, key=lambda c: (carga[c], nombre[c]))
                cuantas = len(restantes)
                if self.dividir_zonas:
                    cuantas = min(cuantas, max(tope - carga[cid], 1))
                asignar(restantes[:cuantas], participan.browse(cid), "equidad")
                restantes = restantes[cuantas:]

    def _accion_lista(self, modelo, vista, nombre):
        """Lista aparte: en una lista dentro de un formulario no se pueden
        seleccionar varias filas y editarlas a la vez."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": nombre,
            "res_model": modelo,
            "view_mode": "list",
            "views": [(self.env.ref("atc_visitas_tecnicas.%s" % vista).id, "list")],
            "domain": [("lote_id", "=", self.id)],
        }

    def action_editar_sectores(self):
        self._exigir_paso("sectores")
        return self._accion_lista(
            "atc.asignacion.sector", "view_atc_asignacion_sector_list",
            self.env._("Sectores — %s", self.name))

    def action_editar_zonas(self):
        self._exigir_paso("zonas")
        return self._accion_lista(
            "atc.asignacion.zona", "view_atc_asignacion_zona_list",
            self.env._("Zonas — %s", self.name))

    def action_ver_por_contratista(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Órdenes por contratista — %s", self.name),
            "res_model": "atc.asignacion.linea",
            "view_mode": "list",
            "views": [(self.env.ref(
                "atc_visitas_tecnicas.view_atc_asignacion_linea_plan_list").id, "list")],
            "search_view_id": self.env.ref(
                "atc_visitas_tecnicas.view_atc_asignacion_linea_search").id,
            "domain": [("lote_id", "=", self.id), ("incluida", "=", True)],
            "context": {"group_by": ["contratista_id"]},
        }

    # ------------------------------------------------------------------
    # Paso 4: confirmar
    # ------------------------------------------------------------------
    def action_confirmar(self):
        self._exigir_paso("plan")
        caches = {"servicio": {}, "vendedor": {}, "franquicia": {}}
        conteo = {"creada": 0, "actualizada": 0, "omitida": 0, "error": 0}
        detalles = []
        for linea in self.linea_ids.sorted("fila"):
            try:
                with self.env.cr.savepoint():
                    res, detalle = linea._aplicar(caches)
            except Exception as exc:  # una fila mala no frena el lote
                _logger.info("Asignación: fila %s no aplicada: %s", linea.fila, exc)
                res = "error"
                detalle = exc.args[0] if exc.args else str(exc)
            linea.with_context(atc_plan=True).write(
                {"resultado": res, "resultado_detalle": detalle or False})
            conteo[res] += 1
            if res in ("omitida", "error"):
                detalles.append(self.env._(
                    "Fila %(n)s, %(c)s: %(d)s", n=linea.fila, c=linea.nombre, d=detalle))
        self._recordar_zonas()
        _ = self.env._
        texto = [
            _("Órdenes creadas: %s", conteo["creada"]),
            _("Órdenes actualizadas: %s", conteo["actualizada"]),
            _("Omitidas: %s", conteo["omitida"]),
            _("Con error: %s", conteo["error"]),
        ] + detalles
        self.write({
            "state": "confirmado",
            "resultado": "\n".join(texto),
            "confirmado_por_id": self.env.user.id,
            "fecha_confirmado": fields.Datetime.now(),
        })
        return self._reabrir()

    def _recordar_zonas(self):
        """Cada zona queda sugerida al contratista con más órdenes suyas en
        este lote (sin contar ventas propias). El próximo lote se puede cambiar."""
        por_zona = {}
        for linea in self.linea_ids.filtered(
                lambda l: l.zona_id and l.contratista_id and l.motivo != "propia"
                and l.resultado in ("creada", "actualizada")):
            cuenta = por_zona.setdefault(linea.zona_id, {})
            cuenta[linea.contratista_id] = cuenta.get(linea.contratista_id, 0) + 1
        for zona, cuenta in por_zona.items():
            mayor = max(cuenta, key=lambda c: (cuenta[c], c.name))
            if zona.contratista_sugerido_id != mayor:
                zona.contratista_sugerido_id = mayor


class AtcAsignacionLinea(models.Model):
    _name = "atc.asignacion.linea"
    _description = "Orden dentro de un lote de asignación"
    _order = "contratista_id, grupo_nombre, fila"

    lote_id = fields.Many2one(
        "atc.asignacion.lote", required=True, ondelete="cascade", index=True)
    lote_state = fields.Selection(related="lote_id.state", string="Paso")
    fila = fields.Integer(string="Fila", readonly=True, aggregator=None)
    nro_orden = fields.Char(string="Nº orden", readonly=True)
    cedula = fields.Char(string="Cédula / RIF", readonly=True)
    nombre = fields.Char(string="Cliente", readonly=True)
    telefono_movil = fields.Char(string="Móvil", readonly=True)
    telefono_fijo = fields.Char(string="Fijo", readonly=True)
    direccion = fields.Char(string="Dirección", readonly=True)
    sector = fields.Char(string="Sector", readonly=True)
    franquicia_nombre = fields.Char(string="Franquicia", readonly=True)
    franquicia_id = fields.Many2one("atc.franquicia", string="Franquicia en Odoo", readonly=True)
    zona_id = fields.Many2one("atc.zona", string="Zona de Odoo", readonly=True)
    grupo_clave = fields.Char(readonly=True, index=True)
    grupo_nombre = fields.Char(string="Zona", readonly=True)
    vendedor = fields.Char(string="Vendedor", readonly=True)
    tipo_servicio = fields.Char(string="Servicio", readonly=True)
    antiguedad = fields.Integer(string="Días", readonly=True, aggregator="max")
    fecha_pago = fields.Date(string="Fecha de pago", readonly=True)

    incluida = fields.Boolean(string="En el plan", default=True, readonly=True)
    exclusion = fields.Selection([
        ("sin_pago", "Sin fecha de pago"),
        ("asignada_odoo", "Ya asignada en Odoo"),
        ("tecnico_sistema", "Ya tiene técnico en TotalNet (cargar con el importador)"),
        ("no_realizada", "No realizada en Odoo (reabrir a mano si corresponde)"),
        ("cerrada", "Ya instalada o archivada en Odoo (revisar si hay que reinstalar)"),
        ("estatus", "Finalizada o cancelada en TotalNet"),
        ("repetida", "Cédula repetida en el archivo"),
        ("error", "Error en la fila"),
    ], string="Por qué queda fuera", readonly=True)
    exclusion_detalle = fields.Char(string="Detalle", readonly=True)

    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista", ondelete="restrict", index=True)
    motivo = fields.Selection([
        ("propia", "Propia"),
        ("zona", "Zona"),
        ("equidad", "Equidad"),
        ("manual", "Manual"),
    ], string="Por qué", readonly=True)
    visita_id = fields.Many2one(
        "atc.visita", string="Orden", readonly=True, ondelete="set null")
    resultado = fields.Selection([
        ("creada", "Creada"),
        ("actualizada", "Actualizada"),
        ("omitida", "Omitida"),
        ("error", "Error"),
    ], string="Resultado", readonly=True)
    resultado_detalle = fields.Char(string="Detalle del resultado", readonly=True)
    en_totalnet = fields.Boolean(
        string="En TotalNet",
        help="Márcala cuando ya registraste esta asignación en TotalNet.")

    def write(self, vals):
        if "contratista_id" in vals and not self.env.context.get("atc_plan"):
            if any(l.lote_id.state != "plan" for l in self):
                raise UserError(self.env._(
                    "El contratista solo se cambia en el paso Plan. Después de "
                    "confirmar, reasígnalo en la orden."))
            vals = dict(vals, motivo="manual" if vals["contratista_id"] else False)
        return super().write(vals)

    def _aplicar(self, caches):
        """Crea o actualiza la orden. Vuelve a mirar el estado actual: desde
        el análisis alguien pudo haberla asignado. Devuelve (resultado, detalle)."""
        self.ensure_one()
        _ = self.env._
        Visita = self.env["atc.visita"]
        Imp = self.env["atc.instalacion.import"]
        todas = Visita.sudo().with_context(active_test=False)
        hoy = fields.Date.context_today(self)
        abierta = cerrada = Visita
        if self.cedula:
            abierta = todas.search([
                ("tipo_orden", "=", "instalacion"), ("cedula", "=", self.cedula),
                ("active", "=", True), ("estado", "in", ABIERTAS_ODOO),
            ], order="id desc", limit=1)
            if not abierta:
                cerrada = todas.search([
                    ("tipo_orden", "=", "instalacion"), ("cedula", "=", self.cedula),
                ], order="id desc", limit=1)
        if abierta.contratista_id:
            return "omitida", _("ya la asignaron a %s", abierta.contratista_id.name)
        if cerrada:
            return "omitida", _("la orden del cliente cambió de estado desde el análisis")

        vendedor = Imp._buscar_o_crear(
            self.env["atc.vendedor"], self.vendedor, caches["vendedor"])
        servicio = Imp._buscar_o_crear(
            self.env["atc.tipo.servicio"], self.tipo_servicio, caches["servicio"])
        franquicia = Imp._buscar_franquicia(self.franquicia_nombre, caches["franquicia"])
        zona = self.zona_id
        # Una zona de otra franquicia cambiaría la franquicia de la orden
        if zona.franquicia_id and franquicia and zona.franquicia_id != franquicia:
            zona = self.env["atc.zona"]
        contratista = self.contratista_id

        if abierta:
            orden = abierta.sudo(False)
            if not contratista:
                return "omitida", _("sin contratista en el plan: sigue pendiente")
            cambios = {"contratista_id": contratista.id, "fecha_asignacion": hoy}
            if zona:
                cambios["zona_id"] = zona.id
            if vendedor and not orden.vendedor_id:
                cambios["vendedor_id"] = vendedor.id
            orden.write(cambios)
            resultado = "actualizada"
        else:
            vals = {
                "tipo_orden": "instalacion",
                "cedula": self.cedula or False,
                "nombre": self.nombre,
                "fecha": hoy,
                "tipo_servicio_id": servicio.id,
                "vendedor_id": vendedor.id,
                "telefono_movil": self.telefono_movil,
                "telefono_fijo": self.telefono_fijo,
                "direccion": self.direccion or False,
                "zona_id": zona.id,
                "tecnico_id": False,
                "estado": "asignada" if contratista else "pendiente",
            }
            if franquicia:
                vals["franquicia_id"] = franquicia.id
            if contratista:
                vals.update({"contratista_id": contratista.id, "fecha_asignacion": hoy})
            orden = Visita.create(vals)
            partner = orden.cliente_id.sudo()
            if partner and not partner.phone and self.telefono_movil:
                partner.phone = self.telefono_movil
            resultado = "creada"

        self.with_context(atc_plan=True).visita_id = orden
        etiquetas = dict(self._fields["motivo"]._description_selection(self.env))
        if contratista:
            orden.message_post(body=_(
                "Asignada a %(c)s en el lote «%(l)s» (%(m)s). Falta registrarla en "
                "TotalNet.", c=contratista.name, l=self.lote_id.name,
                m=etiquetas.get(self.motivo, "—")))
        return resultado, False


class AtcAsignacionSector(models.Model):
    _name = "atc.asignacion.sector"
    _description = "Sector de un lote de asignación"
    _order = "origen desc, ordenes desc, clave"

    lote_id = fields.Many2one(
        "atc.asignacion.lote", required=True, ondelete="cascade", index=True)
    clave = fields.Char(string="Sector", readonly=True)
    franquicia_id = fields.Many2one("atc.franquicia", string="Franquicia", readonly=True)
    zona_id = fields.Many2one("atc.zona", string="Zona")
    origen = fields.Selection([
        ("conocido", "Ya conocido"),
        ("sugerida", "Sugerida, revisar"),
        ("sin_zona", "Sin zona"),
        ("manual", "Elegida por ATC"),
    ], string="Estado", readonly=True)
    ordenes = fields.Integer(string="Órdenes", readonly=True)

    def write(self, vals):
        if "zona_id" in vals:
            vals = dict(vals, origen="manual" if vals["zona_id"] else "sin_zona")
        return super().write(vals)


class AtcAsignacionZona(models.Model):
    _name = "atc.asignacion.zona"
    _description = "Zona de un lote de asignación"
    _order = "ordenes desc, nombre"

    lote_id = fields.Many2one(
        "atc.asignacion.lote", required=True, ondelete="cascade", index=True)
    clave = fields.Char(readonly=True, index=True)
    nombre = fields.Char(string="Zona", readonly=True)
    zona_id = fields.Many2one("atc.zona", string="Zona de Odoo", readonly=True)
    franquicias = fields.Char(string="Franquicia", readonly=True)
    sectores = fields.Char(string="Sectores", readonly=True)
    ordenes = fields.Integer(string="Órdenes", readonly=True)
    propias = fields.Integer(
        string="Propias", readonly=True,
        help="Órdenes de la zona vendidas por un contratista.")
    antiguedad_max = fields.Integer(
        string="Días", readonly=True, help="Antigüedad de la orden más antigua de la zona.")
    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista",
        help="Vacío = se reparte según el criterio de equidad.")
    sugerido = fields.Boolean(
        string="Sugerido", compute="_compute_sugerido",
        help="Es el contratista con el que quedó esta zona la última vez.")

    @api.depends("contratista_id", "zona_id.contratista_sugerido_id")
    def _compute_sugerido(self):
        for z in self:
            z.sugerido = bool(z.contratista_id) \
                and z.contratista_id == z.zona_id.contratista_sugerido_id


class AtcAsignacionContratista(models.Model):
    _name = "atc.asignacion.contratista"
    _description = "Contratista dentro de un lote de asignación"
    _order = "contratista_id"

    lote_id = fields.Many2one(
        "atc.asignacion.lote", required=True, ondelete="cascade", index=True)
    contratista_id = fields.Many2one(
        "atc.contratista", string="Contratista", required=True, readonly=True,
        ondelete="cascade")
    participa = fields.Boolean(string="Participa", default=True)
    abiertas = fields.Integer(
        string="Abiertas", readonly=True,
        help="Pendientes, asignadas y visitas por garantía al analizar el archivo.")
    propias = fields.Integer(string="Ventas propias", compute="_compute_totales")
    en_lote = fields.Integer(string="En este lote", compute="_compute_totales")
    carga_total = fields.Integer(string="Carga total", compute="_compute_totales")
    zonas = fields.Integer(string="Zonas", compute="_compute_totales")

    @api.depends("abiertas", "lote_id.linea_ids.contratista_id",
                 "lote_id.linea_ids.vendedor", "lote_id.linea_ids.grupo_clave")
    def _compute_totales(self):
        for fila in self:
            lineas = fila.lote_id.linea_ids
            nombre = _norm(fila.contratista_id.name)
            suyas = lineas.filtered(lambda l: l.contratista_id == fila.contratista_id)
            fila.propias = len(lineas.filtered(lambda l: _norm(l.vendedor) == nombre))
            fila.en_lote = len(suyas)
            fila.carga_total = fila.abiertas + len(suyas)
            fila.zonas = len(set(suyas.mapped("grupo_clave")))
