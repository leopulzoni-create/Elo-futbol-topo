import streamlit as st
import sqlite3
from datetime import datetime, date, time as dtime

DB_NAME = "elo_futbol.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- Helpers de fecha/hora y texto ----------
_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def weekday_es(yyyy_mm_dd: str) -> str:
    """Devuelve el día de la semana en español para una fecha 'YYYY-MM-DD'."""
    try:
        dt = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
        return _DIAS_ES[dt.weekday()]
    except Exception:
        return ""

def time_int_from_time(t: dtime) -> int:
    """Convierte time(19,00) -> 1900 (INTEGER)."""
    return t.hour * 100 + t.minute

def time_from_int_str(hhmm_int: int) -> dtime:
    """Convierte 1900 -> time(19,0). Soporta None devolviendo 19:00 por defecto."""
    if hhmm_int is None:
        return dtime(19, 0)
    hh = int(hhmm_int) // 100
    mm = int(hhmm_int) % 100
    try:
        return dtime(hh, mm)
    except Exception:
        return dtime(19, 0)

def time_label(hhmm_int: int) -> str:
    """Convierte 1900 -> '19:00'."""
    if hhmm_int is None:
        return "Sin hora"
    hh = int(hhmm_int) // 100
    mm = int(hhmm_int) % 100
    return f"{hh:02d}:{mm:02d}"

# ---------- Paleta de colores para cada partido ----------
COLORES = [
    "#1e293b",  # slate-800
    "#3b0764",  # purple-950
    "#164e63",  # cyan-900
    "#4a044e",  # fuchsia-950
    "#0b3a3d",  # teal deep
    "#2b2c58",  # indigo deep
    "#3c1c4f",  # purple deep
    "#052e2e",  # teal-950
]

def color_por_partido(pid: int) -> str:
    return COLORES[pid % len(COLORES)]

