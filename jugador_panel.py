# jugador_panel.py
# Panel para usuarios con rol "jugador".
# Cambios clave:
# - Normalizo siempre: user -> dict
# - TODAS las lecturas de DB (fetchall/one) se convierten a dict antes de usarse
#   para evitar errores de sqlite3.Row sin .get

import streamlit as st
import sqlite3
from datetime import date
import matplotlib.pyplot as plt

# Si preferís centralizar, podés reemplazar por: from database import get_connection
def get_connection():
    conn = sqlite3.connect("elo_futbol.db")
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------
# Utilidades internas
# -------------------------

def _asdict_user(user):
    """Convierte sqlite3.Row a dict. Si ya es dict, lo devuelve igual."""
    try:
        if isinstance(user, dict):
            return user
        if hasattr(user, "keys"):
            return {k: user[k] for k in user.keys()}
        return dict(user)
    except Exception:
        return {"username": str(user), "rol": None, "jugador_id": None}

def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    try:
        if hasattr(row, "keys"):
            return {k: row[k] for k in row.keys()}
        return dict(row)
    except Exception:
        return row

def _rows_to_dicts(rows):
    return [_row_to_dict(r) for r in rows] if rows else []

def _today_str():
    return date.today().strftime("%Y-%m-%d")

def _ensure_flash_store():
    if "flash" not in st.session_state:
        st.session_state["flash"] = []

def _push_flash(msg, level="info"):
    _ensure_flash_store()
    st.session_state["flash"].append((level, msg))

def _render_flash():
    _ensure_flash_store()
    if st.session_state["flash"]:
        for level, msg in st.session_state["flash"]:
            {"success": st.success, "warning": st.warning,
             "error": st.error}.get(level, st.info)(msg)
        st.session_state["flash"].clear()

def _nombre_jugador(jugador_id):
    if jugador_id is None:
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nombre FROM jugadores WHERE id = ?", (jugador_id,))
        row = _row_to_dict(cur.fetchone())
        return row["nombre"] if row else None

def _nombre_cancha(cancha_id):
    if cancha_id is None:
        return "Sin asignar"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT nombre FROM canchas WHERE id = ?", (cancha_id,))
        row = _row_to_dict(cur.fetchone())
        return row["nombre"] if row else "Sin asignar"

def _jugadores_en_partido(partido_id):
    """Devuelve lista de dicts: [{jugador_id, confirmado_por_jugador, nombre}, ...]"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT pj.jugador_id, pj.confirmado_por_jugador, j.nombre
            FROM partido_jugadores pj
            JOIN jugadores j ON j.id = pj.jugador_id
            WHERE pj.partido_id = ?
            ORDER BY j.nombre ASC
        """, (partido_id,))
        return _rows_to_dicts(cur.fetchall())

def _existe_inscripcion(partido_id, jugador_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1
            FROM partido_jugadores
            WHERE partido_id = ? AND jugador_id = ?
            LIMIT 1
        """, (partido_id, jugador_id))
        return cur.fetchone() is not None

def _insertar_confirmacion(partido_id, jugador_id):
    if _existe_inscripcion(partido_id, jugador_id):
        return False, "Ya estabas inscripto en este partido."
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO partido_jugadores (partido_id, jugador_id, confirmado_por_jugador, camiseta)
            VALUES (?, ?, 1, 'clara')
        """, (partido_id, jugador_id))
        conn.commit()
    return True, "Confirmaste tu asistencia 🟢"

def _cancelar_confirmacion(partido_id, jugador_id):
    if not _existe_inscripcion(partido_id, jugador_id):
        return False, "No estabas inscripto en este partido."
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM partido_jugadores WHERE partido_id = ? AND jugador_id = ?",
                    (partido_id, jugador_id))
        conn.commit()
    return True, "Cancelaste tu asistencia."

