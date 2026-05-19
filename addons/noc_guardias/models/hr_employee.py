from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    noc_region_id = fields.Many2one(
        'noc.region', string='Región NOC',
        tracking=True,
        help='Región geográfica asignada al ingeniero NOC')
