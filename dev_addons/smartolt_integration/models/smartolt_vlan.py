# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class SmartOLTVLAN(models.Model):
    _name = 'smartolt.vlan'
    _description = 'VLAN de SmartOLT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Nombre', required=True, tracking=True)
    vlan_id = fields.Char('ID de VLAN', tracking=True)
    description = fields.Text('Descripción', tracking=True)
    vlan_number = fields.Integer('Número de VLAN', tracking=True)
    olt_id = fields.Many2one('smartolt.olt', string='OLT', tracking=True)
    status = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('reserved', 'Reservado')
    ], string='Estado', default='active', tracking=True)
    last_sync = fields.Datetime('Última Sincronización', tracking=True)

    def sync_from_api(self):
        """Sincroniza VLANs desde la API de SmartOLT"""
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
            
            # Primero obtener la lista de OLTs
            olt_url = f'{api_url}/api/system/get_olts'
            _logger.info(f'Obteniendo lista de OLTs desde: {olt_url}')
            
            olt_response = requests.get(olt_url, headers=headers, timeout=timeout)
            if olt_response.status_code != 200:
                raise UserError(_('Error obteniendo OLTs: HTTP %s: %s') % (olt_response.status_code, olt_response.text))
            
            olt_data = olt_response.json()
            olt_list = []
            
            # Extraer la lista de OLTs según la estructura de respuesta
            if olt_data.get('response_code') == 'success' and olt_data.get('response'):
                olt_list = olt_data.get('response', [])
            elif olt_data.get('status') == 'success' or olt_data.get('status') == True:
                olt_list = olt_data.get('data', [])
            elif olt_data.get('response'):
                olt_list = olt_data.get('response', [])
            
            if not olt_list:
                _logger.warning('No se encontraron OLTs para sincronizar VLANs')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sincronización Completada'),
                        'message': _('No se encontraron OLTs para sincronizar VLANs'),
                        'type': 'info',
                    }
                }
            
            _logger.info(f'Se encontraron {len(olt_list)} OLTs, sincronizando VLANs...')
            
            total_vlans = 0
            
            # Para cada OLT, obtener sus VLANs
            for olt_info in olt_list:
                olt_id = olt_info.get('id') or olt_info.get('olt_id')
                if not olt_id:
                    _logger.warning(f'OLT sin ID válido: {olt_info}')
                    continue
                
                # Endpoint para obtener VLANs de un OLT específico
                vlan_url = f'{api_url}/api/olt/get_vlans/{olt_id}'
                _logger.info(f'Sincronizando VLANs del OLT {olt_id} desde: {vlan_url}')
                
                try:
                    vlan_response = requests.get(vlan_url, headers=headers, timeout=timeout)
                    
                    if vlan_response.status_code == 200:
                        vlan_data = vlan_response.json()
                        
                        # Verificar diferentes estructuras de respuesta  
                        vlan_list = None
                        if vlan_data.get('response_code') == 'success' and vlan_data.get('response'):
                            vlan_list = vlan_data.get('response', [])
                        elif vlan_data.get('status') == 'success' or vlan_data.get('status') == True:
                            vlan_list = vlan_data.get('data', [])
                        elif vlan_data.get('response'):
                            vlan_list = vlan_data.get('response', [])
                        else:
                            vlan_list = []
                        
                        if vlan_list:
                            _logger.info(f'Se encontraron {len(vlan_list)} VLANs para el OLT {olt_id}')
                            
                            # Procesar cada VLAN
                            for vlan_info in vlan_list:
                                # Agregar el OLT ID a la información de la VLAN
                                vlan_info['olt_id'] = olt_id
                                self._process_vlan_data(vlan_info)
                                total_vlans += 1
                        else:
                            _logger.info(f'No se encontraron VLANs para el OLT {olt_id}')
                    else:
                        _logger.warning(f'Error obteniendo VLANs del OLT {olt_id}: HTTP {vlan_response.status_code}')
                        
                except Exception as e:
                    _logger.error(f'Error procesando VLANs del OLT {olt_id}: {e}')
                    continue
            
            if total_vlans > 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sincronización Exitosa'),
                        'message': _('Se sincronizaron %s VLANs desde la API de SmartOLT') % total_vlans,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Sincronización Completada'),
                        'message': _('No se encontraron VLANs para sincronizar'),
                        'type': 'info',
                    }
                }
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando VLANs: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando VLANs: {e}')
            raise UserError(_('Error de timeout con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando VLANs: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando VLANs: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    def _process_vlan_data(self, vlan_info):
        """Procesa los datos de una VLAN individual"""
        try:
            # Buscar VLAN existente por identificador único
            existing_vlan = self.search([
                '|',
                ('vlan_id', '=', vlan_info.get('vlan_id')),
                ('vlan_number', '=', vlan_info.get('vlan_number'))
            ], limit=1)
            
            # Extraer número de VLAN del campo vlan_id o vlan_number
            vlan_number = None
            if vlan_info.get('vlan_number'):
                try:
                    vlan_number = int(vlan_info.get('vlan_number'))
                except (ValueError, TypeError):
                    _logger.warning(f'No se pudo convertir vlan_number "{vlan_info.get("vlan_number")}" para VLAN {vlan_info.get("name", "desconocida")}')
            
            if not vlan_number and vlan_info.get('vlan_id'):
                try:
                    vlan_number = int(vlan_info.get('vlan_id'))
                except (ValueError, TypeError):
                    _logger.warning(f'No se pudo convertir vlan_id "{vlan_info.get("vlan_id")}" para VLAN {vlan_info.get("name", "desconocida")}')
            
            # Si no hay número de VLAN, intentar extraer del nombre
            if not vlan_number and vlan_info.get('name'):
                import re
                vlan_match = re.search(r'(\d+)', vlan_info.get('name'))
                if vlan_match:
                    try:
                        vlan_number = int(vlan_match.group(1))
                        _logger.info(f'Número de VLAN extraído del nombre: {vlan_number}')
                    except (ValueError, TypeError):
                        _logger.warning(f'No se pudo extraer número de VLAN del nombre "{vlan_info.get("name")}"')
            
            # Buscar OLT relacionada si se proporciona olt_id
            olt_id = None
            if vlan_info.get('olt_id'):
                olt = self.env['smartolt.olt'].search([
                    ('olt_id', '=', str(vlan_info.get('olt_id')))
                ], limit=1)
                if olt:
                    olt_id = olt.id
            
            vlan_vals = {
                'name': vlan_info.get('name', 'VLAN Sin Nombre'),
                'vlan_id': vlan_info.get('vlan_id') or str(vlan_number) if vlan_number else '',
                'description': vlan_info.get('description') or f'VLAN {vlan_number}' if vlan_number else 'VLAN sin descripción',
                'vlan_number': vlan_number,
                'status': vlan_info.get('status', 'active'),
                'olt_id': olt_id,
                'last_sync': fields.Datetime.now(),
            }
            
            if existing_vlan:
                # Actualizar VLAN existente
                existing_vlan.write(vlan_vals)
                _logger.info(f'VLAN actualizada: {existing_vlan.name} (Número: {vlan_number})')
            else:
                # Crear nueva VLAN
                new_vlan = self.create(vlan_vals)
                _logger.info(f'Nueva VLAN creada: {new_vlan.name} (Número: {vlan_number})')
                
        except Exception as e:
            _logger.error(f'Error procesando VLAN {vlan_info.get("name", "desconocida")}: {e}')

    def action_get_vlan_details(self):
        """Obtiene detalles completos de una VLAN específica"""
        try:
            import requests
            
            if not self.vlan_id:
                raise UserError(_('Esta VLAN no tiene un ID válido para consultar detalles'))
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = config.get_timeout()
            
            headers = {
                'X-Token': api_token
            }
            
            # Endpoint para obtener detalles de VLAN específica
            url = f'{api_url}/api/vlan/get_vlan_details?vlan_id={self.vlan_id}'
            
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' or data.get('status') == True:
                    vlan_details = data.get('data', {})
                    
                    # Actualizar campos con la información obtenida
                    self.write({
                        'description': vlan_details.get('description'),
                        'status': vlan_details.get('status', 'active'),
                        'last_sync': fields.Datetime.now(),
                    })
                    
                    details_message = _('Detalles de VLAN %s:\n') % self.name
                    details_message += _('Descripción: %s\n') % vlan_details.get('description', 'N/A')
                    details_message += _('Estado: %s') % vlan_details.get('status', 'N/A')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Detalles de VLAN'),
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
            _logger.error(f'Error obteniendo detalles de VLAN {self.name}: {e}')
            raise UserError(_('Error obteniendo detalles de VLAN: %s') % str(e)) 