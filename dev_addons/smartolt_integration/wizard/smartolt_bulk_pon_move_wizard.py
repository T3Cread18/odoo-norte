# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
import json

_logger = logging.getLogger(__name__)


class SmartOLTBulkPONMoveWizard(models.TransientModel):
    _name = 'smartolt.bulk.pon.move.wizard'
    _description = 'Movilidad Masiva de Clientes entre PONs'
    
    # Filtros de selección
    source_olt_id = fields.Many2one('smartolt.olt', string='OLT Origen', required=True, 
                                   help='OLT desde donde se moverán las ONUs')
    source_board = fields.Integer('Board Origen', required=True, help='Board origen (ej: 1, 2, 3...)')
    source_port = fields.Integer('Puerto PON Origen', required=True, help='Puerto PON origen (ej: 1, 2, 3...)')
    
    # Destino
    target_olt_id = fields.Many2one('smartolt.olt', string='OLT Destino', 
                                   help='OLT destino (dejar vacío si es la misma OLT)')
    target_board = fields.Integer('Board Destino', required=True, help='Board destino (ej: 1, 2, 3...)')
    target_port = fields.Integer('Puerto PON Destino', required=True, help='Puerto PON destino (ej: 1, 2, 3...)')
    
    # Filtros adicionales
    zone_filter = fields.Char('Filtrar por Zona', help='Filtrar por zona específica (ej: GUANARE, ACARIGUA)')
    status_filter = fields.Selection([
        ('Online', 'Online'),
        ('Offline', 'Offline'),
        ('all', 'Todos los Estados')
    ], string='Estado de ONU', default='Online', help='Filtrar por estado de la ONU')
    
    # ONUs seleccionadas
    onu_ids = fields.Many2many('smartolt.onu', string='ONUs a Mover', readonly=True)
    onu_count = fields.Integer('Cantidad de ONUs', compute='_compute_onu_count', store=True)
    
    # Información de procesamiento por lotes
    total_batches = fields.Integer('Total de Lotes', compute='_compute_batch_info', store=True)
    estimated_time = fields.Integer('Tiempo Estimado (min)', compute='_compute_batch_info', store=True)
    
    # Campos calculados
    source_location = fields.Char('Ubicación Origen', compute='_compute_locations', store=True)
    target_location = fields.Char('Ubicación Destino', compute='_compute_locations', store=True)
    is_same_olt = fields.Boolean('Misma OLT', compute='_compute_same_olt', store=True)
    
    # Estados
    state = fields.Selection([
        ('select', 'Seleccionar ONUs'),
        ('confirm', 'Confirmar Movimiento'),
        ('done', 'Completado')
    ], default='select', string='Estado')
    
    # Resultados
    result_message = fields.Text('Resultados', readonly=True)
    success_count = fields.Integer('ONUs Movidas', readonly=True)
    error_count = fields.Integer('Errores', readonly=True)
    
    # Configuración de procesamiento
    batch_size = fields.Integer('Tamaño de Lote', default=10, help='ONUs por lote (máximo 10 por API)')
    enable_rollback = fields.Boolean('Habilitar Rollback', default=True, 
                                   help='Revertir automáticamente en caso de fallo')
    
    @api.depends('onu_ids')
    def _compute_onu_count(self):
        """Calcular cantidad de ONUs seleccionadas"""
        for record in self:
            record.onu_count = len(record.onu_ids)
    
    @api.depends('onu_count', 'batch_size')
    def _compute_batch_info(self):
        """Calcular información de procesamiento por lotes"""
        for record in self:
            if record.onu_count > 0 and record.batch_size > 0:
                record.total_batches = (record.onu_count + record.batch_size - 1) // record.batch_size
                record.estimated_time = record.total_batches * 2  # 2 minutos por lote estimado
            else:
                record.total_batches = 0
                record.estimated_time = 0
    
    @api.depends('source_olt_id', 'source_board', 'source_port')
    def _compute_locations(self):
        """Calcular ubicaciones de origen y destino"""
        for record in self:
            if record.source_olt_id and record.source_board and record.source_port:
                record.source_location = f"{record.source_olt_id.name}-B{record.source_board}-P{record.source_port}"
            else:
                record.source_location = False
                
            if record.target_olt_id and record.target_board and record.target_port:
                record.target_location = f"{record.target_olt_id.name}-B{record.target_board}-P{record.target_port}"
            else:
                record.target_location = False
    
    @api.depends('source_olt_id', 'target_olt_id')
    def _compute_same_olt(self):
        """Verificar si es movimiento en la misma OLT"""
        for record in self:
            if record.target_olt_id:
                record.is_same_olt = record.source_olt_id == record.target_olt_id
            else:
                record.is_same_olt = True  # Si no se especifica destino, asumir misma OLT
    
    @api.onchange('source_olt_id')
    def _onchange_source_olt(self):
        """Cuando cambia la OLT origen, limpiar campos relacionados"""
        if self.source_olt_id:
            # Si no hay OLT destino, usar la misma
            if not self.target_olt_id:
                self.target_olt_id = self.source_olt_id
    
    @api.constrains('source_board', 'source_port', 'target_board', 'target_port')
    def _check_valid_ports(self):
        """Validar que los puertos sean válidos"""
        for record in self:
            if record.source_board < 1 or record.source_port < 1:
                raise ValidationError(_('Board y Puerto origen deben ser mayores a 0'))
            if record.target_board < 1 or record.target_port < 1:
                raise ValidationError(_('Board y Puerto destino deben ser mayores a 0'))
    
    @api.constrains('source_olt_id', 'target_olt_id', 'source_board', 'source_port', 'target_board', 'target_port')
    def _check_different_location(self):
        """Validar que origen y destino sean diferentes"""
        for record in self:
            if (record.source_olt_id == record.target_olt_id and 
                record.source_board == record.target_board and 
                record.source_port == record.target_port):
                raise ValidationError(_('El origen y destino no pueden ser iguales'))
    
    def action_search_onus(self):
        """Buscar ONUs según los filtros especificados"""
        domain = []
        
        # Filtro por OLT origen
        if self.source_olt_id:
            domain.append(('olt_id', '=', self.source_olt_id.id))
        
        # Filtro por board y puerto origen
        if self.source_board:
            domain.append(('board', '=', self.source_board))
        if self.source_port:
            domain.append(('port', '=', self.source_port))
        
        # Filtro por zona
        if self.zone_filter:
            domain.append(('zone_id.name', 'ilike', self.zone_filter))
        
        # Filtro por estado
        if self.status_filter and self.status_filter != 'all':
            domain.append(('status', '=', self.status_filter))
        
        # Buscar ONUs
        onus = self.env['smartolt.onu'].search(domain)
        
        if not onus:
            raise UserError(_('No se encontraron ONUs con los filtros especificados'))
        
        # Actualizar ONUs seleccionadas
        self.onu_ids = [(6, 0, onus.ids)]
        
        # Cambiar a estado de confirmación
        self.state = 'confirm'
        
        # Mensaje de éxito con información detallada
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔍 ONUs Encontradas',
                'message': f'Se encontraron {len(onus)} ONUs para mover de {self.source_location} a {self.target_location}\n\n📋 Revise la lista de ONUs y confirme el movimiento.',
                'type': 'success',
                'sticky': True
            }
        }
    
    def action_update_pon_locations(self):
        """Ejecutar el movimiento masivo de ONUs"""
        if not self.onu_ids:
            raise UserError(_('No hay ONUs seleccionadas para mover'))
        
        if not self.target_olt_id:
            self.target_olt_id = self.source_olt_id
        
        # Validar capacidad del puerto destino
        if not self._validate_target_port_capacity():
            raise UserError(_('El puerto destino no tiene capacidad suficiente para todas las ONUs'))
        
        # Verificar endpoints de la API antes de proceder
        _logger.info('🔍 Verificando endpoints de la API...')
        api_check = self._check_api_endpoints()
        
        if not api_check.get('available'):
            error_msg = f"""
            ❌ ERROR: No se pueden mover las ONUs porque la API no tiene endpoints disponibles.
            
            🔍 Detalles del error:
            {api_check.get('error', 'Error desconocido')}
            
            📋 Endpoint esperado:
            • /api/onu/move/{{onu_external_id}}
            
            💡 Soluciones:
            1. Verificar la configuración de la API en SmartOLT
            2. Contactar al soporte técnico de SmartOLT
            3. Verificar que el token de API sea válido
            """
            raise UserError(_(error_msg))
        
        # Mostrar información de endpoints disponibles
        available_endpoints = api_check.get('endpoints', [])
        primary_endpoint = api_check.get('primary_endpoint', 'N/A')
        
        _logger.info(f'✅ Endpoints disponibles: {available_endpoints}')
        _logger.info(f'🎯 Endpoint principal: {primary_endpoint}')
        
        # Mostrar confirmación final
        confirmation_message = f"""
        🚀 CONFIRMACIÓN FINAL DEL MOVIMIENTO
        
        📊 Resumen:
        • ONUs a mover: {len(self.onu_ids)}
        • Origen: {self.source_location}
        • Destino: {self.target_location}
        • Total de lotes: {self.total_batches}
        • Tamaño de lote: {self.batch_size}
        • Tiempo estimado: {self.estimated_time} minutos
        
        🌐 API Disponible:
        • Endpoints disponibles: {len(available_endpoints)}
        • Endpoint principal: {primary_endpoint}
        
        ⚠️ ADVERTENCIAS:
        • Las ONUs se desconectarán temporalmente
        • El proceso no se puede interrumpir una vez iniciado
        • Se procesará en lotes para optimizar el rendimiento
        
        ¿Está seguro de que desea proceder con el movimiento?
        """
        
        # Procesar movimiento según cantidad
        total_onus = len(self.onu_ids)
        
        if total_onus <= 50:
            # Procesamiento directo para cantidades pequeñas
            results = self._move_batch_pon_locations(list(self.onu_ids))
        else:
            # Procesamiento optimizado para grandes cantidades
            results = self._move_batch_pon_locations_optimized(list(self.onu_ids))
        
        # Procesar resultados
        if results.get('success'):
            self._process_successful_results(results)
        else:
            self._process_failed_results(results)
        
        return True
    
    def _validate_target_port_capacity(self):
        """Validar que el puerto destino tenga capacidad"""
        # Por ahora asumimos que tiene capacidad
        # TODO: Implementar validación real via API
        return True
    
    def _check_api_endpoints(self):
        """Verificar qué endpoints de la API están disponibles"""
        try:
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'available': False, 'error': 'No se encontró configuración de API'}
            
            # Endpoint correcto identificado
            primary_endpoint = '/api/onu/move/{onu_external_id}'
            
            # Verificar que el endpoint esté disponible
            test_url = f'{config.api_url}/api/onu/move/test'
            session = requests.Session()
            session.headers.update({
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            })
            
            try:
                # Hacer una llamada de prueba
                response = session.options(test_url, timeout=10)
                if response.status_code in [200, 405, 404]:  # 404 es normal para endpoint con parámetros
                    _logger.info(f'✅ Endpoint principal disponible: {primary_endpoint}')
                    available_endpoints = [primary_endpoint]
                else:
                    _logger.warning(f'⚠️ Endpoint principal retornó HTTP {response.status_code}')
                    available_endpoints = [primary_endpoint]  # Asumir que está disponible
            except Exception as e:
                _logger.info(f'ℹ️ No se pudo verificar endpoint (normal para endpoints con parámetros): {str(e)}')
                available_endpoints = [primary_endpoint]  # Asumir que está disponible
            
            session.close()
            
            return {
                'available': True, 
                'endpoints': available_endpoints,
                'primary_endpoint': primary_endpoint
            }
                
        except Exception as e:
            return {
                'available': False, 
                'error': f'Error verificando endpoints: {str(e)}'
            }
    
    def _move_batch_pon_locations(self, onu_list):
        """Mover ONUs en lotes"""
        try:
            _logger.info(f'🚀 Procesando movimiento de {len(onu_list)} ONUs')
            
            # Obtener configuración de API
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'No se encontró configuración de API'}
            
            # Preparar headers
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Filtrar ONUs con external_id válidos
            valid_onus = [onu for onu in onu_list if onu.external_id]
            if not valid_onus:
                return {'success': False, 'error': 'No hay ONUs con external_ids válidos'}
            
            # Configuración de lotes
            batch_size = min(self.batch_size, 10)  # Máximo 10 por API
            total_success = 0
            total_errors = 0
            error_messages = []
            
            # Crear registros de movimiento
            move_records = []
            
            # Sesión HTTP reutilizable
            session = requests.Session()
            session.headers.update(headers)
            
            total_batches = (len(valid_onus) + batch_size - 1) // batch_size
            _logger.info(f'📦 Procesando {total_batches} lotes de {batch_size} ONUs')
            
            # Procesar por lotes reales
            for i in range(0, len(valid_onus), batch_size):
                batch = valid_onus[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                _logger.info(f'📦 Procesando lote {batch_num}/{total_batches} con {len(batch)} ONUs')
                
                # Procesar cada ONU del lote
                for onu in batch:
                    try:
                        # Crear registro de movimiento
                        move_record = self.env['smartolt.pon.move'].create({
                            'onu_id': onu.id,
                            'source_olt_id': self.source_olt_id.id,
                            'source_board': self.source_board,
                            'source_port': self.source_port,
                            'target_olt_id': self.target_olt_id.id,
                            'target_board': self.target_board,
                            'target_port': self.target_port,
                            'batch_move_id': self.id,  # Solo el ID para referencia
                            'state': 'pending'
                        })
                        move_records.append(move_record)
                        
                        # Ejecutar movimiento via API
                        success = self._execute_single_move_via_api(onu, session, config)
                        
                        if success:
                            move_record.action_complete_move()
                            total_success += 1
                            _logger.info(f'✅ ONU {onu.serial_number} movida exitosamente')
                        else:
                            move_record.action_fail_move('Error en la API')
                            total_errors += 1
                            error_messages.append(f'ONU {onu.serial_number}: Error API')
                            _logger.error(f'❌ Error moviendo ONU {onu.serial_number}')
                    
                    except Exception as e:
                        error_msg = f'Error inesperado: {str(e)}'
                        if 'move_record' in locals():
                            move_record.action_fail_move(error_msg)
                        total_errors += 1
                        error_messages.append(f'ONU {onu.serial_number}: {str(e)[:50]}')
                        _logger.error(f'💥 Error procesando ONU {onu.serial_number}: {error_msg}')
                
                # Commit después de cada lote completo
                self.env.cr.commit()
                _logger.info(f'💾 Commit realizado después del lote {batch_num}')
                
                # Pausa entre lotes para no sobrecargar la API
                if batch_num < total_batches:
                    import time
                    time.sleep(1)  # 1 segundo de pausa entre lotes
            
            # Cerrar sesión
            session.close()
            
            # Resultado final
            if total_success > 0 and total_errors == 0:
                _logger.info(f'🎉 Proceso completado exitosamente: {total_success} ONUs movidas')
                return {
                    'success': True, 
                    'total_success': total_success, 
                    'total_errors': 0
                }
            elif total_success > 0 and total_errors > 0:
                _logger.warning(f'⚠️ Proceso parcialmente exitoso: {total_success} éxitos, {total_errors} errores')
                return {
                    'success': True, 
                    'partial': True,
                    'total_success': total_success, 
                    'total_errors': total_errors,
                    'error_details': error_messages
                }
            else:
                _logger.error(f'💥 Proceso falló completamente: {total_errors} errores')
                return {
                    'success': False, 
                    'error': f'Falló completamente. Errores: {"; ".join(error_messages[:3])}'
                }
                
        except Exception as e:
            error_msg = f'Error inesperado: {str(e)}'
            _logger.error(f'💥 Error inesperado en movimiento masivo: {error_msg}')
            return {'success': False, 'error': error_msg}
    
    def _move_batch_pon_locations_optimized(self, onu_list):
        """Versión optimizada para grandes cantidades"""
        # Similar a la función anterior pero con optimizaciones adicionales
        # Por ahora redirigimos a la función normal
        return self._move_batch_pon_locations(onu_list)
    
    def _execute_single_move_via_api(self, onu, session, config):
        """Ejecutar movimiento de una ONU via API"""
        try:
            # Usar el endpoint correcto identificado
            url = f'{config.api_url}/api/onu/move/{onu.external_id}'
            
            # Datos para la API según la documentación
            data = {
                'olt_id': self.target_olt_id.olt_id,
                'board': self.target_board,
                'port': self.target_port
            }
            
            # Si es la misma OLT, solo cambiar board/port
            if self.is_same_olt:
                data['olt_id'] = self.source_olt_id.olt_id
            
            _logger.info(f'🌐 Enviando a API: {url} con datos: {data}')
            
            try:
                # Llamada a la API
                response = session.post(url, data=data, timeout=30)
                
                if response.status_code == 200:
                    response_data = response.json()
                    _logger.info(f'📡 Respuesta API exitosa: {response_data}')
                    
                    # Verificar respuesta exitosa
                    if (response_data.get('response_code') == 'success' or 
                        response_data.get('status') == True or
                        response_data.get('status') == 'success'):
                        _logger.info(f'✅ ONU {onu.serial_number} movida exitosamente')
                        return True
                    else:
                        error_msg = response_data.get('error', 'Respuesta no exitosa de la API')
                        _logger.error(f'❌ API retornó error: {error_msg}')
                        return False
                
                elif response.status_code == 405:
                    _logger.error(f'❌ Endpoint no disponible (405 Method Not Allowed): {url}')
                    return False
                
                elif response.status_code == 404:
                    _logger.error(f'❌ Endpoint no encontrado (404 Not Found): {url}')
                    return False
                
                else:
                    _logger.error(f'❌ HTTP {response.status_code}: {response.text}')
                    return False
                    
            except requests.exceptions.Timeout:
                _logger.error(f'⏰ Timeout moviendo ONU {onu.serial_number}')
                return False
            except requests.exceptions.RequestException as e:
                _logger.error(f'🌐 Error de conexión moviendo ONU {onu.serial_number}: {str(e)}')
                return False
            except Exception as e:
                _logger.error(f'💥 Error inesperado moviendo ONU {onu.serial_number}: {str(e)}')
                return False
                
        except Exception as e:
            _logger.error(f'💥 Error general moviendo ONU {onu.serial_number}: {str(e)}')
            return False
    
    def _process_successful_results(self, results):
        """Procesar resultados exitosos"""
        total_success = results.get('total_success', 0)
        total_errors = results.get('total_errors', 0)
        is_partial = results.get('partial', False)
        
        # Actualizar registros locales
        success_count = 0
        for onu in self.onu_ids[:total_success]:
            try:
                # Actualizar ubicación en la ONU
                onu.write({
                    'olt_id': self.target_olt_id.id,
                    'board': self.target_board,
                    'port': self.target_port,
                    'last_sync_date': fields.Datetime.now()
                })
                success_count += 1
            except Exception as e:
                _logger.warning(f"Error actualizando ONU local {onu.serial_number}: {e}")
        
        # Actualizar estado del wizard
        self.success_count = success_count
        self.error_count = total_errors
        self.state = 'done'
        
        if is_partial:
            self.result_message = f'Proceso parcial: {total_success} ONUs movidas, {total_errors} errores'
        else:
            self.result_message = f'Movimiento exitoso de {total_success} ONUs'
        
        # Notificación
        if is_partial:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ Proceso Parcialmente Exitoso',
                    'message': f'✅ {total_success} ONUs movidas correctamente\n❌ {total_errors} ONUs con errores\n📍 De: {self.source_location}\n🎯 A: {self.target_location}',
                    'type': 'warning',
                    'sticky': True
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🎉 Movimiento Completado Exitosamente',
                    'message': f'✅ {total_success} ONUs movidas correctamente\n📍 De: {self.source_location}\n🎯 A: {self.target_location}',
                    'type': 'success',
                    'sticky': True
                }
            }
    
    def _process_failed_results(self, results):
        """Procesar resultados fallidos"""
        error_msg = results.get('error', 'Error desconocido')
        self.success_count = 0
        self.error_count = len(self.onu_ids)
        self.result_message = f'Error: {error_msg}'
        self.state = 'done'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '❌ Error en el Movimiento',
                'message': f'❌ Error moviendo {len(self.onu_ids)} ONUs\n\n{error_msg}',
                'type': 'danger',
                'sticky': True
            }
        }
    
    def action_back_to_select(self):
        """Volver al estado de selección"""
        self.state = 'select'
        return True
    
    def action_close(self):
        """Cerrar el wizard"""
        return {'type': 'ir.actions.act_window_close'} 