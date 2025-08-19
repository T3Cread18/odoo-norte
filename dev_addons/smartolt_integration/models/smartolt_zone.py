# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class SmartOLTZone(models.Model):
    _name = 'smartolt.zone'
    _description = 'SmartOLT Zone'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True)
    zone_id = fields.Char('ID Zona', required=True)
    
    # Relaciones
    olt_id = fields.Many2one('smartolt.olt', string='OLT', required=True)
    odb_ids = fields.One2many('smartolt.odb', 'zone_id', string='ODBs')
    onu_ids = fields.One2many('smartolt.onu', 'zone_id', string='ONUs')
    
    # Configuración
    description = fields.Text('Descripción')
    location = fields.Char('Ubicación')
    status = fields.Selection([
        ('active', 'Activa'),
        ('inactive', 'Inactiva'),
        ('maintenance', 'Mantenimiento')
    ], string='Estado', default='active')
    
    # Campos de la API
    api_zone_id = fields.Char('ID API Zona')
    coordinates = fields.Char('Coordenadas')
    last_sync = fields.Datetime('Última Sincronización')
    
    _sql_constraints = [
        ('zone_id_unique', 'unique(zone_id)', 'El ID de zona debe ser único!')
    ]

    def sync_from_api(self):
        """Sincroniza zonas desde la API de SmartOLT"""
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
            
            # Endpoint real de SmartOLT para obtener todas las zonas
            url = f'{api_url}/api/system/get_zones'
            
            _logger.info(f'Sincronizando zonas desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar diferentes estructuras de respuesta
                zone_data = None
                if data.get('status') == 'success' or data.get('status') == True:
                    zone_data = data.get('data', [])
                elif data.get('response_code') == 'success' and data.get('response'):
                    zone_data = data.get('response', [])
                elif data.get('response'):
                    zone_data = data.get('response', [])
                
                _logger.info(f'Se encontraron {len(zone_data) if zone_data else 0} zonas en la API')
                
                if zone_data:
                    # Procesar cada zona
                    for zone_info in zone_data:
                        self._process_zone_data(zone_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s zonas desde la API de SmartOLT') % len(zone_data),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Completada'),
                            'message': _('No se encontraron zonas para sincronizar'),
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando zonas: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando zonas: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando zonas: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando zonas: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_zone_data(self, zone_info):
        """Procesa los datos de una zona individual"""
        try:
            # Buscar zona existente por identificador único
            existing_zone = self.search([
                '|',
                ('zone_id', '=', zone_info.get('zone_id')),
                ('name', '=', zone_info.get('name'))
            ], limit=1)
            
            zone_vals = {
                'name': zone_info.get('name', 'Zona Sin Nombre'),
                'zone_id': zone_info.get('zone_id'),
                'description': zone_info.get('description'),
                'status': zone_info.get('status', 'active'),
                'location': zone_info.get('location'),
                'coordinates': zone_info.get('coordinates'),
                'last_sync': fields.Datetime.now(),
            }
            
            if existing_zone:
                # Actualizar zona existente
                existing_zone.write(zone_vals)
                _logger.info(f'Zona actualizada: {existing_zone.name}')
            else:
                # Crear nueva zona
                new_zone = self.create(zone_vals)
                _logger.info(f'Nueva zona creada: {new_zone.name}')
                
        except Exception as e:
            _logger.error(f'Error procesando zona {zone_info.get("name", "desconocida")}: {e}')

    def action_get_zone_details(self):
        """Obtiene detalles completos de una zona específica"""
        try:
            import requests
            
            if not self.zone_id:
                raise UserError(_('Esta zona no tiene ID configurado'))
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para detalles de zona
            url = f'{api_url}/api/zone/get_zone_details'
            params = {'zone_name': self.name}
            
            _logger.info(f'Obteniendo detalles de zona {self.name} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    zone_details = data.get('data', {})
                    
                    # Actualizar detalles de la zona
                    self.write({
                        'description': zone_details.get('description'),
                        'status': zone_details.get('status'),
                        'location': zone_details.get('location'),
                        'coordinates': zone_details.get('coordinates'),
                        'last_sync': fields.Datetime.now(),
                    })
                    
                    details_message = _('Detalles de Zona %s:\n') % self.name
                    details_message += _('Descripción: %s\n') % zone_details.get('description', 'N/A')
                    details_message += _('Estado: %s\n') % zone_details.get('status', 'N/A')
                    details_message += _('Ubicación: %s\n') % zone_details.get('location', 'N/A')
                    details_message += _('Coordenadas: %s') % zone_details.get('coordinates', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Detalles de Zona'),
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
            _logger.error(f'Error obteniendo detalles de zona {self.name}: {e}')
            raise UserError(_('Error obteniendo detalles de zona: %s') % str(e))


class SmartOLTODB(models.Model):
    _name = 'smartolt.odb'
    _description = 'ODB (Splitter) de SmartOLT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Nombre', required=True, tracking=True)
    odb_id = fields.Char('ID del ODB', tracking=True)
    zone_id = fields.Many2one('smartolt.zone', string='Zona', tracking=True)
    description = fields.Text('Descripción', tracking=True)
    location = fields.Char('Ubicación', tracking=True)
    coordinates = fields.Char('Coordenadas', tracking=True)
    status = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('maintenance', 'En Mantenimiento')
    ], string='Estado', default='active', tracking=True)
    last_sync = fields.Datetime('Última Sincronización', tracking=True)

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
                
                if data.get('status') == 'success' or data.get('status') == True:
                    odb_data = data.get('data', [])
                    _logger.info(f'Se encontraron {len(odb_data)} ODBs en la API')
                    
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
                    error_msg = data.get('error', 'Error desconocido')
                    raise UserError(_('Error en la API: %s') % error_msg)
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
            _logger.error(f'Error de petición HTTP sincronizando ODBs: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando ODBs: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_odb_data(self, odb_info):
        """Procesa los datos de un ODB individual"""
        try:
            # Buscar ODB existente por identificador único
            existing_odb = self.search([
                '|',
                ('odb_id', '=', odb_info.get('odb_id')),
                ('name', '=', odb_info.get('name'))
            ], limit=1)
            
            # Buscar zona relacionada
            zone = None
            if odb_info.get('zone_name'):
                zone = self.env['smartolt.zone'].search([('name', '=', odb_info.get('zone_name'))], limit=1)
            
            odb_vals = {
                'name': odb_info.get('name', 'ODB Sin Nombre'),
                'odb_id': odb_info.get('odb_id'),
                'zone_id': zone.id if zone else False,
                'description': odb_info.get('description'),
                'location': odb_info.get('location'),
                'coordinates': odb_info.get('coordinates'),
                'status': odb_info.get('status', 'active'),
                'last_sync': fields.Datetime.now(),
            }
            
            if existing_odb:
                # Actualizar ODB existente
                existing_odb.write(odb_vals)
                _logger.info(f'ODB actualizado: {existing_odb.name}')
            else:
                # Crear nuevo ODB
                new_odb = self.create(odb_vals)
                _logger.info(f'Nuevo ODB creado: {new_odb.name}')
                
        except Exception as e:
            _logger.error(f'Error procesando ODB {odb_info.get("name", "desconocido")}: {e}')

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
                        'last_sync': fields.Datetime.now(),
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
