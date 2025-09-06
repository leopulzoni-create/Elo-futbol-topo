# usuarios.py
import streamlit as st
import sqlite3
import hashlib

DB_NAME = "elo_futbol.db"

# =========================
# Helpers
# =========================
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# Usa hash de auth si existe; si no, SHA-256 (MVP local)
_HASH_VIA_AUTH = False
try:
    from auth import hash_password as _auth_hash_password
    _HASH_VIA_AUTH = True
except Exception:
    pass

def _sha256_hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def hash_password(pwd: str) -> str:
    return _auth_hash_password(pwd) if _HASH_VIA_AUTH else _sha256_hash(pwd)

def _set_flash(msg: str, typ: str = "success"):
    st.session_state["_flash_msg"] = msg
    st.session_state["_flash_type"] = typ

def _render_and_clear_flash_at_bottom():
    """Muestra el flash (si existe) aquí al final del panel y luego lo limpia."""
    msg = st.session_state.get("_flash_msg")
    typ = st.session_state.get("_flash_type", "info")
    if msg:
        if   typ == "success": st.success(msg)
        elif typ == "warning": st.warning(msg)
        elif typ == "error":   st.error(msg)
        else:                  st.info(msg)
        # limpiar para no repetir
        st.session_state.pop("_flash_msg", None)
        st.session_state.pop("_flash_type", None)

