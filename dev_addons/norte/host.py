from odoo import models, fields, api
import re

class Host(models.Model):
    _name = 'custom.host'
    _description = 'Host Categorization'

    name = fields.Char(string="Host Name", required=True)
    ip_host_pre = fields.Char(string="Dirección IP Anterior")
    ip_host = fields.Char(string="Dirección IP")
    host_type = fields.Selection([
        ('camera', 'Cámara'),
        ('fingerprint', 'Huellero'),
        ('phone', 'Teléfono IP'),
        ('pc', 'PC'),
        ('other', 'Otro'),
    ], string="Tipo de Host", required=True)
    franchise = fields.Many2one('res.partner', string="Franquicia", domain="[('is_company', '=', True)]")
    description = fields.Text(string="Descripción")
    status = fields.Selection([
        ('active','Activa'),
        ('inactive', 'Inactiva'),
    ])
    user = fields.Char(string="Usuario")
    passw = fields.Char(string="Contraseña")

    @api.constrains('ip_host')
    def _check_ip_host(self):
        ip_regex = r'^(\d{1,3}\.){3}\d{1,3}$'
        for record in self:
            if record.ip_host and not re.match(ip_regex, record.ip_host):
                raise models.ValidationError("La dirección IP no tiene un formato válido.")
    @api.constrains('ip_host_pre')
    def _check_ip_host(self):
        ip_regex = r'^(\d{1,3}\.){3}\d{1,3}$'
        for record in self:
            if record.ip_host_pre and not re.match(ip_regex, record.ip_host_pre):
                raise models.ValidationError("La dirección IP no tiene un formato válido.")