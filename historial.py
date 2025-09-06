# historial.py (Py3.8-friendly)
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).with_name("elo_futbol.db")

def get_conn():
    return sqlite3.connect(str(DB_PATH))

def read_sql_df(query: str, params: tuple = ()):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(query, conn, params=params)

# ✅ Incluir empates (ganador NULL) y cualquier partido con resultado cargado
SQL_PARTIDOS_CON_RESULTADO = """
SELECT
  p.id AS partido_id,
  p.fecha,
  p.cancha_id,
  c.nombre AS cancha_nombre,
  p.ganador,
  p.diferencia_gol,
  p.es_oficial
FROM partidos p
LEFT JOIN canchas c ON c.id = p.cancha_id
WHERE p.ganador IS NOT NULL OR p.diferencia_gol IS NOT NULL
ORDER BY datetime(p.fecha) DESC, p.id DESC;
"""

SQL_JUGADORES_DE_PARTIDO = """
SELECT pj.partido_id, pj.equipo, pj.camiseta, j.id AS jugador_id, j.nombre AS jugador_nombre
FROM partido_jugadores pj
JOIN jugadores j ON j.id = pj.jugador_id
WHERE pj.partido_id = ?
ORDER BY pj.equipo ASC, j.nombre ASC;
"""

SQL_HISTORIAL_ELO_BASE = """
SELECT
  he.id               AS historial_id,
  he.fecha            AS fecha,
  he.jugador_id       AS jugador_id,
  j.nombre            AS jugador_nombre,
  he.partido_id       AS partido_id,
  he.elo_antes        AS elo_antes,
  he.elo_despues      AS elo_despues
FROM historial_elo he
JOIN jugadores j ON j.id = he.jugador_id
"""

def _badge(texto: str, background: str, color: str = "white"):
    st.markdown(
        """
        <span style="
            display:inline-block;
            padding:2px 8px;
            border-radius:999px;
            background:%s;
            color:%s;
            font-size:0.8rem;
            margin-left:6px;">
            %s
        </span>
        """ % (background, color, texto),
        unsafe_allow_html=True,
    )

def _camiseta_emoji(camiseta: Optional[str]) -> str:
    if not camiseta:
        return "👕"
    c = str(camiseta).strip().lower()
    if c.startswith("clara"):
        return "⚪"
    if c.startswith("osc"):
        return "⬛"
    return "👕"

def _equipo_label(n: int) -> str:
    return "Equipo 1" if int(n) == 1 else "Equipo 2"

def _ganador_texto_simple(g):
    if g is None:
        return "—"
    try:
        gi = int(g)
    except Exception:
        return str(g)
    return {1: "Ganó Equipo 1", 2: "Ganó Equipo 2", 0: "Empate"}.get(gi, str(g))

def _oficial_texto(es_oficial):
    return "Oficial" if es_oficial else "Amistoso"

def _oficial_color(es_oficial):
    return "#2563eb" if es_oficial else "#64748b"

def _delta_str(antes, despues):
    try:
        d = float(despues) - float(antes)
    except Exception:
        return ""
    signo = "+" if d >= 0 else ""
    return "%s%.1f" % (signo, d)

