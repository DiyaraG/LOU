import streamlit as st

# Configuración básica
st.set_page_config(page_title="LOU Virtual - UCV", layout="wide")

# Estilo para la "marca de agua" y diseño
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), 
                    url("https://raw.githubusercontent.com/DiyaraG/LOU/main/assets/fondo_lou.jpg");
        background-size: cover;
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
        cols = st.columns(3)
        practicas_lou1 = [
            "Calibración de Medidor de Flujo",
            "Pérdidas de Presión por Fricción",
            "Bombas Centrífugas",
            "Balance No Estacionario",
            "Lechos Fluidizados"
        ]
        for i, p in enumerate(practicas_lou1):
            with cols[i % 3]:
                if st.button(p, use_container_width=True):
                    st.session_state.page = p

    with tab2:
        cols = st.columns(3)
        practicas_lou2 = [
            "Hidrodinámica de Columnas",
            "Filtración a Presión Constante",
            "Destilación Diferencial",
            "Destilación Continua",
            "Rectificación en Torre Rellena"
        ]
        for i, p in enumerate(practicas_lou2):
            with cols[i % 3]:
                if st.button(p, use_container_width=True):
                    st.session_state.page = p

# Lógica de navegación simple
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

if st.session_state.page == 'Inicio':
    inicio()
else:
    if st.button("⬅ Volver al Inicio"):
        st.session_state.page = 'Inicio'
        st.rerun()
    st.title(f"Simulación: {st.session_state.page}")
    st.info("Espacio para el modelo matemático e imágenes de la práctica.")
    # Aquí es donde pondrás st.image("tu_imagen.png") para cada una
