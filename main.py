import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🔧")

# 2. Estilos CSS: Minimalismo Tecnológico con Animación y LOGOS
st.markdown(
    """
    <style>
    /* Definición de la animación de ola de color */
    @keyframes wave {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* Fondo principal */
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.8), rgba(240, 242, 245, 0.85)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #2D3748;
    }

    /* Contenedor del Título (Cuadro de Cristal) */
    .title-container {
        background: rgba(255, 255, 255, 0.6);
        border: 1px solid rgba(200, 210, 230, 0.5);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
        backdrop-filter: blur(5px);
        display: flex; /* Para alinear logos y texto */
        align-items: center;
        justify-content: space-between;
    }

    /* Estilo para las imágenes de los logos */
    .logo-img {
        height: 80px; /* Ajusta la altura según necesites */
        width: auto;
    }

    /* Estilo del texto del título (con animación) */
    .text-center-container {
        flex-grow: 1;
        text-align: center;
    }

    .animated-title {
        font-size: 42px; /* Ligeramente más pequeño para que quepan logos */
        font-weight: 800;
        margin: 0;
        /* Efecto de Ola de Color Grises/Azules */
        background: linear-gradient(90deg, #1A202C 0%, #4A5568 25%, #3182CE 50%, #4A5568 75%, #1A202C 100%);
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        animation: wave 8s linear infinite;
        letter-spacing: 2px;
    }

    /* Subtítulo */
    .sub-title {
        font-size: 15px;
        text-align: center;
        color: #718096;
        margin-top: 5px;
        letter-spacing: 4px;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Estilo de Pestañas y Botones (Mantenemos el anterior) */
    .stTabs [data-baseweb="tab-list"] { justify-content: center; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #A0AEC0; transition: 0.4s; }
    .stTabs [aria-selected="true"] { color: #2B6CB0 !important; background-color: white !important; border-radius: 10px; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #3182CE !important; }

    .stButton>button {
        width: 100%; border-radius: 10px; height: 3.8em;
        background-color: rgba(255, 255, 255, 0.8); color: #2D3748;
        border: 1px solid #E2E8F0; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #FFFFFF; border: 1px solid #3182CE;
        box-shadow: 0 8px 15px rgba(49, 130, 206, 0.1); transform: translateY(-2px);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

def mostrar_inicio():
    # Estructura HTML con Logos y Título Animado
    # Importante: Usamos la URL RAW de tus archivos en GitHub
    url_logo_ucv = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_Universidad_Central_de_Venezuela.svg.png"
    url_logo_quimica = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_ingeneriaquimica.png"

    st.markdown(f'''
        <div class="title-container">
            <img src="{url_logo_ucv}" class="logo-img" alt="Logo UCV">
            <div class="text-center-container">
                <h1 class="animated-title">LABORATORIO DE OPERACIONES UNITARIAS</h1>
                <div class="sub-title">CENTRO DE SIMULACIÓN VIRTUAL | UCV</div>
            </div>
            <img src="{url_logo_quimica}" class="logo-img" alt="Logo Ingeniería Química">
        </div>
    ''', unsafe_allow_html=True)
    
    # Resto de la interfaz (Tabs y Botones)
    tab1, tab2 = st.tabs(["LOU I", "LOU II"])

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
    # Botón Volver con estilo (Key diferente para CSS si quieres)
    if st.button("⬅ Regresar al Panel Principal"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    # Mostramos el título de la práctica sin logos para no saturar
    st.markdown(f'<div class="title-container"><h1 class="animated-title" style="font-size:36px; -webkit-background-clip: padding-box;">{nombre.upper()}</h1></div>', unsafe_allow_html=True)
    st.info("Módulo de modelado matemático cargando...")
    st.image("Lou fondo.jpeg", use_container_width=True)

# 4. Render
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
