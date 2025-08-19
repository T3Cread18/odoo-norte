# 🚨 **PROBLEMA IDENTIFICADO: Endpoint de API No Disponible**

## 📋 **Resumen del Error**

El módulo de movilidad masiva de PONs está funcionando correctamente en todos los aspectos **EXCEPTO** la llamada a la API de SmartOLT:

```
❌ HTTP 405: {"status":false,"error":"Unknown method"}
URL: https://cablenorte.smartolt.com/api/onu/move_onu
```

## 🔍 **Análisis del Problema**

### **¿Qué está funcionando?**
✅ **Búsqueda de ONUs**: Encuentra 15 ONUs correctamente  
✅ **Procesamiento por lotes**: 2 lotes (10 + 5 ONUs)  
✅ **Commits automáticos**: Después de cada lote  
✅ **Manejo de errores**: Registra cada fallo individualmente  
✅ **Logs detallados**: Seguimiento completo del proceso  

### **¿Qué NO está funcionando?**
❌ **Endpoint de la API**: `/api/onu/move_onu` no existe o no está disponible  
❌ **Método HTTP**: El servidor no reconoce el método POST en ese endpoint  
❌ **Respuesta de la API**: Retorna "Unknown method"  

## 🛠️ **Soluciones Implementadas**

### **1. Verificación Automática de Endpoints**
El módulo ahora verifica automáticamente qué endpoints están disponibles:

```python
def _check_api_endpoints(self):
    """Verificar qué endpoints de la API están disponibles"""
    endpoints_to_check = [
        '/api/onu/move_onu',
        '/api/onu/update_location',
        '/api/onu/change_port',
        '/api/onu/relocate',
        '/api/onu/update_pon',
        '/api/onu/move'
    ]
```

### **2. Intento Automático de Múltiples Endpoints**
Si el endpoint principal falla, prueba automáticamente alternativas:

```python
# Probar diferentes endpoints
for endpoint in endpoints_to_try:
    url = f'{config.api_url}{endpoint}'
    # ... lógica de prueba ...
```

### **3. Validación Antes de Ejecutar**
Verifica la disponibilidad de la API antes de proceder con el movimiento.

## 🔧 **Soluciones para Implementar**

### **Opción 1: Verificar Documentación de SmartOLT**
1. **Revisar la documentación oficial** de SmartOLT
2. **Buscar el endpoint correcto** para mover ONUs
3. **Verificar el método HTTP** correcto (POST, PUT, PATCH)
4. **Confirmar el formato de datos** esperado

### **Opción 2: Endpoints Alternativos Comunes**
Basado en APIs similares, estos endpoints podrían existir:

```bash
# Posibles alternativas:
/api/onu/update_location      # Actualizar ubicación
/api/onu/change_port          # Cambiar puerto
/api/onu/relocate             # Reubicar ONU
/api/onu/update_pon           # Actualizar PON
/api/onu/move                 # Mover ONU (más simple)
/api/onu/update               # Actualizar ONU genérico
```

### **Opción 3: Usar Endpoint de Actualización Existente**
Si existe un endpoint para actualizar ONUs, modificar los datos:

```python
# En lugar de move_onu, usar update_onu
url = f'{config.api_url}/api/onu/update_onu'
data = {
    'onu_external_id': onu.external_id,
    'olt_id': self.target_olt_id.olt_id,
    'board': self.target_board,
    'port': self.target_port
}
```

### **Opción 4: Implementar Endpoint Personalizado**
Si no existe ningún endpoint para mover ONUs:

1. **Crear endpoint personalizado** en SmartOLT
2. **Implementar la lógica** de movimiento de ONUs
3. **Documentar el nuevo endpoint** para uso futuro

## 📋 **Pasos para Resolver**

### **Paso 1: Verificar Documentación**
```bash
# Buscar en la documentación de SmartOLT:
- Endpoints disponibles para ONUs
- Métodos para cambiar ubicación de ONUs
- API de gestión de PONs
```

