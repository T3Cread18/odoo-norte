# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import time

_logger = logging.getLogger(__name__)


class SmartOLTSyncWizard(models.TransientModel):
    _name = 'smartolt.sync.wizard'
    _description = 'Wizard de Sincronización SmartOLT'

    sync_type = fields.Selection([
        ('all', 'Sincronizar Todo'),
        ('olts', 'Solo OLTs'),
        ('onus', 'Solo ONUs'),
        ('zones', 'Solo Zonas'),
        ('odbs', 'Solo ODBs'),
        ('speed_profiles', 'Solo Perfiles de Velocidad'),
        ('vlans', 'Solo VLANs')
    ], string='Tipo de Sincronización', default='all', required=True)
    
    olt_id = fields.Many2one('smartolt.olt', string='OLT Específico')
    force_sync = fields.Boolean('Forzar Sincronización', default=False)
    
    # Campos para sincronización por lotes
    batch_size = fields.Integer('Tamaño de Lote', default=50, 
                               help='ONUs por lote para evitar errores de cursor')
    enable_batch_sync = fields.Boolean('Sincronización por Lotes', default=True,
                                      help='Habilitar procesamiento por lotes para grandes cantidades')
    
    @api.onchange('sync_type')
    def _onchange_sync_type(self):
        """Oculta el campo OLT si no es necesario"""
        if self.sync_type in ['olts', 'all']:
            self.olt_id = False

    def action_sync(self):
        """Ejecuta la sincronización según el tipo seleccionado"""
        try:
            if self.sync_type == 'all':
                return self._sync_all()
            elif self.sync_type == 'olts':
                return self._sync_olts()
            elif self.sync_type == 'onus':
                return self._sync_onus_batch()
            elif self.sync_type == 'zones':
                return self._sync_zones()
            elif self.sync_type == 'odbs':
                return self._sync_odbs()
            elif self.sync_type == 'speed_profiles':
                return self._sync_speed_profiles()
            elif self.sync_type == 'vlans':
                return self._sync_vlans()
        except Exception as e:
            _logger.error(f'Error en sincronización: {e}')
            raise UserError(_('Error en sincronización: %s') % str(e))

    def _sync_all(self):
        """Sincroniza todos los elementos"""
        # Sincronizar en orden de dependencias
        self.env['smartolt.olt'].sync_from_api()
        self.env['smartolt.zone'].sync_from_api()
        self.env['smartolt.odb'].sync_from_api()
        self.env['smartolt.speed_profile'].sync_from_api()
        self.env['smartolt.vlan'].sync_from_api()
        
        # Sincronizar ONUs por lotes
        return self._sync_onus_batch()

    def _sync_olts(self):
        """Sincroniza solo OLTs"""
        return self.env['smartolt.olt'].sync_from_api()

    def _sync_onus_batch(self):
        """Sincroniza ONUs por lotes para evitar errores de cursor"""
        try:
            if self.enable_batch_sync:
                return self._sync_onus_in_batches()
            else:
                # Sincronización tradicional (puede fallar con grandes cantidades)
                if self.olt_id:
                    return self.env['smartolt.onu'].sync_from_api(self.olt_id.olt_id)
                else:
                    return self.env['smartolt.onu'].sync_from_api()
        except Exception as e:
            _logger.error(f'Error en sincronización por lotes: {e}')
            raise UserError(_('Error en sincronización por lotes: %s') % str(e))

    def _sync_onus_in_batches(self):
        """Sincroniza ONUs procesando por lotes"""
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
            
            # Obtener lista de OLTs para procesar por lotes
            if self.olt_id:
                olts_to_process = [self.olt_id]
            else:
                olts_to_process = self.env['smartolt.olt'].search([])
            
            if not olts_to_process:
                raise UserError(_('No hay OLTs configurados para sincronizar'))
            
            total_onus_processed = 0
            total_errors = 0
            error_details = []
            
            _logger.info(f'🚀 Iniciando sincronización por lotes de {len(olts_to_process)} OLTs')
            
            for olt in olts_to_process:
                try:
                    _logger.info(f'📡 Sincronizando OLT: {olt.name} (ID: {olt.olt_id})')
                    
                    # Obtener ONUs para este OLT específico
                    url = f'{api_url}/api/onu/get_all_onus_details?olt_id={olt.olt_id}'
                    response = requests.get(url, headers=headers, timeout=timeout)
                    
                    if response.status_code == 200:
                        data = response.json()
                        onu_data = self._extract_onu_data(data)
                        
                        if onu_data:
                            _logger.info(f'📊 Procesando {len(onu_data)} ONUs para OLT {olt.name}')
                            
                            # Procesar ONUs por lotes
                            batch_results = self._process_onus_in_batches(onu_data, olt)
                            total_onus_processed += batch_results['processed']
                            total_errors += batch_results['errors']
                            error_details.extend(batch_results['error_details'])
                            
                            # Commit después de cada OLT para liberar memoria
                            self.env.cr.commit()
                            _logger.info(f'💾 Commit realizado para OLT {olt.name}')
                            
                            # Pausa entre OLTs para no sobrecargar la API
                            time.sleep(1)
                        else:
                            _logger.info(f'ℹ️ No hay ONUs para OLT {olt.name}')
                    else:
                        _logger.warning(f'⚠️ Error HTTP {response.status_code} para OLT {olt.name}: {response.text}')
                        total_errors += 1
                        error_details.append(f'OLT {olt.name}: HTTP {response.status_code}')
                        
                except Exception as e:
                    _logger.error(f'❌ Error procesando OLT {olt.name}: {str(e)}')
                    total_errors += 1
                    error_details.append(f'OLT {olt.name}: {str(e)}')
                    continue
            
            # Resultado final
            if total_errors == 0:
                message = f'✅ Sincronización exitosa: {total_onus_processed} ONUs procesadas'
                message_type = 'success'
            elif total_onus_processed > 0:
                message = f'⚠️ Sincronización parcial: {total_onus_processed} ONUs procesadas, {total_errors} errores'
                message_type = 'warning'
            else:
                message = f'❌ Sincronización falló: {total_errors} errores'
                message_type = 'danger'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Completada'),
                    'message': message,
                    'type': message_type,
                    'sticky': True
                }
            }
            
        except Exception as e:
            _logger.error(f'💥 Error general en sincronización por lotes: {str(e)}')
            raise UserError(_('Error en sincronización por lotes: %s') % str(e))

    def _extract_onu_data(self, data):
        """Extrae datos de ONUs de la respuesta de la API"""
        # Verificar diferentes estructuras de respuesta
        if data.get('onus') and isinstance(data.get('onus'), list):
            return data.get('onus', [])
        elif data.get('response_code') == 'success' and data.get('response'):
            return data.get('response', [])
        elif data.get('status') == 'success' or data.get('status') == True:
            return data.get('data', [])
        elif data.get('response') and isinstance(data.get('response'), list):
            return data.get('response', [])
        elif isinstance(data, list):
            return data
        else:
            _logger.warning(f'Estructura de respuesta inesperada: {data}')
            return []

    def _process_onus_in_batches(self, onu_data, olt):
        """Procesa ONUs en lotes para evitar errores de cursor"""
        processed = 0
        errors = 0
        error_details = []
        
        # Dividir en lotes
        batch_size = self.batch_size
        total_batches = (len(onu_data) + batch_size - 1) // batch_size
        
        _logger.info(f'📦 Procesando {len(onu_data)} ONUs en {total_batches} lotes de {batch_size}')
        
        for i in range(0, len(onu_data), batch_size):
            batch = onu_data[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            _logger.info(f'📦 Procesando lote {batch_num}/{total_batches} con {len(batch)} ONUs')
            
            try:
                # Procesar cada ONU del lote
                for onu_info in batch:
                    try:
                        self._process_single_onu(onu_info, olt)
                        processed += 1
                    except Exception as e:
                        errors += 1
                        error_msg = f'ONU {onu_info.get("sn", "desconocida")}: {str(e)}'
                        error_details.append(error_msg)
                        _logger.error(f'❌ {error_msg}')
                
                # Commit después de cada lote
                self.env.cr.commit()
                _logger.info(f'💾 Commit realizado después del lote {batch_num}')
                
                # Pausa entre lotes
                if batch_num < total_batches:
                    time.sleep(0.5)
                    
            except Exception as e:
                _logger.error(f'💥 Error procesando lote {batch_num}: {str(e)}')
                errors += len(batch)
                error_details.append(f'Lote {batch_num}: {str(e)}')
                continue
        
        return {
            'processed': processed,
            'errors': errors,
            'error_details': error_details
        }

    def _process_single_onu(self, onu_info, olt):
        """Procesa una sola ONU con manejo robusto de errores"""
        try:
            # Generar serial_number único
            serial_number = onu_info.get('sn') or onu_info.get('serial_number')
            if not serial_number or serial_number.strip() == '':
                serial_number = f"EXT_{onu_info.get('unique_external_id', 'UNKNOWN')}"
            
            # Buscar ONU existente por external_id o serial_number
            existing_onu = self.env['smartolt.onu'].search([
                '|',
                ('external_id', '=', str(onu_info.get('unique_external_id'))),
                ('serial_number', '=', serial_number)
            ], limit=1)
            
            # Buscar zona relacionada
            zone_id = None
            if onu_info.get('zone_id'):
                zone = self.env['smartolt.zone'].search([
                    ('zone_id', '=', str(onu_info.get('zone_id')))
                ], limit=1)
                if zone:
                    zone_id = zone.id
            
            # Buscar ODB relacionado
            odb_splitter_id = None
            if onu_info.get('odb_name') and onu_info.get('odb_name').strip():
                odb = self.env['smartolt.odb'].search([
                    ('name', '=', onu_info.get('odb_name'))
                ], limit=1)
                if odb:
                    odb_splitter_id = odb.id
            
            # Preparar datos de la ONU
            onu_vals = {
                'serial_number': serial_number,
                'name': onu_info.get('name', f'ONU {serial_number}'),
                'onu_type': onu_info.get('onu_type', 'Unknown'),
                'pon_type': onu_info.get('pon_type', 'gpon'),
                'status': onu_info.get('status', 'Offline'),
                'olt_id': olt.id,
                'board': onu_info.get('board', 0),
                'port': onu_info.get('port', 0),
                'allocated_onu': onu_info.get('allocated_onu', 0),
                'address': onu_info.get('address', ''),
                'signal': onu_info.get('signal', 'Unknown'),
                'signal_1310': onu_info.get('signal_1310'),
                'signal_1490': onu_info.get('signal_1490'),
                'zone_id': zone_id,
                'odb_splitter': odb_splitter_id,
                'external_id': onu_info.get('unique_external_id'),
                'last_sync_date': fields.Datetime.now()
            }
            
            # Procesar SOLO service_ports para extraer velocidades (campos requeridos)
            if onu_info.get('service_ports') and len(onu_info.get('service_ports')) > 0:
                service_port = onu_info.get('service_ports')[0]  # Tomar el primer puerto de servicio
                
                # Extraer campos de velocidad requeridos
                upload_speed = service_port.get('upload_speed')
                download_speed = service_port.get('download_speed')
                
                _logger.info(f'🔍 Service Port encontrado para ONU {serial_number}')
                _logger.info(f'📊 Velocidades extraídas - Upload: {upload_speed}, Download: {download_speed}')
                
                # Solo actualizar los campos de velocidad que necesitas
                onu_vals.update({
                    'service_port_upload_speed': upload_speed,
                    'service_port_download_speed': download_speed,
                })
                
                # Validar que se extrajeron correctamente
                if upload_speed and download_speed:
                    _logger.info(f'✅ Campos de velocidad extraídos correctamente para ONU {serial_number}')
                else:
                    _logger.warning(f'⚠️ Campos de velocidad incompletos para ONU {serial_number} - Upload: {upload_speed}, Download: {download_speed}')
            else:
                _logger.warning(f'⚠️ No se encontraron service_ports para ONU {serial_number} - Campos de velocidad no disponibles')
            
            if existing_onu:
                # Actualizar ONU existente - NO cambiar serial_number si ya existe
                update_vals = {k: v for k, v in onu_vals.items() if k != 'serial_number'}
                existing_onu.write(update_vals)
                _logger.info(f'🔄 ONU actualizada: {existing_onu.serial_number}')
            else:
                # Crear nueva ONU
                self.env['smartolt.onu'].create(onu_vals)
                _logger.info(f'🆕 Nueva ONU creada: {serial_number}')
                
        except Exception as e:
            _logger.error(f'❌ Error procesando ONU {onu_info.get("sn", "desconocida")}: {str(e)}')
            raise

    def _sync_zones(self):
        """Sincroniza zonas"""
        if self.olt_id:
            return self.env['smartolt.zone'].sync_from_api(self.olt_id.olt_id)
        else:
            return self.env['smartolt.zone'].sync_from_api()

    def _sync_odbs(self):
        """Sincroniza ODBs"""
        if self.olt_id:
            return self.env['smartolt.odb'].sync_from_api(self.olt_id.olt_id)
        else:
            return self.env['smartolt.odb'].sync_from_api()

    def _sync_speed_profiles(self):
        """Sincroniza perfiles de velocidad"""
        return self.env['smartolt.speed_profile'].sync_from_api()

    def _sync_vlans(self):
        """Sincroniza VLANs"""
        return self.env['smartolt.vlan'].sync_from_api()
