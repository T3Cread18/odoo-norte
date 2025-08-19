# 🚀 Módulo de Movilidad Masiva de Clientes entre PONs

## 📋 **Descripción General**

Este módulo permite mover masivamente clientes (ONUs) entre diferentes PONs (Puertos Ópticos) de una o múltiples OLTs de forma eficiente y controlada.

## 🎯 **Funcionalidades Principales**

### **1. Movilidad Masiva de PONs**
- **Selección inteligente**: Filtros por OLT, board, puerto, zona y estado
- **Validación automática**: Verifica capacidad del puerto destino
- **Procesamiento en lotes**: Optimiza el rendimiento para grandes cantidades
- **Rollback automático**: Revertir cambios en caso de fallo

### **2. Gestión de Movimientos**
- **Registro completo**: Historial de todos los movimientos realizados
- **Estados de seguimiento**: Pendiente, En Progreso, Completado, Fallido, Revertido
- **Auditoría completa**: Logs de cambios y respuestas de la API

### **3. Interfaz Intuitiva**
- **Wizard paso a paso**: Guía al usuario durante todo el proceso
- **Validaciones en tiempo real**: Previene errores antes de la ejecución
- **Notificaciones inteligentes**: Informa sobre el progreso y resultados

## 🏗️ **Arquitectura del Módulo**

### **Modelos Principales**

#### **`smartolt.pon.move`**
Registro individual de cada movimiento de ONU:
- Información de origen y destino
- Estado del movimiento
- Fechas y duración
- Respuestas de la API
- Historial de cambios

#### **`smartolt.bulk.pon.move.wizard`**
Wizard para ejecutar movimientos masivos:
- Filtros de selección
- Configuración de procesamiento
- Ejecución en lotes
- Manejo de resultados

### **Flujo de Trabajo**

```
1. Selección de ONUs → 2. Configuración de Destino → 3. Validación → 4. Ejecución → 5. Resultados
```

## 🔧 **Configuración y Uso**

### **Acceso al Módulo**
1. **Menú**: SmartOLT > Herramientas > Movilidad Masiva de PONs
2. **Permisos**: Usuarios con acceso a SmartOLT pueden usar la funcionalidad

### **Proceso de Uso**

#### **Paso 1: Seleccionar ONUs**
- **OLT Origen**: Seleccionar la OLT de donde se moverán las ONUs
- **Board y Puerto**: Especificar el PON origen exacto
- **Filtros adicionales**: Zona, estado de ONU, etc.
- **Buscar**: El sistema encuentra automáticamente las ONUs

#### **Paso 2: Configurar Destino**
- **OLT Destino**: Nueva OLT (opcional, si es la misma OLT)
- **Board y Puerto**: Nuevo PON destino
- **Validación**: El sistema verifica la capacidad disponible

#### **Paso 3: Confirmar y Ejecutar**
- **Revisar**: Lista de ONUs a mover
- **Confirmar**: Ejecutar el movimiento masivo
- **Monitorear**: Seguimiento del progreso en tiempo real

### **Configuraciones Avanzadas**

#### **Tamaño de Lote**
- **Por defecto**: 10 ONUs por lote
- **Máximo**: 10 ONUs (límite de la API)
- **Optimización**: Ajuste automático según cantidad

#### **Rollback Automático**
- **Habilitado por defecto**: Revierte cambios en caso de fallo
- **Configurable**: Se puede deshabilitar si es necesario
- **Seguridad**: Previene estados inconsistentes

## 🌐 **Integración con API SmartOLT**

### **Endpoints Utilizados**

#### **Mover ONU Individual**
```
POST /api/onu/move_onu
{
    "onu_external_id": "12345",
    "new_olt_id": "2",
    "new_board": "3",
    "new_port": "4"
}
```

#### **Mover Múltiples ONUs**
```
POST /api/onu/bulk_move_onus
{
    "onus_external_ids": ["12345", "67890"],
    "new_olt_id": "2",
    "new_board": "3",
    "new_port": "4"
}
```

### **Manejo de Respuestas**

#### **Respuesta Exitosa**
```json
{
    "status": "success",
    "response_code": "success",
    "message": "ONU moved successfully"
}
```

