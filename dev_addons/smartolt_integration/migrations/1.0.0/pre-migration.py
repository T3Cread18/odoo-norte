# -*- coding: utf-8 -*-

def migrate(cr, version):
    """
    Migración pre-1.0.0 para el módulo de movilidad masiva de PONs
    
    Este script se ejecuta antes de la actualización del módulo para:
    1. Verificar que no existan conflictos en la base de datos
    2. Preparar la estructura necesaria
    3. Limpiar datos obsoletos si es necesario
    """
    
    # Verificar si la tabla smartolt_pon_move ya existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'smartolt_pon_move'
        );
    """)
    
    table_exists = cr.fetchone()[0]
    
    if table_exists:
        # La tabla ya existe, verificar si tiene la estructura correcta
        cr.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'smartolt_pon_move'
            ORDER BY ordinal_position;
        """)
        
        columns = {row[0]: row[1] for row in cr.fetchall()}
        
        # Verificar si necesitamos actualizar la estructura
        if 'batch_move_id' in columns and columns['batch_move_id'] == 'integer':
            # La estructura ya está correcta
            print("✅ Tabla smartolt_pon_move ya tiene la estructura correcta")
        else:
            # Necesitamos actualizar la estructura
            print("🔄 Actualizando estructura de tabla smartolt_pon_move")
            
            # Cambiar el tipo de columna batch_move_id si es necesario
            if 'batch_move_id' in columns:
                try:
                    cr.execute("""
                        ALTER TABLE smartolt_pon_move 
                        ALTER COLUMN batch_move_id TYPE integer;
                    """)
                    print("✅ Columna batch_move_id actualizada a integer")
                except Exception as e:
                    print(f"⚠️ No se pudo actualizar batch_move_id: {e}")
    else:
        print("ℹ️ La tabla smartolt_pon_move será creada durante la actualización")
    
    # Verificar que las tablas relacionadas existan
    required_tables = ['smartolt_onu', 'smartolt_olt']
    
    for table in required_tables:
        cr.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = '{table}'
            );
        """)
        
        if cr.fetchone()[0]:
            print(f"✅ Tabla {table} existe")
        else:
            print(f"⚠️ Tabla {table} no existe - puede causar problemas")
    
    print("🚀 Migración pre-1.0.0 completada") 