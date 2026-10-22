def migrate(cr, version):
    """Fecha en que se marcó no realizada: la del último cambio de estado a
    'No realizada' en el chatter; si no hay, la última modificación."""
    cr.execute("""
        UPDATE atc_visita v SET fecha_no_realizada = sub.fecha
          FROM (SELECT m.res_id, max(m.date) AS fecha
                  FROM mail_tracking_value t
                  JOIN mail_message m ON m.id = t.mail_message_id
                  JOIN ir_model_fields f ON f.id = t.field_id
                 WHERE m.model = 'atc.visita' AND f.model = 'atc.visita'
                   AND f.name = 'estado' AND t.new_value_char = 'No realizada'
                 GROUP BY m.res_id) sub
         WHERE sub.res_id = v.id AND v.fecha_no_realizada IS NULL
    """)
    cr.execute("""
        UPDATE atc_visita SET fecha_no_realizada = write_date
         WHERE estado = 'no_realizada' AND fecha_no_realizada IS NULL
    """)
