# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SmartOLTSyncPortWizard(models.TransientModel):
    _name = 'smartolt.sync.port.wizard'
    _description = 'Wizard para Sincronizar ONUs por Puerto'

    olt_id = fields.Many2one('smartolt.olt', string='OLT', required=True)
    olt_olt_id = fields.Char('ID del OLT', required=True)
    board = fields.Integer('Board', required=True, help='Número del board del OLT')
    port = fields.Integer('Puerto PON', required=True, help='Número del puerto PON')

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto"""
        res = super().default_get(fields_list)
        if self.env.context.get('default_olt_id'):
            olt = self.env['smartolt.olt'].browse(self.env.context.get('default_olt_id'))
            res['olt_id'] = olt.id
            res['olt_olt_id'] = olt.olt_id
        return res

    def action_sync_onus_by_port(self):
        """Sincroniza ONUs del puerto específico"""
        try:
            if not self.board:
                raise UserError(_('Debe especificar un número de board'))
            if not self.port:
                raise UserError(_('Debe especificar un número de puerto'))
            
            # Llamar al método de sincronización del modelo de ONUs
            onu_model = self.env['smartolt.onu']
            return onu_model.sync_onus_by_port(int(self.olt_olt_id), self.board, self.port)
            
        except Exception as e:
            raise UserError(_('Error sincronizando ONUs del board %s, puerto %s: %s') % (self.board, self.port, str(e)))
