# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TotalnetClient(models.Model):
    _name = 'totalnet.client'
    _description = 'Cliente Totalnet'
    _rec_name = 'razon_social'
    _order = 'fecha_registro desc'

    # Campos de ubicación
    zona = fields.Selection([
        ('ACARIGUA', 'ACARIGUA'),
        ('GUANARE', 'GUANARE'),
        ('BARINAS', 'BARINAS'),
        ('APURE', 'APURE'),
        ('OTRO', 'OTRO')
    ], string='Zona', required=True, help='Zona geográfica del cliente')
    
    franquicia = fields.Char('Franquicia', help='Nombre de la franquicia')
    sector = fields.Char('Sector', help='Sector o área específica')
    ubicacion = fields.Char('Ubicación', help='Ubicación específica del cliente')
    
    # Campos de contrato
    contrato = fields.Char('Contrato', required=True, help='Número de contrato (identificador único)')
    id_contrato = fields.Integer('ID Contrato', help='Identificador interno del contrato')
    id_detalle_contr = fields.Integer('ID Detalle Contrato', help='Identificador del detalle del contrato')
    id_recibo_contr = fields.Integer('ID Recibo Contrato', help='Identificador del recibo del contrato')
    id_cliente = fields.Integer('ID Cliente', help='Identificador del cliente')
    
    # Información del cliente
    rif = fields.Char('RIF', help='Registro de Información Fiscal')
    razon_social = fields.Char('Razón Social', required=True, help='Nombre completo o razón social del cliente')
    nombre = fields.Char('Nombre', help='Primer nombre del cliente')
    apellido = fields.Char('Apellido', help='Apellido del cliente')
    
    # Estado del servicio
    estado_servicio = fields.Selection([
        ('ACTIVO', 'ACTIVO'),
        ('INACTIVO', 'INACTIVO'),
        ('SUSPENDIDO', 'SUSPENDIDO'),
        ('CANCELADO', 'CANCELADO'),
        ('PENDIENTE', 'PENDIENTE'),
        ('CORTADO', 'CORTADO'),
        ('POR CORTAR', 'POR CORTAR'),
        ('POR SUSPENDER', 'POR SUSPENDER'),
        ('EXONERADO', 'EXONERADO'),
        ('POR RECONECTAR', 'POR RECONECTAR'),
        ('POR INSTALAR', 'POR INSTALAR'),
        ('BAJA TOTAL', 'BAJA TOTAL'),
        ('BAJA TEMPORAL', 'BAJA TEMPORAL'),
        ('POR REINSTALAR', 'POR REINSTALAR'),
        ('NO RECONECTADO', 'NO RECONECTADO'),
        ('RETIRADO', 'RETIRADO')
    ], string='Estado Servicio', default='ACTIVO', help='Estado actual del servicio')
    
    # Información del servicio
    servicio = fields.Selection([
        ('INTERNET', 'INTERNET'),
        ('TELEFONIA', 'TELEFONIA'),
        ('TV', 'TV'),
        ('COMBO', 'COMBO'),
        ('OTRO', 'OTRO'),
        ('TELEVISION', 'TELEVISION'),
        ('INTERNET TV', 'INTERNET TV')
    ], string='Servicio', help='Tipo de servicio contratado')
    
    tipo_servicio = fields.Char('Tipo Servicio', help='Tipo específico del servicio (ej: INT FTTH)')
    paquete = fields.Char('Paquete', help='Nombre del paquete contratado')
    referencia = fields.Char('Referencia', help='Referencia de ubicación')
    
    # Dirección física
    num_casa = fields.Char('Número Casa', help='Número de la casa o local')
    poste = fields.Char('Poste', help='Número o referencia del poste')
    precinto = fields.Char('Precinto', help='Número de precinto')
    
    # Información técnica
    direccion_ip = fields.Char('Dirección IP', help='Dirección IP asignada al cliente')
    direccion_mac = fields.Char('Dirección MAC', help='Dirección MAC del equipo del cliente')
    direccion_mac_trabajo = fields.Char('Dirección MAC Trabajo', help='Dirección MAC del equipo de trabajo')
    serial_decodificador = fields.Char('Serial Decodificador', help='Número de serie del decodificador')
    
    # Información de contacto
    tlf_fijo = fields.Char('Teléfono Fijo', help='Número de teléfono fijo')
    tlf_movil = fields.Char('Teléfono Móvil', help='Número de teléfono móvil')
    correo = fields.Char('Correo Electrónico', help='Dirección de correo electrónico')
    
    # Información financiera
    financiado = fields.Selection([
        ('SI', 'SI'),
        ('NO', 'NO')
    ], string='Financiado', default='NO', help='Indica si el servicio está financiado')
    
    # Fechas
    fecha_registro = fields.Datetime('Fecha Registro', default=fields.Datetime.now, help='Fecha de registro del cliente')
    fecha_instalacion = fields.Datetime('Fecha Instalación', help='Fecha de instalación del servicio')
    fecha_ultimo_status = fields.Datetime('Fecha Último Status', help='Fecha del último cambio de estado')
    
    # Información comercial
    vendedor = fields.Char('Vendedor', help='Nombre del vendedor que realizó la venta')
    tarifa = fields.Float('Tarifa', digits=(10, 2), help='Monto de la tarifa del servicio')
    moneda = fields.Selection([
        ('BsD', 'Bolívares Digitales'),
        ('USD', 'Dólares Americanos'),
        ('EUR', 'Euros'),
        ('OTRO', 'Otro')
    ], string='Moneda', default='BsD', help='Moneda de la tarifa')
    
    # Campos computados
    nombre_completo = fields.Char('Nombre Completo', compute='_compute_nombre_completo', store=True)
    direccion_completa = fields.Text('Dirección Completa', compute='_compute_direccion_completa', store=True)
    
    # Campos de auditoría
    active = fields.Boolean('Activo', default=True, help='Indica si el registro está activo')
    create_date = fields.Datetime('Fecha Creación', readonly=True)
    write_date = fields.Datetime('Fecha Modificación', readonly=True)
    create_uid = fields.Many2one('res.users', 'Creado por', readonly=True)
    write_uid = fields.Many2one('res.users', 'Modificado por', readonly=True)

    @api.depends('nombre', 'apellido')
    def _compute_nombre_completo(self):
        for record in self:
            if record.nombre and record.apellido:
                record.nombre_completo = f"{record.nombre} {record.apellido}"
            elif record.nombre:
                record.nombre_completo = record.nombre
            elif record.apellido:
                record.nombre_completo = record.apellido
            else:
                record.nombre_completo = record.razon_social or ''

    @api.depends('zona', 'franquicia', 'sector', 'ubicacion', 'referencia', 'num_casa')
    def _compute_direccion_completa(self):
        for record in self:
            parts = []
            if record.zona:
                parts.append(record.zona)
            if record.franquicia:
                parts.append(record.franquicia)
            if record.sector:
                parts.append(record.sector)
            if record.ubicacion:
                parts.append(record.ubicacion)
            if record.referencia:
                parts.append(record.referencia)
            if record.num_casa:
                parts.append(f"Casa/Local: {record.num_casa}")
            
            record.direccion_completa = ', '.join(parts) if parts else 'Sin dirección especificada'

    @api.constrains('contrato')
    def _check_unique_contrato(self):
        for record in self:
            if record.contrato:
                existing = self.search([
                    ('contrato', '=', record.contrato),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(_('El número de contrato %s ya existe en otro registro.') % record.contrato)

    @api.constrains('correo')
    def _check_email_format(self):
        for record in self:
            if record.correo and '@' not in record.correo:
                raise ValidationError(_('El formato del correo electrónico no es válido.'))

    @api.constrains('tarifa')
    def _check_tarifa(self):
        for record in self:
            if record.tarifa and record.tarifa < 0:
                raise ValidationError(_('La tarifa no puede ser negativa.'))
    
    @api.model
    def _handle_invalid_values(self, values):
        """
        Maneja valores inválidos durante la importación, tratándolos como en blanco
        """
        # Campos de selección que pueden tener valores inválidos
        selection_fields = ['estado_servicio', 'servicio', 'financiado', 'moneda']
        
        for field in selection_fields:
            if field in values:
                # Si el valor no está en las opciones válidas, lo tratamos como en blanco
                field_obj = self._fields.get(field)
                if field_obj and hasattr(field_obj, 'selection'):
                    valid_values = [option[0] for option in field_obj.selection]
                    if values[field] not in valid_values:
                        values[field] = False  # Tratar como en blanco
        
        # Generar contrato automáticamente si falta o está vacío
        if 'contrato' not in values or not values.get('contrato'):
            values['contrato'] = self._generate_contract_number()
        
        return values
    
    @api.model
    def _generate_contract_number(self):
        """
        Genera un número de contrato único automáticamente
        """
        import random
        import time
        
        # Obtener el timestamp actual para asegurar unicidad
        timestamp = int(time.time())
        
        # Generar un número aleatorio de 4 dígitos
        random_num = random.randint(1000, 9999)
        
        # Combinar timestamp y número aleatorio para crear un contrato único
        contract_number = f"CONTRATO_{timestamp}_{random_num}"
        
        # Verificar que no exista ya en la base de datos
        existing = self.search([('contrato', '=', contract_number)], limit=1)
        if existing:
            # Si existe, generar uno nuevo con un número aleatorio diferente
            random_num = random.randint(10000, 99999)
            contract_number = f"CONTRATO_{timestamp}_{random_num}"
        
        return contract_number
    
    @api.model
    def generate_contracts_for_batch(self, data_list):
        """
        Genera contratos únicos para una lista de datos que no los tengan
        
        Args:
            data_list: Lista de diccionarios con los datos
            
        Returns:
            list: Lista de datos con contratos generados
        """
        generated_count = 0
        
        for data in data_list:
            if not data.get('contrato'):
                data['contrato'] = self._generate_contract_number()
                generated_count += 1
                _logger.info(f"✅ Contrato generado automáticamente: {data['contrato']}")
        
        if generated_count > 0:
            _logger.info(f"📋 Total de contratos generados automáticamente: {generated_count}")
        
        return data_list
    
    @api.model
    def generate_single_contract(self, prefix="CONTRATO"):
        """
        Genera un contrato único individual
        
        Args:
            prefix: Prefijo para el contrato (por defecto "CONTRATO")
            
        Returns:
            str: Número de contrato único generado
        """
        import random
        import time
        
        # Obtener el timestamp actual para asegurar unicidad
        timestamp = int(time.time())
        
        # Generar un número aleatorio de 4 dígitos
        random_num = random.randint(1000, 9999)
        
        # Crear contrato con el prefijo personalizado
        contract_number = f"{prefix}_{timestamp}_{random_num}"
        
        # Verificar que no exista ya en la base de datos
        existing = self.search([('contrato', '=', contract_number)], limit=1)
        if existing:
            # Si existe, generar uno nuevo con un número aleatorio diferente
            random_num = random.randint(10000, 99999)
            contract_number = f"{prefix}_{timestamp}_{random_num}"
        
        _logger.info(f"✅ Contrato único generado: {contract_number}")
        return contract_number
    
    @api.model
    def _handle_duplicate_contratos(self, values):
        """
        Maneja contratos duplicados durante la importación
        """
        # Si hay un contrato duplicado, generar uno nuevo único
        if 'contrato' in values and values['contrato']:
            existing = self.search([('contrato', '=', values['contrato'])], limit=1)
            if existing:
                # Generar un nuevo contrato único
                values['contrato'] = self._generate_contract_number()
        
        return values
    
    @api.model
    def create(self, values):
        """
        Sobrescribe create para manejar valores inválidos y contratos duplicados
        """
        values = self._handle_invalid_values(values)
        values = self._handle_duplicate_contratos(values)
        return super().create(values)
    
    def write(self, values):
        """
        Sobrescribe write para manejar valores inválidos y contratos duplicados
        """
        values = self._handle_invalid_values(values)
        values = self._handle_duplicate_contratos(values)
        return super().write(values)

    def name_get(self):
        """Personalizar la representación del nombre del registro"""
        result = []
        for record in self:
            if record.razon_social:
                name = f"{record.razon_social}"
                if record.contrato:
                    name += f" (Contrato: {record.contrato})"
                if record.zona:
                    name += f" - {record.zona}"
            else:
                name = f"Cliente {record.id}"
            result.append((record.id, name))
        return result

    def action_activar_servicio(self):
        """Activar el servicio del cliente"""
        self.ensure_one()
        self.estado_servicio = 'ACTIVO'
        self.fecha_ultimo_status = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Servicio Activado',
                'message': f'El servicio del cliente {self.razon_social} ha sido activado.',
                'type': 'success',
            }
        }

    def action_suspender_servicio(self):
        """Suspender el servicio del cliente"""
        self.ensure_one()
        self.estado_servicio = 'SUSPENDIDO'
        self.fecha_ultimo_status = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Servicio Suspendido',
                'message': f'El servicio del cliente {self.razon_social} ha sido suspendido.',
                'type': 'warning',
            }
        }

    def action_cancelar_servicio(self):
        """Cancelar el servicio del cliente"""
        self.ensure_one()
        self.estado_servicio = 'CANCELADO'
        self.fecha_ultimo_status = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Servicio Cancelado',
                'message': f'El servicio del cliente {self.razon_social} ha sido cancelado.',
                'type': 'danger',
            }
        }

    def action_ver_detalles(self):
        """Abrir vista detallada del cliente"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'totalnet.client',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def import_totalnet_data(self, data_list, update_existing=False):
        """
        Método para importar datos de Totalnet con manejo de duplicados
        
        Args:
            data_list: Lista de diccionarios con los datos a importar
            update_existing: Si es True, actualiza registros existentes; si es False, los ignora
        
        Returns:
            dict: Resumen de la importación
        """
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        # Generar contratos automáticamente para registros que no los tengan
        data_list = self.generate_contracts_for_batch(data_list)
        
        for i, data in enumerate(data_list):
            try:
                # Manejar valores inválidos
                data = self._handle_invalid_values(data)
                
                if update_existing and data.get('contrato'):
                    # Buscar registro existente por contrato
                    existing = self.search([('contrato', '=', data['contrato'])], limit=1)
                    if existing:
                        # Actualizar registro existente
                        existing.write(data)
                        updated_count += 1
                        continue
                
                # Si no se actualiza o no existe, crear nuevo registro
                # Manejar duplicados antes de crear
                data = self._handle_duplicate_contratos(data)
                self.create(data)
                created_count += 1
                
            except Exception as e:
                errors.append(f"Fila {i+1}: {str(e)}")
                skipped_count += 1
        
        return {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'errors': errors,
            'total_processed': len(data_list)
        } 