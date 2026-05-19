from odoo import models, fields, api


class NocTarea(models.Model):
    _name = 'noc.tarea'
    _description = 'Actividad / Tarea NOC'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Título', required=True, tracking=True)
    descripcion = fields.Html(string='Descripción')
    employee_id = fields.Many2one(
        'hr.employee', string='Responsable', index=True, tracking=True)
    date_start = fields.Datetime(
        string='Fecha Inicio', required=True, default=fields.Datetime.now, tracking=True)
    date_stop = fields.Datetime(string='Fecha Fin', tracking=True)
    allday = fields.Boolean(string='Todo el día', default=False)
    tipo = fields.Selection([
        ('tarea', 'Tarea'),
        ('actividad', 'Actividad'),
        ('incidente', 'Incidente'),
        ('mantenimiento', 'Mantenimiento'),
        ('cambio', 'Cambio'),
    ], string='Tipo', required=True, default='tarea', tracking=True)
    estado = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('en_progreso', 'En Progreso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ], string='Estado', default='pendiente', required=True, tracking=True)
    prioridad = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Alta'),
        ('2', 'Crítica'),
    ], string='Prioridad', default='0')
    guardia_id = fields.Many2one(
        'noc.guardia', string='Guardia Asociada',
        help='Guardia NOC a la que pertenece esta actividad')
    departamento_id = fields.Many2one(
        'noc.departamento', string='Departamento', index=True, tracking=True)
    tag_ids = fields.Many2many('noc.tag', string='Etiquetas')
    color = fields.Integer(compute='_compute_color', store=True)

    @api.depends('tipo')
    def _compute_color(self):
        color_map = {
            'tarea': 4,
            'actividad': 2,
            'incidente': 1,
            'mantenimiento': 3,
            'cambio': 6,
        }
        for rec in self:
            rec.color = color_map.get(rec.tipo, 0)
