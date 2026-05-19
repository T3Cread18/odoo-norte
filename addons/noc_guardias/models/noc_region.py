from odoo import models, fields


class NocRegion(models.Model):
    _name = 'noc.region'
    _description = 'Región NOC'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    descripcion = fields.Text(string='Descripción')
    color = fields.Integer(string='Color', default=0)
    employee_ids = fields.One2many('hr.employee', 'noc_region_id', string='Ingenieros')
    employee_count = fields.Integer(compute='_compute_employee_count', string='N° Ingenieros')

    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.employee_ids)
