import streamlit as st

# Configuración básica
st.set_page_config(page_title="LOU Virtual - UCV", layout="wide")

# Estilo para la "marca de agua" ajustado a tu archivo subido
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), 
                    url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-attachment: fixed;
    }
    .titulo {
        text-align: center;
        color: #1E3A8A;
        font-size: 40px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

def inicio():
    st.markdown('<p class="titulo">Bienvenido al Laboratorio de Operaciones Unitarias Virtual</p>', unsafe_allow_html=True)
    st.write("---")
    
    tab1, tab2 = st.tabs(["LOU 1", "LOU 2"])

    with tab1:
        cols = st.columns(2)
        practicas_lou1 = [
            "Calibración de un Medidor de Flujo",
            "Pérdidas de Presión por Fricción",
            "Curvas Características de Bombas Centrífugas",
            "Balance en Estado No Estacionario",
            "Lechos Fluidizados"
        ]
        for i, p in enumerate(practicas_lou1):
            with cols[i % 2]:
                if st.button(p, use_container_width=True, key=f"L1_{i}"):
                    st.session_state.page = p
                    st.rerun()

    with tab2:
        cols = st.columns(2)
        practicas_lou2 = [
            "Hidrodinámica de Columnas Empacadas",
            "Filtración a Presión Constante",
            "Destilación Diferencial",
            "Destilación Continua",
            "Rectificación en Torre Rellena"
        ]
        for i, p in enumerate(practicas_lou2):
            with cols[i % 2]:
                if st.button(p, use_container_width=True, key=f"L2_{i}"):
                    st.session_state.page = p
                    st.rerun()

# Lógica de navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

if st.session_state.page == 'Inicio':
    inicio()
else:
    if st.button("⬅ Volver al Inicio"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    st.title(f"Práctica: {st.session_state.page}")
    st.info("Visualización de la práctica (Modelo matemático en desarrollo)")
    # Aquí podrías poner una imagen genérica o específica del equipo
    st.image("Lou fondo.jpeg", caption=f"Equipo de {st.session_state.page}", use_column_width=True)
