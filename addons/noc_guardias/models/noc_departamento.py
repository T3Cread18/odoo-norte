from odoo import models, fields


class NocDepartamento(models.Model):
    _name = 'noc.departamento'
    _description = 'Departamento NOC'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    descripcion = fields.Text(string='Descripción')
    color = fields.Integer(string='Color', default=0)
