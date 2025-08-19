# -*- coding: utf-8 -*-

import logging
import json
import time
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SmartOLTAPILogger:
    """Logger especializado para APIs de SmartOLT"""
    
    def __init__(self, logger_name='smartolt.api'):
        self.logger = logging.getLogger(logger_name)
        self.request_id = None
        self.start_time = None
        
    def start_request(self, method, url, params=None, headers=None):
        """Inicia el logging de una petición"""
        self.request_id = f"req_{int(time.time() * 1000)}"
        self.start_time = time.time()
        
        # Log de inicio de petición
        self.logger.info(f"🚀 [{self.request_id}] INICIANDO PETICIÓN")
        self.logger.info(f"📍 [{self.request_id}] Método: {method}")
        self.logger.info(f"🌐 [{self.request_id}] URL: {url}")
        
        if params:
            self.logger.info(f"📝 [{self.request_id}] Parámetros: {json.dumps(params, indent=2)}")
        
        if headers:
            # Ocultar token en logs por seguridad
            safe_headers = headers.copy()
            if 'X-Token' in safe_headers:
                safe_headers['X-Token'] = f"{safe_headers['X-Token'][:8]}...{safe_headers['X-Token'][-4:]}"
            self.logger.info(f"🔑 [{self.request_id}] Headers: {json.dumps(safe_headers, indent=2)}")
        
        return self.request_id
    
    def log_response(self, response, request_id=None):
        """Log de respuesta de la API"""
        if not request_id:
            request_id = self.request_id
            
        if not request_id:
            self.logger.error("❌ No hay request_id para logging de respuesta")
            return
            
        # Calcular tiempo de respuesta
        response_time = time.time() - self.start_time if self.start_time else 0
        
        # Log de respuesta
        self.logger.info(f"📥 [{request_id}] RESPUESTA RECIBIDA")
        self.logger.info(f"⏱️  [{request_id}] Tiempo de respuesta: {response_time:.3f}s")
        self.logger.info(f"📊 [{request_id}] Status Code: {response.status_code}")
        self.logger.info(f"📏 [{request_id}] Tamaño respuesta: {len(response.content)} bytes")
        
        # Log de headers de respuesta
        response_headers = dict(response.headers)
        self.logger.info(f"🔍 [{request_id}] Headers respuesta: {json.dumps(response_headers, indent=2)}")
        
        # Log del contenido de la respuesta
        try:
            if response.headers.get('content-type', '').startswith('application/json'):
                response_data = response.json()
                self.logger.info(f"📋 [{request_id}] Contenido JSON: {json.dumps(response_data, indent=2)}")
            else:
                # Para respuestas no-JSON, mostrar primeros 500 caracteres
                content_preview = response.text[:500]
                if len(response.text) > 500:
                    content_preview += "... [TRUNCADO]"
                self.logger.info(f"📋 [{request_id}] Contenido: {content_preview}")
        except Exception as e:
            self.logger.error(f"❌ [{request_id}] Error parseando respuesta: {e}")
            self.logger.info(f"📋 [{request_id}] Contenido raw: {response.text[:500]}")
    
    def log_error(self, error, request_id=None, context=None):
        """Log de errores de la API"""
        if not request_id:
            request_id = self.request_id
            
        self.logger.error(f"💥 [{request_id}] ERROR EN API")
        self.logger.error(f"🚨 [{request_id}] Tipo de error: {type(error).__name__}")
        self.logger.error(f"📝 [{request_id}] Mensaje: {str(error)}")
        
        if context:
            self.logger.error(f"🔍 [{request_id}] Contexto: {json.dumps(context, indent=2)}")
        
        # Log del stack trace completo
        import traceback
        stack_trace = traceback.format_exc()
        self.logger.error(f"📚 [{request_id}] Stack trace:\n{stack_trace}")
    
    def log_success(self, message, request_id=None, data=None):
        """Log de operaciones exitosas"""
        if not request_id:
            request_id = self.request_id
            
        self.logger.info(f"✅ [{request_id}] ÉXITO: {message}")
        
        if data:
            if isinstance(data, (dict, list)):
                self.logger.info(f"📊 [{request_id}] Datos: {json.dumps(data, indent=2)}")
            else:
                self.logger.info(f"📊 [{request_id}] Datos: {data}")
    
    def log_warning(self, message, request_id=None, data=None):
        """Log de advertencias"""
        if not request_id:
            request_id = self.request_id
            
        self.logger.warning(f"⚠️  [{request_id}] ADVERTENCIA: {message}")
        
        if data:
            self.logger.warning(f"📊 [{request_id}] Datos: {json.dumps(data, indent=2)}")
    
    def end_request(self, request_id=None):
        """Finaliza el logging de una petición"""
        if not request_id:
            request_id = self.request_id
            
        if self.start_time:
            total_time = time.time() - self.start_time
            self.logger.info(f"🏁 [{request_id}] PETICIÓN COMPLETADA en {total_time:.3f}s")
        
        # Resetear variables
        self.request_id = None
        self.start_time = None

class SmartOLTResponseHandler:
    """Manejador de respuestas de la API con logging detallado"""
    
    def __init__(self, logger=None):
        self.logger = logger or SmartOLTAPILogger()
    
    def handle_response(self, response, expected_status_codes=[200], success_indicators=['success', True]):
        """Maneja la respuesta de la API con logging detallado"""
        request_id = self.logger.request_id
        
        # Log de la respuesta
        self.logger.log_response(response, request_id)
        
        # Verificar status code
        if response.status_code not in expected_status_codes:
            error_msg = f"Status code inesperado: {response.status_code}"
            self.logger.log_error(Exception(error_msg), request_id, {
                'expected_codes': expected_status_codes,
                'received_code': response.status_code,
                'response_text': response.text
            })
            raise UserError(_('Error HTTP %s: %s') % (response.status_code, response.text))
        
        # Parsear respuesta JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            self.logger.log_error(e, request_id, {'response_text': response.text})
            raise UserError(_('Error parseando respuesta JSON: %s') % str(e))
        
        # Verificar indicadores de éxito
        is_success = False
        for indicator in success_indicators:
            if response_data.get('status') == indicator:
                is_success = True
                break
        
        if is_success:
            self.logger.log_success("Respuesta exitosa de la API", request_id, response_data)
            return response_data
        else:
            error_msg = response_data.get('error', 'Error desconocido en la API')
            self.logger.log_error(Exception(error_msg), request_id, response_data)
            raise UserError(_('Error en la API: %s') % error_msg)
    
    def handle_error(self, error, context=None):
        """Maneja errores de la API con logging detallado"""
        request_id = self.logger.request_id
        self.logger.log_error(error, request_id, context)
        
        # Re-lanzar el error para que sea manejado por el código superior
        if isinstance(error, UserError):
            raise error
        else:
            raise UserError(_('Error inesperado: %s') % str(error))

# Función helper para crear logger
def get_api_logger(name='smartolt.api'):
    """Obtiene un logger de API configurado"""
    return SmartOLTAPILogger(name)

def get_response_handler(logger=None):
    """Obtiene un manejador de respuestas configurado"""
    return SmartOLTResponseHandler(logger)
