import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import text
import numpy as np

# 1. Configuración de la conexión a la base de datos local
# Usuario, contraseña, host, puerto, nombre_db (definidos en tu docker-compose)
db_url = 'postgresql://hexa_admin:hexa@localhost:5432/hexa_dwh'
engine = create_engine(db_url)

print("Iniciando extracción de datos...")
# 1. Extracción del CSV
df = pd.read_csv('KaggleV2-May-2016.csv')

print("Iniciando limpieza y transformación...")
# 2. Limpieza de fechas y cálculo de LeadTime
df['ScheduledDay'] = pd.to_datetime(df['ScheduledDay']).dt.normalize()
df['AppointmentDay'] = pd.to_datetime(df['AppointmentDay']).dt.normalize()

# Calcular LeadTime_Num (días de diferencia)
df['LeadTime_Num'] = (df['AppointmentDay'] - df['ScheduledDay']).dt.days

# Filtros de limpieza: eliminar edades negativas y lead times negativos
df = df[(df['Age'] >= 0) & (df['LeadTime_Num'] >= 0)].copy()

# --- NUEVAS LÍNEAS: Casteos estrictos ---
df['Scholarship'] = df['Scholarship'].astype(bool)
df['PatientId'] = df['PatientId'].astype('int64') 
# ----------------------------------------

# 3. Transformación de No-show
# Yes = No se presentó (1), No = Sí se presentó (0)
df['Contador_NoShow'] = df['No-show'].map({'Yes': 1, 'No': 0})
df['Cita_Count'] = 1

# 4. Transformación Geográfica (Neighbourhood)
# Mapeo de ejemplo. Los que no estén aquí caerán en 'Otras Zonas'
mapeo_zonas = {
    'JARDIM DA PENHA': 'Zona Este',
    'MATA DA PRAIA': 'Zona Este',
    'CENTRO': 'Zona Centro',
    'REPÚBLICA': 'Zona Centro',
    'MARUÍPE': 'Zona Norte',
    'SÃO PEDRO': 'Zona Sur'
}
df['Zona_Ciudad'] = df['Neighbourhood'].map(mapeo_zonas).fillna('Otras Zonas')

# 5. Transformación de Rangos Etarios
bins = [-1, 12, 18, 60, 150] # -1 para incluir a los de 0 años
labels = ['Infante', 'Adolescente', 'Adulto', 'Senior']
df['Rango_Etario'] = pd.cut(df['Age'], bins=bins, labels=labels)

# 6. Transformación de Fechas (Dimensión Tiempo)
df['ID_Fecha'] = df['AppointmentDay'].dt.strftime('%Y%m%d').astype(int)
df['Anio'] = df['AppointmentDay'].dt.year
df['Mes'] = df['AppointmentDay'].dt.month
df['Dia_Semana'] = df['AppointmentDay'].dt.day_name()
# Lógica simple para fin de semana (Sábado=5, Domingo=6)
df['Es_Feriado'] = df['AppointmentDay'].dt.weekday >= 5 

# --- LIMPIEZA DE TABLAS (Hacer el script idempotente) ---
print("Limpiando base de datos para carga limpia...")
with engine.begin() as conn:
    conn.execute(text("""
        TRUNCATE TABLE fact_citas, dim_paciente, dim_geografica, 
                       dim_tiempo, dim_condicion, dim_espera, 
                       dim_notificacion RESTART IDENTITY CASCADE;
    """))

# --- PREPARACIÓN Y CARGA DE DIMENSIONES ---
print("Cargando tablas de dimensiones...")

# Dim_Geografica
dim_geo = df[['Zona_Ciudad', 'Neighbourhood']].drop_duplicates().rename(
    columns={'Neighbourhood': 'neighbourhood', 'Zona_Ciudad': 'zona_ciudad'}
)
dim_geo.to_sql('dim_geografica', engine, if_exists='append', index=False)

# Recuperar los IDs generados usando interpolación de variables en la query
tabla_geo = 'dim_geografica'
dim_geo_db = pd.read_sql(f"SELECT * FROM {tabla_geo}", engine)
# Cruzar (Merge) para traer el ID_Barrio al DataFrame principal
df = df.merge(dim_geo_db, left_on=['Zona_Ciudad', 'Neighbourhood'], right_on=['zona_ciudad', 'neighbourhood'], how='left')

# Dim_Paciente (No usamos autoincremental porque tenemos el PatientId)
dim_paciente = df[['PatientId', 'Rango_Etario', 'Age', 'Gender', 'Scholarship']].drop_duplicates(subset=['PatientId'])
dim_paciente = dim_paciente.rename(columns={
    'PatientId': 'id_paciente', 'Rango_Etario': 'rango_etario', 
    'Age': 'edad', 'Gender': 'gender', 'Scholarship': 'scholarship'
})
dim_paciente.to_sql('dim_paciente', engine, if_exists='append', index=False)
df['id_paciente'] = df['PatientId']