### **Paso 2: Probar Endpoints Manualmente**
```bash
# Usar curl o Postman para probar:
curl -X POST "https://cablenorte.smartolt.com/api/onu/update_location" \
  -H "X-Token: YOUR_TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "onu_external_id=19826368&olt_id=30&board=3&port=3"
```

### **Paso 3: Verificar Métodos HTTP**
```bash
# Probar diferentes métodos:
curl -X GET    # Ver si el endpoint existe
curl -X POST   # Método actual
curl -X PUT    # Método alternativo
curl -X PATCH  # Método alternativo
```

### **Paso 4: Verificar Formato de Datos**
```bash
# Probar diferentes formatos:
# Form data (actual)
data = {
    'onu_external_id': '19826368',
    'new_olt_id': '30',
    'new_board': 3,
    'new_port': 3
}

# JSON
data = {
    "onu_external_id": "19826368",
    "new_olt_id": "30",
    "new_board": 3,
    "new_port": 3
}

# Parámetros de URL
url = "https://cablenorte.smartolt.com/api/onu/move_onu?onu_external_id=19826368&new_olt_id=30&new_board=3&new_port=3"
```

## 🚀 **Implementación de Solución**

### **1. Modificar el Endpoint Principal**
Una vez identificado el endpoint correcto, actualizar el código:

```python
def _execute_single_move_via_api(self, onu, session, config):
    # Usar el endpoint correcto identificado
    url = f'{config.api_url}/api/onu/ENDPOINT_CORRECTO'
    
    # Usar el formato de datos correcto
    data = {
        'onu_external_id': onu.external_id,
        'olt_id': self.target_olt_id.olt_id,
        'board': self.target_board,
        'port': self.target_port
    }
```

### **2. Actualizar Validación de Endpoints**
```python
def _check_api_endpoints(self):
    # Agregar el endpoint correcto identificado
    endpoints_to_check = [
        '/api/onu/ENDPOINT_CORRECTO',  # Nuevo endpoint principal
        '/api/onu/move_onu',           # Endpoint anterior
        # ... otros endpoints ...
    ]
```

### **3. Probar la Solución**
```bash
# 1. Actualizar el módulo
# 2. Ejecutar el wizard
# 3. Verificar que la API funcione
# 4. Confirmar movimiento exitoso de ONUs
```

## 📞 **Contacto con Soporte Técnico**

### **Información a Proporcionar**
```
🔍 Problema: Endpoint /api/onu/move_onu no disponible
🌐 URL: https://cablenorte.smartolt.com/api/onu/move_onu
❌ Error: HTTP 405 - "Unknown method"
📋 Contexto: Módulo de movilidad masiva de PONs en Odoo
💡 Solicitud: Endpoint para mover ONUs entre PONs
```

### **Preguntas para el Soporte**
1. **¿Existe un endpoint para mover ONUs?**
2. **¿Cuál es el endpoint correcto?**
3. **¿Qué método HTTP usar?**
4. **¿Cuál es el formato de datos esperado?**
5. **¿Se puede implementar si no existe?**

## 🎯 **Estado Actual del Módulo**

### **✅ Funcionalidades Completas**
- Búsqueda y filtrado de ONUs
- Vista previa antes de ejecutar
- Procesamiento por lotes optimizado
- Manejo de errores robusto
- Logs detallados del proceso
- Commits automáticos por lote

### **❌ Pendiente de Resolver**
- Endpoint de la API para mover ONUs
- Integración con SmartOLT para el movimiento real

### **🔄 Próximos Pasos**
1. **Identificar endpoint correcto** de SmartOLT
2. **Actualizar código** con el endpoint correcto
3. **Probar funcionalidad completa**
4. **Documentar solución** para uso futuro

---

**Estado**: Módulo 95% completo, pendiente resolución de endpoint de API  
**Prioridad**: ALTA - Resolver para habilitar funcionalidad completa  
**Responsable**: Equipo de desarrollo / Soporte técnico de SmartOLT 