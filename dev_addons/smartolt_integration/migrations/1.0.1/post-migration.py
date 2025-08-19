# -*- coding: utf-8 -*-
"""
Migración 1.0.1: Agregar nuevos campos a la tabla smartolt_onu
"""

def migrate(cr, version):
    """
    Agrega los nuevos campos a la tabla smartolt_onu
    """
    # Agregar campo onu_type_id
    try:
        cr.execute("""
            ALTER TABLE smartolt_onu 
            ADD COLUMN IF NOT EXISTS onu_type_id VARCHAR
        """)
        print("✅ Campo onu_type_id agregado correctamente")
    except Exception as e:
        print(f"⚠️  Error agregando onu_type_id: {e}")
    
    # Agregar campo ethernet_port
    try:
        cr.execute("""
            ALTER TABLE smartolt_onu 
            ADD COLUMN IF NOT EXISTS ethernet_port VARCHAR
        """)
        print("✅ Campo ethernet_port agregado correctamente")
    except Exception as e:
        print(f"⚠️  Error agregando ethernet_port: {e}")
    
    # Agregar campo ethernet_admin_state
    try:
        cr.execute("""
            ALTER TABLE smartolt_onu 
            ADD COLUMN IF NOT EXISTS ethernet_admin_state VARCHAR
        """)
        print("✅ Campo ethernet_admin_state agregado correctamente")
    except Exception as e:
        print(f"⚠️  Error agregando ethernet_admin_state: {e}")
    
    # Verificar que los campos se agregaron correctamente
    try:
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'smartolt_onu' 
            AND column_name IN ('onu_type_id', 'ethernet_port', 'ethernet_admin_state')
        """)
        
        columns = [row[0] for row in cr.fetchall()]
        print(f"📋 Campos verificados: {columns}")
        
        if len(columns) == 3:
            print("🎉 Migración completada exitosamente")
        else:
            print(f"⚠️  Solo se encontraron {len(columns)} de 3 campos esperados")
            
    except Exception as e:
        print(f"❌ Error verificando campos: {e}")
    
    print("🚀 Migración 1.0.1 finalizada")

