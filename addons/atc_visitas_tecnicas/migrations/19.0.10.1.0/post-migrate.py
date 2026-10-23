import json

PARAM_MAPEO = "atc_visitas_tecnicas.import_instalaciones_mapeo"
NUEVOS = {"ESTATUS ORDEN SERVICIO": "estatus",
          "FECHA FINALIZACION": "fecha_finalizacion"}


def migrate(cr, version):
    """Estas columnas del export se ignoraban al importar y el mapeo
    recordado lo guardó así: ahora se sugieren."""
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s",
               (PARAM_MAPEO,))
    fila = cr.fetchone()
    if not fila:
        return
    try:
        mapeo = json.loads(fila[0] or "{}")
    except ValueError:
        return
    cambios = {k: v for k, v in NUEVOS.items() if mapeo.get(k) == ""}
    if cambios:
        mapeo.update(cambios)
        cr.execute("UPDATE ir_config_parameter SET value = %s WHERE key = %s",
                   (json.dumps(mapeo, ensure_ascii=False), PARAM_MAPEO))