# =========================
# UI principal
# =========================
def panel_gestion():
    st.subheader("Administrar usuarios 👤")

    accion = st.radio(
        "Selecciona acción:",
        ["Crear usuario", "Editar usuario", "Eliminar usuario", "Ver usuarios"],
        key="usuarios_accion_radio"
    )

    # Utilidades de datos
    def cargar_jugadores():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM jugadores ORDER BY estado DESC, nombre ASC")
        data = cur.fetchall()
        conn.close()
        return data

    def cargar_usuarios():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.rol, u.jugador_id, j.nombre AS jugador_nombre
            FROM usuarios u
            LEFT JOIN jugadores j ON j.id = u.jugador_id
            ORDER BY u.rol ASC, u.username ASC
        """)
        data = cur.fetchall()
        conn.close()
        return data

    # -------------------------
    # CREAR USUARIO
    # -------------------------
    if accion == "Crear usuario":
        st.write("### Crear nuevo usuario")
        username = st.text_input("Nombre de usuario", key="usuarios_create_username")
        password = st.text_input("Contraseña", type="password", key="usuarios_create_password")
        rol = st.selectbox("Rol", ["jugador", "admin"], key="usuarios_create_rol")

        jugadores = cargar_jugadores()
        opciones_j = ["(sin vincular)"] + [f"{j['id']} - {j['nombre']}" for j in jugadores]
        vinculo_sel = st.selectbox("Vincular a jugador (opcional)", opciones_j, key="usuarios_create_vinculo")

        if st.button("Crear usuario", key="usuarios_create_btn"):
            if not username.strip():
                st.error("El nombre de usuario no puede estar vacío.")
            elif not password:
                st.error("La contraseña no puede estar vacía.")
            else:
                conn = get_connection()
                cur = conn.cursor()

                # Username único
                cur.execute("SELECT COUNT(*) AS c FROM usuarios WHERE username = ?", (username,))
                if cur.fetchone()["c"]:
                    conn.close()
                    st.error(f"Ya existe un usuario con username '{username}'.")
                else:
                    # Vinculación opcional y única
                    jugador_id = None
                    if vinculo_sel != "(sin vincular)":
                        jugador_id = int(vinculo_sel.split(" - ")[0])
                        cur.execute("SELECT COUNT(*) AS c FROM usuarios WHERE jugador_id = ?", (jugador_id,))
                        if cur.fetchone()["c"]:
                            conn.close()
                            st.error("Ese jugador ya está vinculado a otro usuario.")
                            return

                    pwd_hash = hash_password(password)
                    cur.execute(
                        "INSERT INTO usuarios (jugador_id, username, password_hash, rol) VALUES (?, ?, ?, ?)",
                        (jugador_id, username, pwd_hash, rol)
                    )
                    conn.commit()
                    conn.close()

                    _set_flash(f"Usuario '{username}' creado con éxito ✅", "success")
                    st.rerun()

    # -------------------------
    # EDITAR USUARIO
    # -------------------------
    elif accion == "Editar usuario":
        st.write("### Editar usuario existente")

        usuarios = cargar_usuarios()
        if not usuarios:
            st.info("No hay usuarios cargados.")
        else:
            opciones_u = [f"{u['id']} - {u['username']} ({u['rol']})" for u in usuarios]
            usuario_sel = st.selectbox("Selecciona usuario", opciones_u, key="usuarios_edit_sel")
            usuario_id = int(usuario_sel.split(" - ")[0])

            u_row = next(u for u in usuarios if u["id"] == usuario_id)
            nuevo_username = st.text_input("Nuevo username", value=u_row["username"], key=f"usuarios_edit_username_{usuario_id}")
            nuevo_rol = st.selectbox("Rol", ["jugador", "admin"], index=(0 if u_row["rol"]=="jugador" else 1), key=f"usuarios_edit_rol_{usuario_id}")

            # Vinculación
            jugadores = cargar_jugadores()
            mapa_j = {j["id"]: j["nombre"] for j in jugadores}
            opciones_j = ["(sin vincular)"] + [f"{j['id']} - {j['nombre']}" for j in jugadores]
            if u_row["jugador_id"] and u_row["jugador_id"] in mapa_j:
                actual_label = f"{u_row['jugador_id']} - {mapa_j[u_row['jugador_id']]}"
                default_index = opciones_j.index(actual_label) if actual_label in opciones_j else 0
            else:
                default_index = 0
            vinculo_sel = st.selectbox("Vincular a jugador (opcional)", opciones_j, index=default_index, key=f"usuarios_edit_vinc_{usuario_id}")

            # Resetear contraseña (opcional)
            reset_pwd = st.checkbox("Resetear contraseña", key=f"usuarios_edit_resetpwd_{usuario_id}")
            nueva_pwd = st.text_input("Nueva contraseña", type="password", key=f"usuarios_edit_newpwd_{usuario_id}") if reset_pwd else None

            if st.button("Guardar cambios", key=f"usuarios_edit_guardar_{usuario_id}"):
                if not nuevo_username.strip():
                    st.error("El username no puede estar vacío.")
                else:
                    conn = get_connection()
                    cur = conn.cursor()

                    # Username único entre otros
                    cur.execute("SELECT COUNT(*) AS c FROM usuarios WHERE username = ? AND id != ?", (nuevo_username, usuario_id))
                    if cur.fetchone()["c"]:
                        conn.close()
                        st.error(f"Ya existe otro usuario con username '{nuevo_username}'.")
                        return

                    # Determinar jugador_id y verificar que no esté vinculado a otro
                    jugador_id = None
                    if vinculo_sel != "(sin vincular)":
                        jugador_id = int(vinculo_sel.split(" - ")[0])
                        cur.execute("SELECT COUNT(*) AS c FROM usuarios WHERE jugador_id = ? AND id != ?", (jugador_id, usuario_id))
                        if cur.fetchone()["c"]:
                            conn.close()
                            st.error("Ese jugador ya está vinculado a otro usuario.")
                            return

                    # Update (con o sin reset de contraseña)
                    if reset_pwd:
                        if not (nueva_pwd and nueva_pwd.strip()):
                            conn.close()
                            st.error("Debe ingresar la nueva contraseña.")
                            return
                        pwd_hash = hash_password(nueva_pwd)
                        cur.execute(
                            "UPDATE usuarios SET jugador_id=?, username=?, password_hash=?, rol=? WHERE id=?",
                            (jugador_id, nuevo_username, pwd_hash, nuevo_rol, usuario_id)
                        )
                    else:
                        cur.execute(
                            "UPDATE usuarios SET jugador_id=?, username=?, rol=? WHERE id=?",
                            (jugador_id, nuevo_username, nuevo_rol, usuario_id)
                        )

                    conn.commit()
                    conn.close()
                    _set_flash("Usuario actualizado ✏️", "success")
                    st.rerun()

    # -------------------------
    # ELIMINAR USUARIO
    # -------------------------
    elif accion == "Eliminar usuario":
        st.write("### Eliminar usuario")

        usuarios = cargar_usuarios()
        if not usuarios:
            st.info("No hay usuarios cargados.")
        else:
            opciones_u = [f"{u['id']} - {u['username']} ({u['rol']})" for u in usuarios]
            usuario_sel = st.selectbox("Selecciona usuario a eliminar", opciones_u, key="usuarios_del_sel")
            usuario_id = int(usuario_sel.split(" - ")[0])

            confirmar = st.checkbox("Confirmo que deseo eliminar este usuario", key=f"usuarios_del_confirm_{usuario_id}")
            if st.button("Eliminar usuario", key=f"usuarios_del_btn_{usuario_id}"):
                if not confirmar:
                    st.error("Debes marcar la confirmación para eliminar.")
                else:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
                    conn.commit()
                    conn.close()
                    _set_flash("Usuario eliminado ❌", "success")
                    st.rerun()

    # -------------------------
    # VER USUARIOS
    # -------------------------
    elif accion == "Ver usuarios":
        st.write("### Usuarios registrados")
        usuarios = cargar_usuarios()
        if not usuarios:
            st.info("No hay usuarios cargados.")
        else:
            for u in usuarios:
                vinc = u["jugador_nombre"] if u["jugador_nombre"] else "(sin vincular)"
                st.write(f"ID: {u['id']} | Username: {u['username']} | Rol: {u['rol']} | Jugador: {vinc}")

    # -------------------------
    # FLASH (debajo) + VOLVER
    # -------------------------
    _render_and_clear_flash_at_bottom()  # ← mensaje aparece aquí, arriba del botón Volver

    if st.button("⬅️ Volver al menú principal", key="usuarios_back"):
        st.session_state.admin_page = None
        st.rerun()
