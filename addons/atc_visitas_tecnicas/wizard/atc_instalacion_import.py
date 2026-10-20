import base64
import csv
import datetime
import io
import json
import logging
import re
import unicodedata
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Campos a los que se puede mapear una columna del archivo, en el orden en
# que se muestran en la vista previa.
CAMPOS = [
    ("cedula", "Cédula / RIF"),
    ("nombre", "Nombre / razón social"),
    ("contratista", "Contratista"),
    ("tipo_servicio", "Tipo de servicio"),
    ("telefono_movil", "Teléfono móvil"),
    ("telefono_fijo", "Teléfono fijo"),
    ("direccion", "Dirección"),
    ("zona", "Zona"),
    ("antiguedad", "Antigüedad (días)"),
    ("fecha_asignacion", "Fecha de asignación"),
]
ETIQUETAS = dict(CAMPOS)
OBLIGATORIOS = ("cedula", "nombre")

# Encabezados que se reconocen solos (normalizados: mayúsculas, sin acentos
# ni puntos). El mapeo que el usuario elige se recuerda en PARAM_MAPEO y
# tiene prioridad sobre estos.
ALIAS = {
    "tipo_servicio": ["TIPO SERVICIO", "TIPO DE SERVICIO", "SERVICIO"],
    "cedula": ["RIF", "CEDULA", "CI", "RIF CEDULA", "CEDULA RIF"],
    "nombre": ["RAZON SOCIAL", "NOMBRE", "CLIENTE", "NOMBRE CLIENTE"],
    "telefono_movil": ["TLF MOVIL", "TELEFONO MOVIL", "MOVIL", "CELULAR"],
    "telefono_fijo": ["TLF FIJO", "TELEFONO FIJO", "FIJO"],
    "antiguedad": ["ANTIGUEDAD", "DIAS"],
    "contratista": ["TECNICO", "CONTRATISTA"],
    "direccion": ["REFERENCIA", "DIRECCION"],
    "zona": ["ZONA", "SECTOR"],
    "fecha_asignacion": ["FECHA ASIGNACION", "FECHA DE ASIGNACION"],
}
PARAM_MAPEO = "atc_visitas_tecnicas.import_instalaciones_mapeo"
# Campo de la orden que actualiza cada dato del archivo cuando la orden ya
# existe (abierta, misma cédula).
ACTUALIZABLES = {
    "tipo_servicio": "tipo_servicio_id",
    "contratista": "contratista_id",
    "telefono_movil": "telefono_movil",
    "telefono_fijo": "telefono_fijo",
    "direccion": "direccion",
}

ESTADOS_ABIERTOS = ("pendiente", "asignada")
FILAS_PREVIA = 5


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
    if isinstance(val, float) and val.is_integer():
        val = int(val)
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


def leer_fecha(val):
    """Fecha de una celda: ISO (así se guardan las fechas de Excel), o
    dd/mm/aaaa, dd-mm-aaaa, dd/mm/aa. None si no hay o no se entiende."""
    txt = _limpiar(val)
    if not txt:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.datetime.strptime(txt[:10], fmt).date()
        except ValueError:
            continue
    return None


