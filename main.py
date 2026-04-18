import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# 2. Estilos CSS: Minimalismo Tecnológico con Animación de Ola
st.markdown(
    """
    <style>
    @keyframes wave {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.8), rgba(240, 242, 245, 0.85)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #2D3748;
    }

    /* Cuadro del Título con Animación de Luz */
    .title-container {
        background: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(200, 210, 230, 0.5);
        border-radius: 15px;
        padding: 30px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
        backdrop-filter: blur(5px);
    }

    .animated-title {
        font-size: 48px;
        font-weight: 800;
        margin: 0;
        /* Efecto de Ola de Color */
        background: linear-gradient(90deg, #1A202C 0%, #4A5568 25%, #3182CE 50%, #4A5568 75%, #1A202C 100%);
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        animation: wave 8s linear infinite;
        letter-spacing: 3px;
    }

    .sub-title {
        font-size: 16px;
        text-align: center;
        color: #718096;
        margin-top: 10px;
        letter-spacing: 5px;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Estilo de Pestañas Limpias */
    .stTabs [data-baseweb="tab-list"] {
        justify-content: center;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #A0AEC0;
        transition: 0.4s;
    }

    .stTabs [aria-selected="true"] {
        color: #2B6CB0 !important;
        background-color: white !important;
        border-radius: 10px 10px 0 0;
        box-shadow: 0 -4px 10px rgba(0,0,0,0.03);
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #3182CE !important;
    }

    /* Botones con efecto Hover suave */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 4em;
        background-color: rgba(255, 255, 255, 0.8);
        color: #2D3748;
        border: 1px solid #E2E8F0;
        transition: all 0.4s ease;
        font-size: 16px;
    }
    
    .stButton>button:hover {
        background-color: #FFFFFF;
        border: 1px solid #3182CE;
        box-shadow: 0 10px 20px rgba(49, 130, 206, 0.1);
        transform: translateY(-2px);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

def mostrar_inicio():
    # Título Animado
    st.markdown('''
        <div class="title-container">
            <h1 class="animated-title">LABORATORIO DE OPERACIONES UNITARIAS</h1>
            <div class="sub-title">CENTRO DE SIMULACIÓN VIRTUAL | UCV</div>
        </div>
    ''', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["LOU I", "LOU II"])

    with tab1:
        st.write("##")
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
        st.write("##")
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
    if st.button("⬅ Regresar al Panel Principal"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    st.markdown(f'<div class="title-container"><h1 class="animated-title">{nombre.upper()}</h1></div>', unsafe_allow_html=True)
    st.info("Módulo de modelado matemático cargando...")
    st.image("Lou fondo.jpeg", use_container_width=True)

# 4. Render
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
