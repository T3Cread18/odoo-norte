import json

PARAM_MAPEO = "atc_visitas_tecnicas.import_instalaciones_mapeo"


def migrate(cr, version):
    """La columna VENDEDOR se ignoraba al importar y el mapeo recordado lo
    guardó así: ahora se sugiere como vendedor."""
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s",
               (PARAM_MAPEO,))
    fila = cr.fetchone()
    if not fila:
        return
    try:
        mapeo = json.loads(fila[0] or "{}")
    except ValueError:
        return
    if mapeo.get("VENDEDOR") == "":
        mapeo["VENDEDOR"] = "vendedor"
        cr.execute("UPDATE ir_config_parameter SET value = %s WHERE key = %s",
                   (json.dumps(mapeo, ensure_ascii=False), PARAM_MAPEO))
