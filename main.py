import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="LOU Virtual - UCV", layout="wide")

# 2. Aplicación de Estilos CSS (Diseño y Fondo)
st.markdown(
    """
    <style>
    /* Fondo con imagen del laboratorio y capa blanquecina para legibilidad */
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.85), rgba(255, 255, 255, 0.85)), 
                          url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
        background-size: cover;
        background-attachment: fixed;
    }

    /* Estilo para el título principal */
    .main-title {
        font-size: 42px;
        font-weight: bold;
        color: #1E3A8A; /* Azul UCV */
        text-align: center;
        margin-top: 20px;
        padding: 10px;
    }

    /* Estilo para los subtítulos */
    .sub-title {
        font-size: 20px;
        text-align: center;
        color: #4B5563;
        margin-bottom: 30px;
    }

    /* Personalización de botones */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #f0f2f6;
        color: #1E3A8A;
        border: 1px solid #1E3A8A;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        background-color: #1E3A8A;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Lógica de Navegación
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

# --- FUNCIÓN: PANTALLA DE INICIO ---
def mostrar_inicio():
    st.markdown('<div class="main-title">Bienvenido al Laboratorio de Operaciones Unitarias Virtual</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Escuela de Ingeniería Química - Universidad Central de Venezuela</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📌 LOU 1", "📌 LOU 2"])

    with tab1:
        st.write("### Prácticas de LOU 1")
        cols1 = st.columns(2)
        practicas1 = [
            "Calibración de un Medidor de Flujo",
            "Pérdidas de Presión por Fricción en Conexiones y Tuberías",
            "Curvas Características de Bombas Centrífugas",
            "Balance en Estado No Estacionario",
            "Lechos Fluidizados"
        ]
        for i, p in enumerate(practicas1):
            with cols1[i % 2]:
                if st.button(p, key=f"btn_l1_{i}"):
                    st.session_state.page = p
                    st.rerun()

    with tab2:
        st.write("### Prácticas de LOU 2")
        cols2 = st.columns(2)
        practicas2 = [
            "Hidrodinámica de Columnas Empacadas",
            "Filtración a Presión Constante",
            "Estudio de la Destilación Diferencial",
            "Destilación Continua (Mezcla Binaria)",
            "Rectificación en Torre Rellena"
        ]
        for i, p in enumerate(practicas2):
            with cols2[i % 2]:
                if st.button(p, key=f"btn_l2_{i}"):
                    st.session_state.page = p
                    st.rerun()

# --- FUNCIÓN: VISTA DE CADA PRÁCTICA ---
def mostrar_simulador(nombre_practica):
    if st.button("⬅ Volver al Inicio"):
        st.session_state.page = 'Inicio'
        st.rerun()
    
    st.markdown(f'<div class="main-title">{nombre_practica}</div>', unsafe_allow_html=True)
    
    st.info("Actualmente se muestra la imagen del equipo. El modelo matemático está en desarrollo.")
    
    # Aquí puedes poner la imagen del laboratorio o una específica si la tienes
    st.image("Lou fondo.jpeg", caption=f"Equipo real: {nombre_practica}", use_container_width=True)

# 4. Renderizado de la página
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