# ---------- TAB: PARTIDOS ----------
def _render_tab_partidos():
    st.subheader("📅 Partidos con resultado")
    df_p = read_sql_df(SQL_PARTIDOS_CON_RESULTADO)

    if df_p.empty:
        st.info("Aún no hay partidos con resultado cargado.")
        return

    # 🔑 keys únicas
    ordenar_desc = st.toggle("Ordenar por fecha descendente", value=True, key="hist_partidos_toggle_order")

    # Filtros: ID y FECHA (texto)
    col_busq1, col_busq2 = st.columns([1, 1])
    with col_busq1:
        filtro_id = st.text_input("Buscar por ID de partido", value="", key="hist_partidos_filtro_id").strip()
    with col_busq2:
        filtro_fecha = st.text_input("Buscar por fecha (YYYY-MM-DD)", value="", key="hist_partidos_filtro_fecha").strip()

    if filtro_id:
        df_p = df_p[df_p["partido_id"].astype(str).str.contains(filtro_id)]
    if filtro_fecha:
        df_p = df_p[df_p["fecha"].astype(str).str.contains(filtro_fecha)]

    if not ordenar_desc:
        df_p = df_p.sort_values(by=["fecha", "partido_id"], ascending=[True, True]).reset_index(drop=True)

    if df_p.empty:
        st.warning("No se encontraron partidos con esos filtros.")
        return

    for _, row in df_p.iterrows():
        partido_id = int(row["partido_id"])
        fecha = row["fecha"]
        cancha = row["cancha_nombre"] or "—"
        ganador = row["ganador"]
        dif = row["diferencia_gol"]
        es_ofi = bool(row["es_oficial"])

        with st.expander("Partido #%d — %s — %s" % (partido_id, fecha, cancha)):
            _badge(_oficial_texto(es_ofi), _oficial_color(es_ofi))
            if dif is not None:
                _badge("Diff: %d" % int(dif), "#334155")

            # Mostrar 'Empate' si ganador es NULL y diff = 0
            if ganador is None and (dif == 0 or str(dif) == "0"):
                resultado_txt = "Empate"
            else:
                resultado_txt = _ganador_texto_simple(ganador)

            st.markdown("**Resultado:** %s" % resultado_txt)

            # Jugadores por equipo
            df_j = read_sql_df(SQL_JUGADORES_DE_PARTIDO, (partido_id,))
            if df_j.empty:
                st.caption("Sin jugadores asignados.")
                continue

            for equipo_n in (1, 2):
                sub = df_j[df_j["equipo"] == equipo_n].copy()
                if sub.empty:
                    st.write("**%s:** (sin datos)" % _equipo_label(equipo_n))
                    continue

                camiseta_repr = sub["camiseta"].mode().iloc[0] if sub["camiseta"].notna().any() else None
                camiseta_icon = _camiseta_emoji(camiseta_repr)
                jugadores_list = " · ".join(sub["jugador_nombre"].tolist())
                st.write("**%s %s:** %s" % (_equipo_label(equipo_n), camiseta_icon, jugadores_list))

# ---------- TAB: HISTORIAL ELO ----------
def _render_tab_historial_elo():
    st.subheader("📈 Historial de ELO")

    df = read_sql_df(SQL_HISTORIAL_ELO_BASE + " ORDER BY datetime(fecha) DESC, historial_id DESC")
    if df.empty:
        st.info("Aún no hay cambios de ELO registrados.")
        return

    # 🔑 keys únicas en todos los widgets
    with st.container():
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            jugadores_unicos = ["(Todos)"] + sorted(df["jugador_nombre"].dropna().unique().tolist())
            jug_sel = st.selectbox("Filtrar por jugador", jugadores_unicos, index=0, key="hist_elo_sel_jugador")
        with col2:
            id_part = st.text_input("Filtrar por ID de partido", value="", key="hist_elo_filtro_partido")
        with col3:
            ordenar_desc = st.toggle("Ordenar por fecha descendente", value=True, key="hist_elo_toggle_order")

    if jug_sel != "(Todos)":
        df = df[df["jugador_nombre"] == jug_sel]

    if id_part.strip():
        df = df[df["partido_id"].astype(str).str.contains(id_part.strip())]

    if df.empty:
        st.warning("No hay resultados con esos filtros.")
        return

    df = df.copy()
    df["ΔELO"] = df.apply(lambda r: _delta_str(r["elo_antes"], r["elo_despues"]), axis=1)
    cols_orden = ["fecha", "jugador_nombre", "partido_id", "elo_antes", "elo_despues", "ΔELO", "historial_id"]
    df = df[cols_orden]

    if ordenar_desc:
        df = df.sort_values(by=["fecha", "historial_id"], ascending=[False, False]).reset_index(drop=True)
    else:
        df = df.sort_values(by=["fecha", "historial_id"], ascending=[True, True]).reset_index(drop=True)

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Tip: usa el buscador de la esquina superior derecha de la tabla para filtrar por texto.")

# ---------- PANEL PÚBLICO ----------
def panel_historial():
    st.title("6️⃣ Historial")

    tabs = st.tabs(["Partidos", "Historial ELO"])
    with tabs[0]:
        _render_tab_partidos()
    with tabs[1]:
        _render_tab_historial_elo()

    st.divider()
    if st.button("⬅️ Volver al menú principal", key="hist_btn_volver"):
        st.session_state.admin_page = None
        st.rerun()
