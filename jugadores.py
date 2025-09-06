import streamlit as st
import sqlite3

DB_NAME = "elo_futbol.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def panel_gestion():
    st.subheader("Gestión de jugadores ⚽")

    accion = st.radio(
        "Selecciona acción:",
        ["Crear jugador", "Eliminar jugador", "Editar jugador", "Ver jugadores"],
    )

    # --- CREAR JUGADOR ---
    if accion == "Crear jugador":
        nombre = st.text_input("Nombre del jugador")
        elo_inicial = st.number_input("ELO inicial", min_value=0, value=1000, step=50)
        estado = st.selectbox("Estado", ["activo", "inactivo"])

        if st.button("Crear jugador"):
            if nombre.strip() == "":
                st.error("Debe ingresar un nombre válido.")
            else:
                conn = get_connection()
                cur = conn.cursor()
                # Verificar si el nombre ya existe
                cur.execute("SELECT COUNT(*) FROM jugadores WHERE nombre = ?", (nombre,))
                existe = cur.fetchone()[0]
                if existe:
                    st.error(f"Ya existe un jugador con el nombre '{nombre}'.")
                else:
                    cur.execute(
                        "INSERT INTO jugadores (nombre, elo_actual, estado) VALUES (?, ?, ?)",
                        (nombre, elo_inicial, estado),
                    )
                    conn.commit()
                    st.success(f"Jugador {nombre} creado con éxito ✅.")
                conn.close()

    # --- ELIMINAR JUGADOR ---
    elif accion == "Eliminar jugador":
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM jugadores ORDER BY nombre ASC")
        jugadores = cur.fetchall()
        conn.close()

        opciones = [f"{j['id']} - {j['nombre']}" for j in jugadores]
        if opciones:
            jugador_sel = st.selectbox("Selecciona jugador a eliminar", opciones)

            if st.button("Eliminar jugador"):
                jugador_id = int(jugador_sel.split(" - ")[0])
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM jugadores WHERE id = ?", (jugador_id,))
                conn.commit()
                conn.close()
                st.success(f"Jugador {jugador_sel} eliminado ❌.")
        else:
            st.info("No hay jugadores cargados.")

    # --- EDITAR JUGADOR ---
    elif accion == "Editar jugador":
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, elo_actual, estado FROM jugadores ORDER BY nombre ASC")
        jugadores = cur.fetchall()
        conn.close()

        if jugadores:
            opciones = [f"{j['id']} - {j['nombre']}" for j in jugadores]
            jugador_sel = st.selectbox("Selecciona jugador a editar", opciones)
            jugador_id = int(jugador_sel.split(" - ")[0])

            # Obtener datos actuales
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jugadores WHERE id = ?", (jugador_id,))
            jugador = cur.fetchone()
            conn.close()

            # Formulario de edición
            nuevo_nombre = st.text_input("Nombre", value=jugador["nombre"])
            nuevo_elo = st.number_input("ELO", min_value=0, step=50, value=jugador["elo_actual"])
            nuevo_estado = st.selectbox(
                "Estado", ["activo", "inactivo"], index=(0 if jugador["estado"] == "activo" else 1)
            )

            if st.button("Guardar cambios"):
                conn = get_connection()
                cur = conn.cursor()
                # Verificar si el nuevo nombre ya existe en otro jugador
                cur.execute(
                    "SELECT COUNT(*) FROM jugadores WHERE nombre = ? AND id != ?",
                    (nuevo_nombre, jugador_id)
                )
                existe = cur.fetchone()[0]
                if existe:
                    st.error(f"Ya existe otro jugador con el nombre '{nuevo_nombre}'.")
                else:
                    cur.execute(
                        "UPDATE jugadores SET nombre = ?, elo_actual = ?, estado = ? WHERE id = ?",
                        (nuevo_nombre, nuevo_elo, nuevo_estado, jugador_id),
                    )
                    conn.commit()
                    st.success(f"Jugador {nuevo_nombre} actualizado ✏️.")
                conn.close()
        else:
            st.info("No hay jugadores cargados.")

    # --- VER JUGADORES ---
    elif accion == "Ver jugadores":
        conn = get_connection()
        cur = conn.cursor()
        # Primero activos, luego inactivos
        cur.execute("SELECT id, nombre, elo_actual, estado FROM jugadores ORDER BY estado DESC, nombre ASC")
        jugadores = cur.fetchall()
        conn.close()

        if jugadores:
            st.write("### Lista de jugadores:")
            for j in jugadores:
                estado_icon = "🟢" if j["estado"] == "activo" else "⚪"
                st.write(
                    f"{estado_icon} ID: {j['id']} | Nombre: {j['nombre']} | "
                    f"ELO: {j['elo_actual']} | Estado: {j['estado']}"
                )
        else:
            st.info("No hay jugadores cargados todavía.")

    # --- VOLVER ---
    if st.button("⬅️ Volver al menú principal"):
        st.session_state.admin_page = None
        st.rerun()
