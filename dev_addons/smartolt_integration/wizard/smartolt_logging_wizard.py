# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

class SmartOLTLoggingWizard(models.TransientModel):
    _name = 'smartolt.logging.wizard'
    _description = 'Wizard para Configuración de Logging de SmartOLT'

    log_level = fields.Selection([
        ('DEBUG', 'Debug - Muy detallado'),
        ('INFO', 'Info - Información general'),
        ('WARNING', 'Warning - Solo advertencias y errores'),
        ('ERROR', 'Error - Solo errores')
    ], string='Nivel de Logging', default='INFO', required=True)
    
    enable_file_logging = fields.Boolean('Habilitar Logging a Archivo', default=True)
    enable_console_logging = fields.Boolean('Habilitar Logging a Consola', default=True)
    log_file_path = fields.Char('Ruta del Archivo de Log', default='/var/log/odoo/smartolt/smartolt_api.log')
    
    @api.model
    def default_get(self, fields_list):
        """Obtener valores por defecto"""
        res = super().default_get(fields_list)
        
        # Obtener nivel actual de logging
        current_level = logging.getLogger('smartolt').getEffectiveLevel()
        level_names = {
            logging.DEBUG: 'DEBUG',
            logging.INFO: 'INFO',
            logging.WARNING: 'WARNING',
            logging.ERROR: 'ERROR'
        }
        res['log_level'] = level_names.get(current_level, 'INFO')
        
        return res

    def action_apply_logging_config(self):
        """Aplica la configuración de logging"""
        try:
            from ..utils.logging_config import SmartOLTLoggingConfig
            
            # Aplicar nivel de logging
            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR
            }
            
            selected_level = level_map.get(self.log_level, logging.INFO)
            
            # Configurar loggers principales
            loggers = ['smartolt', 'smartolt.api', 'smartolt.http', 'smartolt.sync', 'smartolt.data']
            for logger_name in loggers:
                SmartOLTLoggingConfig.set_log_level(logger_name, selected_level)
            
            # Configurar handlers según selección
            smartolt_logger = logging.getLogger('smartolt')
            
            # Limpiar handlers existentes
            for handler in smartolt_logger.handlers[:]:
                smartolt_logger.removeHandler(handler)
            
            # Agregar handlers según configuración
            if self.enable_console_logging:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(selected_level)
                console_formatter = logging.Formatter(
                    '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(console_formatter)
                smartolt_logger.addHandler(console_handler)
            
            if self.enable_file_logging:
                try:
                    import os
                    log_dir = os.path.dirname(self.log_file_path)
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir, exist_ok=True)
                    
                    file_handler = logging.FileHandler(self.log_file_path)
                    file_handler.setLevel(selected_level)
                    file_formatter = logging.Formatter(
                        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    )
                    file_handler.setFormatter(file_formatter)
                    smartolt_logger.addHandler(file_handler)
                    
                except Exception as e:
                    raise UserError(_('Error configurando logging a archivo: %s') % str(e))
            
            # Mensaje de confirmación
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuración Aplicada'),
                    'message': _('Configuración de logging aplicada exitosamente:\n'
                               '• Nivel: %s\n'
                               '• Consola: %s\n'
                               '• Archivo: %s') % (
                                   self.log_level,
                                   'Habilitado' if self.enable_console_logging else 'Deshabilitado',
                                   'Habilitado' if self.enable_file_logging else 'Deshabilitado'
                               ),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise UserError(_('Error aplicando configuración: %s') % str(e))

    def action_test_logging(self):
        """Prueba el sistema de logging"""
        try:
            from ..utils.logging_config import SmartOLTLoggingConfig
            
            logger = SmartOLTLoggingConfig.get_logger('smartolt.test')
            
            # Generar logs de prueba
            logger.debug('🔍 Este es un mensaje de DEBUG')
            logger.info('ℹ️ Este es un mensaje de INFO')
            logger.warning('⚠️ Este es un mensaje de WARNING')
            logger.error('💥 Este es un mensaje de ERROR')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Logging de Prueba'),
                    'message': _('Se han generado mensajes de prueba en el sistema de logging.\n'
                               'Verifica la consola y el archivo de log para confirmar que funcionan correctamente.'),
                    'type': 'info',
                }
            }
            
        except Exception as e:
            raise UserError(_('Error probando logging: %s') % str(e))

    def action_clear_logs(self):
        """Limpia los logs existentes"""
        try:
            if self.enable_file_logging and self.log_file_path:
                import os
                if os.path.exists(self.log_file_path):
                    # Crear backup antes de limpiar
                    backup_path = f"{self.log_file_path}.backup"
                    import shutil
                    shutil.copy2(self.log_file_path, backup_path)
                    
                    # Limpiar archivo
                    with open(self.log_file_path, 'w') as f:
                        f.write(f"# Logs limpiados el {fields.Datetime.now()}\n")
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Logs Limpiados'),
                            'message': _('Los logs han sido limpiados exitosamente.\n'
                                       'Se creó un backup en: %s') % backup_path,
                            'type': 'success',
                        }
                    }
                else:
                    raise UserError(_('El archivo de log no existe'))
            else:
                raise UserError(_('El logging a archivo no está habilitado'))
                
        except Exception as e:
            raise UserError(_('Error limpiando logs: %s') % str(e))
