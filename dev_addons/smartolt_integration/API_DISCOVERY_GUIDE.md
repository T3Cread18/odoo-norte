# 🚀 Guía de Descubrimiento Automático de la API SmartOLT

## 🎯 **Problema Resuelto**

El error **HTTP 405 - "Unknown method"** en todos los endpoints indica que la estructura de la API de SmartOLT es **completamente diferente** a la documentación estándar. El sistema ahora puede **descubrir automáticamente** la estructura correcta basándose en la **documentación oficial de SmartOLT**.

## 🔍 **Estructura Real de la API SmartOLT**

### **Formato de URL Base**
```
https://{{subdomain}}.smartolt.com
```

**Ejemplos:**
- `https://empresa1.smartolt.com`
- `https://redlocal.smartolt.com`
- `https://olt-principal.smartolt.com`

### **Estructura de Endpoints**
```
/api/onu/get_all_onus_details
/api/olt/get_olt_list
/api/zone/get_all_zones
/api/odb/get_all_odbs
/api/speed_profile/get_all_speed_profiles
/api/vlan/get_all_vlans
/api/system/get_system_info
```

### **Método HTTP**
- **GET**: Para obtener información
- **Headers**: Solo `X-Token` (no `Content-Type: application/json`)

### **Parámetros**
- **Query Parameters**: Los parámetros van en la URL, no en el cuerpo
- **Ejemplo**: `?olt_id=1&board=2&port=3&zone=City%20Centre`

## 🔍 **Cómo Funciona el Descubrimiento Automático**

### **1. Análisis Inteligente de Patrones**
El sistema prueba **25 combinaciones diferentes** basadas en la documentación oficial:

#### **Patrones de ONU (más importantes)**
```
GET /api/onu/get_all_onus_details
GET /api/onu/get_all_onus_details?olt_id=1
GET /api/onu/get_all_onus_details?olt_id=1&board=1
GET /api/onu/get_all_onus_details?olt_id=1&board=1&port=1
```

#### **Patrones de OLT**
```
GET /api/olt/get_olt_list
GET /api/olt/get_olt_details?olt_id=1
GET /api/olt/get_olt_status?olt_id=1
```

#### **Patrones de Zona**
```
GET /api/zone/get_all_zones
GET /api/zone/get_zone_details?zone_name=test
```

#### **Patrones de ODB (Splitter)**
```
GET /api/odb/get_all_odbs
GET /api/odb/get_odb_details?odb_name=test
```

#### **Patrones de Perfil de Velocidad**
```
GET /api/speed_profile/get_all_speed_profiles
GET /api/speed_profile/get_speed_profile_details?profile_id=1
```

#### **Patrones de VLAN**
```
GET /api/vlan/get_all_vlans
GET /api/vlan/get_vlan_details?vlan_id=1
```

#### **Patrones de Sistema**
```
GET /api/system/get_system_info
GET /api/system/get_system_status
GET /api/status
```

## 🛠️ **Cómo Usar el Sistema de Descubrimiento**

### **Paso 1: Configurar la URL Base**
Ingresa la **URL completa** de tu servidor SmartOLT:
```
https://tusubdominio.smartolt.com
https://empresa.smartolt.com
https://olt-principal.smartolt.com
```

**⚠️ Importante**: Debe incluir el subdominio y el protocolo HTTPS

### **Paso 2: Configurar el Token**
Ingresa tu token de API válido de SmartOLT

### **Paso 3: Ejecutar el Descubrimiento**
Haz clic en **"Probar Conexión"** y el sistema:
1. **Probará automáticamente** los 25 patrones oficiales
2. **Identificará** cuáles funcionan
3. **Guardará** la configuración descubierta
4. **Te mostrará** exactamente qué funcionó

## 📊 **Resultados del Descubrimiento**

### **✅ Endpoint Exitoso (200)**
- **Respuesta**: `status: "success"` o `status: true`
- **Acción**: Se guarda como configuración principal
- **Uso**: Para todas las operaciones futuras

### **✅ Endpoint con Bad Request (400)**
- **Respuesta**: `status: false` con `error`
- **Acción**: Se registra como disponible (los parámetros son incorrectos)
- **Uso**: El endpoint funciona, solo necesita parámetros correctos

### **⚠️ Endpoint con Error de API**
- **Respuesta**: `status: false` con `error`
- **Acción**: Se registra como disponible pero con problemas
- **Uso**: Para debugging y troubleshooting

### **✅ Endpoint con Formato Diferente**
- **Respuesta**: Formato JSON válido pero estructura diferente
- **Acción**: Se adapta automáticamente
- **Uso**: Con adaptadores de formato

### **✅ Endpoint con Respuesta No-JSON**
- **Respuesta**: Texto plano o HTML
- **Acción**: Se registra como disponible
- **Uso**: Para endpoints básicos de estado

## 🔧 **Configuración Automática Guardada**

Cuando se descubre un endpoint funcional, el sistema guarda automáticamente:

