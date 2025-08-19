# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging
import json
import time
import threading
from datetime import datetime

_logger = logging.getLogger(__name__)


class SmartOLTBulkProgressWizard(models.TransientModel):
    _name = 'smartolt.bulk.progress.wizard'
    _description = 'Ventana de Progreso Responsiva para Gestión Masiva'

    # Información del proceso
    parent_wizard_id = fields.Many2one('smartolt.bulk.plan.wizard', string='Wizard Principal')
    process_title = fields.Char('Título del Proceso', default='🚀 Gestión Masiva de Planes de Velocidad')
    
    # Progreso principal
    total_onus = fields.Integer('Total ONUs', default=0)
    processed_onus = fields.Integer('ONUs Procesadas', default=0)
    progress_percentage = fields.Float('Porcentaje de Progreso', compute='_compute_progress', store=True)
    
    # Información de lotes
    current_batch_num = fields.Integer('Número Lote Actual', default=0)
    total_batches = fields.Integer('Total Lotes', default=0)
    current_batch_info = fields.Char('Info Lote Actual', default='Preparando...')
    
    # Estadísticas en tiempo real
    success_count = fields.Integer('Éxitos', default=0)
    error_count = fields.Integer('Errores', default=0)
    warning_count = fields.Integer('Advertencias', default=0)
    
    # Estado del proceso (más responsivo)
    state = fields.Selection([
        ('running', 'Ejecutando'),
        ('completed', 'Completado'),
        ('error', 'Error'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='running')
    
    # Log en tiempo real
    log_output = fields.Text('Log en Tiempo Real', default='🚀 Iniciando proceso...\n')
    
    # Información de tiempo
    start_time = fields.Datetime('Hora de Inicio', default=fields.Datetime.now)
    end_time = fields.Datetime('Hora de Fin')
    
    # Datos para el proceso
    onu_data = fields.Text('Datos ONUs')
    upload_profile = fields.Char('Perfil Subida')
    download_profile = fields.Char('Perfil Bajada')
    remaining_onu_ids = fields.Text('ONUs Restantes (IDs)')
    
    @api.depends('processed_onus', 'total_onus')
    def _compute_progress(self):
        """Calcular porcentaje de progreso en tiempo real"""
        for record in self:
            if record.total_onus > 0:
                record.progress_percentage = min((record.processed_onus / record.total_onus) * 100, 100.0)
            else:
                record.progress_percentage = 0.0
    
    def _log_message(self, message, log_type='info'):
        """Agregar mensaje al log con timestamp y emojis"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Emojis por tipo de mensaje
        emoji_map = {
            'info': '📋',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'process': '🔄',
            'api': '🌐',
            'batch': '📦',
            'time': '⏱️',
            'stats': '📊'
        }
        
        emoji = emoji_map.get(log_type, '📋')
        formatted_message = f"[{timestamp}] {emoji} {message}"
        
        # Actualizar log (mantener últimas 100 líneas para rendimiento)
        current_log = self.log_output or ''
        lines = current_log.split('\n')
        lines.append(formatted_message)
        
        if len(lines) > 100:
            lines = lines[-100:]
        
        self.log_output = '\n'.join(lines)
        
        # Log también en servidor para debugging
        _logger.info(f"Progress Log: {formatted_message}")
    
    def _update_progress_ui(self):
        """Actualizar interfaz de usuario inmediatamente"""
        # Forzar recálculo de campos computados
        self._compute_progress()
        
        # Commit inmediato para reflejar cambios
        try:
            self.env.cr.commit()
        except Exception as e:
            _logger.warning(f"No se pudo hacer commit inmediato: {e}")
    
    def start_batch_process(self, onu_list, upload_profile, download_profile):
        """Proceso principal con actualizaciones en tiempo real"""
        try:
            _logger.info(f"🚀 Iniciando proceso responsivo para {len(onu_list)} ONUs")
            
            # Configuración inicial
            batch_size = 8  # Lotes más pequeños para mejor responsividad
            self.total_onus = len(onu_list)
            self.total_batches = (len(onu_list) + batch_size - 1) // batch_size
            self.processed_onus = 0
            self.current_batch_num = 0
            self.state = 'running'
            self.start_time = fields.Datetime.now()
            
            # Log inicial
            self._log_message(f"🎯 Configurando proceso para {self.total_onus} ONUs", 'process')
            self._log_message(f"📦 Dividido en {self.total_batches} lotes de máximo {batch_size} ONUs", 'info')
            self._log_message(f"📤 Perfil subida: {upload_profile}", 'info')
            self._log_message(f"📥 Perfil bajada: {download_profile}", 'info')
            self._log_message("=" * 50, 'info')
            
            # Actualizar UI inicial
            self._update_progress_ui()
            
            results = []
            
            # Procesar en lotes con actualizaciones en tiempo real
            for i in range(0, len(onu_list), batch_size):
                batch = onu_list[i:i + batch_size]
                self.current_batch_num = (i // batch_size) + 1
                self.current_batch_info = f"Procesando {len(batch)} ONUs"
                
                # Log inicio de lote
                self._log_message(f"📦 === LOTE {self.current_batch_num}/{self.total_batches} ===", 'batch')
                self._log_message(f"🔄 Procesando {len(batch)} ONUs...", 'process')
                
                # Actualizar UI antes del lote
                self._update_progress_ui()
                time.sleep(0.1)  # Pausa para UI
                
                # Procesar lote
                batch_result = self._process_batch_responsive(batch, upload_profile, download_profile)
                
                # Actualizar estadísticas
                if batch_result['success']:
                    self.success_count += len(batch)
                    self._log_message(f"✅ Lote completado: {len(batch)} ONUs actualizadas", 'success')
                    results.append(f"✅ Lote {self.current_batch_num}: {len(batch)} ONUs exitosas")
                else:
                    self.error_count += len(batch)
                    error_msg = batch_result.get('error', 'Error desconocido')
                    self._log_message(f"❌ Error en lote: {error_msg}", 'error')
                    results.append(f"❌ Lote {self.current_batch_num}: {error_msg}")
                
                # Actualizar progreso
                self.processed_onus += len(batch)
                self._log_message(f"📊 Progreso: {self.processed_onus}/{self.total_onus} ({self.progress_percentage:.1f}%)", 'stats')
                
                # Actualizar UI después del lote
                self._update_progress_ui()
                time.sleep(0.15)  # Pausa para responsividad
            
            # Finalizar proceso
            self.end_time = fields.Datetime.now()
            elapsed = self.end_time - self.start_time
            
            if self.error_count == 0:
                self.state = 'completed'
                self._log_message("=" * 50, 'info')
                self._log_message("🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!", 'success')
            else:
                self.state = 'error' if self.success_count == 0 else 'completed'
                self._log_message("=" * 50, 'info')
                self._log_message("⚠️ Proceso completado con errores", 'warning')
            
            # Estadísticas finales
            self._log_message(f"📊 RESUMEN FINAL:", 'stats')
            self._log_message(f"   ✅ Éxitos: {self.success_count}", 'success')
            self._log_message(f"   ❌ Errores: {self.error_count}", 'error')
            self._log_message(f"   ⏱️ Tiempo: {elapsed}", 'time')
            
            # Actualizar registros locales si hay éxitos
            if self.success_count > 0:
                self._update_local_records_responsive(onu_list[:self.success_count], upload_profile, download_profile)
            
            # Actualización final de UI
            self._update_progress_ui()
            
            return {
                'success_count': self.success_count,
                'error_count': self.error_count,
                'results': results
            }
            
        except Exception as e:
            self.state = 'error'
            self.end_time = fields.Datetime.now()
            error_msg = f"💥 Error crítico: {str(e)}"
            self._log_message(error_msg, 'error')
            self._update_progress_ui()
            _logger.error(f"Error crítico en proceso responsivo: {e}")
            raise UserError(_(error_msg))
    
    def _process_batch_responsive(self, onu_batch, upload_profile, download_profile):
        """Procesar lote con logging responsivo"""
        try:
            # Obtener configuración
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'Sin configuración API'}
            
            # Preparar external_ids
            external_ids = [onu.external_id for onu in onu_batch if onu.external_id]
            if not external_ids:
                self._log_message("⚠️ No hay external_ids válidos", 'warning')
                return {'success': False, 'error': 'Sin external_ids válidos'}
            
            self._log_message(f"🌐 Llamando API para {len(external_ids)} ONUs...", 'api')
            
            # Preparar petición
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'onus_external_ids': ','.join(external_ids),
                'upload_speed_profile_name': upload_profile,
                'download_speed_profile_name': download_profile
            }
            
            url = f'{config.api_url}/api/onu/bulk_update_speed_profiles'
            
            # Actualizar UI antes de API call
            self._update_progress_ui()
            
            # Hacer petición
            response = requests.post(url, headers=headers, data=data, timeout=30)
            
            self._log_message(f"📡 Respuesta API: HTTP {response.status_code}", 'api')
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('response_code') == 'success' or response_data.get('status') == True:
                    self._log_message("✅ API respondió exitosamente", 'success')
                    return {'success': True, 'data': response_data}
                else:
                    error_msg = response_data.get('error', 'Error en API')
                    self._log_message(f"❌ API error: {error_msg}", 'error')
                    return {'success': False, 'error': error_msg}
            else:
                error_msg = f'HTTP {response.status_code}'
                self._log_message(f"🚫 Error HTTP: {error_msg}", 'error')
                return {'success': False, 'error': error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = "⏱️ Timeout de API (30s)"
            self._log_message(error_msg, 'error')
            return {'success': False, 'error': error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"🌐 Error conexión: {str(e)[:50]}"
            self._log_message(error_msg, 'error')
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"💥 Error inesperado: {str(e)[:50]}"
            self._log_message(error_msg, 'error')
            return {'success': False, 'error': error_msg}
    
    def _update_local_records_responsive(self, successful_onus, upload_profile, download_profile):
        """Actualizar registros locales con feedback"""
        try:
            self._log_message(f"💾 Actualizando {len(successful_onus)} registros locales...", 'process')
            
            updated_count = 0
            for onu in successful_onus:
                try:
                    onu.write({
                        'service_port_upload_speed': upload_profile,
                        'service_port_download_speed': download_profile,
                        'last_sync_date': fields.Datetime.now()
                    })
                    updated_count += 1
                except Exception as e:
                    self._log_message(f"⚠️ Error actualizando ONU {onu.serial_number}: {str(e)[:30]}", 'warning')
            
            self._log_message(f"✅ {updated_count} registros actualizados localmente", 'success')
            
        except Exception as e:
            self._log_message(f"⚠️ Error en actualización local: {str(e)[:50]}", 'warning')
    
    def refresh(self):
        """Refrescar la vista de progreso"""
        self._update_progress_ui()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'smartolt.bulk.progress.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }
    
    def action_refresh(self):
        """Refrescar la vista de progreso (alias)"""
        return self.refresh()
    
    def cancel_process(self):
        """Cancelar proceso en curso"""
        if self.state == 'running':
            self.state = 'cancelled'
            self.end_time = fields.Datetime.now()
            self._log_message("🛑 Proceso cancelado por el usuario", 'warning')
            self._update_progress_ui()
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_cancel_process(self):
        """Cancelar proceso en curso (alias)"""
        return self.cancel_process()
    
    def start_process_manual(self):
        """Iniciar el proceso real de actualización masiva"""
        if not self.parent_wizard_id:
            self._log_message("❌ Error: No hay wizard principal asociado", 'error')
            return
        
        # Obtener información
        onus = list(self.parent_wizard_id.onu_ids)
        upload_profile = self.upload_profile
        download_profile = self.download_profile
        
        if not onus:
            self._log_message("❌ Error: No hay ONUs para procesar", 'error')
            return
        
        # Mensaje inicial
        self._log_message(f"🚀 Iniciando proceso REAL para {len(onus)} ONUs", 'process')
        self._log_message(f"📤 Perfil subida: {upload_profile}", 'info')
        self._log_message(f"📥 Perfil bajada: {download_profile}", 'info')
        self._log_message("=" * 50, 'info')
        
        # Preparar estado inicial
        self.state = 'running'
        self.processed_onus = 0
        self.success_count = 0
        self.error_count = 0
        self.warning_count = 0
        
        # Configurar lotes
        batch_size = 8
        total_batches = (len(onus) + batch_size - 1) // batch_size
        self.total_batches = total_batches
        self.current_batch_num = 0
        self.current_batch_info = 'Iniciando proceso real...'
        
        self._update_progress_ui()
        
        # Ejecutar solo el primer lote y retornar inmediatamente
        try:
            # Marcar que el proceso ha iniciado
            self._log_message("🔥 PROCESO REAL INICIADO - Procesando primer lote", 'process')
            
            # Ejecutar solo el primer lote para no bloquear
            batch_size = 8
            first_batch = onus[:batch_size]
            remaining_onus = onus[batch_size:]
            
            if first_batch:
                self.current_batch_num = 1
                self.current_batch_info = f"Procesando lote 1 ({len(first_batch)} ONUs)"
                self._log_message(f"📦 Procesando lote 1 con {len(first_batch)} ONUs", 'batch')
                
                # Procesar primer lote
                result = self._process_batch_responsive(first_batch, upload_profile, download_profile)
                
                if result['success']:
                    self.success_count += len(first_batch)
                    self._log_message(f"✅ Lote 1 completado: {len(first_batch)} ONUs actualizadas", 'success')
                else:
                    self.error_count += len(first_batch)
                    self._log_message(f"❌ Error en lote 1: {result.get('error', 'Error desconocido')}", 'error')
                
                self.processed_onus += len(first_batch)
                
                # Guardar progreso restante para continuar después
                if remaining_onus:
                    self.write({
                        'remaining_onu_ids': str([onu.id for onu in remaining_onus]),
                        'current_batch_num': 1,
                        'upload_profile': upload_profile,
                        'download_profile': download_profile
                    })
            
            self._update_progress_ui()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '🚀 Primer Lote Procesado',
                    'message': f'Lote 1 completado. {len(remaining_onus) if remaining_onus else 0} ONUs restantes. Usa "🔄 Continuar" para el siguiente lote.',
                    'type': 'success',
                    'sticky': False
                }
            }
            
        except Exception as e:
            self._log_message(f"❌ Error al iniciar proceso: {str(e)}", 'error')
            self.state = 'error'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '❌ Error',
                    'message': f'Error al iniciar proceso: {str(e)}',
                    'type': 'danger',
                    'sticky': True
                }
            }
    
    def continue_next_batch(self):
        """Continuar con el siguiente lote de ONUs"""
        try:
            if not self.remaining_onu_ids:
                self._log_message("✅ No hay más lotes que procesar", 'success')
                if self.processed_onus >= self.total_onus:
                    self.state = 'completed'
                    self.end_time = fields.Datetime.now()
                    self._log_message("🎉 ¡Proceso completado!", 'success')
                return {'type': 'ir.actions.client', 'tag': 'reload'}
            
            # Obtener ONUs restantes
            import ast
            remaining_ids = ast.literal_eval(self.remaining_onu_ids)
            remaining_onus = self.env['smartolt.onu'].browse(remaining_ids)
            
            if not remaining_onus:
                self._log_message("✅ No hay más ONUs que procesar", 'success')
                self.state = 'completed'
                return {'type': 'ir.actions.client', 'tag': 'reload'}
            
            # Procesar siguiente lote
            batch_size = 8
            current_batch = remaining_onus[:batch_size]
            new_remaining = remaining_onus[batch_size:]
            
            self.current_batch_num += 1
            self.current_batch_info = f"Procesando lote {self.current_batch_num} ({len(current_batch)} ONUs)"
            self._log_message(f"📦 Procesando lote {self.current_batch_num} con {len(current_batch)} ONUs", 'batch')
            
            # Procesar lote actual
            result = self._process_batch_responsive(current_batch, self.upload_profile, self.download_profile)
            
            if result['success']:
                self.success_count += len(current_batch)
                self._log_message(f"✅ Lote {self.current_batch_num} completado: {len(current_batch)} ONUs actualizadas", 'success')
            else:
                self.error_count += len(current_batch)
                self._log_message(f"❌ Error en lote {self.current_batch_num}: {result.get('error', 'Error desconocido')}", 'error')
            
            self.processed_onus += len(current_batch)
            
            # Actualizar ONUs restantes
            if new_remaining:
                self.remaining_onu_ids = str([onu.id for onu in new_remaining])
            else:
                self.remaining_onu_ids = ''
                if self.processed_onus >= self.total_onus:
                    self.state = 'completed'
                    self.end_time = fields.Datetime.now()
                    self._log_message("🎉 ¡Proceso completado completamente!", 'success')
            
            self._update_progress_ui()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': f'📦 Lote {self.current_batch_num} Completado',
                    'message': f'{len(new_remaining) if new_remaining else 0} ONUs restantes. Progreso: {self.processed_onus}/{self.total_onus}',
                    'type': 'success' if result['success'] else 'warning',
                    'sticky': False
                }
            }
            
        except Exception as e:
            self._log_message(f"❌ Error procesando lote: {str(e)}", 'error')
            return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def simulate_progress(self):
        """Simular progreso incrementando valores sin bloquear"""
        try:
            # Incrementar progreso simulado
            if self.processed_onus < self.total_onus:
                # Simular procesamiento de 5-10 ONUs
                increment = min(10, self.total_onus - self.processed_onus)
                self.processed_onus += increment
                
                # Simular algunos éxitos y errores
                successes = max(1, int(increment * 0.8))  # 80% éxito
                errors = increment - successes
                self.success_count += successes
                self.error_count += errors
                
                # Actualizar lote actual
                batch_size = 8
                self.current_batch_num = (self.processed_onus // batch_size) + 1
                self.current_batch_info = f"Procesando lote {self.current_batch_num}"
                
                # Agregar mensajes al log
                self._log_message(f"📦 Lote {self.current_batch_num} procesado: {successes} éxitos, {errors} errores", 'batch')
                self._log_message(f"📊 Progreso: {self.processed_onus}/{self.total_onus} ({self.progress_percentage:.1f}%)", 'stats')
                
                # Si terminó, cambiar estado
                if self.processed_onus >= self.total_onus:
                    self.state = 'completed'
                    self.end_time = fields.Datetime.now()
                    self._log_message("🎉 ¡Proceso completado!", 'success')
            
            self._update_progress_ui()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '📊 Progreso Actualizado',
                    'message': f'Procesadas {self.processed_onus}/{self.total_onus} ONUs',
                    'type': 'info',
                    'sticky': False
                }
            }
            
        except Exception as e:
            self._log_message(f"❌ Error en simulación: {str(e)}", 'error')
            return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    @api.model
    def _execute_process_background(self):
        """Ejecutar el proceso en segundo plano"""
        try:
            # Obtener datos del contexto
            progress_wizard_id = self.env.context.get('progress_wizard_id')
            onu_ids = self.env.context.get('onu_ids', [])
            upload_profile = self.env.context.get('upload_profile')
            download_profile = self.env.context.get('download_profile')
            
            if not progress_wizard_id:
                return
            
            # Obtener el wizard de progreso
            progress_wizard = self.browse(progress_wizard_id)
            if not progress_wizard.exists():
                return
            
            # Obtener las ONUs
            onus = self.env['smartolt.onu'].browse(onu_ids)
            if not onus:
                progress_wizard._log_message("❌ Error: No se encontraron ONUs", 'error')
                return
            
            # Ejecutar el proceso
            progress_wizard.start_batch_process(list(onus), upload_profile, download_profile)
            
        except Exception as e:
            _logger.error(f"Error en proceso background: {e}")
            if progress_wizard_id:
                try:
                    progress_wizard = self.browse(progress_wizard_id)
                    progress_wizard._log_message(f"💥 Error crítico: {str(e)}", 'error')
                    progress_wizard.state = 'error'
                except:
                    pass
    
    def action_close(self):
        """Cerrar ventana"""
        return {'type': 'ir.actions.act_window_close'}