def _partidos_abiertos_o_futuros():
    """Lista de dicts [{id, fecha, cancha_id, tipo}, ...]"""
    hoy = _today_str()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, fecha, cancha_id, tipo
            FROM partidos
            WHERE tipo = 'abierto' AND fecha >= ?
            ORDER BY fecha ASC, id ASC
        """, (hoy,))
        abiertos = _rows_to_dicts(cur.fetchall())
        if abiertos:
            return abiertos
        cur.execute("""
            SELECT id, fecha, cancha_id, tipo
            FROM partidos
            WHERE fecha >= ?
            ORDER BY fecha ASC, id ASC
        """, (hoy,))
        return _rows_to_dicts(cur.fetchall())

def _stats_por_sql(jugador_id):
    """Devuelve dict con jugados, w, d, l, winrate y lista 'partidos' (dicts)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.fecha, p.cancha_id, p.ganador, p.diferencia_gol
            FROM partidos p
            JOIN partido_jugadores pj ON pj.partido_id = p.id
            WHERE pj.jugador_id = ?
            ORDER BY p.fecha ASC, p.id ASC
        """, (jugador_id,))
        rows = _rows_to_dicts(cur.fetchall())

        jugados = len(rows)
        w = d = l = 0

        for r in rows:
            pid = r["id"]
            ganador = r["ganador"]  # 0=empate, 1/2=ganador, None=pte
            if ganador is None:
                continue
            cur.execute("""
                SELECT equipo
                FROM partido_jugadores
                WHERE partido_id = ? AND jugador_id = ?
                LIMIT 1
            """, (pid, jugador_id))
            eq_row = _row_to_dict(cur.fetchone())
            equipo = eq_row["equipo"] if eq_row and eq_row["equipo"] in (1, 2) else None
            if equipo is None:
                continue
            if ganador == 0:
                d += 1
            elif ganador == equipo:
                w += 1
            else:
                l += 1

        winrate = (w / (w + l)) * 100 if (w + l) > 0 else 0.0
        return {"jugados": jugados, "w": w, "d": d, "l": l, "winrate": winrate, "partidos": rows}

def _elo_history_sql(jugador_id):
    """Lista de dicts [{fecha, elo_antes, elo_despues}, ...]"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.fecha AS fecha, h.elo_antes, h.elo_despues
            FROM historial_elo h
            JOIN partidos p ON p.id = h.partido_id
            WHERE h.jugador_id = ?
            ORDER BY p.fecha ASC, p.id ASC
        """, (jugador_id,))
        return _rows_to_dicts(cur.fetchall())

# -------------------------
# Vistas del panel jugador
# -------------------------

def panel_menu_jugador(user):
    # Normalizar user para evitar Row
    user = _asdict_user(user)

    if "jugador_page" not in st.session_state:
        st.session_state["jugador_page"] = "menu"

    _render_flash()

    jugador_id = user.get("jugador_id")
    username = user.get("username") or "jugador"
    nombre_vinculado = _nombre_jugador(jugador_id)
    nombre_para_saludo = nombre_vinculado or username

    st.header(f"Bienvenido, {nombre_para_saludo} 👋")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ver partidos disponibles ⚽", key="btn_partidos_disponibles"):
            st.session_state["jugador_page"] = "partidos"
            st.rerun()
    with c2:
        if st.button("Ver mis estadísticas 📊", key="btn_mis_stats"):
            st.session_state["jugador_page"] = "stats"
            st.rerun()

def panel_partidos_disponibles(user):
    _render_flash()

    user = _asdict_user(user)
    jugador_id = user.get("jugador_id")
    if not jugador_id:
        st.warning("Tu usuario no está vinculado a ningún jugador. Pedile al admin que te vincule para poder confirmar asistencia y ver estadísticas.")
        if st.button("⬅️ Volver", key="back_sin_vinculo"):
            st.session_state["jugador_page"] = "menu"
            st.rerun()
        return

    st.subheader("Partidos disponibles")
    partidos = _partidos_abiertos_o_futuros()

    if not partidos:
        st.info("No hay partidos abiertos ni futuros por el momento.")
    else:
        for p in partidos:
            partido_id = p["id"]
            fecha = p["fecha"]
            cancha_name = _nombre_cancha(p["cancha_id"])
            tipo = p["tipo"]
            with st.expander(f"{fecha} • {cancha_name} • ({tipo})", expanded=False):
                jugadores = _jugadores_en_partido(partido_id)
                if jugadores:
                    st.write("**Inscripciones:**")
                    for j in jugadores:
                        icon = "🟢" if j["confirmado_por_jugador"] == 1 else "🔵"
                        st.write(f"{icon} {j['nombre']}")
                else:
                    st.write("_Aún no hay inscriptos._")

                yo_estoy = any(j["jugador_id"] == jugador_id for j in jugadores)
                yo_confirmado = any((j["jugador_id"] == jugador_id and j["confirmado_por_jugador"] == 1) for j in jugadores)

                c1, c2 = st.columns(2)
                with c1:
                    if not yo_estoy:
                        if st.button("Confirmar asistencia", key=f"confirm_{partido_id}"):
                            ok, msg = _insertar_confirmacion(partido_id, jugador_id)
                            _push_flash(msg, "success" if ok else "warning")
                            st.rerun()
                    else:
                        if yo_confirmado:
                            st.success("Estado: confirmado por vos (🟢)")
                        else:
                            st.info("Estado: agregado por admin (🔵)")

                with c2:
                    if yo_estoy:
                        if st.button("Cancelar asistencia", key=f"cancel_{partido_id}"):
                            ok, msg = _cancelar_confirmacion(partido_id, jugador_id)
                            _push_flash(msg, "success" if ok else "warning")
                            st.rerun()

    st.divider()
    if st.button("⬅️ Volver", key="back_partidos"):
        st.session_state["jugador_page"] = "menu"
        st.rerun()

def panel_mis_estadisticas(user):
    _render_flash()

    user = _asdict_user(user)
    jugador_id = user.get("jugador_id")
    if not jugador_id:
        st.warning("Tu usuario no está vinculado a ningún jugador. Pedile al admin que te vincule para ver tus estadísticas.")
        if st.button("⬅️ Volver", key="back_stats_sin_vinculo"):
            st.session_state["jugador_page"] = "menu"
            st.rerun()
        return

    st.subheader("Mis estadísticas")

    stats = _stats_por_sql(jugador_id)
    jugados, w, d, l, winrate = stats["jugados"], stats["w"], stats["d"], stats["l"], stats["winrate"]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Jugados", jugados)
    m2.metric("Victorias", w)
    m3.metric("Empates", d)
    m4.metric("Derrotas", l)
    m5.metric("Winrate %", f"{winrate:.1f}")

    st.write("")
    st.write("### Partidos (con resultado si está cargado)")
    if stats["partidos"]:
        for r in stats["partidos"]:
            fecha = r["fecha"]
            cancha = _nombre_cancha(r["cancha_id"])
            ganador = r["ganador"]
            dif = r["diferencia_gol"]
            linea = f"• {fecha} • {cancha}"
            if ganador is None:
                linea += " — resultado: _pendiente_"
            else:
                res = "empate" if ganador == 0 else f"ganador equipo {ganador}"
                suf = f" (dif: {dif})" if dif is not None else ""
                linea += f" — resultado: **{res}**{suf}"
            st.write(linea)
    else:
        st.info("No se encontraron partidos asociados a tu jugador.")

    st.write("")
    st.write("### Evolución de ELO")
    elo_hist = _elo_history_sql(jugador_id)
    if elo_hist:
        fechas = [row["fecha"] for row in elo_hist]
        elos = [row["elo_despues"] if row["elo_despues"] is not None else row["elo_antes"] for row in elo_hist]
        fig = plt.figure()
        plt.plot(fechas, elos, marker="o")
        plt.xticks(rotation=45, ha="right")
        plt.xlabel("Fecha")
        plt.ylabel("ELO")
        plt.title("Evolución del ELO")
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("Aún no hay historial de ELO para graficar.")

    st.divider()
    if st.button("⬅️ Volver", key="back_stats"):
        st.session_state["jugador_page"] = "menu"
        st.rerun()
