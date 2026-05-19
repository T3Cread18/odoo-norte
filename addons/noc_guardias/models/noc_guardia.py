from odoo import models, fields, api


class NocGuardia(models.Model):
    _name = 'noc.guardia'
    _description = 'Guardia NOC'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Ingeniero', required=True, index=True, tracking=True)
    date_start = fields.Datetime(string='Inicio de Guardia', required=True, tracking=True)
    date_stop = fields.Datetime(string='Fin de Guardia', required=True, tracking=True)
    turno = fields.Selection([
        ('manana', 'Mañana (7am - 3pm)'),
        ('tarde', 'Tarde (3pm - 11pm)'),
        ('noche', 'Noche (11pm - 7am)'),
        ('completo', '24 Horas'),
        ('personalizado', 'Personalizado'),
    ], string='Turno', required=True, default='manana', tracking=True)
    allday = fields.Boolean(compute='_compute_allday', store=True)
    notas = fields.Text(string='Notas')
    tarea_ids = fields.One2many('noc.tarea', 'guardia_id', string='Actividades / Tareas')
    color = fields.Integer(compute='_compute_color', store=True)

    @api.depends('employee_id', 'turno', 'date_start')
    def _compute_name(self):
        turno_labels = {
            'manana': 'Mañana',
            'tarde': 'Tarde',
            'noche': 'Noche',
            'completo': '24h',
            'personalizado': 'Personalizado',
        }
        for rec in self:
            empleado = rec.employee_id.name or 'Sin asignar'
            turno = turno_labels.get(rec.turno, '')
            rec.name = f'{empleado} — {turno}'

    @api.depends('turno')
    def _compute_allday(self):
        for rec in self:
            rec.allday = rec.turno == 'completo'

    @api.depends('turno')
    def _compute_color(self):
        colores = {
            'manana': 2,
            'tarde': 3,
            'noche': 6,
            'completo': 1,
            'personalizado': 4,
        }
        for rec in self:
            rec.color = colores.get(rec.turno, 0)
