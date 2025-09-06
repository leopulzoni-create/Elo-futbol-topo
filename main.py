import streamlit as st
from auth import verify_user
from init_db import ensure_schema_and_admin  # ← agregar

ensure_schema_and_admin()  # ← inicializa tablas y admin si falta

st.title("Topo Partidos ⚽")

# --- LOGIN ---
if "user" not in st.session_state:
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        user = verify_user(username, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

else:
    user = st.session_state.user
    rol = user["rol"]

    # ==================================================
    # PANEL ADMIN
    # ==================================================
    if rol == "admin":
        st.header(f"Panel Administrador - {user['username']}")

        # Guardamos qué página está activa
        if "admin_page" not in st.session_state:
            st.session_state.admin_page = None

        # --- MENÚ PRINCIPAL ---
        if st.session_state.admin_page is None:
            st.subheader("Selecciona una opción:")
            if st.button("1️⃣ Gestión de jugadores"):
                st.session_state.admin_page = "jugadores"
                st.rerun()
            if st.button("2️⃣ Gestión de canchas"):
                st.session_state.admin_page = "canchas"
                st.rerun()
            if st.button("3️⃣ Crear partido"):
                st.session_state.admin_page = "crear_partido"
                st.rerun()
            if st.button("4️⃣ Generar equipos"):
                st.session_state.admin_page = "generar_equipos"
                st.rerun()
            if st.button("5️⃣ Registrar resultado"):
                st.session_state.admin_page = "registrar_resultado"
                st.rerun()
            if st.button("6️⃣ Historial"):
                st.session_state.admin_page = "historial"
                st.rerun()
            if st.button("7️⃣ Administrar usuarios"):  # ← NUEVO
                st.session_state.admin_page = "usuarios"
                st.rerun()

        # --- CARGA DE MÓDULOS SEGÚN BOTÓN ---
        elif st.session_state.admin_page == "jugadores":
            import jugadores
            jugadores.panel_gestion()
        elif st.session_state.admin_page == "canchas":
            import canchas
            canchas.panel_canchas()
        elif st.session_state.admin_page == "crear_partido":
            import partidos
            partidos.panel_creacion()
        elif st.session_state.admin_page == "generar_equipos":
            import equipos
            equipos.panel_generacion()
        elif st.session_state.admin_page == "registrar_resultado":
            import cargaresultados
            cargaresultados.panel_resultados()
        elif st.session_state.admin_page == "historial":
            import historial
            historial.panel_historial()
        elif st.session_state.admin_page == "usuarios":  # ← NUEVO
            import usuarios
            usuarios.panel_gestion()

    # ==================================================
    # PANEL JUGADOR
    # ==================================================
    elif rol == "jugador":
        import jugador_panel  # ← agregado: import local del módulo de panel jugador
        st.header(f"Panel Jugador - {user['username']}")

        # Router del panel jugador (no interfiere con admin_page)
        if "jugador_page" not in st.session_state:
            st.session_state.jugador_page = "menu"

        if st.session_state.jugador_page == "menu":
            jugador_panel.panel_menu_jugador(user)
        elif st.session_state.jugador_page == "partidos":
            jugador_panel.panel_partidos_disponibles(user)
        elif st.session_state.jugador_page == "stats":
            jugador_panel.panel_mis_estadisticas(user)
        else:
            st.session_state.jugador_page = "menu"
            st.rerun()

