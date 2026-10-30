import re
from datetime import timedelta

from odoo import SUPERUSER_ID, api
from odoo.tools import html2plaintext

ETIQUETA = "Visita por garantía"
_MOTIVO = re.compile(r"Visita por garantía \(instalada .*?\):\s*(.*)", re.S)


def migrate(cr, version):
    """Rellena atc.visita.garantia con las garantías anteriores a este
    modelo, a partir del seguimiento del campo estado en el chatter. El
    motivo sale del mensaje que publica _pasar_a_garantia."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Garantia = env["atc.visita.garantia"]
    if Garantia.search_count([]):
        return
    cr.execute("""
        SELECT m.res_id, m.id, m.date, m.author_id,
               t.old_value_char, t.new_value_char
          FROM mail_tracking_value t
          JOIN mail_message m ON m.id = t.mail_message_id
          JOIN ir_model_fields f ON f.id = t.field_id
         WHERE m.model = 'atc.visita' AND f.model = 'atc.visita'
           AND f.name = 'estado'
           AND (t.old_value_char = %s OR t.new_value_char = %s)
         ORDER BY m.res_id, m.date, m.id
    """, (ETIQUETA, ETIQUETA))
    cambios = cr.fetchall()
    root = env.ref("base.partner_root").id
    abiertas = {}
    for res_id, msg_id, fecha, autor, viejo, nuevo in cambios:
        visita = env["atc.visita"].with_context(active_test=False).browse(res_id).exists()
        if not visita:
            continue
        if nuevo == ETIQUETA:
            # El mensaje con el motivo se publica justo después del cambio
            motivo = env["mail.message"].search([
                ("model", "=", "atc.visita"), ("res_id", "=", res_id),
                ("body", "ilike", "Visita por garantía (instalada"),
                ("date", ">=", fecha - timedelta(minutes=2)),
                ("date", "<=", fecha + timedelta(minutes=2)),
            ], limit=1)
            m = _MOTIVO.search(html2plaintext(motivo.body or "")) if motivo else None
            texto = m.group(1).strip() if m else False
            abiertas[res_id] = Garantia.create({
                "visita_id": res_id,
                "contratista_id": visita.contratista_id.id,
                "fecha_inicio": fecha,
                "motivo": texto,
                "automatica": autor == root,
            })
        elif viejo == ETIQUETA and res_id in abiertas:
            usuario = env["res.users"].with_context(active_test=False).search(
                [("partner_id", "=", autor)], limit=1) if autor else env["res.users"]
            if nuevo != "Realizada":
                resultado = "cambio_estado"
            elif autor == root:
                resultado = "recuperada"
            else:
                resultado = "atendida"
            abiertas.pop(res_id).write({
                "resultado": resultado, "fecha_cierre": fecha,
                "cerrada_por_id": usuario.id,
            })
    # Las que siguen en garantía: datos exactos de la orden
    for res_id, g in abiertas.items():
        v = g.visita_id
        if v.estado == "garantia":
            g.write({"fecha_inicio": v.garantia_desde or g.fecha_inicio,
                     "motivo": v.garantia_motivo or g.motivo,
                     "automatica": v.garantia_automatica})
    # Órdenes en garantía sin rastro en el chatter
    for v in env["atc.visita"].search([("estado", "=", "garantia"),
                                       ("garantia_ids", "=", False)]):
        v._abrir_historial_garantia()
