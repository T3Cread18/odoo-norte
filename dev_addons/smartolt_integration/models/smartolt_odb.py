# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SmartOLTODB(models.Model):
    _name = 'smartolt.odb'
    _description = 'SmartOLT ODB'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True)
    odb_id = fields.Char('ID ODB', required=True)
    
    # Relaciones
    zone_id = fields.Many2one('smartolt.zone', string='Zona', required=True)
    onu_ids = fields.One2many('smartolt.onu', 'odb_splitter', string='ONUs')
    
    # Configuración
    description = fields.Text('Descripción')
    location = fields.Char('Ubicación')
    status = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('maintenance', 'Mantenimiento')
    ], string='Estado', default='active')
    
    # Campos de la API
    api_odb_id = fields.Char('ID API ODB')
    coordinates = fields.Char('Coordenadas')
    last_sync = fields.Datetime('Última Sincronización')
    
    _sql_constraints = [
        ('odb_id_unique', 'unique(odb_id)', 'El ID de ODB debe ser único!')
    ]

    def sync_from_api(self):
        """Sincroniza ODBs desde la API de SmartOLT"""
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
            
            # Endpoint real de SmartOLT para obtener todos los ODBs
            url = f'{api_url}/api/system/get_odbs'
            
            _logger.info(f'Sincronizando ODBs desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar diferentes estructuras de respuesta
                odb_data = None
                if data.get('status') == 'success' or data.get('status') == True:
                    odb_data = data.get('data', [])
                elif data.get('response_code') == 'success' and data.get('response'):
                    odb_data = data.get('response', [])
                elif data.get('response'):
                    odb_data = data.get('response', [])
                
                _logger.info(f'Se encontraron {len(odb_data) if odb_data else 0} ODBs en la API')
                
                if odb_data:
                    # Procesar cada ODB
                    for odb_info in odb_data:
                        self._process_odb_data(odb_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s ODBs desde la API de SmartOLT') % len(odb_data),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Completada'),
                            'message': _('No se encontraron ODBs para sincronizar'),
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando ODBs: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando ODBs: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición sincronizando ODBs: {e}')
            raise UserError(_('Error de petición a la API de SmartOLT'))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando ODBs: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_odb_data(self, odb_info):
        """Procesa los datos de un ODB individual desde la API de SmartOLT"""
        try:
            # Buscar ODB existente por identificador único
            existing_odb = self.search([
                ('odb_id', '=', odb_info.get('odb_id'))
            ], limit=1)
            
            # Buscar zona relacionada
            zone = None
            if odb_info.get('zone_id'):
                zone = self.env['smartolt.zone'].search([('zone_id', '=', odb_info.get('zone_id'))], limit=1)
            
            # Mapear campos de la API de SmartOLT al modelo Odoo
            odb_vals = {
                'name': odb_info.get('name', 'ODB Sin Nombre'),
                'odb_id': odb_info.get('odb_id'),
                'zone_id': zone.id if zone else False,
                'description': odb_info.get('description'),
                'location': odb_info.get('location'),
                'status': odb_info.get('status', 'active'),
                'api_odb_id': odb_info.get('api_odb_id'),
                'coordinates': odb_info.get('coordinates'),
            }
            
            if existing_odb:
                # Actualizar ODB existente
                existing_odb.write(odb_vals)
                _logger.info(f'ODB actualizado: {existing_odb.name} (ID: {existing_odb.id})')
            else:
                # Crear nuevo ODB
                new_odb = self.create(odb_vals)
                _logger.info(f'Nuevo ODB creado: {new_odb.name} (ID: {new_odb.id})')
                
        except Exception as e:
            _logger.error(f'Error procesando ODB {odb_info.get("name", "desconocido")}: {e}')
            raise UserError(_('Error procesando ODB %s: %s') % (odb_info.get("name", "desconocido"), str(e)))

    def action_get_odb_details(self):
        """Obtiene detalles completos de un ODB específico"""
        try:
            import requests
            
            if not self.odb_id:
                raise UserError(_('Este ODB no tiene ID configurado'))
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para detalles de ODB
            url = f'{api_url}/api/odb/get_odb_details'
            params = {'odb_name': self.name}
            
            _logger.info(f'Obteniendo detalles de ODB {self.name} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    odb_details = data.get('data', {})
                    
                    # Actualizar detalles del ODB
                    self.write({
                        'description': odb_details.get('description'),
                        'location': odb_details.get('location'),
                        'coordinates': odb_details.get('coordinates'),
                        'status': odb_details.get('status'),
                    })
                    
                    details_message = _('Detalles de ODB %s:\n') % self.name
                    details_message += _('Descripción: %s\n') % odb_details.get('description', 'N/A')
                    details_message += _('Ubicación: %s\n') % odb_details.get('location', 'N/A')
                    details_message += _('Coordenadas: %s\n') % odb_details.get('coordinates', 'N/A')
                    details_message += _('Estado: %s') % odb_details.get('status', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Detalles de ODB'),
                            'message': details_message,
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
            _logger.error(f'Error obteniendo detalles de ODB {self.name}: {e}')
            raise UserError(_('Error obteniendo detalles de ODB: %s') % str(e))
