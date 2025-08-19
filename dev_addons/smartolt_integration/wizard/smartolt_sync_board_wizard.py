# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SmartOLTSyncBoardWizard(models.TransientModel):
    _name = 'smartolt.sync.board.wizard'
    _description = 'Wizard para Sincronizar ONUs por Board'

    olt_id = fields.Many2one('smartolt.olt', string='OLT', required=True)
    olt_olt_id = fields.Char('ID del OLT', required=True)
    board = fields.Integer('Board', required=True, help='Número del board del OLT')

    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto"""
        res = super().default_get(fields_list)
        if self.env.context.get('default_olt_id'):
            olt = self.env['smartolt.olt'].browse(self.env.context.get('default_olt_id'))
            res['olt_id'] = olt.id
            res['olt_olt_id'] = olt.olt_id
        return res

    def action_sync_onus_by_board(self):
        """Sincroniza ONUs del board específico"""
        try:
            if not self.board:
                raise UserError(_('Debe especificar un número de board'))
            
            # Llamar al método de sincronización del modelo de ONUs
            onu_model = self.env['smartolt.onu']
            return onu_model.sync_onus_by_board(int(self.olt_olt_id), self.board)
            
        except Exception as e:
            raise UserError(_('Error sincronizando ONUs del board %s: %s') % (self.board, str(e)))