```python
# Parámetros del sistema
smartolt.discovered_api_url      # URL base descubierta
smartolt.discovered_api_method  # Método HTTP que funciona
smartolt.discovered_api_structure # Estructura completa del endpoint
```

## 📋 **Ejemplos de Descubrimiento Exitoso**

### **Ejemplo 1: API SmartOLT Estándar**
```
✅ Descubierto: GET https://empresa.smartolt.com/api/onu/get_all_onus_details
Respuesta: {"status": true, "data": [...]}
```

### **Ejemplo 2: API con Parámetros**
```
✅ Descubierto: GET https://redlocal.smartolt.com/api/olt/get_olt_details?olt_id=1
Respuesta: {"status": "success", "olt": {...}}
```

### **Ejemplo 3: API con Bad Request (funciona)**
```
✅ Descubierto: GET https://olt-principal.smartolt.com/api/zone/get_zone_details?zone_name=test
Respuesta: {"status": false, "error": "Zone not found"}
```

## 🚨 **Casos de Error y Soluciones**

### **Error: "No se pudo descubrir la estructura"**
**Causas posibles:**
1. **URL incorrecta** - Debe ser `https://subdominio.smartolt.com`
2. **Subdominio incorrecto** - Verifica el subdominio en tu servidor
3. **Servidor no ejecutándose** - Confirma que SmartOLT esté activo
4. **Token inválido** - Confirma que el token sea correcto

**Soluciones:**
1. **Verifica la URL** en el servidor SmartOLT
2. **Confirma el subdominio** correcto
3. **Revisa los logs** del servidor
4. **Contacta soporte** de SmartOLT

### **Error: "Endpoint encontrado pero token inválido"**
**Solución:**
- El sistema **encontró la API** pero el token no es válido
- **Actualiza el token** en la configuración
- **Verifica permisos** del usuario en SmartOLT

### **Error: "Endpoint encontrado pero sin permisos"**
**Solución:**
- El sistema **encontró la API** pero el usuario no tiene permisos
- **Verifica roles** del usuario en SmartOLT
- **Contacta al administrador** del sistema

## 🎯 **Beneficios del Sistema de Descubrimiento**

### **✅ Basado en Documentación Oficial**
- Usa la estructura real de SmartOLT
- No adivina endpoints
- Sigue los patrones oficiales

### **✅ Inteligente**
- Prueba múltiples combinaciones de parámetros
- Identifica patrones de respuesta
- Guarda configuración automáticamente

### **✅ Robusto**
- Maneja diferentes formatos de respuesta
- Interpreta correctamente códigos HTTP 400
- Proporciona información detallada de debugging

### **✅ Persistente**
- Guarda la configuración descubierta
- Reutiliza endpoints funcionales
- Mantiene historial de descubrimientos

## 🚀 **Próximos Pasos Después del Descubrimiento**

### **1. Verificar la Configuración**
- Revisa qué endpoints se descubrieron
- Confirma que la estructura sea correcta
- Verifica que las respuestas tengan sentido

### **2. Probar Funcionalidades**
- Ejecuta sincronización de OLTs
- Prueba sincronización de ONUs
- Verifica gestión de zonas

### **3. Optimizar Configuración**
- Ajusta timeouts si es necesario
- Configura reintentos automáticos
- Habilita logging detallado

### **4. Documentar la API**
- Guarda la estructura descubierta
- Comparte con el equipo
- Actualiza documentación interna

## 📞 **Obtener Ayuda Adicional**

### **Si el Descubrimiento Falla:**
1. **Revisa los logs** de Odoo para información detallada
2. **Verifica conectividad** con el servidor SmartOLT
3. **Confirma el subdominio** en la URL
4. **Contacta soporte** de SmartOLT con los errores específicos

### **Información Útil para Soporte:**
- **URL completa** del servidor SmartOLT (con subdominio)
- **Versión de SmartOLT** instalada
- **Logs de error** completos
- **Respuestas HTTP** recibidas
- **Configuración de red** (firewall, proxy, etc.)

## 🔗 **Referencias de la API**

### **Endpoints Principales (según documentación oficial):**
- **ONU**: `/api/onu/get_all_onus_details`
- **OLT**: `/api/olt/get_olt_list`
- **Zona**: `/api/zone/get_all_zones`
- **ODB**: `/api/odb/get_all_odbs`
- **Perfil**: `/api/speed_profile/get_all_speed_profiles`
- **VLAN**: `/api/vlan/get_all_vlans`
- **Sistema**: `/api/system/get_system_info`

### **Parámetros Comunes:**
- `olt_id`: ID del OLT
- `board`: Número de placa
- `port`: Puerto PON
- `zone`: Nombre de la zona
- `odb`: Nombre del ODB/Splitter

---

**Nota**: El sistema de descubrimiento automático ahora está basado en la **documentación oficial de SmartOLT** y probará los endpoints reales con la estructura correcta. Una vez que se descubre la configuración, todas las funcionalidades del módulo funcionarán automáticamente.