#### **Respuesta de Error**
```json
{
    "status": "error",
    "response_code": "failed",
    "error": "Port capacity exceeded"
}
```

## 📊 **Monitoreo y Auditoría**

### **Estados de Movimiento**

1. **Pendiente**: Movimiento creado, esperando ejecución
2. **En Progreso**: Movimiento en ejecución via API
3. **Completado**: Movimiento exitoso
4. **Fallido**: Error durante la ejecución
5. **Revertido**: Movimiento revertido por rollback

### **Información de Auditoría**

- **Fecha y hora** de cada movimiento
- **Duración** del proceso
- **Respuestas de la API** completas
- **Mensajes de error** detallados
- **Historial de cambios** con timestamps

## 🚨 **Consideraciones de Seguridad**

### **Validaciones Previas**
- **Capacidad del puerto**: Verifica que haya espacio disponible
- **Estado de ONU**: Solo mueve ONUs online
- **Permisos de usuario**: Verifica acceso a la funcionalidad
- **Conflictos de red**: Previene movimientos problemáticos

### **Protecciones Durante la Ejecución**
- **Transacciones**: Rollback automático en caso de fallo
- **Timeouts**: Manejo de respuestas lentas de la API
- **Reintentos**: Intento automático en caso de fallo temporal
- **Logs detallados**: Registro completo de todas las operaciones

## 🔍 **Troubleshooting**

### **Problemas Comunes**

#### **Error: "No se encontraron ONUs"**
- **Causa**: Filtros muy restrictivos
- **Solución**: Relajar los filtros de búsqueda

#### **Error: "Puerto destino sin capacidad"**
- **Causa**: Puerto destino lleno
- **Solución**: Seleccionar otro puerto o verificar capacidad

#### **Error: "API no responde"**
- **Causa**: Problemas de conectividad o API caída
- **Solución**: Verificar conectividad y estado de SmartOLT

#### **Error: "Movimiento parcialmente exitoso"**
- **Causa**: Algunas ONUs fallaron durante el proceso
- **Solución**: Revisar logs de error y reintentar ONUs fallidas

### **Logs de Debug**

El módulo genera logs detallados en:
- **Odoo logs**: Información general del proceso
- **Modelo de movimiento**: Detalles específicos de cada ONU
- **Respuestas de API**: Comunicación completa con SmartOLT

## 📈 **Casos de Uso**

### **1. Mantenimiento de Red**
- **Escenario**: Mover clientes durante trabajos de mantenimiento
- **Beneficio**: Servicio continuo para los clientes

### **2. Optimización de Carga**
- **Escenario**: Redistribuir clientes entre PONs sobrecargados
- **Beneficio**: Mejor rendimiento de red

### **3. Expansión de Infraestructura**
- **Escenario**: Migrar clientes a nueva infraestructura
- **Beneficio**: Actualización sin interrupciones

### **4. Balanceo de Tráfico**
- **Escenario**: Equilibrar tráfico entre puertos
- **Beneficio**: Distribución uniforme de la carga

## 🚀 **Próximas Funcionalidades**

### **Funcionalidades Planificadas**
- **Programación de movimientos**: Agendar para horarios específicos
- **Notificaciones automáticas**: Alertas por email/SMS
- **Análisis de impacto**: Previsualización de cambios
- **Movimientos condicionales**: Basados en métricas de red

### **Mejoras Técnicas**
- **API asíncrona**: Movimientos en segundo plano
- **Cache inteligente**: Optimización de consultas
- **Métricas en tiempo real**: Dashboard de movimientos
- **Integración con NMS**: Sincronización con sistemas externos

## 📞 **Soporte y Contacto**

### **Documentación Adicional**
- **API Discovery Guide**: Descubrimiento automático de endpoints
- **SmartOLT Integration**: Documentación general del módulo
- **Ejemplos de Uso**: Casos prácticos y configuraciones

### **Reportar Problemas**
- **Logs de Odoo**: Incluir logs completos del error
- **Configuración**: Detalles de la configuración de API
- **Pasos de reproducción**: Secuencia exacta que causa el problema

---

**Versión**: 1.0  
**Fecha**: Agosto 2025  
**Compatibilidad**: Odoo 16.0, SmartOLT API v2+ 