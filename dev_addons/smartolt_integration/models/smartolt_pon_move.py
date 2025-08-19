# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SmartOLTPONMove(models.Model):
    _name = 'smartolt.pon.move'
    _description = 'Registro de Movimientos de PON'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'move_date desc'
    
    # ONU movida
    onu_id = fields.Many2one('smartolt.onu', string='ONU', required=True, ondelete='cascade')
    
    # Origen
    source_olt_id = fields.Many2one('smartolt.olt', string='OLT Origen', required=True)
    source_board = fields.Integer('Board Origen', required=True)
    source_port = fields.Integer('Puerto PON Origen', required=True)
    source_location = fields.Char('Ubicación Origen', compute='_compute_locations', store=True)
    
    # Destino
    target_olt_id = fields.Many2one('smartolt.olt', string='OLT Destino', required=True)
    target_board = fields.Integer('Board Destino', required=True)
    target_port = fields.Integer('Puerto PON Destino', required=True)
    target_location = fields.Char('Ubicación Destino', compute='_compute_locations', store=True)
    
    # Estado del movimiento
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('rolled_back', 'Revertido')
    ], default='pending', tracking=True, string='Estado')
    
    # Información adicional
    move_date = fields.Datetime('Fecha de Movimiento', default=fields.Datetime.now, tracking=True)
    completed_date = fields.Datetime('Fecha de Completado')
    error_message = fields.Text('Mensaje de Error')
    api_response = fields.Text('Respuesta de la API')
    
    # Campos calculados
    move_duration = fields.Float('Duración (minutos)', compute='_compute_duration', store=True)
    is_same_olt = fields.Boolean('Misma OLT', compute='_compute_same_olt', store=True)
    
    # Relaciones
    batch_move_id = fields.Integer('ID Movimiento Masivo', help='ID del wizard de movimiento masivo (solo para referencia)')
    
    # Restricciones SQL
    _sql_constraints = [
        ('unique_onu_move', 'unique(onu_id, move_date)', 'No puede haber múltiples movimientos de la misma ONU en la misma fecha!')
    ]
    
    @api.depends('source_olt_id', 'source_board', 'source_port')
    def _compute_locations(self):
        """Calcular ubicaciones de origen y destino"""
        for record in self:
            if record.source_olt_id and record.source_board and record.source_port:
                record.source_location = f"{record.source_olt_id.name}-B{record.source_board}-P{record.source_port}"
            else:
                record.source_location = False
                
            if record.target_olt_id and record.target_board and record.target_port:
                record.target_location = f"{record.target_olt_id.name}-B{record.target_board}-P{record.target_port}"
            else:
                record.target_location = False
    
    @api.depends('move_date', 'completed_date')
    def _compute_duration(self):
        """Calcular duración del movimiento en minutos"""
        for record in self:
            if record.move_date and record.completed_date:
                duration = (record.completed_date - record.move_date).total_seconds() / 60
                record.move_duration = round(duration, 2)
            else:
                record.move_duration = 0.0
    
    @api.depends('source_olt_id', 'target_olt_id')
    def _compute_same_olt(self):
        """Verificar si es movimiento en la misma OLT"""
        for record in self:
            record.is_same_olt = record.source_olt_id == record.target_olt_id
    
    @api.constrains('source_board', 'source_port', 'target_board', 'target_port')
    def _check_valid_ports(self):
        """Validar que los puertos sean válidos"""
        for record in self:
            if record.source_board < 1 or record.source_port < 1:
                raise ValidationError(_('Board y Puerto origen deben ser mayores a 0'))
            if record.target_board < 1 or record.target_port < 1:
                raise ValidationError(_('Board y Puerto destino deben ser mayores a 0'))
    
    @api.constrains('source_olt_id', 'target_olt_id', 'source_board', 'source_port', 'target_board', 'target_port')
    def _check_different_location(self):
        """Validar que origen y destino sean diferentes"""
        for record in self:
            if (record.source_olt_id == record.target_olt_id and 
                record.source_board == record.target_board and 
                record.source_port == record.target_port):
                raise ValidationError(_('El origen y destino no pueden ser iguales'))
    
    def action_start_move(self):
        """Iniciar el movimiento de la ONU"""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Solo se pueden iniciar movimientos pendientes'))
        
        self.state = 'in_progress'
        self.message_post(body=_('Movimiento iniciado'))
        
        # Aquí se implementaría la lógica de la API
        try:
            # TODO: Implementar llamada a API de SmartOLT
            self._execute_move_via_api()
        except Exception as e:
            self.state = 'failed'
            self.error_message = str(e)
            self.message_post(body=_('Error en el movimiento: %s') % str(e))
    
    def action_complete_move(self):
        """Marcar movimiento como completado"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Solo se pueden completar movimientos en progreso'))
        
        self.state = 'completed'
        self.completed_date = fields.Datetime.now()
        self.message_post(body=_('Movimiento completado exitosamente'))
    
    def action_fail_move(self, error_message):
        """Marcar movimiento como fallido"""
        self.ensure_one()
        self.state = 'failed'
        self.error_message = error_message
        self.message_post(body=_('Movimiento fallido: %s') % error_message)
    
    def action_rollback_move(self):
        """Revertir el movimiento"""
        self.ensure_one()
        if self.state not in ['completed', 'failed']:
            raise UserError(_('Solo se pueden revertir movimientos completados o fallidos'))
        
        # TODO: Implementar rollback via API
        self.state = 'rolled_back'
        self.message_post(body=_('Movimiento revertido'))
    
    def _execute_move_via_api(self):
        """Ejecutar el movimiento via API de SmartOLT"""
        # Esta función se implementará cuando se cree el wizard
        # Por ahora solo simula el proceso
        _logger.info(f'Simulando movimiento de ONU {self.onu_id.serial_number} de {self.source_location} a {self.target_location}')
        
        # Simular delay de API
        import time
        time.sleep(2)
        
        # Simular éxito
        return True
    
    def name_get(self):
        """Personalizar nombre mostrado"""
        result = []
        for record in self:
            if record.onu_id:
                name = f"{record.onu_id.serial_number} ({record.source_location} → {record.target_location})"
            else:
                name = f"Movimiento {record.id}"
            result.append((record.id, name))
        return result 