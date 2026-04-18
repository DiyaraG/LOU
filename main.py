import streamlit as st

# 1. Configuración de la página (Mantenemos wide para mejor visualización)
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# 2. Aplicación de Estilos CSS Avanzados (Futurista / LED / Corrección de Fondo)
st.markdown(
    """
    <style>
    /* Fondo corregido: Adaptado al ancho, centrado y con efecto Parallax */
    .stApp {
        background-image: linear-gradient(rgba(10, 15, 30, 0.9), rgba(10, 15, 30, 0.95)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: contain; /* Corrección: Se adapta al ancho sin recortar */
        background-repeat: no-repeat;
        background-position: center top; /* Centrado horizontalmente, empieza arriba */
        background-attachment: fixed; /* Efecto Parallax suave */
        background-color: #050a14; /* Fondo oscuro profundo */
        color: #e0e6ed;
    }

    /* Título principal con efecto de brillo neón sutil */
    .main-title {
        font-size: 45px;
        font-weight: bold;
        text-align: center;
        margin-top: 20px;
        padding: 15px;
        color: #fff;
        text-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 15px #00d2ff, 0 0 20px #00d2ff, 0 0 30px #00d2ff;
        border-bottom: 2px solid rgba(0, 210, 255, 0.3);
        margin-bottom: 10px;
    }

    /* Subtítulos con color Cyan Tech */
    .sub-title {
        font-size: 22px;
        text-align: center;
        color: #00d2ff; /* Cian futurista */
        margin-bottom: 40px;
        font-family: 'Courier New', Courier, monospace; /* Toque de código */
    }

    /* Personalización de Pestañas (Tabs) con estilo LED */
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
        background-color: rgba(0, 30, 60, 0.5);
        padding: 10px;
        border-radius: 10px;
        border: 1px solid rgba(0, 210, 255, 0.2);
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: transparent;
        border-radius: 5px;
        color: #a0aec0;
        transition: 0.3s;
        border: 1px solid transparent;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #fff;
        border: 1px solid rgba(0, 210, 255, 0.5);
        box-shadow: 0 0 10px rgba(0, 210, 255, 0.3);
    }

    .stTabs [aria-selected="true"] {
        background-color: rgba(0, 210, 255, 0.1) !important;
        color: #00d2ff !important;
        font-weight: bold;
        border: 1px solid #00d2ff !important;
        box-shadow: 0 0 15px rgba(0, 210, 255, 0.5);
    }

    /* Títulos de sección dentro de las pestañas */
    .section-header {
        color: #e0e6ed;
        font-size: 24px;
        margin-top: 20px;
        margin-bottom: 15px;
        border-left: 4px solid #00d2ff;
        padding-left: 10px;
    }

    /* Personalización de Botones de Práctica: Efecto LED interactivo */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3.5em;
        background-color: rgba(0, 15, 30, 0.7);
        color: #e0e6ed;
        border: 1px solid rgba(0, 210, 255, 0.3);
        transition: all 0.3s ease;
        font-size: 16px;
        text-align: left;
        padding-left: 15px;
    }
    
    .stButton>button:hover {
        background-color: rgba(0, 210, 255, 0.15);
        color: #fff;
        border: 1px solid #00d2ff;
        box-shadow: 0 0 15px rgba(0, 210, 255, 0.6); /* Brillo LED al pasar el mouse */
        transform: translateY(-2px); /* Pequeña animación de levante */
    }

    /* Estilo para los Info Boxes y alertas */
    .stAlert {
        background-color: rgba(0, 30, 60, 0.6);
        border: 1px solid #00d2ff;
        color: #00d2ff;
        border-radius: 5px;
    }
    
    /* Botón de volver con estilo diferente */
    .stButton>button[key^="back_"] {
        background-color: rgba(255, 60, 60, 0.1);
        border: 1px solid rgba(255, 60, 60, 0.5);
        color: #ffcccc;
    }
    
    .stButton>button[key^="back_"]:hover {
        background-color: rgba(255, 60, 60, 0.3);
        border: 1px solid #ff4d4d;
        box-shadow: 0 0 15px rgba(255, 77, 77, 0.6);
    }

    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

# --- FUNCIÓN: PANTALLA DE INICIO (MENÚ PRINCIPAL FUTURISTA) ---
def mostrar_inicio():
    st.markdown('<div class="main-title">LABORATORIO DE OPERACIONES UNITARIAS</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">:: LOU VIRTUAL :: ESCUELA DE INGENIERÍA QUÍMICA :: UCV ::</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs([" LOU 1 ", " LOU 2 "])

    with tab1:
        st.markdown('<div class="section-header">Módulo de Mecánica de Fluidos y Transferencia de Calor</div>', unsafe_allow_html=True)
        cols1 = st.columns(2)
        practicas1 = [
            "Manual de la Práctica 1. Calibración de un Medidor de Flujo.",
            "Manual de la Práctica 2. Determinación de las Pérdidas de Presión por Fricción en Conexiones y Tramos de Tuberías.",
            "Manual de la Práctica 3. Determinación de Curvas Características de Bombas Centrífugas.",
            "Manual de la Práctica 4. Balance en Estado No Estacionario. (2)",
            "Manual de la Práctica 5. Lechos Fluidizados. Estudio de sus Principales Características."
        ]
        # Limpiamos el nombre para el botón
        nombres_limpios1 = [p.split('. ', 1)[1] if '. ' in p else p for p in practicas1]
        
        for i, (nombre_completo, nombre_boton) in enumerate(zip(practicas1, nombres_limpios1)):
            with cols1[i % 2]:
                # Usamos nombre_completo como ID interna y nombre_boton como texto
                if st.button(nombre_boton, key=f"btn_l1_{i}"):
                    st.session_state.page = nombre_completo
                    st.rerun()

    with tab2:
        st.markdown('<div class="section-header">Módulo de Transferencia de Masa y Separaciones</div>', unsafe_allow_html=True)
        cols2 = st.columns(2)
        practicas2 = [
            "Manual de la Práctica 1. Hidrodinámica de Columnas Empacadas.",
            "Manual de la Práctica 3. Estudio de las Características de la Filtración a Presión Constante de una Suspensión.",
            "Manual de la Práctica 4. Estudio de la Destilación Diferencial.",
            "Manual de la Práctica 5. Destilación Continua de una Mezcla Binaria en una Columna de Separación por Etapas.",
            "Manual de la Práctica 6. Rectificación de una Mezcla Binaria en una Torre Rellena."
        ]
        # Limpiamos el nombre para el botón
        nombres_limpios2 = [p.split('. ', 1)[1] if '. ' in p else p for p in practicas2]

        for i, (nombre_completo, nombre_boton) in enumerate(zip(practicas2, nombres_limpios2)):
            with cols2[i % 2]:
                if st.button(nombre_boton, key=f"btn_l2_{i}"):
                    st.session_state.page = nombre_completo
                    st.rerun()

# --- FUNCIÓN: VISTA DE CADA PRÁCTICA (SIMULADOR EN DESARROLLO) ---
def mostrar_simulador(nombre_completo_practica):
    col_back, col_spacer = st.columns([1, 4])
    with col_back:
        if st.button("⬅ Volver", key="back_btn"):
            st.session_state.page = 'Inicio'
            st.rerun()
    
    # Extraemos solo el nombre de la práctica para el título
    nombre_titulo = nombre_completo_practica.split('. ', 1)[1] if '. ' in nombre_completo_practica else nombre_completo_practica
    
    st.markdown(f'<div class="main-title">{nombre_titulo.upper()}</div>', unsafe_allow_html=True)
    
    st.info("SISTEMA EN DESARROLLO :: Visualización del equipo real activada :: Modelo matemático no cargado.")
    
    st.image("Lou fondo.jpeg", caption=f"Referencia visual: {nombre_titulo}", use_container_width=True)

# 4. Renderizado de la página
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
