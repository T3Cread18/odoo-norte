# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class SmartOLTBulkPlanWizard(models.TransientModel):
    _name = 'smartolt.bulk.plan.wizard'
    _description = 'Gestión Masiva de Planes de Velocidad'

    # Filtros de selección
    olt_id = fields.Many2one('smartolt.olt', string='Filtrar por OLT', help='Seleccionar OLT específico (opcional)')
    current_plan_filter = fields.Char('Filtro Plan Actual', help='Filtrar por plan actual (ej: GUA-FTTH-RES-100M)')
    current_plan_speed_mb = fields.Integer('Velocidad Actual (MB)', help='Filtrar por velocidad de descarga específica (ej: 100 para buscar 100M en download)')
    zone_prefix = fields.Selection([
        ('GUA', 'GUANARE (GUA)'),
        ('ACA', 'ACARIGUA (ACA)'),
        ('BAR', 'BARINAS (BAR)'),
        ('APUR', 'APURE (APUR)')
    ], string='Zona', help='Filtrar por zona específica')
    
    # ONUs seleccionadas
    onu_ids = fields.Many2many('smartolt.onu', string='ONUs Seleccionadas', readonly=True)
    onu_count = fields.Integer('Cantidad de ONUs', compute='_compute_onu_count', store=True)
    
    # Nuevo plan
    new_speed_mb = fields.Integer('Nueva Velocidad DESCARGA (MB)', required=True, help='Velocidad de DESCARGA en MB (subida será la mitad automáticamente)')
    upload_speed_profile = fields.Char('Perfil Subida (Auto)', compute='_compute_speed_profiles', store=True)
    download_speed_profile = fields.Char('Perfil Bajada (Auto)', compute='_compute_speed_profiles', store=True)
    
    # Campos editables para personalizar velocidades
    custom_upload_speed = fields.Char('Velocidad Subida Personalizada', 
                                     help='Personalizar velocidad de subida (ej: GUA-FTTH-RES-50M). Si se deja vacío, se usará la mitad de la velocidad de descarga.')
    custom_download_speed = fields.Char('Velocidad Bajada Personalizada', 
                                       help='Personalizar velocidad de bajada (ej: GUA-FTTH-RES-100M). Si se deja vacío, se usará la velocidad automática.')
    
    # Campo para habilitar personalización
    enable_custom_speeds = fields.Boolean('Habilitar Velocidades Personalizadas', default=False,
                                         help='Marcar para personalizar velocidades de subida y bajada independientemente')
    
    # Estados
    state = fields.Selection([
        ('select', 'Seleccionar ONUs'),
        ('confirm', 'Confirmar Cambios'),
        ('done', 'Completado')
    ], default='select', string='Estado')
    
    # Resultados
    result_message = fields.Text('Resultados', readonly=True)
    success_count = fields.Integer('ONUs Actualizadas', readonly=True)
    error_count = fields.Integer('Errores', readonly=True)

    @api.depends('onu_ids')
    def _compute_onu_count(self):
        for record in self:
            record.onu_count = len(record.onu_ids)

    @api.depends('new_speed_mb', 'zone_prefix', 'enable_custom_speeds', 'custom_upload_speed', 'custom_download_speed')
    def _compute_speed_profiles(self):
        for record in self:
            if record.new_speed_mb and record.zone_prefix:
                if record.enable_custom_speeds:
                    # Usar velocidades personalizadas si están habilitadas
                    if record.custom_upload_speed:
                        record.upload_speed_profile = record.custom_upload_speed
                    else:
                        # Fallback a la mitad de la velocidad de descarga
                        upload_speed = record.new_speed_mb // 2
                        record.upload_speed_profile = f"{record.zone_prefix}-FTTH-RES-{upload_speed}M"
                    
                    if record.custom_download_speed:
                        record.download_speed_profile = record.custom_download_speed
                    else:
                        # Fallback a la velocidad automática
                        record.download_speed_profile = f"{record.zone_prefix}-FTTH-RES-{record.new_speed_mb}M"
                else:
                    # Planes asimétricos automáticos: upload es la mitad del download
                    upload_speed = record.new_speed_mb // 2  # Mitad de la velocidad de descarga
                    download_speed = record.new_speed_mb
                    
                    # Formato: (GUA/ACA/BAR/APUR)-FTTH-RES-(VELOCIDAD)M
                    record.upload_speed_profile = f"{record.zone_prefix}-FTTH-RES-{upload_speed}M"
                    record.download_speed_profile = f"{record.zone_prefix}-FTTH-RES-{download_speed}M"
            else:
                record.upload_speed_profile = False
                record.download_speed_profile = False

    def action_search_onus(self):
        """Buscar ONUs según los filtros especificados"""
        domain = []
        
        # Filtro por OLT
        if self.olt_id:
            domain.append(('olt_id', '=', self.olt_id.id))
        
        # Filtro por plan actual (texto completo)
        if self.current_plan_filter:
            # Buscar en los campos relacionados con velocidad/plan
            domain.extend([
                '|', '|', '|',
                ('service_port_upload_speed', 'ilike', self.current_plan_filter),
                ('service_port_download_speed', 'ilike', self.current_plan_filter),
                ('service_port_vlan', 'ilike', self.current_plan_filter),
                ('name', 'ilike', self.current_plan_filter)
            ])
        
        # Combinar filtros de zona y velocidad si ambos están presentes
        if self.zone_prefix and self.current_plan_speed_mb:
            # Caso especial: buscar zona + velocidad específica (ej: ACA-FTTH-RES-400M)
            combined_pattern = f'{self.zone_prefix}-FTTH-RES-{self.current_plan_speed_mb}M'
            domain.append(('service_port_download_speed', 'ilike', combined_pattern))
            
        elif self.current_plan_speed_mb:
            # Solo filtro por velocidad específica (número)
            speed_patterns = [
                f'{self.current_plan_speed_mb}M',           # Ej: 100M
                f'{self.current_plan_speed_mb}MB',          # Ej: 100MB  
                f'RES-{self.current_plan_speed_mb}M',       # Ej: RES-100M
                f'-{self.current_plan_speed_mb}M',          # Ej: -100M
                f'{self.current_plan_speed_mb}MBPS',        # Ej: 100MBPS
                f'{self.current_plan_speed_mb}',            # Ej: 100 (solo número)
            ]
            
            # Crear condiciones OR para todos los patrones
            speed_conditions = []
            for pattern in speed_patterns:
                speed_conditions.append(('service_port_download_speed', 'ilike', pattern))
            
            # Agregar condiciones con OR
            if len(speed_conditions) == 1:
                domain.append(speed_conditions[0])
            else:
                # Construir domain con OR entre los patrones
                or_domain = ['|'] * (len(speed_conditions) - 1) + speed_conditions
                domain.extend(or_domain)
                
        elif self.zone_prefix:
            # Solo filtro por zona (en la velocidad de descarga)
            domain.append(('service_port_download_speed', 'ilike', f'{self.zone_prefix}-'))
        
        # Debug: Log del domain construido
        _logger.info(f'Debug Filtrado: Domain construido: {domain}')
        _logger.info(f'Debug Filtrado: OLT={self.olt_id.name if self.olt_id else "Todos"}, Zona={self.zone_prefix}, Plan={self.current_plan_filter}, Velocidad={self.current_plan_speed_mb}')
        
        # Buscar ONUs
        onus = self.env['smartolt.onu'].search(domain)
        
        _logger.info(f'Debug Filtrado: Se encontraron {len(onus)} ONUs')
        if onus:
            # Log algunos ejemplos de velocidades de descarga encontradas
            sample_speeds = onus[:5].mapped('service_port_download_speed')
            _logger.info(f'Debug Filtrado: Ejemplos de velocidades de descarga: {sample_speeds}')
        
        if not onus:
            raise UserError(_('No se encontraron ONUs con los filtros especificados.'))
        
        # Actualizar las ONUs seleccionadas
        self.onu_ids = [(6, 0, onus.ids)]
        self.state = 'confirm'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'smartolt.bulk.plan.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def action_back_to_select(self):
        """Volver a la selección de ONUs"""
        self.state = 'select'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'smartolt.bulk.plan.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def action_update_plans(self):
        """Ejecutar el cambio masivo de planes con ventana de progreso"""
        if not self.onu_ids:
            raise UserError(_('No hay ONUs seleccionadas.'))
        
        if not self.new_speed_mb:
            raise UserError(_('Debe especificar la nueva velocidad.'))
        
        if not self.zone_prefix:
            raise UserError(_('Debe seleccionar la zona.'))
        
        try:
            _logger.info(f"🚀 Iniciando proceso de actualización masiva para {len(self.onu_ids)} ONUs")
            
            # Determinar velocidades finales
            final_upload = self.custom_upload_speed or self.upload_speed_profile
            final_download = self.custom_download_speed or self.download_speed_profile
            
            _logger.info(f"📤 Velocidad subida: {final_upload}")
            _logger.info(f"📥 Velocidad bajada: {final_download}")
            
            # Ejecutar el proceso con optimizaciones para evitar timeout
            _logger.info("🔧 Ejecutando proceso de actualización masiva...")
            
            # ⚡ NUEVA ESTRATEGIA OPTIMIZADA: Usar siempre el método optimizado
            total_onus = len(self.onu_ids)
            
            if total_onus > 50:
                # Para grandes cantidades, usar el método optimizado con agrupación inteligente
                _logger.info(f"🚀 Cantidad grande ({total_onus}) - Usando estrategia optimizada con agrupación en lotes de 10")
                _logger.info(f"⚡ Características: 10s entre lotes, 2 reintentos, timeout 15s por lote")
                results = self._update_batch_speed_profiles(list(self.onu_ids))
            else:
                # Para cantidades pequeñas, también usar el método optimizado
                _logger.info(f"🔧 Cantidad pequeña ({total_onus}) - Usando estrategia optimizada")
                results = self._update_batch_speed_profiles(list(self.onu_ids))
            
            # Procesar resultados
            if results.get('success'):
                # Obtener contadores
                total_success = results.get('total_success', 0)
                total_errors = results.get('total_errors', 0)
                is_partial = results.get('partial', False)
                is_partial_process = results.get('partial_process', False)
                
                # Actualizar registros locales para las ONUs exitosas
                success_count = 0
                for onu in self.onu_ids[:total_success]:  # Solo las primeras que fueron exitosas
                    try:
                        onu.write({
                            'service_port_upload_speed': final_upload,
                            'service_port_download_speed': final_download,
                            'last_sync_date': fields.Datetime.now()
                        })
                        success_count += 1
                    except Exception as e:
                        _logger.warning(f"Error actualizando ONU local {onu.serial_number}: {e}")
                
                # Actualizar estado del wizard
                self.success_count = success_count
                self.error_count = total_errors
                self.state = 'done'
                
                if is_partial_process:
                    # Procesamiento parcial por límite de tiempo
                    processed = results.get('processed', 0)
                    remaining = results.get('remaining', 0)
                    error_details = results.get('error_details', [])
                    
                    self.result_message = f'Proceso parcial completado: {total_success} éxitos, {remaining} pendientes'
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '⚡ Proceso Parcial Completado',
                            'message': f'✅ {total_success} ONUs procesadas correctamente\n⏳ {remaining} ONUs pendientes por límite de tiempo de Odoo\n📤 Subida: {final_upload}\n📥 Bajada: {final_download}\n\n💡 Ejecute nuevamente para procesar las {remaining} ONUs restantes',
                            'type': 'info',
                            'sticky': True
                        }
                    }
                elif is_partial:
                    # Proceso parcialmente exitoso
                    error_details = results.get('error_details', [])
                    retry_count = results.get('retry_count', 0)
                    self.result_message = f'Proceso parcial: {total_success} éxitos, {total_errors} errores'
                    
                    retry_info = f'\n🔄 {retry_count} reintentos realizados' if retry_count > 0 else ''
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '⚠️ Proceso Parcialmente Exitoso',
                            'message': f'✅ {total_success} ONUs actualizadas correctamente\n❌ {total_errors} ONUs con errores\n📤 Subida: {final_upload}\n📥 Bajada: {final_download}{retry_info}\n\nErrores: {"; ".join(error_details[:3])}',
                            'type': 'warning',
                            'sticky': True
                        }
                    }
                else:
                    # Proceso completamente exitoso
                    retry_count = results.get('retry_count', 0)
                    self.result_message = f'Actualización exitosa de {total_success} ONUs'
                    
                    retry_info = f'\n🔄 {retry_count} reintentos realizados para máxima fiabilidad' if retry_count > 0 else ''
                    mode_info = '🚀 Modo optimizado con reintentos automáticos' if len(self.onu_ids) > 50 else '⚡ Procesamiento directo completado'
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '🎉 Proceso Completado Exitosamente',
                            'message': f'✅ {total_success} ONUs actualizadas correctamente\n📤 Subida: {final_upload}\n📥 Bajada: {final_download}{retry_info}\n\n{mode_info}',
                            'type': 'success',
                            'sticky': True
                        }
                    }
            else:
                # Error en el proceso
                error_msg = results.get('error', 'Error desconocido')
                self.success_count = 0
                self.error_count = len(self.onu_ids)
                self.result_message = f'Error: {error_msg}'
                self.state = 'done'
                
                # Mostrar notificación de error
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '❌ Error en el Proceso',
                        'message': f'❌ Error procesando {len(self.onu_ids)} ONUs\n\n{error_msg}\n\nNota: La API permite máximo 10 ONUs por lote',
                        'type': 'danger',
                        'sticky': True
                    }
                }
            
        except Exception as e:
            _logger.error(f'Error en actualización masiva de planes: {e}')
            raise UserError(_('Error al actualizar planes: %s') % str(e))

    def _update_batch_speed_profiles(self, onu_list):
        """Actualizar ONUs mediante la API en lotes de máximo 10 con estrategia optimizada"""
        try:
            _logger.info(f'🚀 Iniciando actualización masiva optimizada de {len(onu_list)} ONUs')
            
            # Obtener configuración de API
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'No se encontró configuración de API'}
            
            # Preparar headers
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Obtener perfiles
            upload_profile = self.custom_upload_speed or self.upload_speed_profile
            download_profile = self.custom_download_speed or self.download_speed_profile
            
            # Filtrar ONUs con external_id válidos
            valid_onus = [onu for onu in onu_list if onu.external_id]
            if not valid_onus:
                return {'success': False, 'error': 'No hay ONUs con external_ids válidos'}
            
            _logger.info(f'📦 Procesando {len(valid_onus)} ONUs válidas en lotes de máximo 10')
            
            # ⚡ ESTRATEGIA OPTIMIZADA: Agrupación en lotes de 10 con tiempos de espera
            batch_size = 10
            total_success = 0
            total_errors = 0
            error_messages = []
            retry_count = 0
            
            # Sesión HTTP reutilizable para mejor rendimiento
            session = requests.Session()
            session.headers.update(headers)
            
            # Calcular total de lotes
            total_batches = (len(valid_onus) + batch_size - 1) // batch_size
            _logger.info(f'⚡ Estrategia optimizada: {total_batches} lotes con agrupación inteligente')
            
            # URL de la API
            url = f'{config.api_url}/api/onu/bulk_update_speed_profiles'
            
            # Procesar lotes con estrategia optimizada
            for i in range(0, len(valid_onus), batch_size):
                batch = valid_onus[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                _logger.info(f'🔄 Procesando lote {batch_num}/{total_batches} ({len(batch)} ONUs)')
                
                # Preparar external_ids del lote
                external_ids = [onu.external_id for onu in batch]
                
                # Preparar datos del formulario
                data = {
                    'onus_external_ids': ','.join(external_ids),
                    'upload_speed_profile_name': upload_profile,
                    'download_speed_profile_name': download_profile
                }
                
                # ⚡ ESTRATEGIA DE REINTENTOS: 2 intentos por lote
                success = False
                for attempt in range(2):
                    try:
                        _logger.info(f'📤 Lote {batch_num} - Intento {attempt + 1}/2')
                        
                        # Timeout balanceado: 15 segundos por lote
                        response = session.post(url, data=data, timeout=15)
                        
                        if response.status_code == 200:
                            response_data = response.json()
                            
                            if response_data.get('response_code') == 'success' or response_data.get('status') == True:
                                total_success += len(batch)
                                success = True
                                _logger.info(f'✅ Lote {batch_num}/{total_batches} exitoso - Total éxitos: {total_success}')
                                break  # Salir del loop de reintentos
                            else:
                                error_msg = response_data.get('error', 'Error API')
                                if attempt == 1:  # Último intento
                                    error_messages.append(f'L{batch_num}: {error_msg[:30]}')
                                    _logger.error(f'❌ Lote {batch_num} falló después de 2 intentos: {error_msg}')
                                else:
                                    _logger.warning(f'⚠️ Lote {batch_num} - Intento {attempt + 1} falló, reintentando...')
                                    
                        elif response.status_code == 500:
                            if attempt == 0:
                                _logger.warning(f'⚠️ HTTP 500 en lote {batch_num}, reintentando en 3s...')
                                import time
                                time.sleep(3)  # Espera antes del reintento
                                continue
                            else:
                                error_messages.append(f'L{batch_num}: HTTP500')
                                _logger.error(f'❌ HTTP 500 (Server Error) en lote {batch_num} después de reintento')
                        else:
                            if attempt == 1:
                                error_msg = f'HTTP {response.status_code}'
                                error_messages.append(f'L{batch_num}: {error_msg}')
                                _logger.error(f'❌ HTTP {response.status_code} en lote {batch_num}')
                            
                    except requests.exceptions.Timeout:
                        if attempt == 0:
                            _logger.warning(f'⚠️ Timeout en lote {batch_num}, reintentando...')
                            retry_count += 1
                            continue
                        else:
                            error_messages.append(f'L{batch_num}: Timeout15s')
                            _logger.error(f'⏱️ Timeout (15s) en lote {batch_num} después de reintento')
                            
                    except requests.exceptions.RequestException as e:
                        if attempt == 0:
                            _logger.warning(f'⚠️ Error conexión lote {batch_num}, reintentando...')
                            continue
                        else:
                            error_messages.append(f'L{batch_num}: Conexión')
                            _logger.error(f'🌐 Error conexión lote {batch_num} después de reintento: {str(e)[:30]}')
                    
                    except Exception as e:
                        if attempt == 1:
                            error_messages.append(f'L{batch_num}: Error-{str(e)[:10]}')
                            _logger.error(f'💥 Error inesperado en lote {batch_num}: {str(e)}')
                
                # Si no tuvo éxito después de 2 intentos
                if not success:
                    total_errors += len(batch)
                    _logger.error(f'❌ Lote {batch_num} falló completamente después de 2 intentos')
                
                # ⚡ TIEMPO DE ESPERA ENTRE LOTES: 10 segundos (similar a importaciones CSV)
                if batch_num < total_batches:  # No esperar después del último lote
                    _logger.info(f'⏳ Esperando 10 segundos antes del siguiente lote...')
                    import time
                    time.sleep(10)
                
                # Commit periódico para evitar timeouts de BD
                if batch_num % 5 == 0:
                    self.env.cr.commit()
                    _logger.info(f'💾 Commit BD - Lote {batch_num} | Éxitos: {total_success} | Errores: {total_errors}')
            
            # Cerrar sesión
            session.close()
            
            # Resultado final con información de reintentos
            _logger.info(f'🏁 Proceso optimizado completado: {total_success} éxitos, {total_errors} errores, {retry_count} reintentos')
            
            if total_success > 0 and total_errors == 0:
                _logger.info(f'🎉 Proceso completado exitosamente: {total_success} ONUs actualizadas')
                return {
                    'success': True, 
                    'total_success': total_success, 
                    'total_errors': 0,
                    'retry_count': retry_count
                }
            elif total_success > 0 and total_errors > 0:
                _logger.warning(f'⚠️ Proceso parcialmente exitoso: {total_success} éxitos, {total_errors} errores')
                return {
                    'success': True, 
                    'partial': True,
                    'total_success': total_success, 
                    'total_errors': total_errors,
                    'error_details': error_messages,
                    'retry_count': retry_count
                }
            else:
                _logger.error(f'💥 Proceso falló completamente: {total_errors} errores')
                return {
                    'success': False, 
                    'error': f'Falló completamente. Errores: {"; ".join(error_messages[:3])}',
                    'retry_count': retry_count
                }
                
        except Exception as e:
            error_msg = f'Error inesperado: {str(e)}'
            _logger.error(f'💥 Error inesperado en bulk update optimizado: {error_msg}')
            return {'success': False, 'error': error_msg}

    def _update_batch_speed_profiles_fast(self, onu_list):
        """Versión optimizada con reintentos para grandes cantidades de ONUs"""
        try:
            _logger.info(f'🚀⚡ Procesamiento OPTIMIZADO: {len(onu_list)} ONUs')
            
            # Obtener configuración de API
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'No se encontró configuración de API'}
            
            # Preparar headers
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Obtener perfiles
            upload_profile = self.custom_upload_speed or self.upload_speed_profile
            download_profile = self.custom_download_speed or self.download_speed_profile
            
            # Filtrar ONUs con external_id válidos
            valid_onus = [onu for onu in onu_list if onu.external_id]
            if not valid_onus:
                return {'success': False, 'error': 'No hay ONUs con external_ids válidos'}
            
            # Configuración optimizada con reintentos
            batch_size = 10
            total_success = 0
            total_errors = 0
            error_messages = []
            retry_count = 0
            
            # Sesión HTTP reutilizable con configuración optimizada
            session = requests.Session()
            session.headers.update(headers)
            
            total_batches = (len(valid_onus) + batch_size - 1) // batch_size
            _logger.info(f'⚡ MODO OPTIMIZADO: {total_batches} lotes - timeout 20s con reintentos')
            
            # URL de la API (preparar una vez)
            url = f'{config.api_url}/api/onu/bulk_update_speed_profiles'
            
            for i in range(0, len(valid_onus), batch_size):
                batch = valid_onus[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                # Preparar datos del lote
                external_ids = [onu.external_id for onu in batch]
                data = {
                    'onus_external_ids': ','.join(external_ids),
                    'upload_speed_profile_name': upload_profile,
                    'download_speed_profile_name': download_profile
                }
                
                # Intentar hasta 2 veces por lote
                success = False
                for attempt in range(2):
                    try:
                        # Timeout más realista para API pesada
                        response = session.post(url, data=data, timeout=20)
                        
                        if response.status_code == 200:
                            response_data = response.json()
                            if response_data.get('response_code') == 'success' or response_data.get('status') == True:
                                total_success += len(batch)
                                success = True
                                # Log cada 5 lotes para seguimiento
                                if batch_num % 5 == 0:
                                    _logger.info(f'✅ Lote {batch_num}/{total_batches} - Total éxitos: {total_success}')
                                break  # Salir del loop de reintentos
                            else:
                                error_msg = response_data.get('error', 'Error API')
                                if attempt == 1:  # Último intento
                                    error_messages.append(f'L{batch_num}:API-{error_msg[:15]}')
                                else:
                                    _logger.warning(f'⚠️ Reintentando lote {batch_num} - Error API: {error_msg[:30]}')
                        elif response.status_code == 500:
                            if attempt == 0:
                                _logger.warning(f'⚠️ HTTP 500 en lote {batch_num}, reintentando en 2s...')
                                import time
                                time.sleep(2)  # Espera antes del reintento
                                continue
                            else:
                                error_messages.append(f'L{batch_num}:HTTP500-final')
                        else:
                            if attempt == 1:
                                error_messages.append(f'L{batch_num}:HTTP{response.status_code}')
                        
                    except requests.exceptions.Timeout:
                        if attempt == 0:
                            _logger.warning(f'⚠️ Timeout en lote {batch_num}, reintentando...')
                            retry_count += 1
                            continue
                        else:
                            error_messages.append(f'L{batch_num}:Timeout20s-final')
                            
                    except requests.exceptions.RequestException as e:
                        if attempt == 0:
                            _logger.warning(f'⚠️ Error conexión lote {batch_num}, reintentando...')
                            continue
                        else:
                            error_messages.append(f'L{batch_num}:Conexión-final')
                    
                    except Exception as e:
                        if attempt == 1:
                            error_messages.append(f'L{batch_num}:Error-{str(e)[:10]}')
                
                # Si no tuvo éxito después de intentos
                if not success:
                    total_errors += len(batch)
                
                # Commit cada 15 lotes para balance entre rendimiento y seguridad
                if batch_num % 15 == 0:
                    self.env.cr.commit()
                    _logger.info(f'💾 Commit BD - Lote {batch_num} | Éxitos: {total_success} | Errores: {total_errors}')
            
            # Cerrar sesión y commit final
            session.close()
            self.env.cr.commit()
            
            # Resultado final optimizado
            _logger.info(f'🏁 OPTIMIZADO COMPLETADO: {total_success} éxitos, {total_errors} errores, {retry_count} reintentos')
            
            if total_success > 0:
                return {
                    'success': True, 
                    'total_success': total_success, 
                    'total_errors': total_errors,
                    'partial': total_errors > 0,
                    'error_details': error_messages[:8] if error_messages else [],
                    'retry_count': retry_count
                }
            else:
                return {'success': False, 'error': f'Proceso falló completamente. Errores: {"; ".join(error_messages[:3])}'}
                
        except Exception as e:
            _logger.error(f'💥 Error en procesamiento optimizado: {str(e)}')
            return {'success': False, 'error': f'Error crítico: {str(e)}'}

    def _update_batch_partial(self, onu_list):
        """Procesamiento parcial para evitar timeouts - Procesa solo los primeros lotes"""
        try:
            _logger.info(f'⚡🎯 Procesamiento PARCIAL para evitar timeout: {len(onu_list)} ONUs')
            
            # Obtener configuración de API
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'No se encontró configuración de API'}
            
            # Preparar headers
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Obtener perfiles
            upload_profile = self.custom_upload_speed or self.upload_speed_profile
            download_profile = self.custom_download_speed or self.download_speed_profile
            
            # Filtrar ONUs con external_id válidos
            valid_onus = [onu for onu in onu_list if onu.external_id]
            if not valid_onus:
                return {'success': False, 'error': 'No hay ONUs con external_ids válidos'}
            
            # ⚡ LÍMITE CRÍTICO: Procesar máximo 80 ONUs (8 lotes) para evitar timeout de 120s
            max_onus_safe = 80
            if len(valid_onus) > max_onus_safe:
                _logger.info(f'⚠️ Limitando procesamiento a {max_onus_safe} ONUs para evitar timeout de Odoo')
                valid_onus = valid_onus[:max_onus_safe]
            
            # Configuración rápida
            batch_size = 10
            total_success = 0
            total_errors = 0
            error_messages = []
            
            # Sesión HTTP optimizada
            session = requests.Session()
            session.headers.update(headers)
            
            total_batches = (len(valid_onus) + batch_size - 1) // batch_size
            _logger.info(f'⚡ MODO PARCIAL: {total_batches} lotes máximo - timeout 15s ultra-rápido')
            
            # URL de la API
            url = f'{config.api_url}/api/onu/bulk_update_speed_profiles'
            
            for i in range(0, len(valid_onus), batch_size):
                batch = valid_onus[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                # Preparar datos del lote
                external_ids = [onu.external_id for onu in batch]
                data = {
                    'onus_external_ids': ','.join(external_ids),
                    'upload_speed_profile_name': upload_profile,
                    'download_speed_profile_name': download_profile
                }
                
                try:
                    # Timeout ultra-reducido para máxima velocidad
                    response = session.post(url, data=data, timeout=15)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        if response_data.get('response_code') == 'success' or response_data.get('status') == True:
                            total_success += len(batch)
                            _logger.info(f'✅ Lote {batch_num}/{total_batches} exitoso - Total: {total_success}')
                        else:
                            total_errors += len(batch)
                            error_msg = response_data.get('error', 'Error API')
                            error_messages.append(f'L{batch_num}:API')
                            _logger.error(f'❌ Error API lote {batch_num}: {error_msg[:30]}')
                    else:
                        total_errors += len(batch)
                        error_messages.append(f'L{batch_num}:HTTP{response.status_code}')
                        _logger.error(f'❌ HTTP {response.status_code} en lote {batch_num}')
                        
                except requests.exceptions.Timeout:
                    total_errors += len(batch)
                    error_messages.append(f'L{batch_num}:Timeout15s')
                    _logger.error(f'⏱️ Timeout (15s) en lote {batch_num}')
                    
                except Exception as e:
                    total_errors += len(batch)
                    error_messages.append(f'L{batch_num}:Error')
                    _logger.error(f'💥 Error en lote {batch_num}: {str(e)[:20]}')
                
                # Commit frecuente para evitar problemas
                if batch_num % 5 == 0:
                    self.env.cr.commit()
            
            # Cerrar sesión y commit final
            session.close()
            self.env.cr.commit()
            
            # Calcular ONUs restantes
            total_original = len(onu_list)
            processed = len(valid_onus)
            remaining = total_original - processed
            
            # Resultado final
            _logger.info(f'🏁 PARCIAL COMPLETADO: {total_success} éxitos, {total_errors} errores')
            if remaining > 0:
                _logger.info(f'⏳ Quedan {remaining} ONUs por procesar en siguiente ejecución')
            
            # Crear mensaje especial para procesamiento parcial
            if remaining > 0:
                return {
                    'success': True,
                    'partial_process': True,
                    'total_success': total_success,
                    'total_errors': total_errors,
                    'processed': processed,
                    'remaining': remaining,
                    'error_details': error_messages[:3]
                }
            else:
                return {
                    'success': True,
                    'total_success': total_success,
                    'total_errors': total_errors,
                    'partial': total_errors > 0,
                    'error_details': error_messages[:3]
                }
                
        except Exception as e:
            _logger.error(f'💥 Error en procesamiento parcial: {str(e)}')
            return {'success': False, 'error': f'Error crítico: {str(e)}'}

    def _update_batch_speed_profiles_quick(self, onu_list):
        """Versión rápida optimizada para cantidades medianas (30-100 ONUs)"""
        try:
            _logger.info(f'⚡ Procesamiento RÁPIDO: {len(onu_list)} ONUs')
            
            # Obtener configuración de API
            config = self.env['smartolt.config'].get_config()
            if not config:
                return {'success': False, 'error': 'No se encontró configuración de API'}
            
            # Preparar headers
            headers = {
                'X-Token': config.api_token,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Obtener perfiles
            upload_profile = self.custom_upload_speed or self.upload_speed_profile
            download_profile = self.custom_download_speed or self.download_speed_profile
            
            # Filtrar ONUs con external_id válidos
            valid_onus = [onu for onu in onu_list if onu.external_id]
            if not valid_onus:
                return {'success': False, 'error': 'No hay ONUs con external_ids válidos'}
            
            # Configuración rápida
            batch_size = 10
            total_success = 0
            total_errors = 0
            error_messages = []
            
            # Sesión HTTP optimizada
            session = requests.Session()
            session.headers.update(headers)
            
            total_batches = (len(valid_onus) + batch_size - 1) // batch_size
            _logger.info(f'⚡ MODO RÁPIDO: {total_batches} lotes - timeout 12s')
            
            # URL de la API
            url = f'{config.api_url}/api/onu/bulk_update_speed_profiles'
            
            for i in range(0, len(valid_onus), batch_size):
                batch = valid_onus[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                
                # Preparar datos del lote
                external_ids = [onu.external_id for onu in batch]
                data = {
                    'onus_external_ids': ','.join(external_ids),
                    'upload_speed_profile_name': upload_profile,
                    'download_speed_profile_name': download_profile
                }
                
                try:
                    # Timeout reducido para velocidad
                    response = session.post(url, data=data, timeout=12)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        if response_data.get('response_code') == 'success' or response_data.get('status') == True:
                            total_success += len(batch)
                            if batch_num % 3 == 0:  # Log cada 3 lotes
                                _logger.info(f'✅ Lote {batch_num}/{total_batches} - Éxitos: {total_success}')
                        else:
                            total_errors += len(batch)
                            error_messages.append(f'L{batch_num}:API')
                    else:
                        total_errors += len(batch)
                        error_messages.append(f'L{batch_num}:HTTP{response.status_code}')
                        
                except requests.exceptions.Timeout:
                    total_errors += len(batch)
                    error_messages.append(f'L{batch_num}:Timeout12s')
                    
                except Exception:
                    total_errors += len(batch)
                    error_messages.append(f'L{batch_num}:Error')
                
                # Commit cada 8 lotes
                if batch_num % 8 == 0:
                    self.env.cr.commit()
            
            # Cerrar sesión y commit final
            session.close()
            self.env.cr.commit()
            
            _logger.info(f'🏁 RÁPIDO COMPLETADO: {total_success} éxitos, {total_errors} errores')
            
            return {
                'success': True,
                'total_success': total_success,
                'total_errors': total_errors,
                'partial': total_errors > 0,
                'error_details': error_messages[:5]
            }
                
        except Exception as e:
            _logger.error(f'💥 Error en procesamiento rápido: {str(e)}')
            return {'success': False, 'error': f'Error crítico: {str(e)}'}

    def action_debug_speeds(self):
        """Debug: Mostrar resumen de velocidades disponibles por zona"""
        try:
            # Obtener todas las ONUs con velocidades de descarga no vacías
            onus_with_speeds = self.env['smartolt.onu'].search([
                ('service_port_download_speed', '!=', False),
                ('service_port_download_speed', '!=', '')
            ])
            
            # Agrupar por velocidades
            speed_summary = {}
            zone_summary = {}
            
            for onu in onus_with_speeds:
                speed = onu.service_port_download_speed
                zone = onu.name[:3] if onu.name and len(onu.name) >= 3 else 'N/A'
                
                # Resumen por velocidad
                if speed not in speed_summary:
                    speed_summary[speed] = 0
                speed_summary[speed] += 1
                
                # Resumen por zona  
                if zone not in zone_summary:
                    zone_summary[zone] = 0
                zone_summary[zone] += 1
            
            # Construir mensaje
            message_parts = []
            message_parts.append(f"TOTAL ONUs CON VELOCIDAD: {len(onus_with_speeds)}")
            message_parts.append("\n=== POR VELOCIDAD ===")
            
            for speed, count in sorted(speed_summary.items()):
                message_parts.append(f"{speed}: {count} ONUs")
            
            message_parts.append("\n=== POR ZONA ===")
            for zone, count in sorted(zone_summary.items()):
                message_parts.append(f"{zone}: {count} ONUs")
            
            # Ejemplos específicos
            message_parts.append(f"\n=== EJEMPLOS ===")
            examples = onus_with_speeds[:10]
            for onu in examples:
                message_parts.append(f"{onu.serial_number}: '{onu.service_port_download_speed}'")
            
            message = "\n".join(message_parts)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Debug: Resumen de Velocidades',
                    'message': message,
                    'type': 'info',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error en Debug',
                    'message': str(e),
                    'type': 'warning',
                }
            }

    @api.constrains('new_speed_mb', 'custom_upload_speed', 'custom_download_speed')
    def _check_speeds(self):
        for record in self:
            if record.new_speed_mb and record.new_speed_mb <= 0:
                raise ValidationError(_('La velocidad debe ser mayor a 0'))
            
            # Validar formato de velocidades personalizadas
            if record.enable_custom_speeds:
                if record.custom_upload_speed and not self._is_valid_speed_format(record.custom_upload_speed):
                    raise ValidationError(_('Formato de velocidad de subida inválido. Use formato: ZONA-FTTH-RES-VELOCIDADM (ej: GUA-FTTH-RES-50M)'))
                
                if record.custom_download_speed and not self._is_valid_speed_format(record.custom_download_speed):
                    raise ValidationError(_('Formato de velocidad de bajada inválido. Use formato: ZONA-FTTH-RES-VELOCIDADM (ej: GUA-FTTH-RES-100M)'))

    def _is_valid_speed_format(self, speed_profile):
        """Valida que el formato del perfil de velocidad sea correcto"""
        if not speed_profile:
            return True
        
        # Formato esperado: ZONA-FTTH-RES-VELOCIDADM
        # Ejemplos: GUA-FTTH-RES-50M, ACA-FTTH-RES-100M
        import re
        pattern = r'^(GUA|ACA|BAR|APUR)-FTTH-RES-\d+M$'
        return bool(re.match(pattern, speed_profile))

    def action_close(self):
        """Cerrar el wizard"""
        return {'type': 'ir.actions.act_window_close'}