def _celda_json(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()[:10]
    if isinstance(val, (int, float, str)) or val is None:
        return val
    return str(val)


class AtcInstalacionImport(models.TransientModel):
    _name = "atc.instalacion.import"
    _description = "Importar instalaciones pendientes desde Excel"

    archivo = fields.Binary(string="Archivo (.xlsx, .xls o .csv)", required=True)
    nombre_archivo = fields.Char(string="Nombre del archivo")
    fecha_reporte = fields.Date(
        string="Fecha del reporte", required=True,
        default=fields.Date.context_today,
        help="Día en que se generó el reporte. Si no hay columna de fecha de "
             "asignación, se calcula como esta fecha menos la ANTIGÜEDAD.")
    state = fields.Selection(
        [("input", "Archivo"), ("mapeo", "Columnas"), ("done", "Resultado")],
        default="input")
    hoja = fields.Char(string="Hoja", readonly=True)
    fila_encabezado = fields.Integer(
        string="Fila de encabezados",
        help="Número de fila (como en Excel) donde están los títulos de las "
             "columnas. Se detecta solo; cámbiala y pulsa 'Volver a leer' si "
             "no es la correcta.")
    datos = fields.Text(help="Filas del archivo bajo el encabezado, en JSON.")
    total_filas = fields.Integer(string="Filas con datos", readonly=True)
    linea_ids = fields.One2many(
        "atc.instalacion.import.columna", "wizard_id", string="Columnas")
    vista_previa = fields.Html(
        string="Vista previa", compute="_compute_vista_previa",
        sanitize=False)
    resultado = fields.Text(string="Resultado", readonly=True)

    # ------------------------------------------------------------------
    # Lectura del archivo
    # ------------------------------------------------------------------
    def _leer_hojas(self):
        """[(nombre_hoja, filas)] con los valores crudos de cada celda."""
        data = base64.b64decode(self.archivo)
        nombre = (self.nombre_archivo or "").lower()
        try:
            if nombre.endswith(".csv"):
                return [("CSV", self._leer_csv(data))]
            if nombre.endswith(".xls"):
                return self._leer_xls(data)
            return self._leer_xlsx(data)
        except UserError:
            raise
        except Exception as exc:
            raise UserError(self.env._(
                "No se pudo leer el archivo: %s") % exc)

    def _leer_xlsx(self, data):
        import openpyxl
        wb = openpyxl.load_workbook(
            io.BytesIO(data), data_only=True, read_only=True)
        hojas = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)])
                 for ws in wb.worksheets]
        wb.close()
        return hojas

    def _leer_xls(self, data):
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        hojas = []
        for sh in wb.sheets():
            filas = []
            for r in range(sh.nrows):
                fila = []
                for c in range(sh.ncols):
                    celda = sh.cell(r, c)
                    if celda.ctype == xlrd.XL_CELL_DATE:
                        fila.append(xlrd.xldate_as_datetime(
                            celda.value, wb.datemode))
                    else:
                        fila.append(celda.value if celda.value != "" else None)
                filas.append(fila)
            hojas.append((sh.name, filas))
        return hojas

    def _leer_csv(self, data):
        try:
            texto = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = data.decode("latin-1")
        try:
            dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        return [[c if c != "" else None for c in fila]
                for fila in csv.reader(io.StringIO(texto), dialecto)]

    # ------------------------------------------------------------------
    # Mapeo de columnas
    # ------------------------------------------------------------------
    def _mapeo_recordado(self):
        try:
            return json.loads(self.env["ir.config_parameter"].sudo().get_param(
                PARAM_MAPEO) or "{}")
        except ValueError:
            return {}

    def _sugerir_campo(self, encabezado, recordado):
        clave = _norm(encabezado)
        if not clave:
            return False
        if clave in recordado:
            return recordado[clave] or False
        for campo, alias in ALIAS.items():
            if clave in alias:
                return campo
        return False

    def _detectar_encabezado(self, hojas, recordado):
        """(hoja, índice de fila) del encabezado: la primera fila, en las 20
        primeras de cada hoja, con más títulos reconocidos (mínimo 2). Si no
        hay, la primera fila no vacía de la primera hoja."""
        mejor = None
        for nombre, filas in hojas:
            for i, fila in enumerate(filas[:20]):
                puntos = sum(1 for c in fila
                             if self._sugerir_campo(c, recordado))
                if puntos >= 2 and (mejor is None or puntos > mejor[0]):
                    mejor = (puntos, nombre, i)
        if mejor:
            return mejor[1], mejor[2]
        nombre, filas = hojas[0]
        for i, fila in enumerate(filas):
            if any(_limpiar(c) for c in fila):
                return nombre, i
        raise UserError(self.env._("El archivo está vacío."))

    def _cargar(self, hoja=None, indice=None):
        """Lee el archivo y prepara las líneas de mapeo. Sin hoja/índice,
        detecta el encabezado."""
        self.ensure_one()
        if not self.archivo:
            raise UserError(self.env._("Debes adjuntar un archivo."))
        hojas = self._leer_hojas()
        recordado = self._mapeo_recordado()
        if hoja is None:
            hoja, indice = self._detectar_encabezado(hojas, recordado)
        filas = dict(hojas).get(hoja) or hojas[0][1]
        if indice >= len(filas):
            raise UserError(self.env._(
                "La hoja solo tiene %s filas.") % len(filas))
        encabezado = filas[indice]
        cuerpo = [f for f in filas[indice + 1:] if any(_limpiar(c) for c in f)]
        ancho = max([len(encabezado)] + [len(f) for f in cuerpo])

        lineas, usados = [], set()
        for col in range(ancho):
            titulo = _limpiar(encabezado[col]) if col < len(encabezado) else ""
            valores = [_limpiar(f[col]) for f in cuerpo if col < len(f)]
            valores = [v for v in valores if v]
            if not titulo and not valores:
                continue
            campo = self._sugerir_campo(titulo, recordado)
            if campo in usados:
                campo = False
            usados.add(campo)
            lineas.append((0, 0, {
                "indice": col,
                "columna": titulo or self.env._("(columna %s sin título)") % (col + 1),
                "ejemplo": " | ".join(valores[:3])[:120],
                "campo": campo,
            }))
        self.linea_ids.unlink()
        self.write({
            "state": "mapeo",
            "hoja": hoja,
            "fila_encabezado": indice + 1,
            "datos": json.dumps([[_celda_json(c) for c in f] for f in cuerpo]),
            "total_filas": len(cuerpo),
            "linea_ids": lineas,
            "resultado": False,
        })

    def _mapeo(self):
        """{campo: índice de columna}; valida obligatorios y duplicados."""
        mapeo = {}
        for linea in self.linea_ids.filtered("campo"):
            if linea.campo in mapeo:
                otra = self.linea_ids.filtered(
                    lambda l: l.indice == mapeo[linea.campo])
                raise UserError(self.env._(
                    "Las columnas «%(a)s» y «%(b)s» están mapeadas al mismo "
                    "campo «%(campo)s».", a=otra.columna, b=linea.columna,
                    campo=ETIQUETAS[linea.campo]))
            mapeo[linea.campo] = linea.indice
        faltan = [ETIQUETAS[c] for c in OBLIGATORIOS if c not in mapeo]
        if faltan:
            raise UserError(self.env._(
                "Falta mapear: %s.") % ", ".join(faltan))
        return mapeo

    def _filas(self, mapeo, limite=None):
        """[(nº de fila en el archivo, dict normalizado)]."""
        cuerpo = json.loads(self.datos or "[]")
        primera = self.fila_encabezado + 1
        res = []
        for n, f in enumerate(cuerpo[:limite] if limite else cuerpo):
            def get(campo):
                i = mapeo.get(campo)
                return f[i] if i is not None and i < len(f) else None

            cedula = normalizar_cedula(get("cedula")) if get("cedula") else ""
            nombre = _limpiar(get("nombre"))
            if not cedula and not nombre:
                continue
            antig = re.search(r"\d+", _limpiar(get("antiguedad")))
            res.append((primera + n, {
                "tipo_servicio": _limpiar(get("tipo_servicio")),
                "cedula": cedula,
                "nombre": nombre,
                "telefono_movil": normalizar_telefono(get("telefono_movil")),
                "telefono_fijo": normalizar_telefono(get("telefono_fijo")),
                "antiguedad": int(antig.group()) if antig else None,
                "fecha_asignacion": leer_fecha(get("fecha_asignacion")),
                "contratista": _limpiar(get("contratista")),
                "direccion": _limpiar(get("direccion")),
                "zona": _limpiar(get("zona")),
            }))
        return res

    def _fecha_asignacion(self, fila):
        if fila["fecha_asignacion"]:
            return fila["fecha_asignacion"]
        return self.fecha_reporte - timedelta(days=fila["antiguedad"] or 0)

    @api.depends("linea_ids.campo", "datos", "fecha_reporte",
                 "fila_encabezado")
    def _compute_vista_previa(self):
        for w in self:
            w.vista_previa = False
            if w.state != "mapeo" or not w.datos:
                continue
            mapeo = {l.campo: l.indice for l in w.linea_ids if l.campo}
            if not mapeo:
                continue
            # Antigüedad y fecha se muestran juntas como la fecha de
            # asignación resultante.
            campos = [c for c, _ in CAMPOS if c in mapeo
                      and c not in ("antiguedad", "fecha_asignacion")]
            cab = Markup("").join(
                Markup("<th>%s</th>") % ETIQUETAS[c] for c in campos)
            cab += Markup("<th>%s</th>") % w.env._("Asignada el")
            cuerpo = Markup("")
            for _n, fila in w._filas(mapeo, limite=FILAS_PREVIA):
                celdas = Markup("").join(
                    Markup("<td>%s</td>") % (fila[c] or "") for c in campos)
                fecha = w._fecha_asignacion(fila) if w.fecha_reporte else ""
                celdas += Markup("<td>%s</td>") % (fecha or "")
                cuerpo += Markup("<tr>%s</tr>") % celdas
            w.vista_previa = Markup(
                '<table class="table table-sm table-striped o_list_table">'
                "<thead><tr>%s</tr></thead><tbody>%s</tbody></table>"
            ) % (cab, cuerpo)

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
    # Importación
    # ------------------------------------------------------------------
    def _importar(self):
        """Crea/actualiza las instalaciones y devuelve el resumen."""
        mapeo = self._mapeo()
        filas = self._filas(mapeo)
        if not filas:
            raise UserError(self.env._("No hay filas con cédula o nombre."))

        Visita = self.env["atc.visita"]
        Contratista = self.env["atc.contratista"]
        Servicio = self.env["atc.tipo.servicio"]
        Zona = self.env["atc.zona"]
        zonas = sorted(
            ((re.sub(r"[^A-Z0-9]+", " ", _norm(z.name)).strip(), z)
             for z in Zona.search([])),
            key=lambda t: -len(t[0]))
        zonas_por_nombre = {_norm(z.name): z for _c, z in zonas}
        cache_c, cache_s = {}, {}

        abiertas = Visita.search([("tipo_orden", "=", "instalacion"),
                                  ("estado", "in", ESTADOS_ABIERTOS)])
        por_cedula = {}
        for v in abiertas:
            if v.cedula:
                por_cedula.setdefault(v.cedula, v)
        # Instalaciones ya cerradas o archivadas: la más reciente por cédula.
        # Si siguen en el reporte, las realizadas/archivadas se omiten y las
        # no realizadas se reabren, en vez de crear una orden duplicada.
        cedulas = {f["cedula"] for _n, f in filas if f["cedula"]}
        cerradas = {}
        for v in Visita.with_context(active_test=False).search(
                [("tipo_orden", "=", "instalacion"),
                 ("cedula", "in", list(cedulas - set(por_cedula))),
                 "|", ("estado", "not in", ESTADOS_ABIERTOS),
                 ("active", "=", False)],
                order="id desc"):
            cerradas.setdefault(v.cedula, v)

        actualizadas = sin_cambios = con_zona = 0
        vistas, errores, repetidas = set(), [], []
        omitidas, reabiertas = [], []
        nuevas, cedulas_nuevas = [], set()   # [(nº fila, vals, teléfono)]
        for n, fila in filas:
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
            cedula = fila["cedula"]
            existente = por_cedula.get(cedula) if cedula else None
            if existente:
                vistas.add(existente.id)
                # Solo columnas mapeadas y con valor: una celda vacía o una
                # columna que no viene no borra lo que ya tiene la orden.
                cambios = {}
                for dato, campo in ACTUALIZABLES.items():
                    nuevo = vals[campo]
                    if dato not in mapeo or not nuevo:
                        continue
                    actual = existente[campo]
                    if (actual.id if hasattr(actual, "id") else actual) != nuevo:
                        cambios[campo] = nuevo
                if cambios:
                    existente.write(cambios)
                    actualizadas += 1
                else:
                    sin_cambios += 1
                continue
            cerrada = cerradas.get(cedula) if cedula else None
            if cerrada:
                if cerrada.active and cerrada.estado == "no_realizada":
                    cambios = {campo: vals[campo]
                               for dato, campo in ACTUALIZABLES.items()
                               if dato in mapeo and vals[campo]}
                    cambios["estado"] = "asignada" if (
                        cambios.get("contratista_id") or cerrada.contratista_id
                        or cerrada.tecnico_asignado_ids) else "pendiente"
                    cerrada.write(cambios)
                    cerrada.message_post(body=self.env._(
                        "Reabierta al importar el reporte del %s: el cliente "
                        "sigue pendiente de instalación.")
                        % fields.Date.to_string(self.fecha_reporte))
                    reabiertas.append(cerrada)
                else:
                    omitidas.append((n, cerrada))
                del cerradas[cedula]
                continue
            if cedula and cedula in cedulas_nuevas:
                repetidas.append(n)
                continue
            cedulas_nuevas.add(cedula)

            fecha_asig = self._fecha_asignacion(fila)
            zona = zonas_por_nombre.get(_norm(fila["zona"]), Zona) \
                if fila["zona"] else Zona
            if not zona:
                zona = self._zona_por_direccion(fila["direccion"], zonas)
            con_zona += bool(zona)
            vals.update({
                "tipo_orden": "instalacion",
                "cedula": cedula or False,
                "nombre": fila["nombre"],
                "fecha": fecha_asig,
                "fecha_asignacion": fecha_asig,
                "zona_id": zona.id,
                "tecnico_id": False,
                "estado": "asignada" if contratista else "pendiente",
            })
            nuevas.append((n, vals, fila["telefono_movil"]))

        creadas = self._crear_en_lote(nuevas, errores)
        for orden, telefono in creadas:
            partner = orden.cliente_id.sudo()
            if partner and not partner.phone and telefono:
                partner.phone = telefono

        fuera = len(abiertas.filtered(lambda v: v.id not in vistas))
        lineas = [
            self.env._("• Filas con datos: %s") % len(filas),
            self.env._("• Instalaciones creadas: %(n)s (con zona: %(z)s)",
                       n=len(creadas), z=con_zona),
            self.env._("• Actualizadas (contratista, servicio, teléfonos o "
                       "dirección): %s") % actualizadas,
            self.env._("• Sin cambios: %s") % sin_cambios,
            self.env._("• Contratistas en el archivo: %s") % len(cache_c),
            self.env._("• Instalaciones abiertas que NO vienen en este "
                       "archivo: %s") % fuera,
        ]
        if reabiertas:
            lineas.append(self.env._(
                "• No realizadas que siguen en el reporte, reabiertas: %s")
                % len(reabiertas))
            lineas += ["    %s (%s)" % (v.nombre, v.cedula) for v in reabiertas]
        if omitidas:
            lineas.append(self.env._(
                "• Ya realizadas o archivadas en Odoo, omitidas (revisar si "
                "hay que reinstalar): %s") % len(omitidas))
            lineas += [
                "    " + self.env._(
                    "Fila %(n)s: %(nombre)s (%(cedula)s) — %(estado)s",
                    n=n, nombre=v.nombre, cedula=v.cedula,
                    estado=dict(v._fields["estado"]._description_selection(
                        self.env))[v.estado]
                    + ("" if v.active else self.env._(", archivada")))
                for n, v in omitidas]
        if repetidas:
            lineas.append(self.env._(
                "• Cédula repetida en el archivo (se usó la primera), "
                "filas: %s") % ", ".join(map(str, repetidas)))
        if errores:
            lineas.append(self.env._("• Filas con error (no importadas): %s")
                          % len(errores))
            lineas += ["    %s" % e for e in errores]
        return "\n".join(lineas)

    def _crear_en_lote(self, nuevas, errores):
        """Crea todas de una vez; si alguna falla, las crea una por una para
        saltar solo las filas con error."""
        Visita = self.env["atc.visita"]
        if not nuevas:
            return []
        try:
            with self.env.cr.savepoint():
                ordenes = Visita.create([vals for _n, vals, _t in nuevas])
            return list(zip(ordenes, [t for _n, _v, t in nuevas]))
        except Exception:
            _logger.info("Import instalaciones: el lote falló, se crea fila a fila")
        creadas = []
        for n, vals, telefono in nuevas:
            try:
                with self.env.cr.savepoint():
                    creadas.append((Visita.create(vals), telefono))
            except Exception as exc:
                msg = exc.args[0] if exc.args else str(exc)
                errores.append(self.env._("Fila %(n)s: %(msg)s", n=n, msg=msg))
        return creadas

    def _recordar_mapeo(self):
        recordado = self._mapeo_recordado()
        for linea in self.linea_ids:
            clave = _norm(linea.columna)
            if clave:
                recordado[clave] = linea.campo or ""
        self.env["ir.config_parameter"].sudo().set_param(
            PARAM_MAPEO, json.dumps(recordado, ensure_ascii=False))

    def _reabrir(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": self.env._("Importar instalaciones"),
        }

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def action_cargar(self):
        self._cargar()
        return self._reabrir()

    def action_releer(self):
        self.ensure_one()
        if self.fila_encabezado < 1:
            raise UserError(self.env._("La fila de encabezados empieza en 1."))
        self._cargar(hoja=self.hoja, indice=self.fila_encabezado - 1)
        return self._reabrir()

    def action_volver(self):
        self.linea_ids.unlink()
        self.write({"state": "input", "resultado": False, "datos": False})
        return self._reabrir()

    def action_probar(self):
        """Simula la importación y deshace todo; muestra el resumen."""
        self.ensure_one()

        class _Simulacion(Exception):
            pass

        try:
            with self.env.cr.savepoint():
                resumen = self._importar()
                raise _Simulacion()
        except _Simulacion:
            pass
        self.env.invalidate_all()
        self.resultado = self.env._(
            "PRUEBA (no se guardó nada):\n\n%s") % resumen
        return self._reabrir()

    def action_importar(self):
        self.ensure_one()
        resumen = self._importar()
        self._recordar_mapeo()
        _logger.info("Import instalaciones: %s", resumen.replace("\n", " | "))
        self.write({"state": "done",
                    "resultado": self.env._("Importación completada.\n\n")
                    + resumen})
        return self._reabrir()


class AtcInstalacionImportColumna(models.TransientModel):
    _name = "atc.instalacion.import.columna"
    _description = "Columna del archivo a importar"
    _order = "indice"

    wizard_id = fields.Many2one(
        "atc.instalacion.import", required=True, ondelete="cascade")
    indice = fields.Integer(readonly=True)
    columna = fields.Char(string="Columna del archivo", readonly=True)
    ejemplo = fields.Char(string="Valores de ejemplo", readonly=True)
    campo = fields.Selection(
        CAMPOS, string="Importar como",
        help="Vacío = no importar esta columna.")
