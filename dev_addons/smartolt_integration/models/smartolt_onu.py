# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SmartOLTONU(models.Model):
    _name = 'smartolt.onu'
    _description = 'SmartOLT ONU'
    _rec_name = 'serial_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos principales de SmartOLT
    external_id = fields.Char('ONU External ID', required=True, help='ID externo único de la ONU')
    pon_type = fields.Selection([
        ('gpon', 'GPON'),
        ('epon', 'EPON')
    ], string='PON Type', default='gpon', help='Tipo de tecnología PON')
    serial_number = fields.Char('SN', required=True, help='Número de serie de la ONU')
    onu_type = fields.Char('Onu Type', help='Tipo/modelo de la ONU')
    onu_type_id = fields.Char('ONU Type ID', help='ID del tipo de ONU en SmartOLT')
    name = fields.Char('Name', required=True, help='Nombre del cliente o descripción')
    
    # Relaciones OLT y Zona
    olt_id = fields.Many2one('smartolt.olt', string='OLT', required=True, help='OLT asociada')
    zone_id = fields.Many2one('smartolt.zone', string='Zone', help='Zona de la ONU')
    speed_profile_id = fields.Many2one('smartolt.speed_profile', string='Speed Profile', help='Perfil de velocidad asociado')
    
    # Campos de ubicación física
    board = fields.Integer('Board', help='Número del board en la OLT')
    port = fields.Integer('Port', help='Número del puerto PON en el board')
    allocated_onu = fields.Integer('Allocated ONU', help='Número de ONU asignada en el puerto')
    address = fields.Char('Address', help='Dirección física de la ONU')
    latitude = fields.Float('Latitude', help='Latitud geográfica')
    longitude = fields.Float('Longitude', help='Longitud geográfica')
    
    # Campos de ODB (Splitter)
    odb_splitter = fields.Many2one('smartolt.odb', string='ODB (Splitter)', help='ODB o splitter asociado')
    odb_port = fields.Integer('ODB Port', help='Puerto del ODB')
    
    # Configuración de red
    mode = fields.Selection([
        ('Routing', 'Routing'),
        ('Bridging', 'Bridging')
    ], string='Mode', help='Modo de operación de la ONU')
    wan_mode = fields.Char('WAN Mode', help='Modo de configuración WAN')
    
    # Configuración de red IP
    ip_address = fields.Char('IP Address', help='Dirección IP de la ONU')
    subnet_mask = fields.Char('Subnet Mask', help='Máscara de subred')
    default_gateway = fields.Char('Default Gateway', help='Gateway por defecto')
    dns1 = fields.Char('DNS1', help='Servidor DNS primario')
    dns2 = fields.Char('DNS2', help='Servidor DNS secundario')
    username = fields.Char('Username', help='Nombre de usuario')
    password = fields.Char('Password', help='Contraseña')
    
    # Configuración de servicios
    catv = fields.Char('CATV', help='Estado del servicio CATV')
    administrative_status = fields.Char('Administrative Status', help='Estado administrativo')
    
    # Fechas y estado
    auth_date = fields.Datetime('Auth Date', help='Fecha de autorización')
    status = fields.Selection([
        ('Online', 'Online'),
        ('Offline', 'Offline'),
        ('LOS', 'LOS'),
        ('Power fail', 'Power fail'),
        ('Log in', 'Log in')
    ], string='Status', default='Offline', tracking=True, help='Estado operativo de la ONU')
    
    # Campos de señal
    signal = fields.Char('Signal', help='Calidad de la señal')
    signal_1310 = fields.Float('Signal 1310', help='Señal en 1310nm (dBm)')
    signal_1490 = fields.Float('Signal 1490', help='Señal en 1490nm (dBm)')
    distance = fields.Float('Distance(m)', help='Distancia en metros')
    
    # Campos del puerto de servicio (service_ports)
    service_port = fields.Integer('Service Port', help='Puerto de servicio')
    service_port_vlan = fields.Char('Service Port VLAN', help='VLAN del puerto de servicio')
    service_port_cvlan = fields.Char('Service Port CVLAN', help='CVLAN del puerto de servicio')
    service_port_svlan = fields.Char('Service Port SVLAN', help='SVLAN del puerto de servicio')
    service_port_tag_transform_mode = fields.Char('Service Port Tag Transform Mode', help='Modo de transformación de tags')
    service_port_upload_speed = fields.Char('Service Port Upload Speed', help='Velocidad de subida del puerto de servicio')
    service_port_download_speed = fields.Char('Service Port Download Speed', help='Velocidad de descarga del puerto de servicio')
    
    # Campos de puertos Ethernet (ethernet_ports)
    ethernet_port = fields.Char('Ethernet Port', help='Puerto Ethernet')
    ethernet_admin_state = fields.Char('Ethernet Admin State', help='Estado administrativo del puerto Ethernet')
    
    # Información de contacto
    contact = fields.Char('Contact', help='Información de contacto')
    
    # Campo calculado para mostrar la ubicación completa
    port_location = fields.Char('Port Location', compute='_compute_port_location', store=True, 
                               help='Ubicación completa: OLT-Board-Port-ONU')
    
    # Campos de auditoría
    last_sync_date = fields.Datetime('Last Sync Date', help='Última fecha de sincronización')
    notes = fields.Text('Notes', help='Notas adicionales')
    
    _sql_constraints = [
        ('serial_number_unique', 'unique(serial_number)', 'El número de serie debe ser único!')
    ]

    @api.depends('olt_id', 'board', 'port', 'allocated_onu')
    def _compute_port_location(self):
        """Calcula la ubicación completa del puerto"""
        for onu in self:
            if onu.olt_id and onu.board and onu.port and onu.allocated_onu:
                onu.port_location = f"{onu.olt_id.name}-Board{onu.board}-Port{onu.port}-ONU{onu.allocated_onu}"
            else:
                onu.port_location = "Ubicación no definida"

    @api.model
    def sync_from_api(self, olt_id=None):
        """Sincroniza ONUs desde la API de SmartOLT"""
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
            
            # Endpoint real de SmartOLT para obtener todas las ONUs
            # Si se especifica un OLT, filtramos por ese OLT para evitar sobrecarga
            if olt_id:
                url = f'{api_url}/api/onu/get_all_onus_details?olt_id={olt_id}'
            else:
                # Comenzamos con un OLT específico para evitar error 500
                # Más tarde implementaremos paginación o iteración por OLTs
                first_olt = self.env['smartolt.olt'].search([], limit=1)
                if first_olt:
                    url = f'{api_url}/api/onu/get_all_onus_details?olt_id={first_olt.olt_id}'
                    _logger.info(f'Sincronizando ONUs para OLT específico: {first_olt.name} (ID: {first_olt.olt_id})')
                else:
                    # Si no hay OLTs, intentamos obtener todas (puede fallar con 500)
                    url = f'{api_url}/api/onu/get_all_onus_details'
                    _logger.warning('No hay OLTs configurados, intentando obtener todas las ONUs (puede fallar)')
            
            _logger.info(f'Sincronizando ONUs desde: {url}')
            
            response = requests.get(url, headers=headers, timeout=timeout)
            _logger.info(f'Respuesta completa de la API: {response.text}')
            
            if response.status_code == 200:
                data = response.json()
                
                # Verificar diferentes estructuras de respuesta
                onu_data = None
                _logger.info(f'Debug: data.get("status") = {data.get("status")}')
                _logger.info(f'Debug: data.get("response_code") = {data.get("response_code")}')
                _logger.info(f'Debug: data.get("response") = {data.get("response")}')
                _logger.info(f'Debug: data.get("onus") = {data.get("onus")}')
                _logger.info(f'Debug: type(data) = {type(data)}')
                
                # La API de ONUs tiene una estructura diferente
                if data.get('onus') and isinstance(data.get('onus'), list):
                    onu_data = data.get('onus', [])
                    _logger.info(f'Debug: Usando data.get("onus") = {onu_data}')
                elif data.get('response_code') == 'success' and data.get('response'):
                    onu_data = data.get('response', [])
                    _logger.info(f'Debug: Usando data.get("response") = {onu_data}')
                elif data.get('status') == 'success' or data.get('status') == True:
                    onu_data = data.get('data', [])
                    _logger.info(f'Debug: Usando data.get("data") = {onu_data}')
                elif data.get('response') and isinstance(data.get('response'), list):
                    onu_data = data.get('response', [])
                    _logger.info(f'Debug: Usando data.get("response") con isinstance = {onu_data}')
                elif isinstance(data, list):
                    onu_data = data
                    _logger.info(f'Debug: Usando data directamente = {onu_data}')
                else:
                    _logger.warning(f'Estructura de respuesta inesperada: {data}')
                    onu_data = []
                
                _logger.info(f'Debug: onu_data final = {onu_data}')
                _logger.info(f'Debug: len(onu_data) = {len(onu_data) if onu_data else "None"}')
                
                _logger.info(f'Se encontraron {len(onu_data)} ONUs en la API')
                _logger.info(f'Estructura de datos: {type(onu_data)}')
                _logger.info(f'Primera ONU: {onu_data[0] if onu_data else "No hay datos"}')
                
                if onu_data:
                    # Procesar cada ONU
                    for onu_info in onu_data:
                        self._process_onu_data(onu_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s ONUs desde la API de SmartOLT') % len(onu_data),
                            'type': 'success',
                        }
                    }
                else:
                    _logger.warning('No se encontraron ONUs en la respuesta de la API')
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sin Datos'),
                            'message': _('No se encontraron ONUs para sincronizar'),
                            'type': 'warning',
                        }
                    }
            else:
                error_msg = f'Error HTTP {response.status_code}: {response.text}'
                raise UserError(_('Error en la API: %s') % error_msg)
                
        except UserError:
            raise
        except Exception as e:
            _logger.error(f'Error sincronizando ONUs: {e}')
            raise UserError(_('Error sincronizando ONUs: %s') % str(e))

    def _process_onu_data(self, onu_info):
        """Procesa los datos de una ONU individual con manejo robusto de transacciones"""
        # Usar savepoint para manejar errores individualmente sin afectar toda la transacción
        with self.env.cr.savepoint():
            try:
                # Buscar ONU existente por external_id (unique_external_id) que es más confiable
                existing_onu = self.search([
                    ('external_id', '=', str(onu_info.get('unique_external_id')))
                ], limit=1)
                
                # Buscar OLT relacionada
                olt_id = None
                if onu_info.get('olt_id'):
                    olt = self.env['smartolt.olt'].search([
                        ('olt_id', '=', str(onu_info.get('olt_id')))
                    ], limit=1)
                    if olt:
                        olt_id = olt.id
            
                # Generar un serial_number único si no existe o está vacío
                serial_number = onu_info.get('sn') or onu_info.get('serial_number')
                if not serial_number or serial_number.strip() == '':
                    # Usar unique_external_id como fallback para garantizar unicidad
                    serial_number = f"EXT_{onu_info.get('unique_external_id', 'UNKNOWN')}"
            
                # Buscar zona relacionada
                zone_id = None
                if onu_info.get('zone_id'):
                    zone = self.env['smartolt.zone'].search([
                        ('zone_id', '=', str(onu_info.get('zone_id')))
                    ], limit=1)
                    if zone:
                        zone_id = zone.id
            
                # Buscar ODB relacionado
                odb_id = None
                if onu_info.get('odb_name') and onu_info.get('odb_name').strip():
                    odb = self.env['smartolt.odb'].search([
                        ('name', '=', onu_info.get('odb_name'))
                    ], limit=1)
                    if odb:
                        odb_id = odb.id

                # Buscar perfil de velocidad relacionado
                speed_profile_id = None
                if onu_info.get('service_ports') and len(onu_info.get('service_ports')) > 0:
                    service_port = onu_info.get('service_ports')[0]
                    if service_port.get('download_speed'):
                        # Buscar perfil por nombre de velocidad
                        speed_profile = self.env['smartolt.speed_profile'].search([
                            ('name', '=', service_port.get('download_speed'))
                        ], limit=1)
                        if speed_profile:
                            speed_profile_id = speed_profile.id
                        else:
                            # Si no existe, crear el perfil automáticamente
                            speed_profile = self.env['smartolt.speed_profile'].create({
                                'name': service_port.get('download_speed'),
                                'profile_id': f"auto_{service_port.get('download_speed')}",
                                'olt_id': olt_id or 1,  # OLT por defecto si no hay
                                'download_speed': 0.0,  # Valor por defecto
                                'upload_speed': 0.0,    # Valor por defecto
                                'description': f'Perfil automático creado desde ONU {onu_info.get("sn", "desconocida")}',
                                'status': 'active'
                            })
                            speed_profile_id = speed_profile.id
            
                # Funciones de conversión segura
                def safe_int(value):
                    """Convierte valor a int de forma segura"""
                    if not value:
                        return None
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        _logger.warning(f'No se pudo convertir "{value}" a int para ONU {onu_info.get("sn", "desconocida")}')
                        return None
                
                def safe_float(value):
                    """Convierte valor a float de forma segura"""
                    if not value:
                        return None
                    try:
                        # Verificar que no sea un string que claramente no es numérico
                        if isinstance(value, str) and any(c.isalpha() for c in value):
                            _logger.warning(f'Valor "{value}" contiene letras, no se puede convertir a float para ONU {onu_info.get("sn", "desconocida")}')
                            return None
                        return float(value)
                    except (ValueError, TypeError):
                        _logger.warning(f'No se pudo convertir "{value}" a float para ONU {onu_info.get("sn", "desconocida")}')
                        return None
            
                # Procesar fecha de autorización
                auth_date = None
                if onu_info.get('authorization_date'):
                    try:
                        auth_date = fields.Datetime.from_string(onu_info.get('authorization_date'))
                    except:
                        auth_date = None
            
                # Mapear status de la API a valores válidos del modelo
                api_status = onu_info.get('status', 'Offline')
                valid_statuses = ['Online', 'Offline', 'LOS', 'Power fail', 'Log in']
                if api_status not in valid_statuses:
                    _logger.warning(f'Status desconocido encontrado: "{api_status}" para ONU {onu_info.get("sn", "desconocida")}. Usando "Offline" como fallback.')
                mapped_status = api_status if api_status in valid_statuses else 'Offline'
            
                onu_vals = {
                    'external_id': str(onu_info.get('unique_external_id', 'N/A')),
                    'serial_number': serial_number,
                    'name': onu_info.get('name') or onu_info.get('olt_name', 'ONU Sin Nombre'),
                    'onu_type': onu_info.get('onu_type_name') or onu_info.get('onu_type'),
                    'onu_type_id': onu_info.get('onu_type_id'),
                    'pon_type': onu_info.get('pon_type', 'gpon'),
                    'status': mapped_status,
                    'olt_id': olt_id,
                    'zone_id': zone_id,
                    'odb_splitter': odb_id,
                    'speed_profile_id': speed_profile_id,
                    'board': safe_int(onu_info.get('board')),
                    'port': safe_int(onu_info.get('port')),
                    'allocated_onu': safe_int(onu_info.get('onu')),
                    'address': onu_info.get('address'),
                    'latitude': safe_float(onu_info.get('latitude')),
                    'longitude': safe_float(onu_info.get('longitude')),
                    'mode': onu_info.get('mode'),
                    'wan_mode': onu_info.get('wan_mode'),
                    'ip_address': onu_info.get('ip_address'),
                    'subnet_mask': onu_info.get('subnet_mask'),
                    'default_gateway': onu_info.get('default_gateway'),
                    'dns1': onu_info.get('dns1'),
                    'dns2': onu_info.get('dns2'),
                    'username': onu_info.get('username'),
                    'password': onu_info.get('password'),
                    'catv': onu_info.get('catv'),
                    'administrative_status': onu_info.get('administrative_status'),
                    'auth_date': auth_date,
                    'signal': onu_info.get('signal'),
                    'signal_1310': safe_float(onu_info.get('signal_1310')),
                    'signal_1490': safe_float(onu_info.get('signal_1490')),
                    'distance': safe_float(onu_info.get('distance')),
                    'contact': onu_info.get('contact'),
                    'last_sync_date': fields.Datetime.now(),
                }
            
                # Procesar service_ports si existe
                if onu_info.get('service_ports') and len(onu_info.get('service_ports')) > 0:
                    service_port = onu_info.get('service_ports')[0]  # Tomar el primer puerto de servicio
                    onu_vals.update({
                        'service_port': safe_int(service_port.get('service_port')),
                        'service_port_vlan': service_port.get('vlan'),
                        'service_port_cvlan': service_port.get('cvlan'),
                        'service_port_svlan': service_port.get('svlan'),
                        'service_port_tag_transform_mode': service_port.get('tag_transform_mode'),
                        'service_port_upload_speed': service_port.get('upload_speed'),
                        'service_port_download_speed': service_port.get('download_speed'),
                    })
            
                # Procesar ethernet_ports si existe
                if onu_info.get('ethernet_ports') and len(onu_info.get('ethernet_ports')) > 0:
                    ethernet_port = onu_info.get('ethernet_ports')[0]  # Tomar el primer puerto Ethernet
                    onu_vals.update({
                        'ethernet_port': ethernet_port.get('port'),
                        'ethernet_admin_state': ethernet_port.get('admin_state'),
                    })
            
                _logger.info(f'Debug: Procesando ONU - Datos: {onu_info}')
                _logger.info(f'Debug: Valores a crear/actualizar: {onu_vals}')
                _logger.info(f'Debug: ONU existente encontrada: {existing_onu}')
                
                if existing_onu:
                    # Actualizar ONU existente
                    existing_onu.write(onu_vals)
                    _logger.info(f'ONU actualizada: {existing_onu.serial_number}')
                    return existing_onu
                else:
                    # Crear nueva ONU
                    if olt_id:  # Solo crear si hay OLT relacionada
                        new_onu = self.create(onu_vals)
                        _logger.info(f'Nueva ONU creada: {new_onu.serial_number}')
                        return new_onu
                    else:
                        _logger.warning(f'ONU {onu_info.get("unique_external_id", onu_info.get("sn", "desconocida"))} sin OLT asociada, se omite')
                        return False
                
            except Exception as e:
                # El savepoint automáticamente hace rollback de esta operación individual
                onu_identifier = onu_info.get("unique_external_id") or onu_info.get("sn") or "desconocida"
                _logger.error(f'Error procesando ONU {onu_identifier}: {e}')
                return False

    @api.model
    def sync_onus_by_olt(self, olt_id):
        """Sincroniza ONUs específicamente de un OLT"""
        try:
            import requests
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = 30
            
            headers = {
                'X-Token': api_token,
                'Content-Type': 'application/json'
            }
            
            # Endpoint específico para ONUs de un OLT
            url = f'{api_url}/api/onu/get_all_onus_details'
            params = {'olt_id': olt_id}
            
            _logger.info(f'Sincronizando ONUs del OLT {olt_id} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info(f'Respuesta API para OLT {olt_id}: {data}')
                
                # Verificar diferentes estructuras de respuesta
                onu_data = None
                if data.get('response_code') == 'success' and data.get('onus'):
                    onu_data = data.get('onus', [])
                elif data.get('response_code') == 'success' and data.get('response'):
                    onu_data = data.get('response', [])
                elif data.get('status') == 'success' or data.get('status') == True:
                    onu_data = data.get('data', []) or data.get('onus', [])
                elif data.get('onus'):
                    onu_data = data.get('onus', [])
                
                _logger.info(f'Se encontraron {len(onu_data) if onu_data else 0} ONUs en la API para OLT {olt_id}')
                
                if onu_data:
                    # Procesar cada ONU
                    for onu_info in onu_data:
                        self._process_onu_data(onu_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s ONUs del OLT %s desde la API de SmartOLT') % (len(onu_data), olt_id),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sin ONUs'),
                            'message': _('No se encontraron ONUs para el OLT %s') % olt_id,
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando ONUs del OLT {olt_id}: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando ONUs del OLT {olt_id}: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando ONUs del OLT {olt_id}: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando ONUs del OLT {olt_id}: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    @api.model
    def sync_onus_by_board(self, olt_id, board):
        """Sincroniza ONUs específicamente de un board de un OLT"""
        try:
            import requests
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = 30
            
            headers = {
                'X-Token': api_token,
                'Content-Type': 'application/json'
            }
            
            # Endpoint específico para ONUs de un board
            url = f'{api_url}/api/onu/get_all_onus_details'
            params = {
                'olt_id': olt_id,
                'board': board
            }
            
            _logger.info(f'Sincronizando ONUs del OLT {olt_id}, Board {board} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info(f'Respuesta API para OLT {olt_id}, Board {board}: {data}')
                
                # Verificar diferentes estructuras de respuesta
                onu_data = None
                if data.get('response_code') == 'success' and data.get('onus'):
                    onu_data = data.get('onus', [])
                elif data.get('response_code') == 'success' and data.get('response'):
                    onu_data = data.get('response', [])
                elif data.get('status') == 'success' or data.get('status') == True:
                    onu_data = data.get('data', []) or data.get('onus', [])
                elif data.get('onus'):
                    onu_data = data.get('onus', [])
                
                # Filtrar por board si viene mezclado
                if onu_data:
                    onu_data = [onu for onu in onu_data if str(onu.get('board', '')) == str(board)]
                
                _logger.info(f'Se encontraron {len(onu_data) if onu_data else 0} ONUs en la API para OLT {olt_id}, Board {board}')
                
                if onu_data:
                    # Procesar cada ONU
                    for onu_info in onu_data:
                        self._process_onu_data(onu_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s ONUs del OLT %s, Board %s desde la API de SmartOLT') % (len(onu_data), olt_id, board),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sin ONUs'),
                            'message': _('No se encontraron ONUs para el OLT %s, Board %s') % (olt_id, board),
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando ONUs del OLT {olt_id}, Board {board}: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando ONUs del OLT {olt_id}, Board {board}: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando ONUs del OLT {olt_id}, Board {board}: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando ONUs del OLT {olt_id}, Board {board}: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))

    @api.model
    def sync_onus_by_port(self, olt_id, board, port):
        """Sincroniza ONUs específicamente de un puerto de un board de un OLT"""
        try:
            import requests
            
            # Obtener configuración de la API
            config = self.env['smartolt.config'].get_config()
            api_url = config.get_api_url()
            api_token = config.get_api_token()
            timeout = 30
            
            headers = {
                'X-Token': api_token,
                'Content-Type': 'application/json'
            }
            
            # Endpoint específico para ONUs de un puerto
            url = f'{api_url}/api/onu/get_all_onus_details'
            params = {
                'olt_id': olt_id,
                'board': board,
                'port': port
            }
            
            _logger.info(f'Sincronizando ONUs del OLT {olt_id}, Board {board}, Puerto {port} desde: {url}')
            
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                _logger.info(f'Respuesta API para OLT {olt_id}, Board {board}, Puerto {port}: {data}')
                
                # Verificar diferentes estructuras de respuesta
                onu_data = None
                if data.get('response_code') == 'success' and data.get('onus'):
                    onu_data = data.get('onus', [])
                elif data.get('response_code') == 'success' and data.get('response'):
                    onu_data = data.get('response', [])
                elif data.get('status') == 'success' or data.get('status') == True:
                    onu_data = data.get('data', []) or data.get('onus', [])
                elif data.get('onus'):
                    onu_data = data.get('onus', [])
                
                # Filtrar por board y puerto si viene mezclado
                if onu_data:
                    onu_data = [onu for onu in onu_data if str(onu.get('board', '')) == str(board) and str(onu.get('port', '')) == str(port)]
                
                _logger.info(f'Se encontraron {len(onu_data) if onu_data else 0} ONUs en la API para OLT {olt_id}, Board {board}, Puerto {port}')
                
                if onu_data:
                    # Procesar cada ONU
                    for onu_info in onu_data:
                        self._process_onu_data(onu_info)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sincronización Exitosa'),
                            'message': _('Se sincronizaron %s ONUs del OLT %s, Board %s, Puerto %s desde la API de SmartOLT') % (len(onu_data), olt_id, board, port),
                            'type': 'success',
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Sin ONUs'),
                            'message': _('No se encontraron ONUs para el OLT %s, Board %s, Puerto %s') % (olt_id, board, port),
                            'type': 'info',
                        }
                    }
            else:
                raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
                
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.error(f'Error de conexión sincronizando ONUs del OLT {olt_id}, Board {board}, Puerto {port}: {e}')
            raise UserError(_('Error de conexión con la API de SmartOLT'))
        except requests.exceptions.Timeout as e:
            _logger.error(f'Timeout sincronizando ONUs del OLT {olt_id}, Board {board}, Puerto {port}: {e}')
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
        except requests.exceptions.RequestException as e:
            _logger.error(f'Error de petición HTTP sincronizando ONUs del OLT {olt_id}, Board {board}, Puerto {port}: {e}')
            raise UserError(_('Error de petición HTTP: %s') % str(e))
        except Exception as e:
            _logger.error(f'Error inesperado sincronizando ONUs del OLT {olt_id}, Board {board}, Puerto {port}: {e}')
            raise UserError(_('Error inesperado: %s') % str(e))
