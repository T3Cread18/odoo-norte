# -*- coding: utf-8 -*-

import requests
import json
import time
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .api_logger import get_api_logger, get_response_handler

class SmartOLTHTTPClient:
    """Cliente HTTP especializado para SmartOLT con logging completo"""
    
    def __init__(self, config_model):
        self.config = config_model
        self.logger = get_api_logger('smartolt.http')
        self.response_handler = get_response_handler(self.logger)
        self.session = requests.Session()
        
        # Configurar timeout por defecto
        self.default_timeout = self.config.get_timeout()
        
        # Configurar headers por defecto
        self.default_headers = {
            'User-Agent': 'SmartOLT-Odoo-Integration/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def _get_auth_headers(self):
        """Obtiene headers de autenticación"""
        token = self.config.get_api_token()
        if not token:
            raise UserError(_('Token de API no configurado'))
        
        headers = self.default_headers.copy()
        headers['X-Token'] = token
        return headers
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None, timeout=None):
        """Realiza una petición HTTP con logging completo"""
        try:
            # Construir URL completa
            base_url = self.config.get_api_url()
            url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Headers finales
            final_headers = self._get_auth_headers()
            if headers:
                final_headers.update(headers)
            
            # Timeout
            final_timeout = timeout or self.default_timeout
            
            # Iniciar logging
            request_id = self.logger.start_request(method, url, params, final_headers)
            
            # Realizar petición
            if method.upper() == 'GET':
                response = self.session.get(
                    url, 
                    params=params, 
                    headers=final_headers, 
                    timeout=final_timeout
                )
            elif method.upper() == 'POST':
                response = self.session.post(
                    url, 
                    params=params, 
                    json=data, 
                    headers=final_headers, 
                    timeout=final_timeout
                )
            elif method.upper() == 'PUT':
                response = self.session.put(
                    url, 
                    params=params, 
                    json=data, 
                    headers=final_headers, 
                    timeout=final_timeout
                )
            elif method.upper() == 'DELETE':
                response = self.session.delete(
                    url, 
                    params=params, 
                    headers=final_headers, 
                    timeout=final_timeout
                )
            else:
                raise ValueError(f"Método HTTP no soportado: {method}")
            
            # Log de respuesta
            self.logger.log_response(response, request_id)
            
            # Finalizar logging
            self.logger.end_request(request_id)
            
            return response
            
        except requests.exceptions.ConnectionError as e:
            self.logger.log_error(e, request_id, {
                'method': method,
                'url': url,
                'error_type': 'ConnectionError'
            })
            self.logger.end_request(request_id)
            raise UserError(_('Error de conexión con la API de SmartOLT'))
            
        except requests.exceptions.Timeout as e:
            self.logger.log_error(e, request_id, {
                'method': method,
                'url': url,
                'timeout': final_timeout,
                'error_type': 'Timeout'
            })
            self.logger.end_request(request_id)
            raise UserError(_('Timeout de conexión con la API de SmartOLT'))
            
        except requests.exceptions.RequestException as e:
            self.logger.log_error(e, request_id, {
                'method': method,
                'url': url,
                'error_type': 'RequestException'
            })
            self.logger.end_request(request_id)
            raise UserError(_('Error de petición HTTP: %s') % str(e))
            
        except Exception as e:
            self.logger.log_error(e, request_id, {
                'method': method,
                'url': url,
                'error_type': 'UnexpectedError'
            })
            self.logger.end_request(request_id)
            raise UserError(_('Error inesperado: %s') % str(e))
    
    def get(self, endpoint, params=None, headers=None, timeout=None):
        """Realiza petición GET"""
        return self._make_request('GET', endpoint, params=params, headers=headers, timeout=timeout)
    
    def post(self, endpoint, data=None, params=None, headers=None, timeout=None):
        """Realiza petición POST"""
        return self._make_request('POST', endpoint, data=data, params=params, headers=headers, timeout=timeout)
    
    def put(self, endpoint, data=None, params=None, headers=None, timeout=None):
        """Realiza petición PUT"""
        return self._make_request('PUT', endpoint, data=data, params=params, headers=headers, timeout=timeout)
    
    def delete(self, endpoint, params=None, headers=None, timeout=None):
        """Realiza petición DELETE"""
        return self._make_request('DELETE', endpoint, params=params, headers=headers, timeout=timeout)
    
    def handle_response(self, response, expected_status_codes=[200], success_indicators=['success', True]):
        """Maneja la respuesta usando el response handler"""
        # Pasar el request_id actual al response handler
        self.response_handler.logger.request_id = self.logger.request_id
        return self.response_handler.handle_response(response, expected_status_codes, success_indicators)
    
    def test_connection(self, test_endpoints=None):
        """Prueba la conexión con diferentes endpoints"""
        if not test_endpoints:
            test_endpoints = [
                '/api/system/get_system_info',
                '/api/onu/get_all_onus_details',
                '/api/system/get_olts'
            ]
        
        results = []
        
        for endpoint in test_endpoints:
            try:
                self.logger.logger.info(f"🧪 Probando endpoint: {endpoint}")
                
                response = self.get(endpoint)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('status') in ['success', True]:
                            results.append({
                                'endpoint': endpoint,
                                'status': 'success',
                                'message': 'Endpoint funcionando correctamente'
                            })
                        else:
                            results.append({
                                'endpoint': endpoint,
                                'status': 'api_error',
                                'message': f"Error en API: {data.get('error', 'Desconocido')}"
                            })
                    except json.JSONDecodeError:
                        results.append({
                            'endpoint': endpoint,
                            'status': 'invalid_json',
                            'message': 'Respuesta no es JSON válido'
                        })
                elif response.status_code == 401:
                    results.append({
                        'endpoint': endpoint,
                        'status': 'unauthorized',
                        'message': 'Token de API inválido'
                    })
                elif response.status_code == 404:
                    results.append({
                        'endpoint': endpoint,
                        'status': 'not_found',
                        'message': 'Endpoint no encontrado'
                    })
                else:
                    results.append({
                        'endpoint': endpoint,
                        'status': 'http_error',
                        'message': f"Error HTTP {response.status_code}: {response.text}"
                    })
                    
            except Exception as e:
                results.append({
                    'endpoint': endpoint,
                    'status': 'exception',
                    'message': str(e)
                })
        
        return results

# Función helper para crear cliente
def get_http_client(config_model):
    """Obtiene un cliente HTTP configurado"""
    return SmartOLTHTTPClient(config_model)
