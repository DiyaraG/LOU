import streamlit as st

# 1. Configuración de la página (Corregido con tus iconos)
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# 2. Estilos CSS: Mantenemos tu diseño favorito de "Cristal" y Animación de Ola
st.markdown(
    """
    <style>
    /* Animación de ola de color */
    @keyframes wave {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    /* Fondo principal con la imagen de tu laboratorio */
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
        display: flex; 
        align-items: center;
        justify-content: space-between;
    }

    .logo-img {
        height: 80px; 
        width: auto;
    }

    .text-center-container {
        flex-grow: 1;
        text-align: center;
    }

    /* El título animado que te gusta */
    .animated-title {
        font-size: 42px;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #1A202C 0%, #4A5568 25%, #3182CE 50%, #4A5568 75%, #1A202C 100%);
        background-size: 200% auto;
        color: transparent;
        -webkit-background-clip: text;
        background-clip: text;
        animation: wave 8s linear infinite;
        letter-spacing: 2px;
    }

    .sub-title {
        font-size: 15px;
        text-align: center;
        color: #718096;
        margin-top: 5px;
        letter-spacing: 4px;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Estilo de Pestañas y Botones */
    .stTabs [data-baseweb="tab-list"] { justify-content: center; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #A0AEC0; transition: 0.4s; }
    .stTabs [aria-selected="true"] { color: #2B6CB0 !important; background-color: white !important; border-radius: 10px; }
    
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
    # URLs de logos (Corregida la de ingeniería química)
    url_logo_ucv = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_Universidad_Central_de_Venezuela.svg.png"
    url_logo_quimica = "https://raw.githubusercontent.com/DiyaraG/LOU/main/Logo_ingenieriaquimica.png"

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

# 4. Vista de cada práctica (Arreglada para que el fondo y letras no cambien)
def mostrar_simulador(nombre):
    # Botón de regreso alineado a la izquierda
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("⬅ Menú Principal"):
            st.session_state.page = 'Inicio'
            st.rerun()
    
    # Reutilizamos el contenedor de cristal para el título de la práctica
    st.markdown(f'''
        <div class="title-container" style="justify-content: center; padding: 30px;">
            <div class="text-center-container">
                <h1 class="animated-title" style="font-size: 38px;">{nombre.upper()}</h1>
                <div class="sub-title" style="letter-spacing: 2px;">SIMULADOR DE PROCESOS QUÍMICOS</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)
    
    st.info(f"Iniciando entorno de cálculo para: {nombre}")
    
    # Aquí irá tu lógica de ingeniería química (gráficas, tablas, etc.)
    st.image("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg", use_container_width=True)

# 5. Ejecución
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
