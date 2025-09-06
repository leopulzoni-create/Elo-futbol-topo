import sqlite3

# Nombre del archivo de base de datos
db_name = "elo_futbol.db"

# Conexión a la base (se crea si no existe)
conn = sqlite3.connect(db_name)
cursor = conn.cursor()

# Creación de tablas
cursor.executescript("""

-- 1. Jugadores y Grupos
CREATE TABLE IF NOT EXISTS grupos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS jugadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    elo_actual INTEGER NOT NULL,
    grupo_id INTEGER,
    estado TEXT CHECK(estado IN ('activo','inactivo')),
    foto TEXT,
    FOREIGN KEY (grupo_id) REFERENCES grupos(id)
);

-- 2. Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jugador_id INTEGER,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT CHECK(rol IN ('admin','jugador')) NOT NULL,
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id)
);

-- 3. Canchas
CREATE TABLE IF NOT EXISTS canchas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    direccion TEXT,
    foto TEXT
);

-- 4. Partidos
CREATE TABLE IF NOT EXISTS partidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME NOT NULL,
    cancha_id INTEGER,
    ganador INTEGER CHECK(ganador IN (1,2)),
    diferencia_gol INTEGER,
    es_oficial INTEGER NOT NULL CHECK(es_oficial IN (0,1)),
    tipo TEXT CHECK(tipo IN ('abierto','cerrado')) NOT NULL,
    FOREIGN KEY (cancha_id) REFERENCES canchas(id)
);

-- 5. Invitaciones y confirmaciones
CREATE TABLE IF NOT EXISTS partido_grupos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partido_id INTEGER NOT NULL,
    grupo_id INTEGER NOT NULL,
    FOREIGN KEY (partido_id) REFERENCES partidos(id),
    FOREIGN KEY (grupo_id) REFERENCES grupos(id)
);

CREATE TABLE IF NOT EXISTS confirmaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partido_id INTEGER NOT NULL,
    jugador_id INTEGER NOT NULL,
    confirmado INTEGER CHECK(confirmado IN (0,1)),
    fecha_confirmacion DATETIME,
    FOREIGN KEY (partido_id) REFERENCES partidos(id),
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id)
);

CREATE TABLE IF NOT EXISTS partido_jugadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partido_id INTEGER NOT NULL,
    jugador_id INTEGER NOT NULL,
    equipo INTEGER CHECK(equipo IN (1,2)) NOT NULL,
    camiseta TEXT CHECK(camiseta IN ('clara','oscura')) NOT NULL,
    FOREIGN KEY (partido_id) REFERENCES partidos(id),
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id)
);

-- 6. Historial de ELO
CREATE TABLE IF NOT EXISTS historial_elo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jugador_id INTEGER NOT NULL,
    partido_id INTEGER NOT NULL,
    elo_antes INTEGER NOT NULL,
    elo_despues INTEGER NOT NULL,
    FOREIGN KEY (jugador_id) REFERENCES jugadores(id),
    FOREIGN KEY (partido_id) REFERENCES partidos(id)
);

""")

# Guardar cambios y cerrar conexión
conn.commit()
conn.close()

print(f"Base de datos '{db_name}' creada con éxito.")


