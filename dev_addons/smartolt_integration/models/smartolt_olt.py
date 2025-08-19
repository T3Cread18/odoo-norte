# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class SmartOLTOLT(models.Model):
    _name = 'smartolt.olt'
    _description = 'SmartOLT OLT'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True)
    olt_id = fields.Char('ID OLT', required=True)
    ip_address = fields.Char('Dirección IP')
    model = fields.Char('Modelo')
    status = fields.Selection([
        ('online', 'En Línea'),
        ('offline', 'Desconectado'),
        ('maintenance', 'Mantenimiento')
    ], string='Estado', default='offline', tracking=True)
    
    # Campos de la API
    api_olt_id = fields.Char('ID API OLT')
    description = fields.Text('Descripción')
    location = fields.Char('Ubicación')
    firmware_version = fields.Char('Versión Firmware')
    hardware_version = fields.Char('Versión Hardware')
    
    # Relaciones
    onu_ids = fields.One2many('smartolt.onu', 'olt_id', string='ONUs')
    zone_ids = fields.One2many('smartolt.zone', 'olt_id', string='Zonas')
    
    # Configuración de API
    api_url = fields.Char('URL API', default='https://api.smartolt.com')
    api_token = fields.Char('Token API')
    last_sync = fields.Datetime('Última Sincronización')
    
    _sql_constraints = [
        ('olt_id_unique', 'unique(olt_id)', 'El ID OLT debe ser único!')
    ]

    @api.model
    def sync_from_api(self):
        """Sincroniza OLTs desde la API de SmartOLT"""
        try:
            import requests
            import json
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para obtener lista de OLTs
            url = f'{api_url}/api/system/get_olts'
            
            _logger.info(f'Sincronizando OLTs desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info(f'Respuesta completa de la API: {json.dumps(data, indent=2)}')
                
                # Verificar diferentes estructuras de respuesta
                olt_data = None
                _logger.info(f'Debug: data.get("status") = {data.get("status")}')
                _logger.info(f'Debug: data.get("response_code") = {data.get("response_code")}')
                _logger.info(f'Debug: data.get("response") = {data.get("response")}')
                _logger.info(f'Debug: type(data.get("response")) = {type(data.get("response"))}')
                
                if data.get('response_code') == 'success' and data.get('response'):
                    olt_data = data.get('response', [])
                    _logger.info(f'Debug: Usando data.get("response") = {olt_data}')
                elif data.get('status') == 'success' or data.get('status') == True:
                    olt_data = data.get('data', [])
                    _logger.info(f'Debug: Usando data.get("data") = {olt_data}')
                elif data.get('response') and isinstance(data.get('response'), list):
                    olt_data = data.get('response', [])
                    _logger.info(f'Debug: Usando data.get("response") con isinstance = {olt_data}')
                elif isinstance(data, list):
                    olt_data = data
                    _logger.info(f'Debug: Usando data directamente = {olt_data}')
                else:
                    _logger.warning(f'Estructura de respuesta inesperada: {data}')
                    olt_data = []
                
                _logger.info(f'Debug: olt_data final = {olt_data}')
                _logger.info(f'Debug: len(olt_data) = {len(olt_data) if olt_data else "None"}')
                
                _logger.info(f'Se encontraron {len(olt_data)} OLTs en la API')
                _logger.info(f'Estructura de datos: {type(olt_data)}')
                _logger.info(f'Primer OLT: {olt_data[0] if olt_data else "No hay datos"}')
                
                if olt_data:
                    # Procesar cada OLT
                    for olt_info in olt_data:
                        self._process_olt_data(olt_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s OLTs desde la API de SmartOLT') % len(olt_data),
                            'type': 'success',
                        }
                    }
                else:
                    _logger.warning('No se encontraron OLTs en la respuesta de la API')
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Completada'),
                            'message': _('No se encontraron OLTs para sincronizar'),
                            'type': 'info',
                        }
                    }
            else:
                _logger.error(f'Error HTTP {response.status_code}: {response.text}')
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando OLTs: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando OLTs: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando OLTs: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando OLTs: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_olt_data(self, olt_info):
        """Procesa los datos de un OLT individual"""
        try:
            # Buscar OLT existente por identificador único
            existing_olt = self.search([
                '|',
                ('olt_id', '=', olt_info.get('id')),  # La API usa 'id'
                ('name', '=', olt_info.get('name'))
            ], limit=1)
            
            olt_vals = {
                'name': olt_info.get('name', 'OLT Sin Nombre'),
                'olt_id': olt_info.get('id'),  # La API usa 'id', no 'olt_id'
                'ip_address': olt_info.get('ip'),  # La API usa 'ip', no 'ip_address'
                'hardware_version': olt_info.get('olt_hardware_version'),  # La API usa 'olt_hardware_version'
                'status': 'online',  # Por defecto online ya que la API responde
                'last_sync': fields.Datetime.now(),
            }
            
            _logger.info(f'Debug: Procesando OLT - Datos: {olt_info}')
            _logger.info(f'Debug: Valores a crear/actualizar: {olt_vals}')
            _logger.info(f'Debug: OLT existente encontrado: {existing_olt}')
            
            if existing_olt:
                # Actualizar OLT existente
                existing_olt.write(olt_vals)
                _logger.info(f'OLT actualizado: {existing_olt.name}')
            else:
                # Crear nuevo OLT
                new_olt = self.create(olt_vals)
                _logger.info(f'Nuevo OLT creado: {new_olt.name}')
                
        except Exception as e:
            _logger.error(f'Error procesando OLT {olt_info.get("name", "desconocido")}: {e}')

    def action_get_system_info(self):
        """Obtiene información del sistema desde la API de SmartOLT"""
        try:
            import requests
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para información del sistema
            url = f'{api_url}/api/system/get_system_info'
            
            _logger.info(f'Obteniendo información del sistema desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    system_info = data.get('data', {})
                    
                    # Mostrar información del sistema
                    info_message = _('Información del Sistema SmartOLT:\n')
                    info_message += _('Versión: %s\n') % system_info.get('version', 'N/A')
                    info_message += _('Estado: %s\n') % system_info.get('status', 'N/A')
                    info_message += _('Última Actualización: %s') % system_info.get('last_update', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Información del Sistema'),
                            'message': info_message,
                            'type': 'info',
                        }
                    }
                else:
                    error_msg = data.get('error', 'Error desconocido')
                    raise UserError(_('Error en la API: %s') % error_msg)
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except Exception as e:
            _logger.error(f'Error obteniendo información del sistema: {e}')
            raise UserError(_('Error obteniendo información del sistema: %s') % str(e))

    def action_get_olt_status(self):
        """Obtiene el estado actual de un OLT específico"""
        try:
            import requests
            
            if not self.olt_id:
                raise UserError(_('Este OLT no tiene ID configurado'))
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para estado del OLT
            url = f'{api_url}/api/olt/get_olt_status'
            params = {'olt_id': self.olt_id}
            
            _logger.info(f'Obteniendo estado del OLT {self.name} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    olt_status = data.get('data', {})
                    
                    # Actualizar estado del OLT
                    self.write({
                        'status': olt_status.get('status', 'unknown'),
                        'last_sync': fields.Datetime.now(),
                    })
                    
                    status_message = _('Estado del OLT %s:\n') % self.name
                    status_message += _('Estado: %s\n') % olt_status.get('status', 'N/A')
                    status_message += _('Última Comunicación: %s\n') % olt_status.get('last_communication', 'N/A')
                    status_message += _('Uptime: %s') % olt_status.get('uptime', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Estado del OLT'),
                            'message': status_message,
                            'type': 'success',
                        }
                    }
                else:
                    error_msg = data.get('error', 'Error desconocido')
                    raise UserError(_('Error en la API: %s') % error_msg)
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except Exception as e:
            _logger.error(f'Error obteniendo estado del OLT {self.name}: {e}')
            raise UserError(_('Error obteniendo estado del OLT: %s') % str(e))

    def action_sync_onus_by_olt(self):
        """Sincroniza ONUs específicamente de este OLT"""
        try:
            if not self.olt_id:
                raise UserError(_('Este OLT no tiene ID configurado'))
            
            # Llamar al método de sincronización del modelo de ONUs
            onu_model = self.env['smartolt.onu']
            return onu_model.sync_onus_by_olt(int(self.olt_id))
            
        except Exception as e:
            _logger.error(f'Error sincronizando ONUs del OLT {self.name}: {e}')
            raise UserError(_('Error sincronizando ONUs: %s') % str(e))

    def action_sync_onus_by_board(self):
        """Sincroniza ONUs por board específico del OLT"""
        try:
            if not self.olt_id:
                raise UserError(_('Este OLT no tiene ID configurado'))
            
            # Crear wizard para seleccionar board
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sincronizar ONUs por Board'),
                'res_model': 'smartolt.sync.board.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_olt_id': self.id,
                    'default_olt_olt_id': self.olt_id,
                }
            }
            
        except Exception as e:
            _logger.error(f'Error abriendo wizard de sincronización por board: {e}')
            raise UserError(_('Error: %s') % str(e))

    def action_sync_onus_by_port(self):
        """Sincroniza ONUs por puerto específico del OLT"""
        try:
            if not self.olt_id:
                raise UserError(_('Este OLT no tiene ID configurado'))
            
            # Crear wizard para seleccionar board y puerto
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sincronizar ONUs por Puerto'),
                'res_model': 'smartolt.sync.port.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_olt_id': self.id,
                    'default_olt_olt_id': self.olt_id,
                }
            }
            
        except Exception as e:
            _logger.error(f'Error abriendo wizard de sincronización por puerto: {e}')
            raise UserError(_('Error: %s') % str(e))
