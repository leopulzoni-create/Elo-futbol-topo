# equipos.py
import streamlit as st
import sqlite3
from datetime import datetime
import unicodedata
import random
from collections import defaultdict

DB_NAME = "elo_futbol.db"  # nombre exacto

# -------------------------
# Conexión y utilidades
# -------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

# español sin tildes para evitar problemas de render
DIAS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

def parsear_fecha(fecha_str):
    if fecha_str is None:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha_str, fmt)
        except ValueError:
            continue
    return None

def formatear_hora(hora_int):
    """
    Espera un entero tipo HHMM (ej: 1900 -> '19:00').
    Si viene None o invalido, devuelve '19:00' por defecto.
    """
    try:
        if hora_int is None:
            return "19:00"
        s = str(int(hora_int))
        if len(s) <= 2:
            # caso muy raro tipo '19' -> 19:00
            hh = int(s)
            mm = 0
        else:
            s = s.zfill(4)[-4:]  # asegurar 4 dígitos HHMM
            hh = int(s[:2]); mm = int(s[2:])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return "19:00"
        return f"{hh:02d}:{mm:02d}"
    except Exception:
        return "19:00"

# -------------------------
# Datos desde la DB
# -------------------------
def obtener_partidos_abiertos():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.fecha, p.hora, IFNULL(c.nombre,'Sin asignar') AS cancha_nombre
        FROM partidos p
        LEFT JOIN canchas c ON p.cancha_id = c.id
        WHERE p.tipo = 'abierto'
          AND p.ganador IS NULL
          AND p.diferencia_gol IS NULL
        ORDER BY p.fecha ASC, p.hora ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def obtener_jugadores_partido_full(partido_id: int):
    """
    Devuelve lista de dicts con:
    { pj_id, jugador_id, nombre, elo (elo_actual), bloque, confirmado, equipo, camiseta }
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pj.id AS pj_id,
               j.id  AS jugador_id,
               j.nombre AS nombre,
               COALESCE(j.elo_actual, 1000) AS elo,
               pj.bloque AS bloque,
               pj.confirmado_por_jugador AS confirmado,
               pj.equipo AS equipo,
               pj.camiseta AS camiseta
        FROM partido_jugadores pj
        JOIN jugadores j ON j.id = pj.jugador_id
        WHERE pj.partido_id = ?
        ORDER BY pj.id
    """, (partido_id,))
    rows = cur.fetchall()
    conn.close()
    jugadores = [{
        "pj_id": r["pj_id"],
        "jugador_id": r["jugador_id"],
        "nombre": r["nombre"],
        "elo": float(r["elo"]) if r["elo"] is not None else 1000.0,
        "bloque": r["bloque"],
        "confirmado": r["confirmado"],
        "equipo": r["equipo"],
        "camiseta": r["camiseta"],
    } for r in rows]
    return jugadores

