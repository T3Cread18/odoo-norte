# -*- coding: utf-8 -*-

import logging
import logging.handlers
import os
from odoo import models, fields, api, _

class SmartOLTLoggingConfig:
    """Configuración de logging para SmartOLT Integration"""
    
    @staticmethod
    def setup_logging():
        """Configura el sistema de logging para SmartOLT"""
        
        # Crear logger principal
        logger = logging.getLogger('smartolt')
        logger.setLevel(logging.INFO)
        
        # Evitar duplicación de handlers
        if logger.handlers:
            return logger
        
        # Handler para consola con formato colorido
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato para consola
        console_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # Handler para archivo con rotación
        log_dir = '/var/log/odoo/smartolt'
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except:
                # Si no se puede crear, usar directorio temporal
                log_dir = '/tmp/smartolt_logs'
                os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, 'smartolt_api.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Formato para archivo (más detallado)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Agregar handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Configurar loggers específicos
        SmartOLTLoggingConfig._setup_specific_loggers()
        
        return logger
    
    @staticmethod
    def _setup_specific_loggers():
        """Configura loggers específicos para diferentes componentes"""
        
        # Logger para API
        api_logger = logging.getLogger('smartolt.api')
        api_logger.setLevel(logging.DEBUG)
        
        # Logger para HTTP
        http_logger = logging.getLogger('smartolt.http')
        http_logger.setLevel(logging.DEBUG)
        
        # Logger para sincronización
        sync_logger = logging.getLogger('smartolt.sync')
        sync_logger.setLevel(logging.INFO)
        
        # Logger para procesamiento de datos
        data_logger = logging.getLogger('smartolt.data')
        data_logger.setLevel(logging.INFO)
    
    @staticmethod
    def get_logger(name):
        """Obtiene un logger configurado"""
        return logging.getLogger(name)
    
    @staticmethod
    def set_log_level(logger_name, level):
        """Establece el nivel de logging para un logger específico"""
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    @staticmethod
    def enable_debug_mode():
        """Habilita el modo debug para todos los loggers de SmartOLT"""
        loggers = ['smartolt', 'smartolt.api', 'smartolt.http', 'smartolt.sync', 'smartolt.data']
        for logger_name in loggers:
            SmartOLTLoggingConfig.set_log_level(logger_name, logging.DEBUG)
    
    @staticmethod
    def disable_debug_mode():
        """Deshabilita el modo debug para todos los loggers de SmartOLT"""
        loggers = ['smartolt', 'smartolt.api', 'smartolt.http', 'smartolt.sync', 'smartolt.data']
        for logger_name in loggers:
            SmartOLTLoggingConfig.set_log_level(logger_name, logging.INFO)

# Configuración automática al importar
SmartOLTLoggingConfig.setup_logging()
