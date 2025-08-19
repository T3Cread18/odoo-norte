# Ejemplos de URLs para SmartOLT

## 🎯 **Análisis del Error 405**

El error **HTTP 405 - "Unknown method"** indica que:
- ✅ **El servidor SmartOLT está funcionando**
- ✅ **La URL base es correcta**
- ❌ **El endpoint o método HTTP no es el correcto**

## 🌐 **Formatos de URL Comunes para SmartOLT**

### **1. Formato Estándar (más común)**
```
http://192.168.1.100:8080
http://localhost:8080
http://smartolt.local:8080
```

### **2. Formato con Subdirectorio**
```
http://192.168.1.100:8080/smartolt
http://192.168.1.100:8080/api
http://192.168.1.100:8080/v1
```

### **3. Formato con Dominio Personalizado**
```
https://smartolt.tuempresa.com
https://api.tuempresa.com
https://olt.tuempresa.com
```

### **4. Formato con Puerto Personalizado**
```
http://192.168.1.100:3000
http://192.168.1.100:5000
http://192.168.1.100:9000
```

## 🔍 **Cómo Encontrar la URL Correcta**

### **Paso 1: Verificar en el Servidor SmartOLT**
1. **Accede al servidor** donde está instalado SmartOLT
2. **Revisa la configuración** del servicio web
3. **Busca archivos de configuración** como:
   - `config.php`
   - `settings.ini`
   - `docker-compose.yml`
   - `nginx.conf` o `apache.conf`

### **Paso 2: Verificar Puertos Abiertos**
```bash
# En el servidor SmartOLT
netstat -tlnp | grep :8080
netstat -tlnp | grep :80
netstat -tlnp | grep :443
```

### **Paso 3: Verificar Servicios Activos**
```bash
# Ver servicios que están ejecutándose
systemctl list-units --type=service | grep smartolt
systemctl list-units --type=service | grep nginx
systemctl list-units --type=service | grep apache
```

## 📋 **Endpoints Comunes para Probar**

### **Endpoints Básicos (probar primero)**
```
GET /api/status
GET /status
GET /api
GET /
```

### **Endpoints de OLT (probar segundo)**
```
GET /api/olt
GET /api/olt/list
GET /olt
GET /olt/list
```

### **Endpoints Alternativos**
```
GET /api/v1/olt
GET /v1/olt
GET /smartolt/api/olt
```

## 🛠️ **Configuración en Odoo**

### **1. Acceder a la Configuración**
- Ve a **SmartOLT > Herramientas > Configuración de API**

### **2. Configurar la URL**
- **URL de la API**: Ingresa la URL correcta de tu servidor
- **Token de API**: Ingresa tu token válido

### **3. Probar la Conexión**
- Haz clic en **"Probar Conexión"**
- El sistema probará automáticamente múltiples endpoints

## 🔧 **Troubleshooting Avanzado**

### **Si el Error 405 Persiste:**
1. **Verifica el método HTTP** que acepta tu servidor
2. **Revisa la documentación** específica de tu versión de SmartOLT
3. **Contacta al soporte** de SmartOLT con el error específico

### **Si No Hay Respuesta:**
1. **Verifica conectividad de red**
2. **Confirma que el firewall permita la conexión**
3. **Verifica que el servidor esté ejecutándose**

### **Si Hay Error de Autenticación:**
1. **Verifica que el token sea válido**
2. **Confirma que el token no haya expirado**
3. **Verifica los permisos del usuario en SmartOLT**

## 📞 **Obtener Ayuda**

### **Información Necesaria:**
- **Versión de SmartOLT** que estás usando
- **Sistema operativo** del servidor
- **Método de instalación** (Docker, nativo, etc.)
- **Logs del servidor** SmartOLT
- **Error específico** que estás recibiendo

### **Recursos Útiles:**
- **Documentación oficial** de SmartOLT
- **Foros de la comunidad** SmartOLT
- **Soporte técnico** de SmartOLT
- **Logs de Odoo** para debugging

## 🎯 **Próximos Pasos**

1. **Identifica la URL correcta** de tu servidor SmartOLT
2. **Configura la URL y token** en el módulo
3. **Prueba la conexión** con el sistema mejorado
4. **Revisa los logs** para información detallada
5. **Contacta soporte** si persisten los problemas

---

**Nota**: El sistema ahora probará automáticamente múltiples endpoints y métodos HTTP para encontrar la configuración correcta de tu servidor SmartOLT.
