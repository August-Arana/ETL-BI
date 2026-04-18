-- 1. Dimensiones (El "cómo" queremos filtrar los datos)

-- Dimensión Tiempo (Jerárquica 1)
CREATE TABLE DIM_Tiempo (
    ID_Fecha INT PRIMARY KEY,
    Anio INT,
    Mes INT,
    Dia_Semana VARCHAR(20),
    Es_Feriado BOOLEAN
);

-- Dimensión Geográfica (Jerárquica 2)
CREATE TABLE DIM_Geografica (
    ID_Barrio SERIAL PRIMARY KEY,
    Zona_Ciudad VARCHAR(50),
    Neighbourhood VARCHAR(100)
);

-- Dimensión Paciente (Jerárquica 3)
CREATE TABLE DIM_Paciente (
    ID_Paciente INT PRIMARY KEY,
    Rango_Etario VARCHAR(20),
    Edad INT,
    Gender VARCHAR(1),
    Scholarship BOOLEAN
);

-- Dimensión Condición de Salud
CREATE TABLE DIM_Condicion (
    ID_Condicion SERIAL PRIMARY KEY,
    Hipertension BOOLEAN,
    Diabetes BOOLEAN,
    Alcoholism BOOLEAN,
    Discapacidad INT
);

-- Dimensión Notificación
CREATE TABLE DIM_Notificacion (
    ID_SMS SERIAL PRIMARY KEY,
    SMS_Received BOOLEAN
);

-- Dimensión Espera (Lead Time)
CREATE TABLE DIM_Espera (
    ID_Espera SERIAL PRIMARY KEY,
    Rango_Espera VARCHAR(20),
    Dias_min INT,
    Dias_max INT
);


-- 2. Tabla de Hechos

-- Fact_Citas: Tabla central que contiene los eventos y métricas
CREATE TABLE FACT_CITAS (
    ID_Paciente INT REFERENCES DIM_Paciente(ID_Paciente),
    ID_Fecha_Cita INT REFERENCES DIM_Tiempo(ID_Fecha),
    ID_Barrio INT REFERENCES DIM_Geografica(ID_Barrio),
    ID_Condicion INT REFERENCES DIM_Condicion(ID_Condicion),
    ID_SMS INT REFERENCES DIM_Notificacion(ID_SMS),
    ID_Espera INT REFERENCES DIM_Espera(ID_Espera),
    
    Contador_NoShow INT,
    LeadTime_Num INT,
    Cita_Count INT DEFAULT 1,
    
    -- Clave primaria compuesta por todas las FK de las dimensiones
    PRIMARY KEY (ID_Paciente, ID_Fecha_Cita, ID_Barrio, ID_Condicion, ID_SMS, ID_Espera)
);
