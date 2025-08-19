# Módulo SmartOLT Integration para Odoo 16.0

Este módulo integra Odoo con la API de SmartOLT para gestionar equipos GPON (OLTs, ONUs, zonas, ODBs, perfiles de velocidad y VLANs).

## Características

- **Gestión de OLTs**: Administración de equipos principales de la red GPON
- **Gestión de ONUs**: Control de equipos de cliente con funcionalidades avanzadas
- **Gestión de Zonas**: Organización geográfica de la red
- **Gestión de ODBs**: Control de cajas de distribución óptica
- **Perfiles de Velocidad**: Configuración de ancho de banda para ONUs
- **Gestión de VLANs**: Segmentación del tráfico de red
- **Sincronización Automática**: Integración bidireccional con la API de SmartOLT
- **Wizard de Sincronización**: Interfaz fácil para sincronizar datos

## Instalación

1. Copia el módulo al directorio `addons` de Odoo
2. Reinicia el servidor Odoo
3. Ve a **Aplicaciones** y busca "SmartOLT Integration"
4. Haz clic en **Instalar**

## Configuración

### Token de API

Antes de usar el módulo, debes configurar el token de API de SmartOLT:

1. Ve a **Configuración > Técnico > Parámetros > Parámetros del Sistema**
2. Crea un nuevo parámetro:
   - **Clave**: `smartolt.api_token`
   - **Valor**: Tu token de API de SmartOLT

### URL de API

Por defecto, el módulo usa `https://api.smartolt.com`. Si necesitas cambiar esta URL:

1. Ve a **Configuración > Técnico > Parámetros > Parámetros del Sistema**
2. Crea un nuevo parámetro:
   - **Clave**: `smartolt.api_url`
   - **Valor**: Tu URL de API personalizada

## Uso

### Sincronización Inicial

1. Ve a **SmartOLT > Herramientas > Sincronización**
2. Selecciona "Sincronizar Todo" y haz clic en **Sincronizar**
3. El módulo descargará todos los datos desde la API de SmartOLT

### Gestión de OLTs

- **Ver OLTs**: SmartOLT > Gestión > OLTs
- **Sincronizar ONUs**: Desde la vista de OLT, haz clic en "Sincronizar ONUs"
- **Información del Sistema**: Haz clic en "Obtener Info Sistema" para actualizar datos

### Gestión de ONUs

- **Ver ONUs**: SmartOLT > Gestión > ONUs
- **Información de Señal**: Haz clic en "Obtener Info Señal" para actualizar métricas
- **Reiniciar ONU**: Haz clic en "Reiniciar ONU" (requiere confirmación)

### Sincronización Selectiva

Puedes sincronizar elementos específicos:

1. Ve a **SmartOLT > Herramientas > Sincronización**
2. Selecciona el tipo de sincronización deseado
3. Opcionalmente, selecciona un OLT específico
4. Haz clic en **Sincronizar**

## Modelos de Datos

### OLT (smartolt.olt)
- Información básica del equipo
- Estado de conexión
- Versiones de firmware y hardware
- Relaciones con ONUs y zonas

### ONU (smartolt.onu)
- Número de serie y MAC
- Configuración de red (VLAN, WAN, VoIP)
- Estado de conexión y facturación
- Métricas de señal y distancia

### Zona (smartolt.zone)
- Organización geográfica
- Relaciones con OLTs y ODBs
- Coordenadas de ubicación

### ODB (smartolt.odb)
- Cajas de distribución óptica
- Número de puertos
- Ubicación y estado

### Perfil de Velocidad (smartolt.speed_profile)
- Velocidades de descarga y subida
- Prioridad y estado
- Asignación a ONUs

### VLAN (smartolt.vlan)
- Identificadores de VLAN
- Prioridad y estado
- Asignación a ONUs

## Funcionalidades de API

El módulo implementa los siguientes endpoints de la API de SmartOLT:

### OLTs
- `GET /api/olt/get_olt_list` - Lista de OLTs
- `GET /api/olt/get_system_info/{olt_id}` - Información del sistema

### ONUs
- `GET /api/onu/get_onu_list` - Lista de ONUs
- `GET /api/onu/get_signal_info/{olt_id}/{onu_id}` - Información de señal
- `POST /api/onu/reboot/{olt_id}/{onu_id}` - Reiniciar ONU

### Zonas y ODBs
- `GET /api/zone/get_zone_list` - Lista de zonas
- `GET /api/odb/get_odb_list` - Lista de ODBs

### Perfiles y VLANs
- `GET /api/speed_profile/get_speed_profile_list` - Lista de perfiles
- `GET /api/vlan/get_vlan_list` - Lista de VLANs

## Permisos

- **Usuarios**: Solo lectura de datos
- **Administradores**: Acceso completo (crear, editar, eliminar)

## Dependencias

- Odoo 16.0
- Módulo `base`
- Módulo `mail` (para funcionalidades de chatter)

## Soporte

Para soporte técnico o reportar problemas, contacta al equipo de desarrollo.

## Licencia

Este módulo está licenciado bajo LGPL-3.

## Versión

16.0.1.0.0