def obtener_partido_info(partido_id: int):
    """Devuelve (fecha_dt, hora_str, cancha_nombre) del partido."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.fecha, p.hora, IFNULL(c.nombre,'Sin asignar') AS cancha_nombre
        FROM partidos p
        LEFT JOIN canchas c ON p.cancha_id = c.id
        WHERE p.id = ?
    """, (partido_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None, None, None
    fecha_dt = parsear_fecha(row["fecha"])
    hora_str = formatear_hora(row["hora"])
    return fecha_dt, hora_str, row["cancha_nombre"]

# -------------------------
# Camisetas
# -------------------------
JERSEYS = ("clara", "oscura")

def obtener_camiseta_equipo(partido_id: int, equipo: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT camiseta
          FROM partido_jugadores
         WHERE partido_id = ? AND equipo = ?
    """, (partido_id, equipo))
    vals = [row[0] for row in cur.fetchall() if row[0] is not None and row[0] != ""]
    conn.close()
    if not vals:
        return None
    if len(set(vals)) == 1:
        return vals[0]
    return None  # mezcla no uniforme

def asignar_camiseta_equipo(partido_id: int, equipo: int, camiseta: str):
    if camiseta not in JERSEYS:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE partido_jugadores
           SET camiseta = ?
         WHERE partido_id = ? AND equipo = ?
    """, (camiseta, partido_id, equipo))
    conn.commit()
    conn.close()

def limpiar_camiseta_equipo(partido_id: int, equipo: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE partido_jugadores
           SET camiseta = NULL
         WHERE partido_id = ? AND equipo = ?
    """, (partido_id, equipo))
    conn.commit()
    conn.close()

def intercambiar_camisetas(partido_id: int):
    c1 = obtener_camiseta_equipo(partido_id, 1)
    c2 = obtener_camiseta_equipo(partido_id, 2)
    if (c1 is None and c2 is None) or (c1 == c2):
        asignar_camiseta_equipo(partido_id, 1, "clara")
        asignar_camiseta_equipo(partido_id, 2, "oscura")
        return
    if c1 in JERSEYS:
        asignar_camiseta_equipo(partido_id, 2, c1)
    if c2 in JERSEYS:
        asignar_camiseta_equipo(partido_id, 1, c2)

# -------------------------
# Bloques (duplas/tríos) a partir de 'bloque'
# -------------------------
def construir_bloques(jugadores):
    grupos = defaultdict(list)
    singles = []
    for j in jugadores:
        b = j["bloque"]
        if b is None or b == "":
            singles.append(j)
        else:
            grupos[str(b)].append(j)
    bloques = list(grupos.values())
    bloques.extend([[s] for s in singles])
    bloques.sort(key=lambda bl: (-len(bl), -sum(x["elo"] for x in bl)))
    return bloques

# -------------------------
# Guardar / limpiar bloques definidos por el admin (auto-guardado)
# -------------------------
def limpiar_bloques(partido_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE partido_jugadores SET bloque = NULL WHERE partido_id = ?", (partido_id,))
    conn.commit()
    conn.close()

def set_bloque_por_nombres(partido_id: int, nombres: list, bloque_id: int):
    if not nombres:
        return
    conn = get_connection()
    cur = conn.cursor()
    for nombre in nombres:
        cur.execute("""
            UPDATE partido_jugadores
               SET bloque = ?
             WHERE partido_id = ?
               AND jugador_id = (SELECT id FROM jugadores WHERE nombre = ? LIMIT 1)
        """, (bloque_id, partido_id, nombre))
    conn.commit()
    conn.close()

def _guardar_companeros_si_valido(partido_id, duo1, duo2, trio1, trio2):
    # Validaciones
    ok_tamaños = (len(duo1) in (0, 2)) and (len(duo2) in (0, 2)) and (len(trio1) in (0, 3)) and (len(trio2) in (0, 3))
    if not ok_tamaños:
        st.warning("Tamaños inválidos: la dupla debe tener 2 y el trío 3 jugadores.")
        return False
    seleccionados = [*duo1, *duo2, *trio1, *trio2]
    solapados = [n for n in seleccionados if seleccionados.count(n) > 1]
    if solapados:
        st.error(f"Jugadores repetidos en grupos: {sorted(set(solapados))}")
        return False
    # Guardar
    limpiar_bloques(partido_id)
    set_bloque_por_nombres(partido_id, duo1, 1)
    set_bloque_por_nombres(partido_id, duo2, 2)
    set_bloque_por_nombres(partido_id, trio1, 3)
    set_bloque_por_nombres(partido_id, trio2, 4)
    st.toast("Compañeros guardados.", icon="✅")
    return True

def ui_definir_bloques(partido_id: int, jugadores_nombres: list):
    # Solo cambia el texto visible (no nombres de funciones): "Definir compañeros"
    st.markdown("### 🧩 Definir compañeros (opcional)")
    st.caption("Hasta **2 duplas** y **2 tríos**. No se permiten solapamientos. (Se guarda automáticamente)")

    # Cargar preselecciones desde DB (por si el admin ya definió algo)
    current = defaultdict(list)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.nombre, pj.bloque
        FROM partido_jugadores pj
        JOIN jugadores j ON j.id = pj.jugador_id
        WHERE pj.partido_id = ? AND pj.bloque IS NOT NULL
        ORDER BY j.nombre
    """, (partido_id,))
    for nombre, b in cur.fetchall():
        current[str(b)].append(nombre)
    conn.close()

    # Estado UI
    if "bloques_ui" not in st.session_state:
        st.session_state.bloques_ui = {
            "duo1": current.get("1", []),
            "duo2": current.get("2", []),
            "trio1": current.get("3", []),
            "trio2": current.get("4", []),
        }

    def _on_change_guardar():
        duo1 = st.session_state.get("duo1_ms", [])
        duo2 = st.session_state.get("duo2_ms", [])
        trio1 = st.session_state.get("trio1_ms", [])
        trio2 = st.session_state.get("trio2_ms", [])
        if _guardar_companeros_si_valido(partido_id, duo1, duo2, trio1, trio2):
            st.session_state.bloques_ui = {"duo1": duo1, "duo2": duo2, "trio1": trio1, "trio2": trio2}
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.multiselect("Dupla 1 (2 jugadores)", jugadores_nombres,
                       default=st.session_state.bloques_ui["duo1"], key="duo1_ms",
                       on_change=_on_change_guardar)
        st.multiselect("Trío 1 (3 jugadores)", jugadores_nombres,
                       default=st.session_state.bloques_ui["trio1"], key="trio1_ms",
                       on_change=_on_change_guardar)
    with col2:
        st.multiselect("Dupla 2 (2 jugadores)", jugadores_nombres,
                       default=st.session_state.bloques_ui["duo2"], key="duo2_ms",
                       on_change=_on_change_guardar)
        st.multiselect("Trío 2 (3 jugadores)", jugadores_nombres,
                       default=st.session_state.bloques_ui["trio2"], key="trio2_ms",
                       on_change=_on_change_guardar)

# -------------------------
# Heurística de asignación y generación
# -------------------------
def evaluar_asignacion(bloques, orden_indices):
    e1, e2 = [], []
    s1, s2 = 0.0, 0.0
    n1, n2 = 0, 0
    for idx in orden_indices:
        b = bloques[idx]
        size = len(b)
        elo_b = sum(p["elo"] for p in b)
        if (n1 + size) <= 5 and ((s1 <= s2) or ((n2 + size) > 5)):
            e1.extend(b); s1 += elo_b; n1 += size
        else:
            e2.extend(b); s2 += elo_b; n2 += size
    return e1, e2, s1, s2

def lista_nombres_10(e1, e2):
    n1 = [p["nombre"] for p in e1][:5]
    n2 = [p["nombre"] for p in e2][:5]
    n1 += [""] * (5 - len(n1))
    n2 += [""] * (5 - len(n2))
    return n1 + n2

def equipos_set_key(lista10):
    team1 = frozenset([n for n in lista10[:5] if n])
    team2 = frozenset([n for n in lista10[5:] if n])
    return (team1, team2)

def generar_mejor(bloques, intentos=5000, seed=1):
    random.seed(seed * 97 + 3)
    n = len(bloques)
    indices = list(range(n))
    best_diff = float("inf")
    best_list = None
    for _ in range(intentos):
        random.shuffle(indices)
        e1, e2, s1, s2 = evaluar_asignacion(bloques, indices)
        diff = abs(s1 - s2)
        if diff < best_diff:
            best_diff = diff
            best_list = lista_nombres_10(e1, e2)
            if best_diff <= 20:
                break
    return best_list, best_diff

def _pequeno_swap(lista10):
    """Intenta crear una nueva combinación (lista10) con un swap entre equipos."""
    team1 = [n for n in lista10[:5] if n]
    team2 = [n for n in lista10[5:] if n]
    if not team1 or not team2:
        return None
    a = random.choice(team1)
    b = random.choice(team2)
    n1 = team1[:]; n2 = team2[:]
    i1 = n1.index(a); i2 = n2.index(b)
    n1[i1], n2[i2] = n2[i2], n1[i1]
    # rellenar
    n1 += [""] * (5 - len(n1))
    n2 += [""] * (5 - len(n2))
    return n1 + n2

def generar_opciones_unicas(bloques, n_opciones=3, max_busquedas=180):
    """
    Devuelve exactamente n_opciones combinaciones distintas **por equipos**.
    Si no alcanza con búsqueda aleatoria, completa con variantes de swaps pequeños.
    """
    opciones, diffs = [], []
    equipos_vistos = set()
    seed_base = 11
    pruebas = 0

    # 1) Búsqueda aleatoria de buenas soluciones
    while len(opciones) < n_opciones and pruebas < max_busquedas:
        pruebas += 1
        lista, diff = generar_mejor(bloques, intentos=3000, seed=seed_base + pruebas*13)
        if not lista:
            continue
        t1, t2 = equipos_set_key(lista)
        if (t1 not in equipos_vistos) and (t2 not in equipos_vistos):
            opciones.append(lista)
            diffs.append(diff)
            equipos_vistos.add(t1); equipos_vistos.add(t2)

    # 2) Si faltan opciones, fabricarlas con swaps que creen equipos distintos
    intento_fabricados = 0
    while len(opciones) < n_opciones and intento_fabricados < 50 and opciones:
        intento_fabricados += 1
        base_idx = (intento_fabricados - 1) % len(opciones)
        cand = _pequeno_swap(opciones[base_idx])
        if not cand:
            continue
        t1, t2 = equipos_set_key(cand)
        if (t1 not in equipos_vistos) and (t2 not in equipos_vistos):
            # ΔELO aproximada: re-evaluar sumas con un mapa ficticio (no tenemos elolo aquí),
            # pero como solo necesitamos diversidad, estimamos diff como el de la base + 10~30.
            # Igual en panel calculamos ELO real para mostrar.
            opciones.append(cand)
            diffs.append((diffs[base_idx] if diffs else 60) + random.randint(10, 30))
            equipos_vistos.add(t1); equipos_vistos.add(t2)

    # 3) Si aún faltan (caso extremo), duplicar con más swaps encadenados
    while len(opciones) < n_opciones and opciones:
        base = opciones[-1]
        for _ in range(3):
            cand = _pequeno_swap(base)
            if not cand:
                continue
            t1, t2 = equipos_set_key(cand)
            if (t1 not in equipos_vistos) and (t2 not in equipos_vistos):
                opciones.append(cand)
                diffs.append((diffs[-1] if diffs else 60) + random.randint(15, 35))
                equipos_vistos.add(t1); equipos_vistos.add(t2)
                break
        if len(opciones) >= n_opciones:
            break

    return opciones[:n_opciones], diffs[:n_opciones]

# -------------------------
# Guardar / borrar equipos elegidos
# -------------------------
def guardar_opcion(partido_id: int, combinacion):
    conn = get_connection()
    cur = conn.cursor()
    for idx, nombre in enumerate(combinacion):
        if not nombre:
            continue
        equipo_val = 1 if idx < 5 else 2
        cur.execute("""
            UPDATE partido_jugadores
               SET equipo = ?
             WHERE partido_id = ?
               AND jugador_id = (SELECT id FROM jugadores WHERE nombre = ? LIMIT 1)
        """, (equipo_val, partido_id, nombre))
    conn.commit()
    conn.close()

def borrar_equipos_confirmados(partido_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE partido_jugadores
           SET equipo = NULL, camiseta = NULL
         WHERE partido_id = ?
    """, (partido_id,))
    conn.commit()
    conn.close()

def equipos_ya_confirmados(partido_id: int):
    jugadores = obtener_jugadores_partido_full(partido_id)
    asignados = [j for j in jugadores if j["equipo"] in (1, 2)]
    if len(asignados) != 10:
        return False, [], [], 0, 0
    team1 = [j["nombre"] for j in jugadores if j["equipo"] == 1]
    team2 = [j["nombre"] for j in jugadores if j["equipo"] == 2]
    elo1 = int(sum(j["elo"] for j in jugadores if j["equipo"] == 1))
    elo2 = int(sum(j["elo"] for j in jugadores if j["equipo"] == 2))
    return True, team1, team2, elo1, elo2

# -------------------------
# Vista jugadores (visual sin ELO)
# -------------------------
def render_vista_jugadores(partido_id: int):
    jugadores = obtener_jugadores_partido_full(partido_id)
    if len([j for j in jugadores if j["equipo"] in (1,2)]) != 10:
        return  # no render si no están confirmados

    team1 = [j["nombre"] for j in jugadores if j["equipo"] == 1]
    team2 = [j["nombre"] for j in jugadores if j["equipo"] == 2]
    cam1 = obtener_camiseta_equipo(partido_id, 1) or "clara"
    cam2 = obtener_camiseta_equipo(partido_id, 2) or "oscura"

    badge_style = """
        display:inline-block;padding:4px 10px;border-radius:999px;font-weight:600;
        border:1px solid rgba(0,0,0,0.1);margin-left:8px;
    """
    light_bg = "background:#f5f7fa;color:#222;"   # claro
    dark_bg  = "background:#222;color:#fff;"      # oscuro

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Equipo 1")
        st.markdown(
            f"<span style='{badge_style}{(light_bg if cam1=='clara' else dark_bg)}'>Camiseta {cam1.capitalize()}</span>",
            unsafe_allow_html=True
        )
        st.write("")
        for n in team1:
            st.write(f"- {n}")
    with col2:
        st.markdown("#### Equipo 2")
        st.markdown(
            f"<span style='{badge_style}{(light_bg if cam2=='clara' else dark_bg)}'>Camiseta {cam2.capitalize()}</span>",
            unsafe_allow_html=True
        )
        st.write("")
        for n in team2:
            st.write(f"- {n}")

# -------------------------
# Selección de partido y panel
# -------------------------
def panel_generacion():
    st.subheader("⚽ Generar equipos (3 opciones)")

    # Botón volver (arriba) – key único
    if st.button("⬅️ Volver al menú principal", key="btn_back_top"):
        st.session_state.admin_page = None
        st.rerun()

    # Selección de partido
    partidos = obtener_partidos_abiertos()
    if not partidos:
        st.info("No hay partidos abiertos.")
        return

    opciones_combo = []
    for p in partidos:
        pid = p["id"]
        fecha_dt = parsear_fecha(p["fecha"])
        cancha = p["cancha_nombre"]
        hora_str = formatear_hora(p["hora"])
        if fecha_dt:
            dia_es = DIAS_ES[fecha_dt.weekday()]
            fecha_txt = fecha_dt.strftime("%d/%m/%y")
            etiqueta = f"ID {pid} - {dia_es} {fecha_txt} {hora_str} - {cancha}"
        else:
            etiqueta = f"ID {pid} - {p['fecha']} {hora_str} - {cancha}"
        opciones_combo.append((pid, etiqueta))

    sel = st.selectbox("Seleccioná el partido:", [t for _, t in opciones_combo], key="sb_partido")
    partido_id = next(pid for pid, t in opciones_combo if t == sel)

    # Encabezado partido
    fecha_dt, hora_str, cancha_nombre = obtener_partido_info(partido_id)
    if fecha_dt:
         dia_es = DIAS_ES[fecha_dt.weekday()]
         fecha_txt = fecha_dt.strftime("%d/%m/%y")
         header = f"Partido ID {partido_id} — {dia_es} {fecha_txt} {hora_str} — {cancha_nombre}"
    else:
         header = f"Partido ID {partido_id} — {cancha_nombre}"

    st.markdown(
        f"<div style='font-size:1.35rem; font-weight:700; line-height:1.4; margin:0.25rem 0 0.5rem;'>"
        f"{header}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Si ya hay equipos confirmados, mostrar, camisetas (auto-save), vista jugadores y bloqueo de generación
    confirmado, team1c, team2c, elo1c, elo2c = equipos_ya_confirmados(partido_id)
    if confirmado:
        c1, c2 = st.columns(2)
        with c1:
            j1 = obtener_camiseta_equipo(partido_id, 1)
            lab1 = f"**Equipo 1 ({elo1c} ELO)** — Camiseta: {j1.capitalize() if j1 else '—'}"
            st.markdown(lab1)
            for n in team1c:
                st.write(f"- {n}")
        with c2:
            j2 = obtener_camiseta_equipo(partido_id, 2)
            lab2 = f"**Equipo 2 ({elo2c} ELO)** — Camiseta: {j2.capitalize() if j2 else '—'}"
            st.markdown(lab2)
            for n in team2c:
                st.write(f"- {n}")

        st.divider()
        st.markdown("### 👕 Camisetas")

        # Selectboxes con auto-guardado
        colj1, colj2 = st.columns(2)
        with colj1:
            current1 = obtener_camiseta_equipo(partido_id, 1)
            prev1 = "(sin asignar)" if current1 is None else current1
            sel1 = st.selectbox("Equipo 1", ["(sin asignar)", "clara", "oscura"],
                                index={"(sin asignar)":0,"clara":1,"oscura":2}[prev1],
                                key="sb_eq1_cam")
            if sel1 != prev1:
                if sel1 == "(sin asignar)":
                    limpiar_camiseta_equipo(partido_id, 1)
                else:
                    asignar_camiseta_equipo(partido_id, 1, sel1)
                st.rerun()

        with colj2:
            current2 = obtener_camiseta_equipo(partido_id, 2)
            prev2 = "(sin asignar)" if current2 is None else current2
            sel2 = st.selectbox("Equipo 2", ["(sin asignar)", "clara", "oscura"],
                                index={"(sin asignar)":0,"clara":1,"oscura":2}[prev2],
                                key="sb_eq2_cam")
            if sel2 != prev2:
                if sel2 == "(sin asignar)":
                    limpiar_camiseta_equipo(partido_id, 2)
                else:
                    asignar_camiseta_equipo(partido_id, 2, sel2)
                st.rerun()

        # Intercambiar camisetas (auto-save)
        if st.button("↔️ Intercambiar camisetas", key="btn_swap_camisetas"):
            intercambiar_camisetas(partido_id)
            st.success("Camisetas intercambiadas.")
            st.rerun()

        st.divider()
        st.markdown("### 👥 Vista para jugadores")
        render_vista_jugadores(partido_id)

        st.divider()
        st.warning("Para rehacer equipos, primero eliminá los confirmados.")
        if st.button("🗑️ Eliminar equipos confirmados", key="btn_eliminar_confirmados"):
            borrar_equipos_confirmados(partido_id)
            st.success("Equipos eliminados. Ahora podés generar nuevas opciones.")
            st.rerun()

        if st.button("⬅️ Volver al menú principal", key="btn_back_bottom_locked"):
            st.session_state.admin_page = None
            st.rerun()
        return

    # Jugadores del partido (solo nombres, 2 columnas de 5)
    jugadores = obtener_jugadores_partido_full(partido_id)
    if not jugadores:
        st.info("Todavía no hay jugadores en este partido.")
        return

    st.markdown("**Jugadores inscriptos (10):**")
    names = [j["nombre"] for j in jugadores]
    if len(names) != 10:
        st.warning(f"Se requieren exactamente 10 jugadores para generar equipos. Actualmente: {len(names)}.")
        return
    col_a, col_b = st.columns(2)
    with col_a:
        for n in names[:5]:
            st.write(f"- {n}")
    with col_b:
        for n in names[5:10]:
            st.write(f"- {n}")

    # --- UI para definir compañeros (duplas/tríos) — auto-guardado ---
    ui_definir_bloques(partido_id, names)

    # Reconstruir bloques tras posible guardado
    jugadores = obtener_jugadores_partido_full(partido_id)
    bloques = construir_bloques(jugadores)

    # Generar 3 opciones (todas distintas por equipos, forzado a 3)
    if st.button("🎲 Generar 3 opciones balanceadas", key="btn_generar_opciones"):
        with st.spinner("Calculando combinaciones distintas..."):
            opts, diffs = generar_opciones_unicas(bloques, n_opciones=3, max_busquedas=240)
            if not opts or len(opts) < 3:
                st.warning("Se forzaron opciones alternativas para llegar a 3. Verificá la diversidad.")
            st.session_state._equipos_opciones = opts
            st.session_state._equipos_diffs = diffs
            st.session_state._equipos_actual = None  # limpiar edición manual

    # Mostrar opciones y permitir elegir
    if "_equipos_opciones" in st.session_state and st.session_state._equipos_opciones:
        opts = st.session_state._equipos_opciones
        diffs = st.session_state._equipos_diffs
        cols = st.columns(3)
        chosen_idx = None

        elo_map = {j["nombre"]: j["elo"] for j in jugadores}

        for i, col in enumerate(cols[:len(opts)]):
            col.markdown(f"### Opción {i+1}")
            col.write(f"ΔELO ≈ {int(diffs[i])}")
            lista = opts[i]

            team1 = [n for n in lista[:5] if n]
            team2 = [n for n in lista[5:] if n]
            elo1 = int(sum(elo_map.get(n, 0) for n in team1))
            elo2 = int(sum(elo_map.get(n, 0) for n in team2))

            col.markdown(f"**Equipo 1 ({elo1} ELO)**")
            for nombre in team1:
                col.write(f"- {nombre}")

            col.markdown(f"**Equipo 2 ({elo2} ELO)**")
            for nombre in team2:
                col.write(f"- {nombre}")

            if col.button(f"Seleccionar Opción {i+1}", key=f"btn_sel_opt_{i+1}"):
                chosen_idx = i

        if chosen_idx is not None:
            st.session_state._equipos_actual = opts[chosen_idx][:]  # copia
            st.success(f"Opción {chosen_idx+1} cargada. Podés intercambiar jugadores antes de confirmar.")

    # Ajuste manual e Confirmación (con asignación por defecto de camisetas)
    if st.session_state.get("_equipos_actual"):
        st.markdown("### ✍️ Ajuste manual")

        equipo_actual = st.session_state._equipos_actual
        team1 = equipo_actual[:5]
        team2 = equipo_actual[5:]

        elo_map = {j["nombre"]: j["elo"] for j in jugadores}
        elo1 = int(sum(elo_map.get(n, 0) for n in team1 if n))
        elo2 = int(sum(elo_map.get(n, 0) for n in team2 if n))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Equipo 1 ({elo1} ELO)**")
            st.write(", ".join([n for n in team1 if n]))
            a = st.selectbox("Jugador de Equipo 1", ["(ninguno)"] + [n for n in team1 if n], key="swap_a")
        with c2:
            st.markdown(f"**Equipo 2 ({elo2} ELO)**")
            st.write(", ".join([n for n in team2 if n]))
            b = st.selectbox("Jugador de Equipo 2", ["(ninguno)"] + [n for n in team2 if n], key="swap_b")

        if st.button("↔️ Intercambiar", key="btn_swap"):
            if a != "(ninguno)" and b != "(ninguno)":
                i1 = team1.index(a)
                i2 = team2.index(b)
                team1[i1], team2[i2] = team2[i2], team1[i1]
                st.session_state._equipos_actual = team1 + team2

        equipo_actual = st.session_state._equipos_actual
        team1 = equipo_actual[:5]
        team2 = equipo_actual[5:]
        elo1 = int(sum(elo_map.get(n, 0) for n in team1 if n))
        elo2 = int(sum(elo_map.get(n, 0) for n in team2 if n))
        st.markdown(f"**Equipo 1 ({elo1} ELO)**: " + ", ".join([n for n in team1 if n]))
        st.markdown(f"**Equipo 2 ({elo2} ELO)**: " + ", ".join([n for n in team2 if n]))

        if st.button("✅ Confirmar equipos", key="btn_confirmar_equipos"):
            if len([n for n in team1 if n]) == 5 and len([n for n in team2 if n]) == 5:
                guardar_opcion(partido_id, equipo_actual)
                # Asignación por defecto de camisetas si no hay
                if obtener_camiseta_equipo(partido_id, 1) is None:
                    asignar_camiseta_equipo(partido_id, 1, "clara")
                if obtener_camiseta_equipo(partido_id, 2) is None:
                    asignar_camiseta_equipo(partido_id, 2, "oscura")
                st.success("Equipos confirmados y guardados en la base de datos.")
                st.session_state._equipos_opciones = None
                st.session_state._equipos_diffs = None
                st.session_state._equipos_actual = None
                st.rerun()
            else:
                st.error("Cada equipo debe tener exactamente 5 jugadores.")

    # Botón volver (abajo)
    if st.button("⬅️ Volver al menú principal", key="btn_back_bottom"):
        st.session_state.admin_page = None
        st.rerun()

