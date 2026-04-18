

import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# 2. Estilos CSS: Minimalismo Tecnológico (Blanco y Gris)
st.markdown(
    """
    <style>
    /* Fondo corregido y adaptado al nuevo estilo */
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.9), rgba(240, 242, 245, 0.95)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #2D3748;
    }

    /* Título con resplandor blanco limpio */
    .main-title {
        font-size: 40px;
        font-weight: 800;
        text-align: center;
        color: #1A202C;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
        padding: 20px;
        letter-spacing: 2px;
    }

    /* Subtítulo gris industrial */
    .sub-title {
        font-size: 18px;
        text-align: center;
        color: #718096;
        margin-bottom: 40px;
        font-family: 'Segoe UI', sans-serif;
    }

    /* ELIMINAR EL ROJO y personalizar pestañas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: rgba(255, 255, 255, 0.5);
        border-radius: 15px;
        padding: 5px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 45px;
        border-radius: 10px;
        color: #4A5568;
        border: none;
    }

    /* Pestaña seleccionada: quitamos el borde rojo de Streamlit */
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #2D3748 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0 !important;
    }

    /* Quitar la línea roja de Streamlit debajo de la pestaña */
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
    }

    /* Botones de Práctica: Estilo Cristal/Blanco */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.8em;
        background-color: rgba(255, 255, 255, 0.7);
        color: #2D3748;
        border: 1px solid #E2E8F0;
        transition: all 0.3s ease;
        font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    
    .stButton>button:hover {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E0;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
        transform: translateY(-3px);
        color: #000;
    }

    /* Mensajes de información en gris azulado */
    .stAlert {
        background-color: rgba(255, 255, 255, 0.8);
        border: 1px solid #E2E8F0;
        color: #4A5568;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

def mostrar_inicio():
    st.markdown('<div class="main-title">LABORATORIO DE OPERACIONES UNITARIAS</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">CENTRO DE SIMULACIÓN VIRTUAL | UCV</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["LOU I", "LOU II"])

    with tab1:
        st.write("###") # Espaciado
        cols1 = st.columns(2)
        practicas1 = [
            "Calibración de un Medidor de Flujo",
            "Pérdidas de Presión por Fricción",
            "Bombas Centrífugas",
            "Balance en Estado No Estacionario",
            "Lechos Fluidizados"
        ]
        for i, p in enumerate(practicas1):
            with cols1[i % 2]:
                if st.button(p, key=f"btn_l1_{i}"):
                    st.session_state.page = p
                    st.rerun()

    with tab2:
        st.write("###") # Espaciado
        cols2 = st.columns(2)
        practicas2 = [
            "Hidrodinámica de Columnas Empacadas",
            "Filtración a Presión Constante",
            "Destilación Diferencial",
            "Destilación Continua",
            "Rectificación en Torre Rellena"
        ]
        for i, p in enumerate(practicas2):
            with cols2[i % 2]:
                if st.button(p, key=f"btn_l2_{i}"):
                    st.session_state.page = p
                    st.rerun()

def mostrar_simulador(nombre):
    if st.button("⬅ Regresar al Panel Principal", key="back"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    st.markdown(f'<div class="main-title">{nombre.upper()}</div>', unsafe_allow_html=True)
    st.info("Módulo de modelado matemático cargando...")
    st.image("Lou fondo.jpeg", use_container_width=True)

# 4. Render
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
