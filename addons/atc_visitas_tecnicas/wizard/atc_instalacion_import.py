import base64
import io
import logging
import re
import unicodedata
from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Encabezados del "Reporte" de órdenes pendientes (normalizados: mayúsculas,
# sin acentos ni puntos).
COLS = {
    "tipo_servicio": ["TIPO SERVICIO", "TIPO DE SERVICIO", "SERVICIO"],
    "rif": ["RIF", "CEDULA", "CI"],
    "nombre": ["RAZON SOCIAL", "NOMBRE", "CLIENTE"],
    "telefono_movil": ["TLF MOVIL", "TELEFONO MOVIL", "MOVIL"],
    "telefono_fijo": ["TLF FIJO", "TELEFONO FIJO", "FIJO"],
    "antiguedad": ["ANTIGUEDAD"],
    "contratista": ["TECNICO", "CONTRATISTA"],
    "direccion": ["REFERENCIA", "DIRECCION"],
}

ESTADOS_ABIERTOS = ("pendiente", "asignada")


def _sin_acentos(txt):
    return "".join(c for c in unicodedata.normalize("NFD", txt)
                   if unicodedata.category(c) != "Mn")


def _norm(val):
    if val is None:
        return ""
    txt = _sin_acentos(str(val)).upper().replace(".", " ")
    return re.sub(r"\s+", " ", txt).strip()


def _limpiar(val):
    """Texto de una celda sin espacios repetidos."""
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def normalizar_cedula(rif):
    """'V-16292774-0' / 'V-09250618' -> '16292774' / '9250618' (formato de
    res.partner.cedula). Los RIF jurídicos (J/G) se dejan como 'J-40880242-5'."""
    txt = _limpiar(rif).upper().replace(" ", "")
    m = re.match(r"^([VEJGP])?-?0*(\d+)(?:-(\d))?$", txt)
    if not m:
        return txt
    letra, numero, digito = m.groups()
    if letra in ("J", "G"):
        return "%s-%s%s" % (letra, numero.zfill(8),
                            "-%s" % digito if digito else "")
    return numero


def normalizar_telefono(val):
    """'4121880078' -> '04121880078'."""
    if val is None or val == "":
        return False
    if isinstance(val, float):
        val = int(val)
    digitos = re.sub(r"\D", "", str(val))
    if not digitos:
        return False
    if len(digitos) == 10 and not digitos.startswith("0"):
        digitos = "0" + digitos
    return digitos


class AtcInstalacionImport(models.TransientModel):
    _name = "atc.instalacion.import"
    _description = "Importar instalaciones pendientes desde Excel"

    archivo = fields.Binary(string="Archivo Excel (.xlsx)", required=True)
    nombre_archivo = fields.Char(string="Nombre del archivo")
    fecha_reporte = fields.Date(
        string="Fecha del reporte", required=True,
        default=fields.Date.context_today,
        help="Día en que se generó el reporte. La fecha de asignación de "
             "cada orden se calcula como esta fecha menos su ANTIGÜEDAD.")
    state = fields.Selection(
        [("input", "Entrada"), ("done", "Resultado")],
        default="input")
    resultado = fields.Text(string="Resultado", readonly=True)

    # ------------------------------------------------------------------
    # Parseo del Excel
    # ------------------------------------------------------------------
    def _map_header(self, row):
        mapping = {}
        for idx, cell in enumerate(row):
            name = _norm(cell)
            for field, aliases in COLS.items():
                if name in aliases:
                    mapping.setdefault(field, idx)
        return mapping

    def _parse(self, data):
        try:
            import openpyxl
        except ImportError:
            raise UserError(self.env._(
                "Falta la librería openpyxl en el servidor."))
        try:
            wb = openpyxl.load_workbook(
                io.BytesIO(data), data_only=True, read_only=True)
        except Exception as exc:
            raise UserError(self.env._(
                "No se pudo leer el archivo Excel: %s") % exc)

        filas = []
        for ws in wb.worksheets:
            header = None
            for raw in ws.iter_rows(values_only=True):
                cells = list(raw)
                if header is None:
                    m = self._map_header(cells)
                    if {"rif", "nombre", "contratista"} <= set(m):
                        header = m
                    continue

                def get(field):
                    i = header.get(field)
                    return cells[i] if i is not None and i < len(cells) else None

                rif = _limpiar(get("rif"))
                nombre = _limpiar(get("nombre"))
                if not rif and not nombre:
                    continue
                antig = re.search(r"\d+", str(get("antiguedad") or ""))
                filas.append({
                    "tipo_servicio": _limpiar(get("tipo_servicio")),
                    "cedula": normalizar_cedula(rif),
                    "nombre": nombre,
                    "telefono_movil": normalizar_telefono(get("telefono_movil")),
                    "telefono_fijo": normalizar_telefono(get("telefono_fijo")),
                    "antiguedad": int(antig.group()) if antig else 0,
                    "contratista": _limpiar(get("contratista")),
                    "direccion": _limpiar(get("direccion")),
                })
            if header:
                break
        wb.close()
        if not filas:
            raise UserError(self.env._(
                "No se encontraron órdenes en el archivo. Verifica que tenga "
                "las columnas RIF, RAZON SOCIAL y TECNICO."))
        return filas

    # ------------------------------------------------------------------
    # Catálogos
    # ------------------------------------------------------------------
    def _buscar_o_crear(self, model, name, cache):
        if not name:
            return model.browse()
        clave = _norm(name)
        if clave not in cache:
            rec = model.with_context(active_test=False).search(
                [("name", "=ilike", name)], limit=1)
            if not rec:
                rec = model.create({"name": name})
            elif not rec.active:
                rec.active = True
            cache[clave] = rec
        return cache[clave]

    def _zona_por_direccion(self, direccion, zonas):
        """Primera zona cuyo nombre aparece como palabra completa en la
        dirección; se prueban primero los nombres más largos para que
        'VILLA ARAURE' gane sobre 'ARAURE'."""
        texto = " %s " % re.sub(r"[^A-Z0-9]+", " ", _norm(direccion))
        for clave, zona in zonas:
            if " %s " % clave in texto:
                return zona
        return self.env["atc.zona"]

    # ------------------------------------------------------------------
    # Acción principal
    # ------------------------------------------------------------------
    def action_importar(self):
        self.ensure_one()
        if not self.archivo:
            raise UserError(self.env._("Debes adjuntar un archivo Excel."))
        filas = self._parse(base64.b64decode(self.archivo))

        Visita = self.env["atc.visita"]
        Contratista = self.env["atc.contratista"]
        Servicio = self.env["atc.tipo.servicio"]
        zonas = sorted(
            ((re.sub(r"[^A-Z0-9]+", " ", _norm(z.name)).strip(), z)
             for z in self.env["atc.zona"].search([])),
            key=lambda t: -len(t[0]))
        cache_c, cache_s = {}, {}

        abiertas = Visita.search([("tipo_orden", "=", "instalacion"),
                                  ("estado", "in", ESTADOS_ABIERTOS)])
        por_cedula = {}
        for v in abiertas:
            if v.cedula:
                por_cedula.setdefault(v.cedula, v)

        creadas = actualizadas = sin_cambios = con_zona = 0
        vistas = set()
        for fila in filas:
            contratista = self._buscar_o_crear(
                Contratista, fila["contratista"], cache_c)
            servicio = self._buscar_o_crear(
                Servicio, fila["tipo_servicio"], cache_s)
            vals = {
                "tipo_servicio_id": servicio.id,
                "contratista_id": contratista.id,
                "telefono_movil": fila["telefono_movil"],
                "telefono_fijo": fila["telefono_fijo"],
                "direccion": fila["direccion"] or False,
            }
            existente = por_cedula.get(fila["cedula"]) if fila["cedula"] else None
            if existente:
                vistas.add(existente.id)
                cambios = {k: v for k, v in vals.items()
                           if (existente[k].id if hasattr(existente[k], "id")
                               else existente[k]) != v}
                if cambios:
                    existente.write(cambios)
                    actualizadas += 1
                else:
                    sin_cambios += 1
                continue

            fecha_asig = self.fecha_reporte - timedelta(days=fila["antiguedad"])
            zona = self._zona_por_direccion(fila["direccion"], zonas)
            con_zona += bool(zona)
            vals.update({
                "tipo_orden": "instalacion",
                "cedula": fila["cedula"] or False,
                "nombre": fila["nombre"],
                "fecha": fecha_asig,
                "fecha_asignacion": fecha_asig,
                "zona_id": zona.id,
                "tecnico_id": False,
                "estado": "asignada" if contratista else "pendiente",
            })
            nueva = Visita.create(vals)
            vistas.add(nueva.id)
            if fila["cedula"]:
                por_cedula[fila["cedula"]] = nueva
            partner = nueva.cliente_id.sudo()
            if partner and not partner.phone and fila["telefono_movil"]:
                partner.phone = fila["telefono_movil"]
            creadas += 1

        fuera = len(abiertas.filtered(lambda v: v.id not in vistas))
        resumen = self.env._(
            "Importación completada.\n\n"
            "• Órdenes en el Excel: %(total)s\n"
            "• Instalaciones creadas: %(creadas)s (con zona detectada: %(con_zona)s)\n"
            "• Actualizadas (contratista, teléfonos o dirección): %(actualizadas)s\n"
            "• Sin cambios: %(sin_cambios)s\n"
            "• Contratistas en el archivo: %(contratistas)s\n"
            "• Instalaciones abiertas que NO vienen en este Excel: %(fuera)s",
            total=len(filas), creadas=creadas, con_zona=con_zona,
            actualizadas=actualizadas, sin_cambios=sin_cambios,
            contratistas=len(cache_c), fuera=fuera)
        _logger.info("Import instalaciones: %s", resumen.replace("\n", " | "))

        self.write({"state": "done", "resultado": resumen})
        return {
            "type": "ir.actions.act_window",
            "res_model": "atc.instalacion.import",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": self.env._("Importar instalaciones"),
        }
