# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class SmartOLTSpeedProfile(models.Model):
    _name = 'smartolt.speed_profile'
    _description = 'SmartOLT Speed Profile'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True)
    profile_id = fields.Char('ID Perfil', required=True)
    
    # Relaciones
    olt_id = fields.Many2one('smartolt.olt', string='OLT', required=True)
    onu_ids = fields.One2many('smartolt.onu', 'speed_profile_id', string='ONUs')
    
    # Configuración de velocidad
    download_speed = fields.Float('Velocidad de Descarga (Mbps)', required=True)
    upload_speed = fields.Float('Velocidad de Subida (Mbps)', required=True)
    
    # Configuración adicional
    description = fields.Text('Descripción')
    status = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('maintenance', 'Mantenimiento')
    ], string='Estado', default='active')
    
    # Campos de la API
    api_profile_id = fields.Char('ID API Perfil')
    priority = fields.Integer('Prioridad', default=0)
    last_sync = fields.Datetime('Última Sincronización')
    
    _sql_constraints = [
        ('profile_id_unique', 'unique(profile_id)', 'El ID de perfil debe ser único!')
    ]

    def sync_from_api(self):
        """Sincroniza perfiles de velocidad desde la API de SmartOLT"""
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
            
            # Endpoint real de SmartOLT para obtener todos los perfiles
            url = f'{api_url}/api/system/get_speed_profiles'
            
            _logger.info(f'Sincronizando perfiles de velocidad desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar diferentes estructuras de respuesta
                profile_data = None
                if data.get('response_code') == 'success' and data.get('response'):
                    profile_data = data.get('response', [])
                elif data.get('status') == 'success' or data.get('status') == True:
                    profile_data = data.get('data', [])
                elif data.get('response'):
                    profile_data = data.get('response', [])
                
                _logger.info(f'Se encontraron {len(profile_data) if profile_data else 0} perfiles en la API')
                
                if profile_data:
                    # Procesar cada perfil
                    for profile_info in profile_data:
                        self._process_speed_profile_data(profile_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s perfiles desde la API de SmartOLT') % len(profile_data),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Completada'),
                            'message': _('No se encontraron perfiles para sincronizar'),
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando perfiles: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando perfiles: {e}')
            raise UserError(_('Error de timeout con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando perfiles: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando perfiles: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_speed_profile_data(self, profile_info):
        """Procesa los datos de un perfil de velocidad individual"""
        try:
            # Buscar perfil existente por identificador único
            existing_profile = self.search([
                '|',
                ('profile_id', '=', profile_info.get('id')),
                ('api_profile_id', '=', profile_info.get('id'))
            ], limit=1)
            
            # Convertir velocidad de bps a Mbps si es necesario
            download_speed = 0.0
            upload_speed = 0.0
            
            # Manejar diferentes formatos de velocidad
            if profile_info.get('speed'):
                try:
                    speed_bps = float(profile_info.get('speed', 0))
                    speed_mbps = speed_bps / 1000000  # Convertir de bps a Mbps
                    
                    # Determinar velocidades de descarga y subida según la dirección
                    if profile_info.get('direction') == 'download':
                        download_speed = speed_mbps
                    elif profile_info.get('direction') == 'upload':
                        upload_speed = speed_mbps
                    else:
                        # Si no hay dirección específica, asumir que es descarga
                        download_speed = speed_mbps
                except (ValueError, TypeError):
                    _logger.warning(f'No se pudo convertir velocidad "{profile_info.get("speed")}" para perfil {profile_info.get("name", "desconocido")}')
            
            # Si no hay velocidad en 'speed', buscar en campos específicos
            if download_speed == 0.0 and profile_info.get('download_speed'):
                try:
                    download_speed = float(profile_info.get('download_speed', 0))
                except (ValueError, TypeError):
                    _logger.warning(f'No se pudo convertir download_speed "{profile_info.get("download_speed")}" para perfil {profile_info.get("name", "desconocido")}')
            
            if upload_speed == 0.0 and profile_info.get('upload_speed'):
                try:
                    upload_speed = float(profile_info.get('upload_speed', 0))
                except (ValueError, TypeError):
                    _logger.warning(f'No se pudo convertir upload_speed "{profile_info.get("upload_speed")}" para perfil {profile_info.get("name", "desconocido")}')
            
            # Si aún no hay velocidades, intentar extraer de nombres como "ACA-FTTH-RES-100M"
            if download_speed == 0.0 and profile_info.get('name'):
                name = profile_info.get('name', '')
                # Buscar patrones como "100M", "50M", etc.
                import re
                speed_match = re.search(r'(\d+)M', name)
                if speed_match:
                    try:
                        download_speed = float(speed_match.group(1))
                        _logger.info(f'Velocidad extraída del nombre del perfil: {download_speed} Mbps')
                    except (ValueError, TypeError):
                        _logger.warning(f'No se pudo extraer velocidad del nombre "{name}"')
            
            profile_vals = {
                'name': profile_info.get('name', 'Perfil Sin Nombre'),
                'profile_id': profile_info.get('id') or profile_info.get('name', ''),
                'api_profile_id': profile_info.get('id') or profile_info.get('name', ''),
                'olt_id': 1,  # OLT por defecto
                'description': profile_info.get('description') or f'Perfil de velocidad: {profile_info.get("name", "desconocido")}',
                'download_speed': download_speed,
                'upload_speed': upload_speed,
                'status': 'active',
                'priority': profile_info.get('priority', 0),
                'last_sync': fields.Datetime.now(),
            }
            
            if existing_profile:
                # Actualizar perfil existente
                existing_profile.write(profile_vals)
                _logger.info(f'Perfil actualizado: {existing_profile.name} (Download: {download_speed} Mbps, Upload: {upload_speed} Mbps)')
            else:
                # Crear nuevo perfil
                new_profile = self.create(profile_vals)
                _logger.info(f'Nuevo perfil creado: {new_profile.name} (Download: {download_speed} Mbps, Upload: {upload_speed} Mbps)')
                
        except Exception as e:
            _logger.error(f'Error procesando perfil {profile_info.get("name", "desconocido")}: {e}')

    def action_get_profile_details(self):
        """Obtiene detalles completos de un perfil específico"""
        try:
            import requests
            
            if not self.profile_id:
                raise UserError(_('Este perfil no tiene ID configurado'))
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint real de SmartOLT para detalles de perfil
            url = f'{api_url}/api/speed_profile/get_speed_profile_details'
            params = {'profile_id': self.profile_id}
            
            _logger.info(f'Obteniendo detalles de perfil {self.name} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    profile_details = data.get('data', {})
                    
                    # Actualizar detalles del perfil
                    self.write({
                        'description': profile_details.get('description'),
                        'download_speed': profile_details.get('download_speed'),
                        'upload_speed': profile_details.get('upload_speed'),
                        'status': profile_details.get('status'),
                        'last_sync': fields.Datetime.now(),
                    })
                    
                    details_message = _('Detalles de Perfil %s:\n') % self.name
                    details_message += _('Descripción: %s\n') % profile_details.get('description', 'N/A')
                    details_message += _('Velocidad Descarga: %s Mbps\n') % profile_details.get('download_speed', 'N/A')
                    details_message += _('Velocidad Subida: %s Mbps\n') % profile_details.get('upload_speed', 'N/A')
                    details_message += _('Estado: %s') % profile_details.get('status', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Detalles de Perfil'),
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
            _logger.error(f'Error obteniendo detalles de perfil {self.name}: {e}')
            raise UserError(_('Error obteniendo detalles de perfil: %s') % str(e)) 