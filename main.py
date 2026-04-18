import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# 2. Estilos CSS: Ola Metálica sutil sobre fondo blanco
st.markdown(
    """
    <style>
    @keyframes wave-light {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.85), rgba(245, 247, 250, 0.9)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }

    /* Contenedor más integrado (menos sombra, más borde suave) */
    .title-container {
        background: rgba(255, 255, 255, 0.4);
        border: 1px solid rgba(226, 232, 240, 0.8);
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 30px;
        backdrop-filter: blur(8px);
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
    }

    .logo-img { height: 75px; width: auto; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05)); }

    .text-center-container { flex-grow: 1; text-align: center; }

    /* Animación de Ola Refinada: Mezcla de Grises, Blancos y Azul Glacial */
    .animated-title {
        font-size: 40px;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, 
            #2D3748 0%, 
            #718096 20%, 
            #EDF2F7 40%, 
            #A3BFFA 50%, 
            #EDF2F7 60%, 
            #718096 80%, 
            #2D3748 100%
        );
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        animation: wave-light 10s linear infinite; /* Más lenta para ser más elegante */
        letter-spacing: 1px;
    }

    .sub-title {
        font-size: 14px;
        text-align: center;
        color: #A0AEC0;
        margin-top: 8px;
        letter-spacing: 6px;
        text-transform: uppercase;
    }

    /* Tabs y Botones con estilo Minimalista */
    .stTabs [data-baseweb="tab-list"] { justify-content: center; }
    .stTabs [data-baseweb="tab"] { color: #CBD5E0; font-weight: 500; }
    .stTabs [aria-selected="true"] { color: #4A5568 !important; border-bottom: 2px solid #BEE3F8 !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: transparent !important; }

    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em;
        background-color: rgba(255, 255, 255, 0.6); color: #4A5568;
        border: 1px solid #EDF2F7; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #FFFFFF; border: 1px solid #BEE3F8;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

def mostrar_inicio():
    url_logo_ucv = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_Universidad_Central_de_Venezuela.svg.png"
    url_logo_quimica = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_ingenieriaquimica.png"

    st.markdown(f'''
        <div class="title-container">
            <img src="{url_logo_ucv}" class="logo-img">
            <div class="text-center-container">
                <h1 class="animated-title">LABORATORIO DE OPERACIONES UNITARIAS</h1>
                <div class="sub-title">Centro de Simulación Virtual | UCV</div>
            </div>
            <img src="{url_logo_quimica}" class="logo-img">
        </div>
    ''', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["MÓDULO LOU I", "MÓDULO LOU II"])

    with tab1:
        st.write("##")
        cols1 = st.columns(2)
        practicas1 = ["Calibración de un Medidor de Flujo", "Pérdidas de Presión por Fricción", "Bombas Centrífugas", "Balance en Estado No Estacionario", "Lechos Fluidizados"]
        for i, p in enumerate(practicas1):
            with cols1[i % 2]:
                if st.button(p, key=f"btn_l1_{i}"):
                    st.session_state.page = p
                    st.rerun()

    with tab2:
        st.write("##")
        cols2 = st.columns(2)
        practicas2 = ["Hidrodinámica de Columnas Empacadas", "Filtración a Presión Constante", "Destilación Diferencial", "Destilación Continua", "Rectificación en Torre Rellena"]
        for i, p in enumerate(practicas2):
            with cols2[i % 2]:
                if st.button(p, key=f"btn_l2_{i}"):
                    st.session_state.page = p
                    st.rerun()

def mostrar_simulador(nombre):
    if st.button("⬅ Volver al Menú Principal"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    st.markdown(f'''
        <div class="title-container" style="justify-content:center;">
            <h1 class="animated-title" style="font-size:32px;">{nombre.upper()}</h1>
        </div>
    ''', unsafe_allow_html=True)
    st.info("Configurando entorno de simulación...")
    st.image("Lou fondo.jpeg", use_container_width=True)

# 4. Render
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