# Dim_Tiempo
dim_tiempo = df[['ID_Fecha', 'Anio', 'Mes', 'Dia_Semana', 'Es_Feriado']].drop_duplicates()
dim_tiempo = dim_tiempo.rename(columns={
    'ID_Fecha': 'id_fecha', 'Anio': 'anio', 'Mes': 'mes', 
    'Dia_Semana': 'dia_semana', 'Es_Feriado': 'es_feriado'
})
# Usamos try/except porque esta tabla usa el ID_Fecha como PK fija y si corres el script 2 veces dará error de duplicidad
try:
    dim_tiempo.to_sql('dim_tiempo', engine, if_exists='append', index=False)
except Exception as e:
    pass

df['id_fecha_cita'] = df['ID_Fecha']

# --- CARGA DE LAS DIMENSIONES FALTANTES ---

print("Procesando Dim_Condicion...")
# Casteo de booleanos e ints según el DDL
df['Hipertension'] = df['Hipertension'].astype(bool)
df['Diabetes'] = df['Diabetes'].astype(bool)
df['Alcoholism'] = df['Alcoholism'].astype(bool)
df['Discapacidad'] = df['Handcap'].astype(int)

dim_condicion = df[['Hipertension', 'Diabetes', 'Alcoholism', 'Discapacidad']].drop_duplicates()
dim_condicion = dim_condicion.rename(columns={
    'Hipertension': 'hipertension', 'Diabetes': 'diabetes', 
    'Alcoholism': 'alcoholism', 'Discapacidad': 'discapacidad'
})
dim_condicion.to_sql('dim_condicion', engine, if_exists='append', index=False)

# Recuperar IDs y hacer merge
dim_cond_db = pd.read_sql("SELECT * FROM dim_condicion", engine)
df = df.merge(dim_cond_db, left_on=['Hipertension', 'Diabetes', 'Alcoholism', 'Discapacidad'], 
              right_on=['hipertension', 'diabetes', 'alcoholism', 'discapacidad'], how='left')


print("Procesando Dim_Notificacion...")
df['SMS_Received'] = df['SMS_received'].astype(bool)
dim_noti = df[['SMS_Received']].drop_duplicates()
dim_noti = dim_noti.rename(columns={'SMS_Received': 'sms_received'})
dim_noti.to_sql('dim_notificacion', engine, if_exists='append', index=False)

dim_noti_db = pd.read_sql("SELECT * FROM dim_notificacion", engine)
df = df.merge(dim_noti_db, left_on='SMS_Received', right_on='sms_received', how='left')


print("Procesando Dim_Espera...")
# Clasificación basada en el documento PDF
bins_espera = [-1, 2, 7, 999999] # -1 para incluir los de 0 días (Inmediato)
labels_espera = ['Inmediato', 'Corto', 'Largo']
df['rango_espera_str'] = pd.cut(df['LeadTime_Num'], bins=bins_espera, labels=labels_espera).astype(str)

# Armamos el DataFrame de la dimensión manualmente ya que los rangos min/max son estáticos
data_espera = {
    'rango_espera': ['Inmediato', 'Corto', 'Largo'],
    'dias_min': [0, 3, 8],
    'dias_max': [2, 7, 999] # 999 como maximo teorico representativo
}
dim_espera = pd.DataFrame(data_espera)
dim_espera.to_sql('dim_espera', engine, if_exists='append', index=False)

dim_espera_db = pd.read_sql("SELECT * FROM dim_espera", engine)
df = df.merge(dim_espera_db, left_on='rango_espera_str', right_on='rango_espera', how='left')

# --- PREPARACIÓN Y CARGA DE HECHOS ---
print("Cargando tabla de hechos (Fact_Citas)...")

# Seleccionamos las columnas
fact_citas = df[[
    'id_paciente', 
    'id_fecha_cita', 
    'id_barrio', 
    'id_condicion', 
    'id_sms', 
    'id_espera', 
    'Contador_NoShow', 
    'LeadTime_Num', 
    'Cita_Count'
]].copy()

fact_citas = fact_citas.rename(columns={
    'Contador_NoShow': 'contador_noshow',
    'LeadTime_Num': 'leadtime_num',
    'Cita_Count': 'cita_count'
})

# --- SOLUCIÓN DE GRANULARIDAD ---
# Agrupamos por la Clave Primaria Compuesta para evitar la UniqueViolation.
# Si un paciente tiene 2 citas exactamente iguales el mismo día, las métricas se suman.
fact_citas = fact_citas.groupby(
    ['id_paciente', 'id_fecha_cita', 'id_barrio', 'id_condicion', 'id_sms', 'id_espera'],
    as_index=False
).agg({
    'contador_noshow': 'sum',
    'leadtime_num': 'max',  # En caso de múltiples turnos, conservamos la espera más larga
    'cita_count': 'sum'     # Aquí 2 turnos sumarán 2
})

# Insertar en base de datos
fact_citas.to_sql('fact_citas', engine, if_exists='append', index=False)

print("¡Proceso ETL finalizado con éxito! El Data Warehouse está listo para BI.")
