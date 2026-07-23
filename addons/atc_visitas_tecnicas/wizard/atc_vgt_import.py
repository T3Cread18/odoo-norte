import base64
import io
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REGION_LABELS = {
    "ANDES": "andes",
    "GENERAL NACIONAL": "general",
}

# Encabezados esperados (se normalizan a mayúsculas sin espacios extra)
COLS = {
    "estado": ["ESTADO"],
    "municipio": ["MUNICIPIO"],
    "nombre": ["NOMBRE"],
    "cantidad_postes": ["CANTIDAD DE POSTES SUPERVISADOS", "CANTIDAD DE POSTES",
                        "POSTES"],
    "codigo": ["CODIGO VGT", "CÓDIGO VGT", "VGT"],
    "fecha_autorizacion": ["FECHA DE AUTORIZACION", "FECHA DE AUTORIZACIÓN",
                           "FECHA"],
    "item": ["ITEM"],
}


class AtcVgtImport(models.TransientModel):
    _name = "atc.vgt.import"
    _description = "Importar catálogo VGT desde Excel"

    archivo = fields.Binary(string="Archivo Excel (.xlsx)", required=True)
    nombre_archivo = fields.Char(string="Nombre del archivo")
    archivar_ausentes = fields.Boolean(
        string="Archivar las VGT que ya no estén en el Excel",
        default=True,
        help="Marca como inactivas (no borra) las VGT existentes cuyo código "
             "no aparezca en el archivo importado.")
    state = fields.Selection(
        [("input", "Entrada"), ("done", "Resultado")],
        default="input")
    resultado = fields.Text(string="Resultado", readonly=True)

    # ------------------------------------------------------------------
    # Parseo del Excel
    # ------------------------------------------------------------------
    def _norm(self, val):
        return (str(val).strip().upper()) if val is not None else ""

    def _to_date(self, val):
        """Convierte una celda a date. Acepta datetime/date o texto común."""
        if not val:
            return False
        if hasattr(val, "date"):
            return val.date()
        if isinstance(val, str):
            import datetime
            txt = val.strip()
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    return datetime.datetime.strptime(txt, fmt).date()
                except ValueError:
                    continue
        return False

    def _pick_sheet(self, wb):
        for ws in wb.worksheets:
            if "AUTORIZ" in ws.title.upper():
                return ws
        return wb.worksheets[0]

    def _map_header(self, row):
        """Devuelve {campo: índice_columna} a partir de una fila de encabezado."""
        mapping = {}
        for idx, cell in enumerate(row):
            name = self._norm(cell)
            if not name:
                continue
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

        ws = self._pick_sheet(wb)
        rows = list(ws.iter_rows(values_only=True))

        header = None
        region = None
        estado = None
        records = {}
        for raw in rows:
            cells = list(raw)
            while cells and cells[-1] is None:
                cells.pop()
            if not cells:
                continue
            # Fila de una sola celda -> posible cabecera de región.
            # Se comprueba SIEMPRE (las regiones pueden aparecer antes o
            # después de la fila de encabezados de columnas).
            filled = [c for c in cells if c not in (None, "")]
            if len(filled) == 1 and isinstance(filled[0], str):
                lbl = self._norm(filled[0])
                if lbl in REGION_LABELS:
                    region = REGION_LABELS[lbl]
                continue
            # Encabezado de columnas
            if header is None:
                m = self._map_header(cells)
                if "codigo" in m and ("nombre" in m or "item" in m):
                    header = m
                continue

            def get(field):
                i = header.get(field)
                return cells[i] if i is not None and i < len(cells) else None

            # Debe tener número de ITEM (si existe la columna)
            item = get("item")
            if header.get("item") is not None and not isinstance(item, (int, float)):
                continue

            est = get("estado")
            if isinstance(est, str) and est.strip() \
                    and not self._norm(est).startswith("PROYECTOS"):
                estado = est.strip()

            codigo = get("codigo")
            codigo = codigo.strip() if isinstance(codigo, str) else ""
            if not codigo:
                continue

            nombre = get("nombre")
            municipio = get("municipio")
            cant = get("cantidad_postes")
            fecha = get("fecha_autorizacion")

            vals = {
                "codigo": codigo,
                "nombre": (nombre.strip() if isinstance(nombre, str) else "") or False,
                "estado": (estado or False),
                "municipio": (municipio.strip()
                              if isinstance(municipio, str) else "") or False,
                "region": region or False,
                "cantidad_postes": int(cant) if isinstance(cant, (int, float)) else 0,
                "fecha_autorizacion": self._to_date(fecha),
            }
            # dedupe: primera aparición gana
            records.setdefault(codigo, vals)

        wb.close()
        if not records:
            raise UserError(self.env._(
                "No se encontraron filas con 'CODIGO VGT' en el archivo. "
                "Verifica que sea el Excel de proyectos autorizados."))
        return records

    # ------------------------------------------------------------------
    # Acción principal
    # ------------------------------------------------------------------
    def _campos_comparar(self):
        return ["nombre", "estado", "municipio", "region",
                "cantidad_postes", "fecha_autorizacion"]

    def action_importar(self):
        self.ensure_one()
        if not self.archivo:
            raise UserError(self.env._("Debes adjuntar un archivo Excel."))
        data = base64.b64decode(self.archivo)
        parsed = self._parse(data)

        Vgt = self.env["atc.vgt"].with_context(active_test=False)
        existentes = {v.codigo: v for v in Vgt.search([])}

        creadas = actualizadas = sin_cambios = reactivadas = 0
        for codigo, vals in parsed.items():
            rec = existentes.get(codigo)
            if not rec:
                Vgt.create(vals)
                creadas += 1
                continue
            cambios = {f: vals[f] for f in self._campos_comparar()
                       if rec[f] != vals[f]}
            if not rec.active:
                cambios["active"] = True
                reactivadas += 1
            if cambios:
                rec.write(cambios)
                if set(cambios) - {"active"}:
                    actualizadas += 1
            else:
                sin_cambios += 1

        archivadas = 0
        codigos_excel = set(parsed)
        if self.archivar_ausentes:
            a_archivar = Vgt.filtered(
                lambda v: v.active and v.codigo not in codigos_excel)
            # recargar por si acaso
            a_archivar = Vgt.search(
                [("active", "=", True), ("codigo", "not in", list(codigos_excel))])
            if a_archivar:
                a_archivar.write({"active": False})
                archivadas = len(a_archivar)

        resumen = self.env._(
            "Importación completada.\n\n"
            "• En el Excel: %(total)s VGT\n"
            "• Creadas: %(creadas)s\n"
            "• Actualizadas: %(actualizadas)s\n"
            "• Reactivadas: %(reactivadas)s\n"
            "• Sin cambios: %(sin_cambios)s\n"
            "• Archivadas (ya no están en el Excel): %(archivadas)s",
            total=len(parsed), creadas=creadas, actualizadas=actualizadas,
            reactivadas=reactivadas, sin_cambios=sin_cambios,
            archivadas=archivadas)
        _logger.info("Import VGT: %s", resumen.replace("\n", " | "))

        self.write({"state": "done", "resultado": resumen})
        return {
            "type": "ir.actions.act_window",
            "res_model": "atc.vgt.import",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": self.env._("Importar VGT"),
        }
