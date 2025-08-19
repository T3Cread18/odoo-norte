# SmartOLT API Endpoints

## Estructura Base de la API

La API de SmartOLT utiliza la siguiente estructura de endpoints:

### Autenticación
- **Header**: `X-Token: {tu_token_aqui}`
- **Content-Type**: `application/json`

### Endpoints Disponibles

#### 1. OLTs (Equipos Principales)
```
GET /api/olt/get_olt_list
GET /api/olt/get_olt_list/{olt_id}
GET /api/olt/get_system_info/{olt_id}
```

#### 2. ONUs (Equipos de Cliente)
```
GET /api/onu/get_onu_list
GET /api/onu/get_onu_list/{olt_id}
GET /api/onu/get_signal_info/{olt_id}/{onu_id}
POST /api/onu/reboot/{olt_id}/{onu_id}
```

#### 3. Zonas
```
GET /api/zone/get_zone_list
GET /api/zone/get_zone_list/{olt_id}
```

#### 4. ODBs (Cajas de Distribución Óptica)
```
GET /api/odb/get_odb_list
GET /api/odb/get_odb_list/{olt_id}
```

#### 5. Perfiles de Velocidad
```
GET /api/speed_profile/get_speed_profile_list
GET /api/speed_profile/get_speed_profile_list/{olt_id}
```

#### 6. VLANs
```
GET /api/vlan/get_vlan_list
GET /api/vlan/get_vlan_list/{olt_id}
```

## Ejemplos de Respuesta

### Respuesta Exitosa
```json
{
    "status": "success",
    "data": [
        {
            "olt_id": "OLT001",
            "name": "OLT Principal",
            "ip_address": "192.168.1.100",
            "status": "online"
        }
    ]
}
```

### Respuesta de Error
```json
{
    "status": "error",
    "message": "Token inválido o expirado"
}
```

## Configuración Recomendada

### URL de API
- **Desarrollo**: `http://localhost:8080` o `http://192.168.1.100:8080`
- **Producción**: `https://smartolt.tuempresa.com` o `https://api.smartolt.com`

### Timeout
- **Recomendado**: 30 segundos
- **Máximo**: 60 segundos

### Reintentos
- **Recomendado**: 3 intentos
- **Intervalo**: 5 segundos entre intentos

## Troubleshooting

### Error 404
- Verificar que la URL de la API sea correcta
- Confirmar que el servidor SmartOLT esté ejecutándose
- Verificar que el puerto sea correcto

### Error 401/403
- Verificar que el token de API sea válido
- Confirmar que el token no haya expirado
- Verificar permisos del usuario en SmartOLT

### Error de Conexión
- Verificar conectividad de red
- Confirmar que el firewall permita la conexión
- Verificar que el servidor SmartOLT esté accesible

## Notas Importantes

1. **Todos los endpoints requieren autenticación** mediante el header `X-Token`
2. **Los IDs de OLT y ONU son obligatorios** para endpoints específicos
3. **La API devuelve siempre JSON** con estructura `{status, data/message}`
4. **Los timeouts largos pueden causar problemas** en entornos de producción
5. **Siempre manejar errores** y respuestas HTTP no exitosas
