import re

from odoo import api, fields, models

_RE_CEDULA = re.compile(r"^[VEJGP]?-?0*(\d{5,10})")


def normalizar_cedula(cedula):
    """'V-08605834-7', 'V8605834' y '8605834' -> '8605834'. Lo que no parece
    una cédula/RIF (seriales, texto) devuelve False."""
    m = _RE_CEDULA.match(re.sub(r"\s+", "", (cedula or "").upper()))
    return m.group(1) if m else False


class AtcClienteFranquicia(models.Model):
    """Franquicia de cada cliente según TotalNet, por cédula. Se aprende sola
    de las órdenes (importación del reporte o cuando alguien pone la franquicia
    a mano) y se puede cargar entera con el importador estándar de Odoo.
    Sirve para dar franquicia a las órdenes que llegan sin ella (caídas LOS)."""
    _name = "atc.cliente.franquicia"
    _description = "Franquicia del cliente"
    _order = "cedula"
    _rec_name = "cedula"

    cedula = fields.Char(string="Cédula", required=True, index=True,
                         help="Normalizada: solo los dígitos (sin V-, ceros a la izquierda ni dígito verificador).")
    nombre = fields.Char(string="Cliente")
    franquicia_id = fields.Many2one(
        "atc.franquicia", string="Franquicia", required=True, index=True, ondelete="cascade")
    origen = fields.Selection(
        [("orden", "Orden"), ("importacion", "Carga TotalNet")],
        string="Origen", default="importacion")

    _cedula_unica = models.Constraint(
        "UNIQUE(cedula)", "Esa cédula ya tiene franquicia.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("cedula"):
                vals["cedula"] = normalizar_cedula(vals["cedula"]) or vals["cedula"].strip()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("cedula"):
            vals = dict(vals, cedula=normalizar_cedula(vals["cedula"]) or vals["cedula"].strip())
        return super().write(vals)

    @api.model
    def _franquicia_de(self, cedula):
        clave = normalizar_cedula(cedula)
        if not clave:
            return self.env["atc.franquicia"]
        return self.sudo().search([("cedula", "=", clave)], limit=1).franquicia_id

    @api.model
    def _aprender(self, cedula, franquicia, nombre=False):
        clave = normalizar_cedula(cedula)
        if not clave or not franquicia:
            return
        reg = self.sudo().search([("cedula", "=", clave)], limit=1)
        if not reg:
            self.sudo().create({"cedula": clave, "franquicia_id": franquicia.id,
                                "nombre": nombre or False, "origen": "orden"})
        elif reg.franquicia_id != franquicia:
            reg.write({"franquicia_id": franquicia.id, "origen": "orden"})
