# -*- coding: utf-8 -*-
{
    'name': 'SmartOLT Integration',
    'version': '16.0.1.0.1',
    'category': 'Network',
    'summary': 'Integración con SmartOLT y gestión de clientes Totalnet',
    'description': """
        Módulo para integrar Odoo con la API de SmartOLT y gestionar clientes del sistema Totalnet.
        Permite gestionar OLTs, ONUs, zonas, ODBs y configuraciones de red.
        
        Funcionalidades SmartOLT:
        - Gestión de OLTs
        - Gestión de ONUs
        - Configuración de zonas y ODBs
        - Gestión de perfiles de velocidad
        - Configuración de VLANs
        - Cambio masivo de planes
        - Movimiento masivo de ONUs entre PONs
        - Facturación y reportes
        
        Funcionalidades Totalnet:
        - Gestión completa de clientes
        - Información de contratos y servicios
        - Estados de servicio (Activo, Suspendido, Cancelado)
        - Gestión de ubicaciones y franquicias
        - Información técnica (IP, MAC, equipos)
        - Seguimiento de vendedores y tarifas
    """,
    'author': 'Tu Empresa',
    'website': 'https://www.tuempresa.com',
    'depends': ['base', 'mail'],
    'data': [
        'security/totalnet_security.xml',  # Primero crear los grupos de seguridad
        'security/ir.model.access.csv',    # Luego asignar permisos
        'views/smartolt_config_views.xml',
        'views/smartolt_olt_views.xml',
        'views/smartolt_onu_views.xml',
        'views/smartolt_zone_views.xml',
        'views/smartolt_odb_views.xml',
        'views/smartolt_speed_profile_views.xml',
        'views/smartolt_vlan_views.xml',
        'wizard/smartolt_sync_wizard.xml',
        'wizard/smartolt_sync_board_wizard.xml',
        'wizard/smartolt_sync_port_wizard.xml',
        'wizard/smartolt_logging_wizard.xml',
        'wizard/smartolt_bulk_plan_wizard.xml',
        'wizard/smartolt_bulk_progress_wizard.xml',
        'wizard/smartolt_bulk_pon_move_wizard.xml',
        'views/smartolt_pon_move_views.xml',
        'views/totalnet_views.xml',        # Vistas de Totalnet
        'views/smartolt_menu_views.xml',   # Los menús al final para que las acciones ya existan
        'data/totalnet_example_data.xml',  # Datos de ejemplo al final
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'smartolt_integration/static/src/css/progress_style.css',
            # 'smartolt_integration/static/src/js/progress_widget.js',  # Temporalmente comentado
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
