# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SmartOLTConfig(models.Model):
    _name = 'smartolt.config'
    _description = 'Configuración de SmartOLT'
    _rec_name = 'name'

    name = fields.Char('Nombre', required=True, default='Configuración Principal')
    
    # Configuración de API
    api_url = fields.Char('URL de la API', required=True, 
                         default='https://api.smartolt.com',
                         help='URL base de la API de SmartOLT')
    api_token = fields.Char('Token de API', required=True,
                           help='Token de autenticación para la API')
    
    # Configuración de conexión
    timeout = fields.Integer('Timeout (segundos)', default=30,
                           help='Tiempo de espera para las peticiones HTTP')
    max_retries = fields.Integer('Máximo de reintentos', default=3,
                                help='Número máximo de reintentos en caso de fallo')
    
    # Configuración de sincronización
    auto_sync_enabled = fields.Boolean('Sincronización automática', default=False,
                                      help='Habilitar sincronización automática')
    sync_interval = fields.Integer('Intervalo de sincronización (minutos)', default=60,
                                  help='Intervalo entre sincronizaciones automáticas')
    
    # Configuración de logging
    debug_mode = fields.Boolean('Modo debug', default=False,
                               help='Habilitar logging detallado')
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El nombre de configuración debe ser único!')
    ]

    @api.model
    def get_config(self):
        """Obtiene la configuración activa de SmartOLT"""
        config = self.search([], limit=1)
        if not config:
            # Crear configuración por defecto
            config = self.create({
                'name': 'Configuración por Defecto',
                'api_url': 'https://api.smartolt.com',
                'api_token': '',
                'timeout': 30,
                'max_retries': 3,
                'auto_sync_enabled': False,
                'sync_interval': 60,
                'debug_mode': False
            })
        return config

    @api.model
    def get_api_url(self):
        """Obtiene la URL de la API desde la configuración"""
        config = self.get_config()
        return config.api_url.rstrip('/')

    @api.model
    def get_api_token(self):
        """Obtiene el token de la API desde la configuración"""
        config = self.get_config()
        if not config.api_token:
            raise UserError(_('Token de API no configurado. Configure el token en SmartOLT > Configuración.'))
        return config.api_token

    @api.model
    def get_timeout(self):
        """Obtiene el timeout desde la configuración"""
        config = self.get_config()
        return config.timeout

    @api.model
    def get_max_retries(self):
        """Obtiene el máximo de reintentos desde la configuración"""
        config = self.get_config()
        return config.max_retries

    def test_connection(self):
        """Prueba la conexión con la API de SmartOLT usando el nuevo sistema de logging"""
        try:
            from ..utils.http_client import get_http_client
            
            # Crear cliente HTTP con logging
            http_client = get_http_client(self)
            
            # Probar conexión con endpoints específicos
            test_endpoints = [
                '/api/onu/get_all_onus_details',
                '/api/system/get_olts',
                '/api/system/get_zones',
                '/api/system/get_odbs',
                '/api/system/get_speed_profiles',
                '/api/olt/get_vlans/1',  # Endpoint correcto para VLANs (requiere OLT ID)
                '/api/system/get_system_info'
            ]
            
            _logger.info("🧪 Iniciando pruebas de conexión con SmartOLT API")
            
            # Realizar pruebas
            results = http_client.test_connection(test_endpoints)
            
            # Analizar resultados
            successful_endpoints = []
            failed_endpoints = []
            
            for result in results:
                if result['status'] == 'success':
                    successful_endpoints.append(result['endpoint'])
                else:
                    failed_endpoints.append(result)
            
            # Generar reporte
            if successful_endpoints:
                success_msg = f"✅ Conexión exitosa con {len(successful_endpoints)} endpoints:\n"
                for endpoint in successful_endpoints:
                    success_msg += f"  • {endpoint}\n"
                
                if failed_endpoints:
                    success_msg += f"\n⚠️  {len(failed_endpoints)} endpoints con problemas:\n"
                    for failure in failed_endpoints:
                        success_msg += f"  • {failure['endpoint']}: {failure['message']}\n"
                
                # Guardar configuración descubierta
                if successful_endpoints:
                    self._save_discovered_api_config(successful_endpoints[0])
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conexión Exitosa'),
                        'message': success_msg,
                        'type': 'success',
                    }
                }
            else:
                # Ningún endpoint funcionó
                error_msg = "❌ No se pudo conectar con ningún endpoint de la API:\n"
                for failure in failed_endpoints:
                    error_msg += f"  • {failure['endpoint']}: {failure['message']}\n"
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error de Conexión'),
                        'message': error_msg,
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error(f"💥 Error inesperado probando conexión: {e}")
            raise UserError(_('Error inesperado probando conexión: %s') % str(e))

    def _save_discovered_api_config(self, endpoint):
        """Guarda la configuración de API descubierta"""
        try:
            # Crear o actualizar parámetros del sistema con la configuración descubierta
            config_params = self.env['ir.config_parameter'].sudo()
            
            # Extraer la URL base del endpoint descubierto
            url_parts = endpoint['url'].split('/')
            if len(url_parts) >= 3:
                base_url = f"{url_parts[0]}//{url_parts[2]}"
                if len(url_parts) > 3:
                    base_url += '/' + '/'.join(url_parts[3:-1])
            else:
                base_url = endpoint['url'].rsplit('/', 1)[0]
            
            # Guardar la configuración descubierta
            config_params.set_param('smartolt.discovered_api_url', base_url)
            config_params.set_param('smartolt.discovered_api_method', endpoint['method'])
            config_params.set_param('smartolt.discovered_api_structure', json.dumps(endpoint))
            
            _logger.info(f'Configuración de API descubierta guardada: {base_url} con método {endpoint["method"]}')
            
        except Exception as e:
            _logger.error(f'Error guardando configuración descubierta: {e}')

    def action_test_connection(self):
        """Acción para probar la conexión desde la interfaz"""
        return self.test_connection()
