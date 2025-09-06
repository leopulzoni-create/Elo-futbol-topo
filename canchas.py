import streamlit as st
import sqlite3

DB_NAME = "elo_futbol.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def panel_canchas():
    st.subheader("Gestión de canchas 🏟️")

    accion = st.radio(
        "Selecciona acción:",
        ["Crear cancha", "Editar cancha", "Eliminar cancha", "Ver canchas"]
    )

    # --- CREAR CANCHA ---
    if accion == "Crear cancha":
        nombre = st.text_input("Nombre de la cancha")
        direccion = st.text_input("Dirección")
        foto = st.text_input("URL o path de la foto")

        if st.button("Crear cancha"):
            if nombre.strip() == "":
                st.error("Debe ingresar un nombre válido.")
            else:
                conn = get_connection()
                cur = conn.cursor()
                # Verificar si ya existe una cancha con ese nombre
                cur.execute("SELECT COUNT(*) FROM canchas WHERE nombre = ?", (nombre,))
                existe = cur.fetchone()[0]
                if existe:
                    st.error(f"Ya existe una cancha con el nombre '{nombre}'.")
                else:
                    cur.execute(
                        "INSERT INTO canchas (nombre, direccion, foto) VALUES (?, ?, ?)",
                        (nombre, direccion, foto)
                    )
                    conn.commit()
                    st.success(f"Cancha '{nombre}' creada con éxito ✅.")
                conn.close()

    # --- EDITAR CANCHA ---
    elif accion == "Editar cancha":
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, direccion, foto FROM canchas ORDER BY nombre ASC")
        canchas = cur.fetchall()
        conn.close()

        if canchas:
            opciones = [f"{c['id']} - {c['nombre']}" for c in canchas]
            cancha_sel = st.selectbox("Selecciona cancha a editar", opciones)
            cancha_id = int(cancha_sel.split(" - ")[0])

            # Datos actuales
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM canchas WHERE id = ?", (cancha_id,))
            cancha = cur.fetchone()
            conn.close()

            nuevo_nombre = st.text_input("Nombre", value=cancha["nombre"])
            nueva_direccion = st.text_input("Dirección", value=cancha["direccion"])
            nueva_foto = st.text_input("Foto", value=cancha["foto"])

            if st.button("Guardar cambios"):
                conn = get_connection()
                cur = conn.cursor()
                # Verificar nombre único
                cur.execute(
                    "SELECT COUNT(*) FROM canchas WHERE nombre = ? AND id != ?",
                    (nuevo_nombre, cancha_id)
                )
                existe = cur.fetchone()[0]
                if existe:
                    st.error(f"Ya existe otra cancha con el nombre '{nuevo_nombre}'.")
                else:
                    cur.execute(
                        "UPDATE canchas SET nombre = ?, direccion = ?, foto = ? WHERE id = ?",
                        (nuevo_nombre, nueva_direccion, nueva_foto, cancha_id)
                    )
                    conn.commit()
                    st.success(f"Cancha '{nuevo_nombre}' actualizada ✏️.")
                conn.close()
        else:
            st.info("No hay canchas cargadas.")

    # --- ELIMINAR CANCHA ---
    elif accion == "Eliminar cancha":
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM canchas ORDER BY nombre ASC")
        canchas = cur.fetchall()
        conn.close()

        if canchas:
            opciones = [f"{c['id']} - {c['nombre']}" for c in canchas]
            cancha_sel = st.selectbox("Selecciona cancha a eliminar", opciones)
            if st.button("Eliminar cancha"):
                cancha_id = int(cancha_sel.split(" - ")[0])
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM canchas WHERE id = ?", (cancha_id,))
                conn.commit()
                conn.close()
                st.success(f"Cancha '{cancha_sel}' eliminada ❌.")
        else:
            st.info("No hay canchas cargadas.")

    # --- VER CANCHAS ---
    elif accion == "Ver canchas":
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, direccion, foto FROM canchas ORDER BY nombre ASC")
        canchas = cur.fetchall()
        conn.close()

        if canchas:
            st.write("### Lista de canchas:")
            for c in canchas:
                st.write(f"ID: {c['id']} | Nombre: {c['nombre']} | Dirección: {c['direccion']} | Foto: {c['foto']}")
        else:
            st.info("No hay canchas cargadas todavía.")

    # --- VOLVER ---
    if st.button("⬅️ Volver al menú principal"):
        st.session_state.admin_page = None
        st.rerun()