# ---------- UI principal ----------
def panel_creacion():
    st.subheader("Gestión de partidos ⚽")

    conn = get_connection()
    cur = conn.cursor()

    # --- CREAR PARTIDO ---
    st.write("### Crear nuevo partido")
    fecha = st.date_input("Fecha del partido", value=date.today())
    hora = st.time_input("Hora del partido", value=dtime(hour=19, minute=0))

    # Canchas
    cur.execute("SELECT id, nombre FROM canchas")
    canchas = cur.fetchall()
    opciones_canchas = ["Sin asignar"] + [f"{c['id']} - {c['nombre']}" for c in canchas]
    cancha_sel = st.selectbox("Seleccionar cancha (opcional)", opciones_canchas)
    cancha_id = int(cancha_sel.split(" - ")[0]) if cancha_sel != "Sin asignar" else None

    if st.button("Crear partido"):
        cur.execute(
            "INSERT INTO partidos (fecha, cancha_id, es_oficial, tipo, hora) VALUES (?, ?, 0, 'abierto', ?)",
            (fecha.strftime("%Y-%m-%d"), cancha_id, time_int_from_time(hora))
        )
        conn.commit()
        st.success("Partido creado ✅")
        st.rerun()

    # --- PARTIDOS EXISTENTES ---
    st.write("### Partidos existentes (pendientes)")
    cur.execute("""
        SELECT id, fecha, cancha_id, hora
        FROM partidos
        WHERE tipo = 'abierto'
          AND ganador IS NULL
          AND diferencia_gol IS NULL
        ORDER BY fecha DESC, id DESC
    """)
    partidos = cur.fetchall()

    for p in partidos:
        pid = p["id"]
        color = color_por_partido(pid)

        # Cancha
        cancha = "Sin asignar"
        if p["cancha_id"]:
            cur.execute("SELECT nombre FROM canchas WHERE id = ?", (p["cancha_id"],))
            cancha_row = cur.fetchone()
            if cancha_row:
                cancha = cancha_row["nombre"]

        # Día (ES) + hora
        dia_es = weekday_es(p["fecha"])
        hora_lbl = time_label(p["hora"])

        # Barra superior con tipografía más grande
        st.markdown(
            f"""
            <div style="
                background:{color};
                padding:12px 14px;
                border-radius:10px;
                margin-top:12px;
                font-size:1.25rem;
                font-weight:700;
                color:#ffffff;
            ">
                ID {pid} | Fecha: {p['fecha']} ({dia_es}) | Cancha: {cancha} | Hora: {hora_lbl}
            </div>
            """,
            unsafe_allow_html=True
        )

        # --- GESTIONAR JUGADORES ---
        with st.expander(f"Gestionar jugadores Partido {pid}"):
            # Contenedor con mismo color dentro del expander
            st.markdown(
                f"""<div style="background:{color};color:#ffffff;padding:12px;border-radius:10px;">""",
                unsafe_allow_html=True
            )

            # Traer jugadores disponibles (activos primero)
            cur.execute("SELECT id, nombre FROM jugadores ORDER BY estado DESC, nombre ASC")
            jugadores = cur.fetchall()

            # Traer jugadores ya asignados al partido
            cur.execute(
                "SELECT pj.jugador_id, pj.confirmado_por_jugador, j.nombre "
                "FROM partido_jugadores pj "
                "JOIN jugadores j ON j.id = pj.jugador_id "
                "WHERE pj.partido_id = ?", (pid,)
            )
            jugadores_partido = cur.fetchall()
            ids_asignados = [j["jugador_id"] for j in jugadores_partido]

            # Contadores y cupo
            total_actual = len(jugadores_partido)
            cupo_total = 10
            cupo_restante = max(0, cupo_total - total_actual)

            # --- Jugadores asignados en dos columnas ---
            st.write("### Jugadores asignados")
            cols = st.columns(2)
            for i, jp in enumerate(jugadores_partido):
                icono = "🟢" if jp["confirmado_por_jugador"] else "🔵"
                col = cols[i % 2]
                with col:
                    st.write(f"{icono} {jp['nombre']}")
                    if st.button(
                        f"Quitar {jp['nombre']} del partido {pid}",
                        key=f"quitar_{pid}_{jp['jugador_id']}"
                    ):
                        cur.execute(
                            "DELETE FROM partido_jugadores WHERE partido_id = ? AND jugador_id = ?",
                            (pid, jp["jugador_id"])
                        )
                        conn.commit()
                        st.rerun()

            # --- Agregar jugadores con contador X/10 y tope ---
            st.write(f"### Agregar jugadores al partido ({total_actual}/{cupo_total})")
            if cupo_restante <= 0:
                st.info("Cupo completo: ya hay 10/10 jugadores en este partido.")

            jugadores_dict = {j["nombre"]: j["id"] for j in jugadores if j["id"] not in ids_asignados}

            seleccionados = st.multiselect(
                "Seleccioná hasta completar el cupo",
                options=list(jugadores_dict.keys()),
                key=f"multiselect_{pid}"
            )

            if len(seleccionados) > cupo_restante:
                st.warning(f"Solo podés agregar {cupo_restante} jugador(es) más para no superar {cupo_total}/10.")
                seleccionados = seleccionados[:cupo_restante]

            if st.button(
                f"Agregar jugadores al partido {pid}",
                key=f"agregar_{pid}",
                disabled=(cupo_restante <= 0 or len(seleccionados) == 0)
            ):
                for nombre in seleccionados:
                    jugador_id = jugadores_dict[nombre]
                    cur.execute(
                        "INSERT INTO partido_jugadores (partido_id, jugador_id, confirmado_por_jugador) VALUES (?, ?, 0)",
                        (pid, jugador_id)
                    )
                conn.commit()
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)  # cierre del contenedor coloreado

        # --- EDITAR PARTIDO (fecha, cancha, hora) ---
        with st.expander(f"Editar partido {pid}"):
            st.markdown(
                f"""<div style="background:{color};color:#ffffff;padding:12px;border-radius:10px;">""",
                unsafe_allow_html=True
            )

            # Valores actuales
            fecha_actual = datetime.strptime(p["fecha"], "%Y-%m-%d").date()
            hora_actual = time_from_int_str(p["hora"])

            # Select de cancha con opción "Sin asignar"
            opciones_canchas_edit = ["Sin asignar"] + [f"{c['id']} - {c['nombre']}" for c in canchas]
            cancha_actual_label = "Sin asignar"
            if p["cancha_id"]:
                for c in canchas:
                    if c["id"] == p["cancha_id"]:
                        cancha_actual_label = f"{c['id']} - {c['nombre']}"
                        break
            idx_pre = opciones_canchas_edit.index(cancha_actual_label) if cancha_actual_label in opciones_canchas_edit else 0

            nueva_fecha = st.date_input("Nueva fecha", value=fecha_actual, key=f"fecha_edit_{pid}")
            nueva_hora = st.time_input("Nueva hora", value=hora_actual, key=f"hora_edit_{pid}")
            nueva_cancha_sel = st.selectbox(
                "Nueva cancha (opcional)", opciones_canchas_edit, index=idx_pre, key=f"cancha_edit_{pid}"
            )
            nueva_cancha_id = int(nueva_cancha_sel.split(" - ")[0]) if nueva_cancha_sel != "Sin asignar" else None

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Guardar cambios", key=f"guardar_edit_{pid}"):
                    cur.execute(
                        "UPDATE partidos SET fecha = ?, cancha_id = ?, hora = ? WHERE id = ?",
                        (nueva_fecha.strftime("%Y-%m-%d"), nueva_cancha_id, time_int_from_time(nueva_hora), pid)
                    )
                    conn.commit()
                    st.success(f"Partido {pid} actualizado ✅")
                    st.rerun()
            with c2:
                st.caption("Los cambios impactan inmediatamente en la vista de jugadores/administrador.")

            st.markdown("</div>", unsafe_allow_html=True)

        # --- ELIMINAR PARTIDO ---
        if st.button(f"Eliminar partido {pid}", key=f"eliminar_{pid}"):
            cur.execute("DELETE FROM partido_jugadores WHERE partido_id = ?", (pid,))
            cur.execute("DELETE FROM partidos WHERE id = ?", (pid,))
            conn.commit()
            st.success(f"Partido {pid} eliminado ❌")
            st.rerun()

    # --- BOTÓN VOLVER AL MENÚ PRINCIPAL ---
    if st.button("⬅️ Volver al menú principal", key="volver_menu"):
        st.session_state.admin_page = None
        st.rerun()

    conn.close()
