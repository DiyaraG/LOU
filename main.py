import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import time
import base64

# =============================================================================
# 1. CONFIGURACIÓN INICIAL Y CONSTANTES
# =============================================================================

# ===== 1.1 VALORES POR DEFECTO =====
modo_auto = False
p_activa = True
p_magnitud = 0.045
p_tiempo = 80

# ===== 1.2 CONFIGURACIÓN DE PÁGINA =====
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

# =============================================================================
# 2. FUNCIONES DE CÁLCULO Y MODELOS FÍSICOS
# =============================================================================

# ===== 2.1 FUNCIONES GEOMÉTRICAS =====
def get_area_transversal(geom, r, h, h_total):
    h_efectiva = max(h, 0.001)
    if geom == "Cilíndrico":
        return np.pi * (r ** 2)
    elif geom == "Cónico":
        radio_actual = (r / h_total) * h_efectiva
        return np.pi * (radio_actual ** 2)
    else:  # Esférico
        if h_efectiva <= 2 * r:
            radio_corte = np.sqrt(r**2 - (h_efectiva - r)**2)
            return np.pi * (radio_corte ** 2)
        else:
            return np.pi * (r ** 2)

# ===== 2.2 FUNCIONES DEL CONTROLADOR PID =====

def calcular_pid_adaptativo(geom, r_max, h_total):
    import math
    area_max = math.pi * (r_max ** 2)
    if geom == "Cilíndrico":
        kp = area_max * 2.5
        ki = kp / 20.0
        kd = kp * 0.1
    elif geom == "Cónico":
        kp = (area_max / 3.0) * 1.5
        ki = kp / 15.0
        kd = kp * 0.05
    else:
        kp = (area_max * 0.6) * 2.0
        ki = kp / 18.0
        kd = kp * 0.2
    return round(kp, 2), round(ki, 3), round(kd, 3)

def sintonizar_controlador_robusto(geom, r, h_t, cd_calculado, area_ori, op_tipo="Llenado"):
    """Sintonización robusta del PID CORREGIDA con ganancias más altas"""
    if geom == "Cilíndrico":
        area_t = np.pi * (r**2)
    elif geom == "Cónico":
        area_t = np.pi * (r/2)**2
    else:  # Esférico
        area_t = (2/3) * np.pi * (r**2)
    
    # Ganancias base MÁS ALTAS
    if op_tipo == "Llenado":
        kp = 25.0 * (area_t / 3.0)
        ki = 5.0 * (area_t / 3.0)
        kd = 2.0 * (area_t / 3.0)
    else:  # Vaciado
        kp = 20.0 * (area_t / 3.0)
        ki = 4.0 * (area_t / 3.0)
        kd = 1.5 * (area_t / 3.0)
    
    factor_cd = np.clip(cd_calculado / 0.61, 0.8, 1.3)
    kp = kp * factor_cd
    ki = ki * factor_cd
    
    kp = np.clip(kp, 15.0, 50.0)
    ki = np.clip(ki, 3.0, 10.0)
    kd = np.clip(kd, 1.0, 3.0)
    
    return round(kp, 2), round(ki, 3), round(kd, 2)
    
# ===== 2.3 FUNCIONES DE COEFICIENTE DE DESCARGA =====
    
def calcular_cd_inteligente(df_usr, r, h_t, geom, area_ori):
    df = pd.DataFrame(df_usr) if isinstance(df_usr, list) else df_usr
    if len(df) < 2:
        return 0.61
    try:
        t1, t2 = df["Tiempo (s)"].iloc[0], df["Tiempo (s)"].iloc[1]
        h1, h2 = df["Nivel Medido (m)"].iloc[0], df["Nivel Medido (m)"].iloc[1]
        dt = abs(t2 - t1)
        if dt == 0:
            return 0.61
        if geom == "Cilíndrico":
            v1 = np.pi*(r**2)*h1
            v2 = np.pi*(r**2)*h2
        elif geom == "Cónico":
            v1 = (1/3)*np.pi*((r/h_t)*h1)**2*h1
            v2 = (1/3)*np.pi*((r/h_t)*h2)**2*h2
        else:
            v1 = (np.pi*(h1**2)/3)*(3*r-h1)
            v2 = (np.pi*(h2**2)/3)*(3*r-h2)
        q_real = abs(v1 - v2) / dt
        h_prom = (h1 + h2) / 2
        q_teorico = area_ori * np.sqrt(2 * 9.81 * max(h_prom, 0.001))
        cd_result = q_real / q_teorico if q_teorico > 0 else 0.61
        return float(np.clip(cd_result, 0.4, 1.0))
    except:
        return 0.61

def calcular_cd_automatico(geom, d_orificio_pulg):
    """Calcula un Cd automático basado en la geometría y el diámetro del orificio."""
    if geom == "Cilíndrico":
        cd_base = 0.61
    elif geom == "Cónico":
        cd_base = 0.58
    else:  # Esférico
        cd_base = 0.55
    
    factor_diametro = np.clip(d_orificio_pulg / 1.0, 0.9, 1.1)
    cd_final = cd_base * factor_diametro
    return round(float(np.clip(cd_final, 0.45, 0.75)), 4)

def calcular_q_max_salida(d_orificio_pulg, cd=0.61, h_max=10.0):
    """Calcula el caudal máximo de salida basado en el orificio."""
    g = 9.81
    d_metros = d_orificio_pulg * 0.0254
    area_orificio = np.pi * (d_metros / 2)**2
    q_max_salida = cd * area_orificio * np.sqrt(2 * g * h_max)
    return round(float(q_max_salida), 4)

# ===== 2.4 SIMULADOR PRINCIPAL =====

def resolver_sistema_robusto(dt, h_prev, sp, geom, r, h_t, q_p_val, e_sum, e_prev, modo_op, cd_val, kp, ki, kd, d_pulgadas):
    """
    Sistema CORREGIDO - Físicamente correcto:
    - V-01 (Entrada): Controla flujo de bomba (0 a Qmax_bomba)
    - V-02 (Salida): Controla flujo por orificio (Ley de Torricelli)
    - Modo_op: "Llenado" o "Vaciado" (control bidireccional)
    """
    from math import sqrt, pi
    
    area_h = get_area_transversal(geom, r, h_prev, h_t)
    area_h = max(area_h, 0.0001)
    
    err = sp - h_prev
    
    # Acciones PID
    P = kp * err
    e_sum += err * dt
    e_sum = np.clip(e_sum, -50.0, 50.0)
    I = ki * e_sum
    D = kd * (err - e_prev) / dt if dt > 0 else 0
    D = np.clip(D, -5.0, 5.0)
    u_control = P + I + D
    
    # Parámetros de la bomba y orificio
    q_max_bomba = 2.0  # Caudal máximo de la bomba [m³/s]
    d_metros = d_pulgadas * 0.0254
    area_orificio = pi * (d_metros / 2)**2
    g = 9.81
    
    # Lógica bidireccional según el modo de operación
    if modo_op == "Llenado":
        # Control de entrada (bomba)
        flujo_base_bomba = q_max_bomba * 0.15
        if err > 0.01:  # Nivel BAJO - Necesito SUBIR
            q_entrada = flujo_base_bomba + np.clip(u_control, 0, q_max_bomba - flujo_base_bomba)
        elif err < -0.01:  # Nivel ALTO - Necesito BAJAR (raro en llenado puro)
            q_entrada = flujo_base_bomba * 0.3
        else:
            q_entrada = flujo_base_bomba
        q_entrada = np.clip(q_entrada, 0, q_max_bomba)
        
        # Salida por gravedad (Ley de Torricelli)
        if h_prev > 0.001:
            q_salida = cd_val * area_orificio * sqrt(2 * g * h_prev)
        else:
            q_salida = 0.0
        
        # Agregar perturbación
        q_entrada_total = q_entrada + q_p_val
        q_salida_total = q_salida
        
    else:  # Modo Vaciado
        # Control de salida (válvula de descarga)
        flujo_base_salida = 0.0
        if err > 0.01:  # Nivel ALTO - Necesito BAJAR más rápido
            apertura_salida = np.clip(u_control / q_max_bomba, 0.3, 1.0)
        elif err < -0.01:  # Nivel BAJO - Cerrar salida
            apertura_salida = 0.1
        else:
            apertura_salida = 0.3
        
        # Caudal teórico de salida
        if h_prev > 0.001:
            q_salida_teorica = cd_val * area_orificio * sqrt(2 * g * h_prev)
        else:
            q_salida_teorica = 0.0
        
        q_salida = apertura_salida * q_salida_teorica
        q_entrada = 0.0  # Sin entrada en modo vaciado puro
        
        # Agregar perturbación (fuga)
        q_entrada_total = q_entrada
        q_salida_total = q_salida + q_p_val
    
    # Balance de masa
    dh_dt = (q_entrada_total - q_salida_total) / area_h
    h_next = h_prev + dh_dt * dt
    h_next = np.clip(h_next, 0, h_t)
    
    # Retorna 6 valores: h_next, q_entrada, q_salida, err, e_sum, err_pasado
    return h_next, q_entrada, q_salida, err, e_sum, err

# =============================================================================
# 3. ESTILOS CSS
# =============================================================================

st.markdown("""
<style>

/* =========================================================================
   CURSORES PERSONALIZADOS - ⚙️ ENGRANAJE REALISTA GRIS
   ========================================================================= */
/* Cursor de ENGRANAJE GRIS - para el fondo general */
html, body, [data-testid="stAppViewContainer"] {
    cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='30' height='30' viewBox='0 0 24 24' fill='none' stroke='%23666666' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='2.5' fill='%23666666' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(45 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(105 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(165 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(225 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(285 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(345 12 12)' fill='%23888888' stroke='none'/><circle cx='12' cy='12' r='5.5' stroke='%23666666' stroke-width='0.8' fill='none'/></svg>") 15 15, auto !important;
}

button, a, [data-testid="stHeaderActionElements"], .stSlider {
    cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' style='font-size: 24px;'><text y='20'>⚙️</text><text x='10' y='28' style='font-size: 14px;'>👆</text></svg>") 16 16, pointer !important;
}


@keyframes wave { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.stApp {
    background-image: linear-gradient(rgba(255,255,255,0.8), rgba(240,242,245,0.85)),
                      url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
    background-size: cover; background-position: center; background-attachment: fixed;
    color: #2D3748;
}
.title-container {
    background: rgba(255,255,255,0.6); 
    border: 1px solid rgba(200,210,230,0.5);
    border-radius: 15px; 
    padding: 20px; 
    margin-bottom: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
    backdrop-filter: blur(5px);
    display: flex; 
    align-items: center; 
    justify-content: center;  
    text-align: center;       
}
.text-center-container {
    text-align: center;
    flex-grow: 1;
}
.logo-img { height: 80px; width: auto; }
.animated-title {
    font-size: 42px; font-weight: 800; margin: 0;
    background: linear-gradient(90deg, #1A202C 0%, #4A5568 25%, #3182CE 50%, #4A5568 75%, #1A202C 100%);
    background-size: 200% auto; color: transparent;
    -webkit-background-clip: text; background-clip: text;
    animation: wave 8s linear infinite; letter-spacing: 2px;
}
.sub-title { font-size: 15px; text-align: center; color: #718096; margin-top: 5px; letter-spacing: 4px; }
.stButton>button {
    width: 100%; border-radius: 10px; height: 3.8em;
    background-color: rgba(255,255,255,0.8); color: #2D3748;
    border: 1px solid #E2E8F0; transition: all 0.3s ease;
}

/* Estilo de Pestañas y Botones */
    .stTabs [data-baseweb="tab-list"] { justify-content: center; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: #A0AEC0; transition: 0.4s; }
    .stTabs [aria-selected="true"] { color: #2B6CB0 !important; background-color: white !important; border-radius: 10px; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #3182CE !important; }

/* ======================== ESTILO PARA BOTONES DE PRÁCTICAS Y MENÚ PRINCIPAL ======================== */
/* Botones de las prácticas en la pantalla de inicio */
.stButton > button {
    background: #ffffff !important;
    border: 1px solid #cbd5e0 !important;
    border-radius: 12px !important;
    color: #1a5276 !important;
    font-weight: 600 !important;
    padding: 0.8rem 1rem !important;
    height: auto !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}

/* Hover - elevación y borde dorado */
.stButton > button:hover {
    border: 1px solid #f1c40f !important;
    box-shadow: 0 6px 16px rgba(0,0,0,0.1) !important;
    transform: translateY(-3px) !important;
    background: #ffffff !important;
    color: #1a5276 !important;
}

/* Botón Menú Principal (el de volver atrás) */
div[data-testid="column"]:first-child .stButton > button {
    background: #ffffff !important;
    border: 1px solid #cbd5e0 !important;
    border-radius: 12px !important;
    color: #1a5276 !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    height: auto !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}

div[data-testid="column"]:first-child .stButton > button:hover {
    border: 1px solid #f1c40f !important;
    box-shadow: 0 6px 16px rgba(0,0,0,0.1) !important;
    transform: translateY(-3px) !important;
    background: #ffffff !important;
    color: #1a5276 !important;
}

/* ======================== TÍTULO PRINCIPAL - CON EFECTO BRILLO SUTIL ======================== */
.title-container {
    background: linear-gradient(135deg, #0d3251 0%, #1a5276 50%, #154360 100%) !important;
    border: 2px solid #f1c40f !important;
    border-radius: 20px !important;
    box-shadow: 0 8px 25px rgba(0,0,0,0.15) !important;
    position: relative;
    overflow: hidden;
    backdrop-filter: none !important;
}

/* Efecto de brillo súper sutil */
.title-container::before {
    content: '';
    position: absolute;
    top: 0;
    left: -150%;
    width: 150%;
    height: 100%;
    background: linear-gradient(90deg, 
        transparent, 
        rgba(241, 196, 15, 0.04), 
        rgba(255, 255, 255, 0.06), 
        rgba(241, 196, 15, 0.04), 
        transparent);
    animation: shine 12s ease-in-out infinite;
    pointer-events: none;
}

@keyframes shine {
    0% { left: -150%; }
    30% { left: 100%; }
    100% { left: 100%; }
}

.animated-title {
    background: linear-gradient(90deg, #f1c40f 0%, #f9e79f 50%, #f1c40f 100%) !important;
    background-size: 200% auto !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    color: transparent !important;
    animation: wave 6s linear infinite !important;
}

.sub-title {
    color: #f0f4f8 !important;
    font-weight: 500 !important;
}

/* ======================== ESTILO TARJETA PARA PESTAÑAS ======================== */
.stTabs [data-baseweb="tab"] {
    font-weight: 700 !important;
    font-size: 1.3rem !important;
    letter-spacing: 1px !important;
    transition: all 0.3s ease !important;
    padding: 0.6rem 1.5rem !important;
    background: #ffffff !important;
    border: 1px solid #cbd5e0 !important;
    border-radius: 12px !important;
    margin: 0 5px !important;
    color: #1a5276 !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}

/* Pestaña no seleccionada */
.stTabs [data-baseweb="tab"]:not([aria-selected="true"]) {
    background: #ffffff !important;
    color: #1a5276 !important;
}

/* Pestaña seleccionada */
.stTabs [aria-selected="true"] {
    background: #1a5276 !important;
    color: #f1c40f !important;
    border: 1px solid #f1c40f !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
    transform: translateY(-2px) !important;
}

/* Ocultar la línea indicadora azul */
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}

/* Línea indicadora - la puedes quitar o mantener */
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;  /* Opcional: oculta la línea azul */
}

/* Línea indicadora LED azul - más gruesa */
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #3498db !important;
    box-shadow: 0 0 15px rgba(52, 152, 219, 1), 0 0 8px rgba(52, 152, 219, 0.7) !important;
    height: 4px !important;
    border-radius: 2px !important;
}

/* Animación LED azul */
@keyframes ledPulseBlue {
    0% { text-shadow: 0 0 8px rgba(52, 152, 219, 0.5), 0 0 3px rgba(52, 152, 219, 0.3); }
    50% { text-shadow: 0 0 25px rgba(52, 152, 219, 1), 0 0 10px rgba(52, 152, 219, 0.7); }
    100% { text-shadow: 0 0 8px rgba(52, 152, 219, 0.5), 0 0 3px rgba(52, 152, 219, 0.3); }
}

/* ======================== ESTILO PARA EXPANDERS (VISIBLE SIEMPRE) ======================== */
/* Encabezado del expander - SIEMPRE VISIBLE */
.streamlit-expanderHeader {
    background-color: #1a5276 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    color: #f1c40f !important;
    border-left: 4px solid #f1c40f !important;
    transition: all 0.2s ease !important;
    padding: 0.75rem 1rem !important;
}

.streamlit-expanderHeader span {
    color: #f1c40f !important;
}

.streamlit-expanderHeader:hover {
    background-color: #2471a3 !important;
    transform: translateX(3px);
}

.streamlit-expanderHeader:hover span {
    color: #ffffff !important;
}

.streamlit-expanderContent {
    background-color: #f5f9fc !important;
    border-radius: 0 0 10px 10px !important;
    border: 1px solid #1a5276 !important;
    border-top: none !important;
    padding: 15px !important;
}

/* =========================================================================
   FORZAR CURSOR EN BOTONES - CORRECCIÓN DEFINITIVA
   ========================================================================= */
.stButton > button,
.stButton > button:hover,
.stButton > button:active,
.stButton > button:focus,
.stButton > button[kind="primary"],
.stButton > button[kind="primary"]:hover,
.stButton > button[kind="secondary"],
.stButton > button[kind="secondary"]:hover,
div[data-testid="column"]:first-child .stButton > button,
div[data-testid="column"]:first-child .stButton > button:hover {
    cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='30' height='30' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='2.5' fill='%23666666' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(45 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(105 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(165 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(225 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(285 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(345 12 12)' fill='%23888888' stroke='none'/><circle cx='12' cy='12' r='5.5' stroke='%23888888' stroke-width='0.8' fill='none'/></svg>") 15 15, pointer !important;
}

/* También forzar en las pestañas */
.stTabs [data-baseweb="tab"],
.stTabs [data-baseweb="tab"]:hover,
.stTabs [aria-selected="true"] {
    cursor: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='30' height='30' viewBox='0 0 24 24' fill='none' stroke='%23888888' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='2.5' fill='%23666666' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(45 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(105 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(165 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(225 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(285 12 12)' fill='%23888888' stroke='none'/><rect x='6.5' y='6.5' width='11' height='1.5' rx='0.5' transform='rotate(345 12 12)' fill='%23888888' stroke='none'/><circle cx='12' cy='12' r='5.5' stroke='%23888888' stroke-width='0.8' fill='none'/></svg>") 15 15, pointer !important;
}
# ===== FIN DEL CSS GLOBAL =====
    </style>
    """,
    unsafe_allow_html=True
)

# =============================================================================
# 4. NAVEGACIÓN Y PÁGINA PRINCIPAL
# =============================================================================

# ===== 4.1 INICIALIZACIÓN DE ESTADO =====
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

# ===== 4.2 PÁGINA DE INICIO CON TABS =====
def mostrar_inicio():
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

# =============================================================================
# SIMULADOR COMPLETO
# =============================================================================

def mostrar_simulador(nombre):
    # ===== ENCABEZADO COMÚN PARA TODAS LAS PRÁCTICAS =====    
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("⬅ Menú Principal"):
            st.session_state.page = 'Inicio'
            st.rerun()
    
    st.markdown(f'''
        <div class="title-container" style="justify-content: center; padding: 30px;">
            <div class="text-center-container">
                <h1 class="animated-title" style="font-size: 38px;">{nombre.upper()}</h1>
                <div class="sub-title" style="letter-spacing: 2px;">LABORATORIO DE OPERACIONES UNITARIAS</div>
            </div>
        </div>
    ''', unsafe_allow_html=True)

    # =============================================================================

    # ===== PRÁCTICA: BALANCE EN ESTADO NO ESTACIONARIO =====
    if nombre == "Balance en Estado No Estacionario":
        
        # ======================== CSS ESPECÍFICO PARA BALANCE ========================
        st.markdown("""
        <style>   

        /* Barra lateral con colores azules y amarillos - SOLO PARA BALANCE */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0d3251 0%, #1a5276 50%, #154360 100%) !important;
            border-right: 4px solid #f1c40f !important;
        }
        
        [data-testid="stSidebar"] .stMarkdown, 
        [data-testid="stSidebar"] label, 
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] span {
            color: #f0f4f8 !important;
            font-weight: 400 !important;
        }
        
        [data-testid="stSidebar"] h1, 
        [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2,
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: #f1c40f !important;
            border-bottom: 1px solid #f1c40f80;
            padding-bottom: 5px;
        }
        
        
        /* Forzar visibilidad del encabezado del expander en barra lateral */
        [data-testid="stSidebar"] .streamlit-expanderHeader {
            background-color: #1a5276 !important;
            color: #f1c40f !important;
            border-left: 4px solid #f1c40f !important;
            border-radius: 10px !important;
        }
        
        [data-testid="stSidebar"] .streamlit-expanderHeader span {
            color: #f1c40f !important;
        }
        
        [data-testid="stSidebar"] .streamlit-expanderHeader:hover {
            background-color: #2471a3 !important;
        }
        
        [data-testid="stSidebar"] .streamlit-expanderHeader:hover span {
            color: #ffffff !important;
        }
        
        /* Forzar visibilidad del contenido del expander */
        [data-testid="stSidebar"] .streamlit-expanderContent {
            background-color: #f5f9fc !important;
            border: 1px solid #1a5276 !important;
            border-top: none !important;
            border-radius: 0 0 10px 10px !important;
        }
        
        /* Forzar visibilidad de los textos dentro del expander */
        [data-testid="stSidebar"] .streamlit-expanderContent .stMarkdown,
        [data-testid="stSidebar"] .streamlit-expanderContent label,
        [data-testid="stSidebar"] .streamlit-expanderContent p,
        [data-testid="stSidebar"] .streamlit-expanderContent span {
            color: #1a5276 !important;
        }
        
        /* Botón de descarga PDF */
        [data-testid="stSidebar"] .stDownloadButton button {
            background: linear-gradient(90deg, #f1c40f, #f39c12) !important;
            color: #1a5276 !important;
            font-weight: bold !important;
            border: none !important;
            border-radius: 25px !important;
        }
        
        [data-testid="stSidebar"] .stDownloadButton button:hover {
            background: linear-gradient(90deg, #f39c12, #f1c40f) !important;
            transform: scale(1.02);
        }
        /* ======================== SLIDER CORREGIDO - SIN SALTOS ======================== */
        /* Línea del slider - fondo (parte no recorrida) */
        div[data-baseweb="slider"] > div {
            background-color: #2c3e50 !important;
            height: 4px !important;
            border-radius: 2px !important;
        }
        
        /* Parte llenada del slider (amarilla) */
        div[data-baseweb="slider"] > div > div:first-child > div {
            background: linear-gradient(90deg, #f1c40f, #f39c12) !important;
            height: 4px !important;
            border-radius: 2px !important;
        }
        
        /* Ocultar barras superpuestas */
        div[data-baseweb="slider"] > div > div > div {
            background: transparent !important;
        }
        
        /* Perilla del slider - ESTABLE, sin transform en hover */
        div[role="slider"] {
            background: #f1c40f !important;
            border: 2px solid white !important;
            width: 14px !important;
            height: 14px !important;
            border-radius: 50% !important;
            box-shadow: 0 1px 4px rgba(0,0,0,0.2) !important;
        }
        
        /* Hover - SOLO cambia el color, NO la posición ni escala */
        div[role="slider"]:hover {
            background: #f39c12 !important;
        }
        
        /* Active - sin cambios bruscos */
        div[role="slider"]:active {
            background: #e67e22 !important;
        }
   
        [data-testid="stSidebar"] .stButton button {
            background: linear-gradient(90deg, #f1c40f, #f39c12) !important;
            color: #1a5276 !important;
            font-weight: bold !important;
            border: none !important;
        }
        
        [data-testid="stSidebar"] .stButton button:hover {
            background: linear-gradient(90deg, #f39c12, #f1c40f) !important;
            transform: scale(1.02);
        }
        
        [data-testid="stSidebar"] .stAlert {
            background-color: rgba(241, 196, 15, 0.15) !important;
            border-left: 4px solid #f1c40f !important;
        }
        
        [data-testid="stSidebar"] hr {
            border-color: #f1c40f40 !important;
        }
        
        [data-testid="stSidebar"] .stCaption {
            color: #f1c40f !important;
        }

                /* ======================== FORZAR VISIBILIDAD DE EXPANDERS EN BARRA LATERAL ======================== */
        /* Esto es lo que realmente controla los expanders */
        [data-testid="stSidebar"] .stExpander {
            border: 1px solid #f1c40f !important;
            border-radius: 10px !important;
            background-color: #1a5276 !important;
            margin-bottom: 10px !important;
        }
        
        /* El encabezado del expander - LO MÁS IMPORTANTE */
        [data-testid="stSidebar"] .stExpander summary {
            background-color: #1a5276 !important;
            color: #f1c40f !important;
            border-radius: 10px !important;
            padding: 0.75rem !important;
            font-weight: bold !important;
            font-size: 1rem !important;
        }
        
        [data-testid="stSidebar"] .stExpander summary:hover {
            background-color: #2471a3 !important;
            color: #ffffff !important;
        }
        
        /* El contenido del expander */
        [data-testid="stSidebar"] .stExpander .stExpanderContent {
            background-color: #f5f9fc !important;
            border-radius: 0 0 10px 10px !important;
            padding: 15px !important;
        }
        
        /* Texto dentro del contenido */
        [data-testid="stSidebar"] .stExpander .stExpanderContent .stMarkdown,
        [data-testid="stSidebar"] .stExpander .stExpanderContent label,
        [data-testid="stSidebar"] .stExpander .stExpanderContent p,
        [data-testid="stSidebar"] .stExpander .stExpanderContent span {
            color: #1a5276 !important;
        }

        /* ======================== ESTILO TARJETA BLANCA NOTORIA CON MOVIMIENTO ======================== */
        .stColumn div[data-testid="stExpander"] {
            background: #ffffff !important;
            border: 1px solid #cbd5e0 !important;
            border-radius: 12px !important;
            margin-bottom: 15px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
            transition: all 0.3s ease !important;
        }
        
        .stColumn div[data-testid="stExpander"] summary {
            background: #ffffff !important;
            color: #1a5276 !important;
            font-weight: 600 !important;
            padding: 0.8rem 1rem !important;
            border-radius: 12px !important;
            transition: all 0.3s ease !important;
        }
        
        .stColumn div[data-testid="stExpander"]:hover {
            border: 1px solid #f1c40f !important;
            box-shadow: 0 6px 16px rgba(0,0,0,0.1) !important;
            transform: translateY(-3px) !important;
        }
        
        .stColumn div[data-testid="stExpander"] .stExpanderContent {
            background-color: #ffffff !important;
            border-radius: 0 0 12px 12px !important;
            padding: 15px !important;
            border-top: 1px solid #e2e8f0 !important;
        }
        
        /* ======================== TÍTULO DEL SIMULADOR ======================== */
        /* Contenedor del título */
        .title-container {
            background: linear-gradient(180deg, #0d3251 0%, #1a5276 50%, #154360 100%) !important;
            border: 1px solid #f1c40f !important;
            border-radius: 15px !important;
            backdrop-filter: none !important;
        }
        
        /* Título principal */
        .animated-title {
            background: none !important;
            -webkit-background-clip: unset !important;
            background-clip: unset !important;
            color: #f1c40f !important;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
        }
        
        /* Subtítulo */
        .sub-title {
            color: #f0f4f8 !important;
        }
                .sub-title {
            color: #f0f4f8 !important;
        }

       
        </style>
        </style>
        """, unsafe_allow_html=True)        
        # ======================== MARCO TEÓRICO ========================
        col_teoria1, col_teoria2, col_teoria3 = st.columns(3)

        with col_teoria1:
            with st.expander("Fundamento teórico: Ecuaciones de Conservación y Descarga", expanded=False):
                st.markdown(r"""
                La dinámica del sistema se describe mediante el **Balance Global de Masa** para un volumen de control con densidad constante ($\rho$):
                
                $$ \frac{dV}{dt} = Q_{in} - Q_{out} \pm Q_{p} $$
                
                Considerando que el volumen es función del nivel ($V = \int A(h)dh$), aplicamos la regla de la cadena para obtener la ecuación general de vaciado/llenado válida para **cualquier área transversal $A(h)$**:
                
                $$ A(h) \frac{dh}{dt} = Q_{in} - (C_d \cdot a \cdot \sqrt{2gh}) \pm Q_{p} $$
                
                **Donde:**
                - **$A(h)$**: Área de la sección transversal en función de la altura (m²)
                - **$Q_{in}$**: Flujo de entrada controlado (m³/s)
                - **$Q_{out}$**: Flujo de salida basado en la **Ley de Torricelli** (m³/s)
                - **$C_d$**: Coeficiente de descarga (adimensional)
                - **$a$**: Área del orificio de salida (m²)
                - **$Q_{p}$**: Flujo de perturbación o falla (m³/s)
                """)

        with col_teoria2:
            with st.expander("Teoría: Estrategia de control PID Robusto", expanded=False):
                st.markdown(r"""
                El "cerebro" de la simulación es un controlador **Proporcional-Integral-Derivativo (PID)** con **Anti-Windup**, cuya acción de control $u(t)$ busca minimizar el error ($e = SP - h$):
                
                $$ u(t) = K_p e(t) + K_i \int_{0}^{t} e(\tau) d\tau + K_d \frac{de(t)}{dt} $$
                
                **Mejoras implementadas para robustez:**
                - **Anti-Windup:** Evita que la integral se sature cuando la válvula está al límite
                - **Sintonización Ziegler-Nichols adaptada:** Parámetros optimizados para rechazo de perturbaciones
                - **Límites en derivativo:** Reduce el ruido en la señal de control
                
                **Funciones de los parámetros sintonizables:**
                - **$K_p$ (Proporcional):** Proporciona una respuesta inmediata al error actual
                - **$K_i$ (Integral):** Elimina el error residual (offset) acumulando desviaciones pasadas; es vital para el rechazo de perturbaciones ($Q_p$)
                - **$K_d$ (Derivativo):** Anticipa el comportamiento futuro del error para evitar sobrepicos y estabilizar la respuesta
                
                En este simulador, las ecuaciones se resuelven numéricamente mediante el **Método de Euler** con un paso de tiempo $\Delta t = 1.0$ s.
                """)

        with col_teoria3:
            with st.expander("Criterios de Desempeño (IAE/ITAE)", expanded=False):
                st.markdown(r"""
                Para evaluar la eficiencia del control, se utilizan métricas integrales del error $e(t) = SP - PV$:
                
                **1. IAE (Integral del Error Absoluto):**
                $$IAE = \int_{0}^{t} |e(t)| dt$$
                Mide el rendimiento acumulado. Es ideal para evaluar la respuesta general del sistema.
                
                **2. ITAE (Integral del Tiempo por el Error Absoluto):**
                $$ITAE = \int_{0}^{t} t \cdot |e(t)| dt$$
                **Penaliza errores que duran mucho tiempo.** Es el criterio más estricto en tesis de control porque asegura que el sistema se estabilice rápido.
                
                **Interpretación práctica:**
                - **IAE bajo** → Respuesta rápida sin errores grandes
                - **ITAE bajo** → El sistema se estabiliza rápidamente sin errores prolongados
                """)

        # ======================== DIAGRAMA DEL PROCESO ========================
        with st.expander("Diagrama del Proceso", expanded=True):
            col_img = st.columns([1, 5, 1])[1]
            with col_img:
                if os.path.exists("Captura de pantalla 2026-03-29 163125 (1).png"):
                    st.image("Captura de pantalla 2026-03-29 163125 (1).png", use_container_width=True)
                else:
                    st.info("📍 El diagrama del sistema se mostrará aquí.")
                    
        # ======================== BARRA LATERAL ========================
        st.sidebar.header("⚙️ Configuración del Sistema")
        
        with st.sidebar.container(border=True):
            op_tipo = st.sidebar.selectbox("Operación Principal", ["Llenado", "Vaciado"])
            geom_tanque = st.sidebar.selectbox("Geometría del Equipo", ["Cilíndrico", "Cónico", "Esférico"])
        
        with st.sidebar.expander("Especificaciones del Tanque", expanded=True):
            r_max = st.number_input("Radio de Diseño (R) [m]", value=1.0, min_value=0.1, step=0.1)
            h_sug = 3.0 if geom_tanque != "Esférico" else r_max * 2
            h_total = st.number_input("Altura de Diseño (H) [m]", value=float(h_sug), min_value=0.1, step=0.5)
            sp_nivel = st.slider("Consigna de Nivel (Setpoint) [m]", 0.1, float(h_total), float(h_total/2))

        with st.sidebar.expander(" Bomba de Alimentación", expanded=True):
            q_max_bomba = st.number_input("Caudal máximo de bomba [m³/s]", value=2.0, min_value=0.0000833, max_value=5.0, step=0.0001,format="%.6f")
            st.caption("💡 Capacidad máxima de la bomba de entrada")        
        
        with st.sidebar.expander("Dimensiones de Salida", expanded=True):
            d_pulgadas = st.number_input("Diámetro del Orificio (pulgadas)", value=1.0, min_value=0.1, step=0.1)
            d_metros = d_pulgadas * 0.0254
            area_orificio = np.pi * (d_metros / 2)**2
            st.caption(f"Área calculada: {area_orificio:.6f} m²")
        
        # Cálculo de Cd y Qmax_salida
        cd_automatico = calcular_cd_automatico(geom_tanque, d_pulgadas)
        q_max_salida = calcular_q_max_salida(d_pulgadas, cd_automatico, h_total)
        st.session_state['cd_calculado'] = cd_automatico
        
        with st.sidebar.expander("🛡️ Escenario de Perturbación ($Q_p$)"):
            p_activa = st.toggle("Simular Falla/Fuga Externas", value=True)
            if p_activa:
                p_tipo = st.selectbox("Tipo de Perturbación", ["Entrada", "Salida (Fuga)"])
                p_tipo = "Entrada" if p_tipo == "Entrada" else "Salida"
                p_magnitud = st.number_input("Magnitud Qp [m³/s]", value=0.5, min_value=0.1, max_value=3.0, step=0.1, format="%.2f")
                p_tiempo = st.slider("Inicio de perturbación [s]", 0, 500, 100)
            else:
                p_magnitud = 0.0
                p_tiempo = 0
                p_tipo = "Entrada"

        with st.sidebar.expander("Parámetros del Controlador PID "):
            cd_actual = st.session_state.get('cd_calculado', 0.61)
            kp_sug, ki_sug, kd_sug = sintonizar_controlador_robusto(
                geom_tanque, r_max, h_total, cd_actual, area_orificio, op_tipo
            )
            modo_auto = st.checkbox("🎯 Modo  Auto-sintonía optimizada", value=True)
            if modo_auto:
                st.success(f"💡 PID optimizado para {op_tipo} (Cd={cd_actual:.3f})")
                st.caption(f"Kp={kp_sug} | Ki={ki_sug} | Kd={kd_sug}")
                kp_val = st.number_input("Kp (robusto)", value=kp_sug, key="kp_asist")
                ki_val = st.number_input("Ki (robusto)", value=ki_sug, format="%.3f", key="ki_asist")
                kd_val = st.number_input("Kd (robusto)", value=kd_sug, format="%.3f", key="kd_asist")
            else:
                st.info(f"✍️ Modo Manual - {op_tipo}")
                if op_tipo == "Llenado":
                    kp_default, ki_default, kd_default = 12.0, 2.5, 0.8
                else:
                    kp_default, ki_default, kd_default = 8.0, 1.5, 0.5
                kp_val = st.number_input("Kp", value=kp_default, step=1.0, key="kp_man")
                ki_val = st.number_input("Ki", value=ki_default, step=0.5, format="%.3f", key="ki_man")
                kd_val = st.number_input("Kd", value=kd_default, step=0.1, format="%.3f", key="kd_man")
            tiempo_ensayo = st.slider("Tiempo de simulación [s]", 60, 1000, 300)      
        
        with st.sidebar.expander("Cargar Datos Experimentales"):
            st.caption("⚠️ Ingresa el nivel en **centímetros (cm)**")
            df_exp_default = pd.DataFrame({
                "Tiempo (s)": [0, 60, 120, 180, 240, 300],
                "Nivel Medido (cm)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            })
            datos_usr = st.data_editor(df_exp_default, num_rows="dynamic")
            mostrar_ref = st.checkbox("Mostrar referencia en gráfica", value=True)
            
            col_cd1, col_cd2 = st.columns(2)
            with col_cd1:
                if op_tipo == "Vaciado":
                    if st.button("Calcular Cd desde datos", use_container_width=True):
                        if not isinstance(datos_usr, pd.DataFrame):
                            datos_usr = pd.DataFrame(datos_usr)
                        
                        if "Nivel Medido (cm)" in datos_usr.columns and len(datos_usr) >= 2:
                            cd_calculado = calcular_cd_inteligente(
                                datos_usr, r_max, h_total, geom_tanque, area_orificio
                            )
                            st.session_state['cd_calculado'] = cd_calculado
                            st.success(f"✅ Cd calculado: {cd_calculado:.4f}")
                        else:
                            st.warning("⚠️ Ingresa al menos 2 datos")
                else:
                    st.button("Calcular Cd desde datos", disabled=True, 
                             help="El Cd solo se calcula en proceso de Vaciado", 
                             use_container_width=True)
                    st.caption("ℹ️ Cd solo válido para Vaciado")
            
            with col_cd2:
                if st.button("🔄 Usar Cd teórico", use_container_width=True):
                    st.session_state['cd_calculado'] = cd_automatico
                    st.success(f"✅ Cd teórico: {cd_automatico:.4f}")
        
        with st.sidebar.expander("Parámetros Calculados Automáticamente", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Qmax Bomba", f"{q_max_bomba:.2f}")
            with col2:
                st.metric("Qmax Salida", f"{q_max_salida:.4f}")
            with col3:
                st.metric("Cd", f"{cd_automatico:.4f}")
            
            ajuste_manual = st.checkbox("Ajuste manual de parámetros", value=False)
            if ajuste_manual:
                q_max_bomba_manual = st.number_input("Qmax Bomba Manual [m³/s]", value=q_max_bomba, min_value=0.5, max_value=5.0, step=0.5)
                cd_manual = st.number_input("Cd Manual", value=cd_automatico, min_value=0.30, max_value=0.90, step=0.01, format="%.4f")
                st.session_state['cd_calculado'] = cd_manual
                q_max_bomba = q_max_bomba_manual
        
        st.sidebar.markdown("---")
        
       
# ======================== BIBLIOTECA TÉCNICA ========================
        st.sidebar.subheader("📚 Biblioteca Técnica")
        
        # Primer contenedor: Práctica Física
        with st.sidebar.container(border=True):
            nombre_pdf = "Guia_Practica_UCV.pdf"
            if os.path.exists(nombre_pdf):
                with open(nombre_pdf, "rb") as f:
                    st.sidebar.download_button(
                        label="📥 Descargar Práctica Física (PDF)",
                        data=f,
                        file_name="Guia_Practica_EIQ_UCV.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.sidebar.caption("📖 Práctica de laboratorio Físico")
            else:
                st.sidebar.warning("⚠️ Archivo 'Guia_Practica_UCV.pdf' no encontrado en el directorio")
                st.sidebar.caption("💡 Coloca el PDF en la misma carpeta que el script")
        
        # Segundo contenedor: Manual de Práctica Virtual
        with st.sidebar.container(border=True):
            nombre_pdf = "Manual_UCV.pdf"
            if os.path.exists(nombre_pdf):
                with open(nombre_pdf, "rb") as f:
                    st.sidebar.download_button(
                        label="📥 Descargar Manual de Práctica Virtual (PDF)",
                        data=f,
                        file_name="Manual_EIQ_UCV.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.sidebar.caption("📖 Manual completo de la práctica de laboratorio")
            else:
                st.sidebar.warning("⚠️ Archivo 'Manual_UCV.pdf' no encontrado en el directorio")
                st.sidebar.caption("💡 Coloca el PDF en la misma carpeta que el script")
        
        # Tercer contenedor: Práctica Virtual
        with st.sidebar.container(border=True):
            nombre_pdf = "PracticaV_UCV.pdf"
            if os.path.exists(nombre_pdf):
                with open(nombre_pdf, "rb") as f:
                    st.sidebar.download_button(
                        label="📥 Descargar Práctica Virtual (PDF)",
                        data=f,
                        file_name="PracticaV_EIQ_UCV.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.sidebar.caption("📖 Práctica Virtual de laboratorio")
            else:
                st.sidebar.warning("⚠️ Archivo 'PracticaV_UCV.pdf' no encontrado en el directorio")
                st.sidebar.caption("💡 Coloca el PDF en la misma carpeta que el script")
        
        st.sidebar.markdown("---")

        # ======================== BOTONES INICIAR Y RESET ========================
        col_btn1, col_btn2 = st.sidebar.columns(2)
        with col_btn1:
            iniciar_sim = st.button("▶️ Iniciar", use_container_width=True, type="primary")
        with col_btn2:
            if st.button("🔄 Reset", use_container_width=True, type="secondary"):
                st.session_state.ejecutando = False
                st.rerun()
        
        if 'ejecutando' not in st.session_state:
            st.session_state.ejecutando = False
    
        # ======================== INICIALIZACIÓN ========================
        if iniciar_sim:
            st.session_state.ejecutando = True
            cd_para_usar = st.session_state.get('cd_calculado', 0.61)
            try:
                if modo_auto:
                    st.session_state['kp_ejecucion'] = kp_val
                    st.session_state['ki_ejecucion'] = ki_val
                    st.session_state['kd_ejecucion'] = kd_val
                    st.session_state['cd_final'] = cd_para_usar
                else:
                    st.session_state['kp_ejecucion'] = kp_val
                    st.session_state['ki_ejecucion'] = ki_val
                    st.session_state['kd_ejecucion'] = kd_val
                    st.session_state['cd_final'] = cd_para_usar
            except:
                st.session_state['kp_ejecucion'] = 18.0
                st.session_state['ki_ejecucion'] = 3.5
                st.session_state['kd_ejecucion'] = 1.5
                st.session_state['cd_final'] = cd_para_usar
    
        # ======================== SIMULACIÓN PRINCIPAL ========================
        if not st.session_state.ejecutando:
            st.info("💡 Ajusta los parámetros en la barra lateral y pulsa 'Iniciar Simulación Robusta'")
        else:
            col_graf, col_met = st.columns([2, 1])
            
            with col_graf:
                st.subheader("Monitor del Proceso - Control Robusto Anti-Perturbaciones")
                placeholder_tanque = st.empty()
                st.subheader("📈 Tendencia Temporal")
                placeholder_grafico = st.empty()
                st.subheader("🔧 Acción de las Válvulas")
                placeholder_valvulas = st.empty()
                st.markdown("---")
                st.subheader(" Comparativa: Modelo Teórico vs Datos Experimentales")
                placeholder_comparativa = st.empty()
            
            with col_met:
                st.subheader(" Métricas de Control")
                
                kp_show = st.session_state.get('kp_ejecucion', 12.0)
                ki_show = st.session_state.get('ki_ejecucion', 2.5)
                cd_show = st.session_state.get('cd_final', 0.61)
                
                st.write(f"**Parámetros Activos:**")
                st.caption(f"Proceso: {op_tipo} | Qmax: {q_max_bomba:.2f} m³/s | Cd: {cd_show:.4f}")
                st.caption(f"Kp: {kp_show} | Ki: {ki_show} | Kd: {st.session_state.get('kd_ejecucion', 0.8)}")
                st.markdown("---")
                
                placeholder_iae = st.empty()
                placeholder_itae = st.empty()
                placeholder_iae.metric("IAE (Error Acumulado)", "0.00")
                placeholder_itae.metric("ITAE (Criterio Tesis)", "0.00")
                
                st.markdown("---")
                m_h = st.empty()
                m_e = st.empty()
                m_qin = st.empty()
                m_qout = st.empty()
                m_h.metric("Nivel PV [m]", "0.000")
                m_e.metric("Error [m]", "0.000")
                m_qin.metric("Flujo Entrada [m³/s]", "0.000")
                m_qout.metric("Flujo Salida [m³/s]", "0.000")
    
            # Preparación
            status_placeholder = st.empty()
            dt = 1.0
            vector_t = np.arange(0, tiempo_ensayo, dt)
            h_log, qin_log, qout_log, e_log = [], [], [], []
            h_corrida = 0.001 if op_tipo == "Llenado" else h_total * 0.95
            valor_presente = h_corrida
            error_presente = 0.0
            err_int, err_pasado = 0.0, 0.0
            iae_acumulado, itae_acumulado = 0.0, 0.0
            
            if not isinstance(datos_usr, pd.DataFrame):
                datos_usr = pd.DataFrame(datos_usr)
            if "Nivel Medido (cm)" in datos_usr.columns and len(datos_usr) > 0:
                t_exp = datos_usr["Tiempo (s)"].values
                h_exp = [val / 100 for val in datos_usr["Nivel Medido (cm)"].values]
                tiene_datos_exp = True
            else:
                t_exp = []
                h_exp = []
                tiene_datos_exp = False
            
            barra_p = st.progress(0)
            cd_para_simular = st.session_state.get('cd_final', 0.61)
    
            for i, t_act in enumerate(vector_t):
                status_placeholder.markdown("**CONTROL ACTIVADO - PROCESANDO...**")

                if p_activa and t_act >= p_tiempo:
                    q_p_inst = p_magnitud
                else:
                    q_p_inst = 0.0
                
                k_p = st.session_state.get('kp_ejecucion', 18.0)
                k_i = st.session_state.get('ki_ejecucion', 3.5)
                k_d = st.session_state.get('kd_ejecucion', 1.5)
                
                h_corrida, q_entrada, q_salida, e_inst, err_int, err_pasado = resolver_sistema_robusto(
                    dt, h_corrida, sp_nivel, geom_tanque, r_max, h_total, q_p_inst,
                    err_int, err_pasado, op_tipo, cd_para_simular, k_p, k_i, k_d, d_pulgadas
                )
                
                valor_presente = h_corrida
                error_presente = e_inst
                iae_acumulado += abs(e_inst) * dt
                itae_acumulado += (t_act * abs(e_inst)) * dt
                
                h_log.append(h_corrida)
                qin_log.append(q_entrada)
                qout_log.append(q_salida)
                e_log.append(e_inst)
                
                m_h.metric("Nivel PV [m]", f"{valor_presente:.3f}")
                m_e.metric("Error [m]", f"{error_presente:.4f}")
                m_qin.metric("Flujo Entrada [m³/s]", f"{q_entrada:.3f}")
                m_qout.metric("Flujo Salida [m³/s]", f"{q_salida:.3f}")
                placeholder_iae.metric("IAE (Error Acumulado)", f"{iae_acumulado:.2f}")
                placeholder_itae.metric("ITAE (Criterio Tesis)", f"{itae_acumulado:.2f}")
                
                # VISUALIZACIÓN DEL TANQUE
                fig_t, ax_t = plt.subplots(figsize=(7, 5))
                ax_t.set_axis_off()
                ax_t.set_xlim(-r_max*3, r_max*3)
                ax_t.set_ylim(-0.8, h_total*1.3)
                
                if abs(e_inst) < 0.05:
                    color_agua = '#27ae60'
                elif abs(e_inst) < 0.15:
                    color_agua = '#f39c12'
                else:
                    color_agua = '#e74c3c'
                
                if geom_tanque == "Cilíndrico":
                    c_in_x, c_in_y = -r_max, h_total*0.8
                    c_out_x, c_out_y = r_max, 0.1
                    ax_t.plot([-r_max, -r_max, r_max, r_max], [h_total, 0, 0, h_total], color='#2c3e50', lw=5, zorder=2)
                    ax_t.add_patch(plt.Rectangle((-r_max, 0), 2*r_max, h_corrida, color=color_agua, alpha=0.85, zorder=1))
                    # Flechas de flujo
                    if q_entrada > 0:
                        ax_t.annotate('', xy=(-r_max-1.5, h_corrida*0.7), xytext=(-r_max-0.3, h_corrida*0.7),
                                    arrowprops=dict(arrowstyle='->', lw=3, color='blue'))
                    if q_salida > 0:
                        ax_t.annotate('', xy=(r_max+1.5, 0.3), xytext=(r_max+0.3, 0.3),
                                    arrowprops=dict(arrowstyle='->', lw=3, color='red'))
                    
                elif geom_tanque == "Cónico":
                    c_in_x, c_in_y = -(r_max/h_total)*(h_total*0.8), h_total*0.8
                    c_out_x, c_out_y = 0, 0
                    ax_t.plot([-r_max, 0, r_max], [h_total, 0, h_total], color='#2c3e50', lw=5, zorder=2)
                    if h_corrida > 0:
                        radio_h = (r_max / h_total) * h_corrida
                        vertices = [[-radio_h, h_corrida], [radio_h, h_corrida], [0, 0]]
                        ax_t.add_patch(plt.Polygon(vertices, color=color_agua, alpha=0.85, zorder=1))
                    
                else:  # Esférico
                    import math
                    c_in_y = h_total * 0.7
                    c_in_x = -math.sqrt(abs(r_max**2 - (c_in_y - r_max)**2))
                    c_out_x, c_out_y = 0, 0
                    agua = plt.Circle((0, r_max), r_max, color=color_agua, alpha=0.85, zorder=1)
                    ax_t.add_patch(agua)
                    recorte = plt.Rectangle((-r_max, 0), 2*r_max, h_corrida, transform=ax_t.transData)
                    agua.set_clip_path(recorte)
                    ax_t.add_patch(plt.Circle((0, r_max), r_max, color='#2c3e50', fill=False, lw=5, zorder=2))
                
                # Tuberías y válvulas
                ax_t.add_patch(plt.Rectangle((c_in_x - 1.5, c_in_y - 0.1), 1.5, 0.2, color='silver', zorder=0))
                ax_t.add_patch(plt.Polygon([[c_in_x-1, c_in_y+0.2], [c_in_x-1, c_in_y-0.2], [c_in_x-0.6, c_in_y]], color='#2c3e50', zorder=2))
                ax_t.add_patch(plt.Polygon([[c_in_x-0.2, c_in_y+0.2], [c_in_x-0.2, c_in_y-0.2], [c_in_x-0.6, c_in_y]], color='#2c3e50', zorder=2))
                ax_t.text(c_in_x-0.6, c_in_y+0.4, "V-01", ha='center', fontsize=9, fontweight='bold', color='blue')
                
                if geom_tanque == "Cilíndrico":
                    ax_t.add_patch(plt.Rectangle((c_out_x, c_out_y - 0.1), 1.5, 0.2, color='silver', zorder=0))
                    vs_x, vs_y = c_out_x + 0.8, c_out_y
                else:
                    ax_t.add_patch(plt.Rectangle((c_out_x - 0.1, -0.6), 0.2, 0.6, color='silver', zorder=0))
                    vs_x, vs_y = c_out_x, -0.4
                
                ax_t.add_patch(plt.Polygon([[vs_x-0.25, vs_y+0.2], [vs_x-0.25, vs_y-0.2], [vs_x, vs_y]], color='#2c3e50', zorder=2))
                ax_t.add_patch(plt.Polygon([[vs_x+0.25, vs_y+0.2], [vs_x+0.25, vs_y-0.2], [vs_x, vs_y]], color='#2c3e50', zorder=2))
                offset_t = 0.4 if geom_tanque == "Cilíndrico" else 0
                ax_t.text(vs_x + offset_t, vs_y - 0.5, "V-02", ha='center', fontsize=9, fontweight='bold', color='red')
                
                ax_t.axhline(y=sp_nivel, color='red', ls='--', lw=2, zorder=3, alpha=0.8)
                ax_t.text(-r_max*2.8, sp_nivel + 0.05, f"SP: {sp_nivel:.2f}m", color='red', fontweight='bold')
                ax_t.text(0, h_total * 1.2, f"PV: {h_corrida:.3f} m", ha='center', fontweight='bold',
                         bbox=dict(facecolor='white', alpha=0.9, edgecolor='#1a5276', boxstyle='round'))
                
                if p_activa and t_act >= p_tiempo:
                    ax_t.text(0, -0.5, f"⚠️ PERTURBACIÓN ACTIVA", ha='center', color='orange', fontweight='bold')
                
                placeholder_tanque.pyplot(fig_t)
                plt.close(fig_t)
                
                # Gráfica de tendencia
                fig_tr, ax_tr = plt.subplots(figsize=(8, 3.5))
                ax_tr.plot(vector_t[:i+1], h_log, color='#2980b9', lw=2, label='Nivel (h) - Control Robusto')
                ax_tr.axhline(y=sp_nivel, color='red', ls='--', alpha=0.5, label='Setpoint')
                if p_activa and p_tiempo > 0 and t_act >= p_tiempo:
                    ax_tr.axvspan(p_tiempo, tiempo_ensayo, alpha=0.1, color='orange', label='Zona con Perturbación')
                ax_tr.set_xlabel('Tiempo [s]')
                ax_tr.set_ylabel('Altura [m]')
                ax_tr.legend(loc='upper right', fontsize='x-small')
                ax_tr.set_xlim(0, tiempo_ensayo)
                ax_tr.set_ylim(0, h_total * 1.1)
                ax_tr.grid(True, alpha=0.2)
                placeholder_grafico.pyplot(fig_tr)
                plt.close(fig_tr)
                
                # Gráfico de válvulas (V-01 y V-02)
                fig_v, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 3))
                ax1.step(vector_t[:i+1], qin_log, where='post', color='blue', lw=2)
                ax1.set_ylabel('Q entrada [m³/s]')
                ax1.set_ylim(0, q_max_bomba * 1.1)
                ax1.grid(True, alpha=0.2)
                ax1.set_title('V-01 (Entrada)')
                
                ax2.step(vector_t[:i+1], qout_log, where='post', color='red', lw=2)
                ax2.set_ylabel('Q salida [m³/s]')
                ax2.set_xlabel('Tiempo [s]')
                ax2.set_ylim(0, q_max_bomba * 1.1)
                ax2.grid(True, alpha=0.2)
                ax2.set_title('V-02 (Salida)')
                plt.tight_layout()
                placeholder_valvulas.pyplot(fig_v)
                plt.close(fig_v)
                
                # Comparativa
                fig_comp, ax_comp = plt.subplots(figsize=(8, 4))
                ax_comp.plot(vector_t[:i+1], h_log, color='#1f77b4', lw=2, label='Simulación Robusta')
                if mostrar_ref and tiene_datos_exp and len(t_exp) > 0:
                    ax_comp.scatter(t_exp, h_exp, color='red', marker='x', s=100, label='Datos Experimentales')
                ax_comp.set_title("Validación de Resultados")
                ax_comp.set_xlabel("Tiempo [s]")
                ax_comp.set_ylabel("Nivel [m]")
                ax_comp.set_ylim(0, h_total * 1.1)
                ax_comp.grid(True, alpha=0.3)
                ax_comp.legend(loc='lower right')
                placeholder_comparativa.pyplot(fig_comp)
                plt.close(fig_comp)
                
                time.sleep(0.01)
                barra_p.progress((i + 1) / len(vector_t))
            
            status_placeholder.empty()
            st.success(f"✅ Simulación completada - El controlador mantuvo el nivel ante las perturbaciones")
            st.balloons()
            
            # ======================== ANÁLISIS FINAL ========================
            st.markdown("---")
            st.subheader("📈 Análisis de Respuesta - Control Robusto Anti-Perturbaciones")
            col_an1, col_an2 = st.columns([2, 1])
            with col_an1:
                fig_amp, ax_amp = plt.subplots(figsize=(10, 5))
                ax_amp.plot(vector_t, h_log, color='#1f77b4', lw=2.5, label='Respuesta del Sistema (PV)')
                ax_amp.axhline(y=sp_nivel, color='#d62728', linestyle='--', lw=2, label='Setpoint')
                if p_activa and p_tiempo > 0:
                    ax_amp.axvline(x=p_tiempo, color='orange', linestyle='--', alpha=0.7)
                    ax_amp.axvspan(p_tiempo, tiempo_ensayo, alpha=0.08, color='orange')
                ax_amp.set_title("Respuesta Transitoria del Lazo de Control Robusto")
                ax_amp.set_xlabel("Tiempo (s)")
                ax_amp.set_ylabel("Amplitud (m)")
                ax_amp.grid(True, which='both', linestyle='--', alpha=0.5)
                ax_amp.legend(loc='lower right')
                st.pyplot(fig_amp)
                plt.close(fig_amp)
            
            with col_an2:
                st.info("**Interpretación del Control Robusto:**")
                sobrepico = ((max(h_log) - sp_nivel) / sp_nivel) * 100 if max(h_log) > sp_nivel else 0
                st.metric("Sobrepico Máximo", f"{sobrepico:.2f} %")
                st.metric("IAE Final", f"{iae_acumulado:.2f}")
                st.metric("ITAE Final", f"{itae_acumulado:.2f}")
            
            # Resumen y descarga
            df_final = pd.DataFrame({
                "Tiempo [s]": vector_t,
                "Nivel [m]": h_log,
                "Q_entrada [m³/s]": qin_log,
                "Q_salida [m³/s]": qout_log,
                "Error [m]": e_log,
                "Kp_Usado": [st.session_state.get('kp_ejecucion', 18.0)] * len(vector_t),
                "Ki_Usado": [st.session_state.get('ki_ejecucion', 3.5)] * len(vector_t),
                "Kd_Usado": [st.session_state.get('kd_ejecucion', 1.5)] * len(vector_t)
            })
            
            st.subheader(" Resumen de Datos y Estabilidad del Control Robusto")
            col_tab, col_res = st.columns([2, 1])
            with col_tab:
                st.dataframe(df_final.tail(10).style.format("{:.4f}"), use_container_width=True)
            with col_res:
                err_f = abs(sp_nivel - h_log[-1]) if len(h_log) > 0 else 0
                st.metric("Error Residual Final", f"{err_f:.4f} m")
                st.download_button(
                    label="📥 Descargar Reporte de Simulación (CSV)",
                    data=df_final.to_csv(index=False),
                    file_name=f"resultados_robustos_{geom_tanque}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            if err_f < 0.05:
                st.success(f"✅ Control excelente - Error final < 5%")
            else:
                st.warning(f"⚠️ Error residual de {err_f:.3f} m. Aumente Ki para mejorar.")
                
    # ======================== CASOS ESPECÍFICOS ========================

    # ===== PRÁCTICAS LOU I (TEÓRICAS) =====

    # ==== PRACTICA 1 Calibración de un Medidor de Flujo =====
    
    elif nombre == "Calibración de un Medidor de Flujo":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "Manual de la Práctica 1. Calibración de un Medidor de Flujo..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label="📥 Descargar Práctica 1 (PDF)", data=f, file_name="Manual_Practica1_Calibracion.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Calibración de Medidores de Flujo
                
                Se presentan los conceptos fundamentales para la **calibración de medidores de flujo**, específicamente enfocándose en los tubos de Venturi y Pitot para fluidos compresibles como el aire.
                
                ### 1. Medidores de Flujo y Principio de Bernoulli
                Los medidores de flujo son dispositivos diseñados para cuantificar el caudal de un fluido que circula por una tubería. Su funcionamiento se fundamenta en el **balance de energía de Bernoulli**, que relaciona la presión, la velocidad y la altura del fluido en distintos puntos del sistema.
                
                ### 2. Tubo de Venturi
                Es un instrumento que genera una **caída de presión** controlada al reducir el área de flujo en una sección llamada "garganta". Esta diferencia de presión se utiliza para determinar el caudal de operación a través de una **constante de proporcionalidad (K)**.
                
                **Relación fundamental de calibración:**
                $$Q = K \cdot \sqrt{\Delta h}$$
                
                Donde $Q$ es el caudal y $\Delta h$ es la diferencia de altura manométrica.
                
                ### 3. Tubo de Pitot
                Se utiliza para medir la **velocidad puntual** ($U_0$) del fluido en coordenadas radiales específicas dentro de la tubería. Su principio se basa en la diferencia entre la **presión estática** y la **presión dinámica**.
                
                **Fórmula de velocidad puntual:**
                $$U_0 = C \cdot \sqrt{\frac{2 \cdot \Delta P_{tp}}{\rho}}$$
                
                Donde $C$ es el coeficiente del tubo (típicamente 0,98), $\Delta P_{tp}$ es la diferencia de presión y $\rho$ la densidad del fluido.
                
                ### 4. Régimen de Flujo y Perfiles de Velocidad
                El comportamiento del fluido depende del **Número de Reynolds ($Re$)**, el cual permite clasificar el régimen como **laminar o turbulento**. Esta clasificación determina la forma del **perfil de velocidad**, que describe cómo varía la velocidad desde el centro hasta las paredes de la tubería.
                
                **Número de Reynolds:**
                $$Re = \frac{D \cdot U_m \cdot \rho}{\mu}$$
                
                Donde $D$ es el diámetro, $U_m$ la velocidad media, $\rho$ la densidad y $\mu$ la viscosidad.
                
                ### 5. Calibración y Desviación
                La calibración consiste en comparar los caudales determinados experimentalmente (mediante la integración de velocidades del Pitot) frente a los valores teóricos del Venturi. La validez del modelo se verifica mediante el **porcentaje de desviación**.
                
                **Caudal Teórico (aproximación):**
                $$U_m = 0,817 \cdot U_{max}$$
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("1.1 CALIBRACIÓN DE UN MEDIDOR DE FLUJO.png", use_container_width=True)

    # ==================== PRACTICA 2 Pérdidas de Presión por Fricción ==============
    
    elif nombre == "Pérdidas de Presión por Fricción":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "Manual de la Práctica 2. Determinación de las Pérdidas de Presión por Fricción en Conexiones y Tramos de Tuberías..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="Manual_Practica2_PerdidasFriccion.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ### Pérdidas de Presión por Fricción
                
                Este marco teórico describe los principios fundamentales para el estudio del comportamiento de un fluido incompresible (agua) dentro de un sistema de tuberías, centrándose en las pérdidas de energía por fricción.
                
                ### 1. Balance de Energía y Pérdidas de Presión
                El estudio del flujo se basa en el **Balance de Energía** (Ecuación de Bernoulli), que permite analizar las transformaciones entre energía cinética, potencial y de presión. Al circular un fluido por tramos de tubería, accesorios y medidores, ocurre una **pérdida de presión estática** debido a la fricción.
                
                Estas pérdidas se clasifican en:
                *   **Pérdidas Mayores:** Ocurren en tramos rectos de tubería debido a la fricción continua con las paredes.
                *   **Pérdidas Menores:** Se generan por cambios en la geometría del flujo en **accesorios** como codos, expansiones y contracciones.
                
                ### 2. Número de Reynolds ($Re$)
                Es un parámetro adimensional que permite caracterizar el **régimen de flujo**. Según la experiencia de Reynolds, el flujo puede ser:
                *   **Laminar:** Movimiento ordenado en capas ($Re < 2100$)
                *   **Transitorio:** Inestabilidad entre regímenes ($2100 \leq Re \leq 4000$)
                *   **Turbulento:** Movimiento caótico y con mezcla intensa ($Re > 4000$)
                
                **Fórmula fundamental:**
                $$Re = \frac{D \cdot U \cdot \rho}{\mu}$$
                
                Donde $D$ es el diámetro (m), $U$ la velocidad media (m/s), $\rho$ la densidad (kg/m³) y $\mu$ la viscosidad dinámica (Pa·s).
                
                ### 3. Cálculo de Pérdidas por Fricción ($H_f$)
                Las pérdidas de carga experimentales ($H_{fe}$) se determinan a partir de la diferencia de presión medida en las tomas manométricas de cada accesorio o tramo.
                
                **Diferencia de presión experimental ($\Delta P$):**
                $$\Delta P = (\rho_m - \rho) \cdot g \cdot H \cdot 0.01$$
                
                *(Basado en la relación entre altura manométrica $H$ en cm y densidad del fluido manométrico $\rho_m$)*.
                
                **Pérdidas teóricas (Ecuación de Darcy-Weisbach):**
                $$H_f = f_d \cdot \frac{L}{D} \cdot \frac{U^2}{2g}$$
                
                Donde:
                - $f_d$ = Factor de fricción de Darcy (adimensional)
                - $L$ = Longitud del tramo (m)
                - $D$ = Diámetro interno (m)
                - $U$ = Velocidad media del flujo (m/s)
                - $g$ = Aceleración de gravedad (9.81 m/s²)
                
                ### 4. Factor de Fricción ($f_d$)
                Para flujo laminar, el factor de fricción se calcula analíticamente mediante la **Ecuación de Hagen-Poiseuille**:
                $$f_d = \frac{64}{Re}$$
                
                Para flujo turbulento, se utiliza la **Ecuación de Colebrook-White**, que requiere solución iterativa:
                $$\frac{1}{\sqrt{f_d}} = -2\log\left(\frac{\varepsilon/D}{3.7} + \frac{2.51}{Re\sqrt{f_d}}\right)$$
                
                Donde $\varepsilon/D$ es la rugosidad relativa de la tubería.
                
                ### 5. Medidores de Flujo
                Para cuantificar el caudal, se utilizan dispositivos que generan una caída de presión medible, como el **Tubo de Venturi** y la **Placa de Orificio**. Cada uno posee un **coeficiente de descarga** característico que relaciona el caudal real con el teórico.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2 Pérdidas de Presión por Fricción en Conexiones y Tramos de Tuberías..png", use_container_width=True)

    # ==================== PRACTICA 3 Bombas Centrífugas ==============
    
    elif nombre == "Bombas Centrífugas":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "Manual de la Práctica 3. Determinación de Curvas Características de Bombas Centrífugas..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="Manual_Practica3_BombaCentrifuga.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                 ### Bombas Centrífugas
                
                El análisis del comportamiento de las **bombas centrífugas** es esencial para entender cómo estas máquinas hidráulicas transforman la energía mecánica en energía cinética y de presión para mover un fluido a través de un sistema.
                
                ### 1. Curvas Características de la Bomba
                El rendimiento de una bomba se describe mediante gráficas que relacionan variables críticas frente al **caudal ($Q$)**. Las principales relaciones son:
                *   **Cabezal vs. Caudal ($H$ vs $Q$):** Representa la altura total de elevación que la bomba puede proporcionar.
                *   **Potencia al freno vs. Caudal ($W$ vs $Q$):** Indica la energía consumida por el motor de la bomba.
                *   **Eficiencia vs. Caudal ($\eta$ vs $Q$):** Determina el punto de operación óptimo donde la conversión de energía es máxima.
                
                ### 2. Cabezal Experimental ($H$)
                El cabezal representa la energía neta transferida al fluido por unidad de peso y se calcula mediante un balance de energía entre la succión y la descarga.
                
                **Fórmula del cabezal para bomba individual:**
                $$H_{Bi} = \frac{P_2 - P_1}{\rho \cdot g} \cdot 6894,757 + Z + \frac{U^2}{2g} + H_{1 \to 2}$$
                
                Donde:
                - $P_2$ = Presión de descarga (psig)
                - $P_1$ = Presión atmosférica (psia)
                - $Z$ = Diferencia de altura geométrica (m)
                - $U$ = Velocidad media del fluido (m/s)
                - $H_{1 \to 2}$ = Pérdidas totales por fricción (m)
                
                ### 3. Eficiencia de la Bomba ($\eta$)
                Es la relación entre la potencia hidráulica entregada al fluido y la potencia mecánica (al freno) suministrada al eje de la bomba.
                
                **Relación fundamental:**
                $$\eta = \frac{\rho \cdot g \cdot Q \cdot H}{W_{Bi} \cdot constante}$$
                
                Donde $W_{Bi}$ es la potencia al freno calculada a partir de la intensidad de corriente o potencia eléctrica.
                
                ### 4. Operación en Sistemas Compuestos
                Cuando las necesidades de un proceso exceden la capacidad de una sola bomba, estas se pueden acoplar en diferentes configuraciones:
                
                *   **Bombas en Serie:** Se utilizan para incrementar el cabezal ($H$) total del sistema. El caudal es el mismo para ambas, pero los cabezales se suman:
                $$H_S = H_1 + H_2$$
                
                *   **Bombas en Paralelo:** Se emplean para aumentar el caudal ($Q$) total. El cabezal se mantiene similar al de una sola bomba, pero los caudales se suman:
                $$Q_P = Q_1 + Q_2$$
                
                ### 5. Fenómeno de Cavitación
                Es un aspecto crítico de la teoría de bombas que ocurre cuando la presión en la succión cae por debajo de la presión de vapor del líquido, formando burbujas de vapor que colapsan y pueden dañar mecánicamente el impulsor. Se evita asegurando que el **NPSH** disponible sea mayor al requerido por el fabricante.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("1.3 Determinación de Curvas Características de Bombas Centrífugas..png", use_container_width=True)


    # ==================== PRACTICA 5 Lechos Fluidizados ==============
    
    elif nombre == "Lechos Fluidizados":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "Manual de la Práctica 5. Lechos Fluidizados. Estudio de sus Principales Características..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="Manual_Practica5_LechosFluidizados.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                 ### Lechos Fluidizados
                
                La **transición de un lecho estático a un estado fluidizado** representa un proceso crítico en la ingeniería química, donde un conjunto de partículas sólidas (como arena o catalizadores) suspende su estructura fija para comportarse dinámicamente como un fluido al interactuar con una corriente ascendente de aire.
                
                ### 1. Caracterización del Flujo: Número de Reynolds ($Re$)
                Para estudiar el comportamiento del aire a través del lecho, se utiliza el **Número de Reynolds**, el cual relaciona las fuerzas inerciales y viscosas para determinar el régimen de flujo en los intersticios de las partículas.
                
                **Fórmula fundamental:**
                $$Re = \frac{D_P \cdot U_S \cdot \rho_a}{\mu_a}$$
                
                Donde:
                - $D_P$ = Diámetro de la partícula (m)
                - $U_S$ = Velocidad superficial del fluido (m/s)
                - $\rho_a$ = Densidad del aire (kg/m³)
                - $\mu_a$ = Viscosidad del aire (Pa·s)
                
                ### 2. Porosidad o Fracción de Vacío ($\epsilon$)
                La **fracción vacía** describe el volumen de espacios libres entre las partículas en relación con el volumen total del lecho. Este valor aumenta conforme el lecho se expande durante la fluidización.
                
                **Relación de porosidad:**
                $$\epsilon = 1 - \frac{H_{LC}}{H}$$
                
                Donde:
                - $H_{LC}$ = Altura del lecho compacto (m)
                - $H$ = Altura promedio del lecho en operación (m)
                
                ### 3. Caída de Presión ($\Delta P$)
                Al fluir a través del lecho, el fluido experimenta una pérdida de energía debido a la resistencia que ofrecen las partículas. Esta caída de presión se mide experimentalmente mediante manómetros diferenciales.
                
                **Cálculo experimental:**
                $$\Delta P = \Delta h \cdot \rho_{LM} \cdot g$$
                
                Donde:
                - $\Delta h$ = Diferencia de altura manométrica (m)
                - $\rho_{LM}$ = Densidad del líquido manométrico (kg/m³)
                - $g$ = Aceleración de gravedad (9.81 m/s²)
                
                ### 4. Punto de Mínima Fluidización ($U_{mf}$)
                Es la velocidad crítica en la cual la fuerza ascendente del fluido iguala el peso del lecho. En este punto, las partículas dejan de estar en contacto permanente y comienzan a moverse libremente. Teóricamente, este valor se puede estimar mediante la **Ecuación de Ergun**, que considera tanto las pérdidas por fricción viscosa como inercial.
                
                **Ecuación de Ergun para $U_{mf}$:**
                $$\frac{1.75}{\epsilon_{mf}^3} \left(\frac{D_P U_{mf} \rho}{\mu}\right)^2 + \frac{150(1-\epsilon_{mf})}{\epsilon_{mf}^3} \left(\frac{D_P U_{mf} \rho}{\mu}\right) = \frac{D_P^3 \rho (\rho_s - \rho) g}{\mu^2}$$
                
                ### 5. Número de Froude ($N_F$)
                Este parámetro adimensional permite clasificar el **tipo de fluidización** (particular o agregativa), comparando las fuerzas de inercia con las fuerzas gravitatorias que actúan sobre las partículas.
                
                **Fórmula de Froude:**
                $$N_F = \frac{U_{MF}^2}{g \cdot D_P}$$
                
                Donde:
                - $U_{MF}$ = Velocidad de mínima fluidización (m/s)
                - $g$ = Aceleración de gravedad (m/s²)
                - $D_P$ = Diámetro de partícula (m)
                
                **Clasificación del tipo de fluidización:**
                - $N_F < 1$: Fluidización particulada (uniforme, típica de líquidos)
                - $N_F > 1$: Fluidización agregativa (con burbujas, típica de gases)
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("1.5 LECHOS FLUIDIZADOS.png", use_container_width=True)

    # =================================LOU II====================================================== 

    # ================ PRACTICA 1 Hidrodinámica de Columnas Empacadas ==============================
    
    elif nombre == "Hidrodinámica de Columnas Empacadas":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "2 Manual de la Práctica 1. Hidrodinámica de Columnas Empacadas..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="ColumnasEmpacadas.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Hidrodinámica de Columnas Empacadas
                
                La **transferencia de masa en la industria química depende fundamentalmente de la interacción eficiente entre fases dentro de una torre de relleno**, la cual busca maximizar el contacto superficial para procesos críticos como la absorción, destilación o extracción.
                
                ### 1. Columnas de Relleno y su Configuración
                Estas torres consisten en columnas cilíndricas equipadas con soportes e inertes sólidos denominados **rellenos**, que pueden ser aleatorios (como los anillos Pall o Raschig) o regulares. El objetivo del relleno es permitir que el líquido fluya en forma de película, ofreciendo una gran superficie para el contacto íntimo con una corriente de gas en contracorriente.
                
                ### 2. Pérdida de Presión en Flujo Monofásico (Relleno Seco)
                Cuando solo circula gas a través de la columna, la caída de presión por unidad de longitud ($\Delta P/Z$) está influenciada por las propiedades del fluido y la geometría del empaque. Este comportamiento se describe mediante la **Ecuación de Ergun**:
                
                $$\frac{\Delta P}{Z} = 150 \frac{(1-\epsilon)^2 \cdot \mu \cdot G'}{\rho_g \cdot \epsilon^3 \cdot d_p^2} + 1.75 \frac{(1-\epsilon) \cdot G'^2}{\rho_g \cdot \epsilon^3 \cdot d_p}$$
                
                Donde:
                - $\epsilon$ = Fracción de vacío del lecho
                - $G'$ = Velocidad másica superficial (kg/m²·s)
                - $\rho_g$ = Densidad del gas (kg/m³)
                - $\mu$ = Viscosidad del gas (Pa·s)
                - $d_p$ = Diámetro efectivo de la partícula (m)
                
                ### 3. Dinámica del Flujo Bifásico: Carga e Inundación
                Al introducir líquido en el sistema, los espacios vacíos se reducen, lo que incrementa la pérdida de presión del gas en comparación con el lecho seco. En este régimen ocurren dos fenómenos críticos:
                
                *   **Punto de Carga:** Es el momento en que la velocidad del gas comienza a impedir el libre descenso del líquido, provocando acumulaciones locales y un cambio brusco en la pendiente de la caída de presión.
                
                *   **Punto de Inundación:** Representa la **capacidad máxima de operación** de la torre; el líquido llena gran parte de los intersticios y el gas burbujea a través de él, pudiendo incluso expulsar el líquido fuera de la columna.
                
                ### 4. Retención de Líquido (Holdup)
                La cantidad de líquido presente en el empaque durante la operación se clasifica en tres modos:
                
                *   **Retención Estática ($h_S$):** Líquido que permanece en el relleno tras ser mojado y drenado por gravedad.
                *   **Retención Dinámica ($h_O$):** Líquido que fluye activamente por el relleno bajo condiciones de operación.
                *   **Retención Total ($h_T$):** Suma de ambos componentes, constante hasta el punto de carga y creciente hasta la inundación.
                
                $$h_T = h_S + h_O$$
                
                ### 5. Correlación de Sherwood - Leva (Flooding)
                Para predecir el punto de inundación en columnas de relleno, se utiliza la **Correlación de Sherwood-Leva**, que relaciona la velocidad másica del gas con las propiedades del sistema:
                
                $$\frac{G'^2 \cdot a_p \cdot \mu^{0.2}}{\rho_g \cdot \rho_l \cdot g \cdot \epsilon^3} = \text{función} \left( \frac{L'}{G'} \sqrt{\frac{\rho_g}{\rho_l}} \right)$$
                
                Donde $L'$ es la velocidad másica del líquido y $a_p$ el área superficial específica del relleno.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2.1 Hidrodinámica de Columnas Empacadas..png", use_container_width=True)

    # ==================== PRACTICA 3 Filtración a Presión Constante (falta la dos) ==============
    
    elif nombre == "Filtración a Presión Constante":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "2 Manual de la Práctica 3. Estudio de las Características de la Filtración a Presión Constante de una Suspensión..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="PresionConstante.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Filtración a Presión Constante
                
                **Entendida como una operación unitaria fundamental**, la filtración permite la separación de una fase dispersa (sólidos) de una fase continua (líquido o gas) mediante un medio poroso que retiene las partículas mientras permite el paso del filtrado.
                
                ### 1. Mecanismo y Cinética de Filtración
                El proceso se rige por la relación básica donde la velocidad de flujo es directamente proporcional a la fuerza impulsora e inversamente proporcional a la resistencia encontrada. En términos matemáticos, se utiliza una adaptación de la **ecuación de Poiseuille** para representar la velocidad diferencial de filtración por unidad de área:
                
                $$\frac{dV}{A \cdot d\theta} = \frac{P}{\mu \left[ \alpha \frac{W}{A} + r \right]}$$
                
                Donde:
                - $P$ = Presión de operación (Pa)
                - $\mu$ = Viscosidad del fluido (Pa·s)
                - $\alpha$ = Resistencia específica de la torta (m/kg)
                - $W$ = Masa de sólidos acumulados (kg)
                - $A$ = Área de filtración (m²)
                - $r$ = Resistencia del medio filtrante (m⁻¹)
                
                ### 2. Resistencias en el Proceso
                La oposición al flujo proviene de dos fuentes principales que se suman durante la operación:
                
                *   **Resistencia del medio filtrante ($r$):** Fuerza de empuje que ofrece el soporte o tela al paso del fluido.
                *   **Resistencia específica de la torta ($\alpha$):** Fuerza contraria generada por el espesor acumulado de sólidos. A mayor espesor y tiempo de operación, mayor es esta resistencia.
                
                ### 3. Modelo de Kozeny a Presión Constante
                Para sistemas que operan a presión constante, se utiliza la **ecuación de Kozeny** modificada para determinar las constantes del proceso mediante la relación entre el volumen de filtrado ($V$) y el tiempo ($\theta$).
                
                **Ecuación característica:**
                $$(V + V_f)^2 = C \cdot (\theta + \theta_f)$$
                
                Donde:
                - $V_f$ = Volumen ficticio que compensa la resistencia del medio filtrante (m³)
                - $\theta_f$ = Tiempo ficticio (s)
                - $C$ = Constante de permeabilidad del lecho (m⁶/s)
                
                ### 4. Determinación de Constantes
                Para implementar este modelo en una interfaz de cálculo, la ecuación se suele **linealizar** representando la recíproca de la velocidad frente al volumen acumulado:
                
                $$\frac{d\theta}{dV} = \frac{2}{C} V + \frac{2V_f}{C}$$
                
                Esta forma permite obtener la constante $C$ a partir de la pendiente de la recta y el volumen ficticio $V_f$ desde la ordenada en el origen.
                
                ### 5. Factores Críticos de Operación
                
                *   **Viscosidad:** La velocidad de filtración es inversamente proporcional a la viscosidad del fluido, la cual disminuye al aumentar la temperatura.
                
                *   **Presión:** En sólidos granulares, un aumento de presión incrementa casi proporcionalmente la velocidad de flujo.
                
                *   **Porosidad ($\epsilon$):** Define la fracción de espacios vacíos en la torta, parámetro esencial para calcular la permeabilidad del lecho.
                
                **Relación entre resistencia específica y porosidad:**
                $$\alpha = \frac{180(1-\epsilon)^2}{\rho_s \cdot d_p^2 \cdot \epsilon^3}$$
                
                Donde $\rho_s$ es la densidad de los sólidos y $d_p$ el diámetro de partícula.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2.2 A PRESIÓN CONSTANTE.png", use_container_width=True)

    # ==================== PRACTICA 5 Destilación Diferencial ==============

    elif nombre == "Destilación Diferencial":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "2 Manual de la Práctica 4. Estudio de la Destilación Diferencial..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="DestilaciónDiferencial.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Destilación Diferencial
                
                Considerada como una sucesión de evaporaciones instantáneas infinitesimales, la **destilación diferencial** es un proceso por lotes donde la mezcla se calienta lentamente en un recipiente y los vapores se retiran y condensan inmediatamente después de su formación. Este método se utiliza principalmente para la obtención de productos costosos en cantidades reducidas o con fines analíticos en el laboratorio.
                
                ### 1. Equilibrio Líquido-Vapor en Sistemas Ideales
                En mezclas de comportamiento ideal, como los hidrocarburos aromáticos, se aplica la **Ley de Raoult**. Esta establece que la presión parcial ($p_J^*$) de un componente es igual al producto de su presión de vapor puro ($P_J^o$) por su fracción molar en el líquido ($X_J$):
                
                $$p_J^* = P_J^o \cdot X_J$$
                
                La presión total del sistema es la suma de las presiones parciales:
                $$P_T = \sum_{J=1}^{n} p_J^* = \sum_{J=1}^{n} P_J^o \cdot X_J$$
                
                ### 2. Volatilidad Relativa ($\alpha$)
                Es un parámetro crítico que mide la facilidad de separación de dos componentes. Para sistemas ideales, se define como la relación entre las presiones de vapor de los componentes puros:
                
                $$\alpha = \frac{P_A^o}{P_B^o}$$
                
                Cuando $\alpha > 1$, el componente A es más volátil, lo que facilita su acumulación en la fase vapor durante la destilación. La relación entre las fases líquida y vapor en equilibrio está dada por:
                
                $$y_A = \frac{\alpha \cdot x_A}{1 + (\alpha - 1)x_A}$$
                
                ### 3. Ecuación de Rayleigh
                Este modelo matemático describe cómo varía la composición del líquido residual en el calderín a medida que avanza la vaporización. Su forma integral relaciona los moles iniciales ($n_o$) y finales ($n$) con las fracciones molares:
                
                $$\ln \frac{n}{n_o} = \int_{x_o}^{x_1} \frac{dx}{y - x}$$
                
                Para **mezclas ideales** con volatilidad relativa constante, la relación entre dos componentes (A y B) se puede simplificar como:
                
                $$\ln \frac{n_A}{n_{OA}} = \alpha_{AB} \cdot \ln \frac{n_B}{n_{OB}}$$
                
                ### 4. Temperatura de Burbuja y Rocío
                
                *   **Temperatura de Burbuja ($t_b$):** Es el punto exacto donde aparece la primera burbuja de vapor al calentar el líquido. Matemáticamente:
                $$\sum_{J=1}^{n} \frac{P_J^o(t_b) \cdot X_J}{P_T} = 1$$
                
                *   **Temperatura de Rocío ($t_r$):** Es el instante en que se condensa la última gota de vapor o desaparece la última gota de líquido durante la vaporización total. Matemáticamente:
                $$\sum_{J=1}^{n} \frac{P_T \cdot Y_J}{P_J^o(t_r)} = 1$$
                
                A cualquier temperatura entre $t_b$ y $t_r$, existe un equilibrio único donde la composición de cada fase depende exclusivamente de la presión y la temperatura del sistema.
                
                ### 5. Aplicaciones de la Destilación Diferencial
                - **Industria de bebidas:** Producción de licores y bebidas destiladas (whisky, brandy, ron)
                - **Industria de perfumes:** Extracción de aceites esenciales y esencias naturales
                - **Industria farmacéutica:** Purificación de compuestos termolábiles
                - **Análisis de laboratorio:** Determinación de curvas de destilación y caracterización de mezclas
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2.4 ESTUDIO DE LA DESTILACIÓN DIFERENCIAL.png", use_container_width=True)
    
    # ==================== PRACTICA 5 Destilación Continua   ==============
 
    elif nombre == "Destilación Continua":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "2 Manual de la Práctica 5. Destilación Continua de una Mezcla Binaria en una Columna de Separación por Etapas..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="DestilaciónContinua.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Destilación Continua
                
                **La rectificación continua, o fraccionamiento, constituye** una operación unitaria de destilación a contracorriente en varias etapas que permite separar los componentes de una solución líquida aprovechando sus diferencias de volatilidad. En este proceso, una fase vapor y una líquida entran en contacto íntimo: el vapor que asciende por la columna se enriquece con el componente más volátil (destilado), mientras que el líquido que desciende se concentra en el componente menos volátil (residuo).
                
                ### 1. Métodos de Cálculo de Etapas
                Para determinar el número de platos o etapas teóricas necesarias para una separación específica, se utilizan principalmente dos métodos:
                
                *   **Método de McCabe-Thiele:** Es un modelo simplificado basado en balances de materia que asume un **derrame molar constante** en las secciones de la columna.
                
                    **Línea de operación (Enriquecimiento):**
                    $$y_{n+1} = \frac{R}{R+1}x_n + \frac{x_D}{R+1}$$
                    
                    **Línea de operación (Agotamiento):**
                    $$y_{m+1} = \frac{L_m}{V_{m+1}}x_m - \frac{W x_W}{V_{m+1}}$$
                
                    Donde:
                    - $R = L_0/D$ = Relación de reflujo
                    - $x_D$ = Fracción molar en el destilado
                    - $x_W$ = Fracción molar en el residuo
                    - $L_m$ = Flujo de líquido en la sección de agotamiento (mol/s)
                    - $V_{m+1}$ = Flujo de vapor en la sección de agotamiento (mol/s)
                    - $W$ = Flujo de residuo (mol/s)
                
                *   **Método de Ponchón-Savarit:** Se considera un enfoque más riguroso al integrar simultáneamente balances de materia y energía a través de diagramas de **entalpía-composición**. Este método no requiere suponer flujos molares constantes y considera la operación como adiabática.
                
                ### 2. Volatilidad Relativa ($\alpha$)
                Es el parámetro fundamental que mide la facilidad de separación de la mezcla. Indica cuánto más volátil es un componente respecto al otro a una presión dada.
                
                **Fórmula de volatilidad:**
                $$\alpha_{AB} = \frac{Y_A(1 - X_A)}{X_A(1 - Y_A)}$$
                
                Donde:
                - $X_A$ = Fracción molar del componente A en el líquido
                - $Y_A$ = Fracción molar del componente A en el vapor
                
                Para mezclas ideales con volatilidad relativa constante, la curva de equilibrio está dada por:
                $$y = \frac{\alpha x}{1 + (\alpha - 1)x}$$
                
                ### 3. Condiciones Límite: Reflujo Total
                Cuando la columna opera sin alimentación ni extracción de productos, se alcanza el **reflujo total**, lo que permite obtener la separación deseada con el **número mínimo de etapas ($N_m$)**. Para este cálculo se puede emplear la **Ecuación de Fenske**:
                
                **Relación de Fenske:**
                $$N_m = \frac{\log \left[ \frac{X_D(1 - X_W)}{X_W(1 - X_D)} \right]}{\log \alpha_{prom}} - 1$$
                
                Donde:
                - $X_D$ = Fracción molar del componente más volátil en el destilado
                - $X_W$ = Fracción molar del componente más volátil en el residuo
                - $\alpha_{prom}$ = Volatilidad relativa promedio geométrica entre la cima y el fondo
                
                ### 4. Relación de Reflujo Mínima ($R_m$)
                Corresponde al valor de reflujo que requiere un **número infinito de etapas** para lograr la separación deseada. Gráficamente, se determina trazando la línea de operación que intersecta la curva de equilibrio en el punto de alimentación.
                
                $$R_m = \frac{x_D - y_F}{y_F - x_F}$$
                
                Donde $x_F$ y $y_F$ son las coordenadas del punto de intersección entre la línea de alimentación y la curva de equilibrio.
                
                ### 5. Eficiencia de la Columna
                La eficiencia permite comparar el desempeño del equipo real frente al modelo ideal.
                
                *   **Eficiencia Global ($E_g$):** Relaciona los platos teóricos ($N_{PT}$) calculados gráficamente con los platos reales ($N_R$) instalados en la torre.
                $$E_g = \frac{N_{PT}}{N_R} \cdot 100$$
                
                *   **Eficiencia de Platos (Eficiencia de Murphree):** Mide la eficiencia de un plato individual:
                $$E_{MV} = \frac{Y_n - Y_{n+1}}{Y_n^* - Y_{n+1}}$$
                
                Donde $Y_n^*$ es la composición del vapor que estaría en equilibrio con el líquido que sale del plato.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2.5 Destilación Continua.png", use_container_width=True)   

    # ======================== PRACTICA 6 Rectificación en Torre Rellena ========================   
 
    elif nombre == "Rectificación en Torre Rellena":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "2 Manual de la Práctica 6. Rectificación de una Mezcla Binaria en una Torre Rellena..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label=" Descargar Práctica (PDF)", data=f, file_name="Rectificacion.pdf", mime="application/pdf")
            else:
                st.warning("⚠️ PDF no encontrado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📖 Marco Teórico", expanded=True):
                st.markdown(r"""
                ## Rectificación de una Mezcla Binaria en una Torre Rellena.
                
                Centrada en maximizar el área de contacto interfacial, la **rectificación en torres empacadas** constituye una operación de transferencia de masa donde una fase vapor y una líquida coexisten a la misma presión y temperatura para separar componentes por sus diferencias de volatilidad. En estos equipos, el líquido desciende en cascada mientras el vapor asciende, permitiendo que los componentes más ligeros se concentren en el tope y los más pesados en el fondo de la columna.
                
                ### 1. Parámetros de Diseño: HETP
                A diferencia de las columnas de platos, el rendimiento de una torre rellena se mide mediante la **Altura Equivalente a un Plato Teórico (HETP)**. Este valor representa la altura de empaque necesaria para lograr un cambio en la composición equivalente a un contacto teórico de equilibrio.
                
                **Relación de dimensionamiento:**
                $$Z = HETP \cdot N$$
                
                Donde:
                - $Z$ = Altura total de relleno (m)
                - $HETP$ = Altura equivalente a un plato teórico (m)
                - $N$ = Número de etapas teóricas
                
                ### 2. Método de McCabe-Thiele y Relación de Reflujo
                Para determinar las etapas de separación, este método gráfico utiliza el balance de materia bajo la suposición de **derrame molar constante**. La eficiencia del proceso está fuertemente ligada a la **relación de reflujo ($R$)**, definida como la razón molar entre el líquido que retorna a la torre ($L$) y el destilado ($D$).
                
                **Línea de operación de rectificación (Enriquecimiento):**
                $$y_n = \frac{R}{R+1}x_{n+1} + \frac{x_D}{R+1}$$
                
                **Línea de operación de agotamiento:**
                $$y_{m+1} = \frac{L_m}{V_{m+1}}x_m - \frac{W x_W}{V_{m+1}}$$
                
                **Línea de alimentación (q-line):**
                $$y = \frac{q}{q-1}x - \frac{x_F}{q-1}$$
                
                Donde:
                - $R = L_0/D$ = Relación de reflujo
                - $x_D$ = Composición del destilado (fracción molar)
                - $x_W$ = Composición del residuo (fracción molar)
                - $x_F$ = Composición de la alimentación (fracción molar)
                - $q$ = Calidad de la alimentación (fracción de líquido en la alimentación)
                
                ### 3. Reflujo Total y Ecuación de Fenske
                Cuando la columna opera sin introducir alimentación ni retirar producto, se alcanza la condición de **reflujo total**, lo que resulta en el número mínimo de etapas necesarias para una separación dada. Si la volatilidad relativa ($\alpha$) es constante, se emplea la **Ecuación de Fenske** para el cálculo analítico.
                
                **Fórmula de Fenske:**
                $$N_{min} = \frac{\log \left[ \frac{x_D (1-x_w)}{x_w (1-x_D)} \right]}{\log \alpha_{prom}}$$
                
                Donde:
                - $x_D$ = Composición del componente más volátil en el destilado
                - $x_w$ = Composición del componente más volátil en el residuo
                - $\alpha_{prom}$ = Volatilidad relativa promedio geométrica
                
                ### 4. Relación de Reflujo Mínima ($R_{min}$)
                Corresponde al valor de reflujo que requiere un número infinito de etapas para lograr la separación deseada.
                
                $$R_{min} = \frac{x_D - y_F}{y_F - x_F}$$
                
                Donde $(x_F, y_F)$ son las coordenadas del punto de intersección entre la línea de alimentación y la curva de equilibrio.
                
                ### 5. Rectificación Discontinua (Batch): Ecuación de Rayleigh
                En operaciones por carga (batch), la composición del líquido en el calderín cambia continuamente a medida que se retira el componente más volátil. La **Ecuación de Rayleigh** permite relacionar los moles cargados inicialmente ($F$) con los moles residuales ($W$) tras la operación.
                
                **Modelo de Rayleigh:**
                $$\ln \frac{F}{W} = \int_{x_w}^{x_F} \frac{dx}{x_D - x}$$
                
                Este cálculo suele resolverse mediante integración gráfica o numérica utilizando datos de equilibrio líquido-vapor.
                
                ### 6. Eficiencia de la Columna
                **Eficiencia Global ($E_g$):**
                $$E_g = \frac{N_{PT}}{N_R} \cdot 100$$
                
                Donde:
                - $N_{PT}$ = Número de platos teóricos
                - $N_R$ = Número de platos reales
                
                **Eficiencia de Murphree (para plato individual):**
                $$E_{MV} = \frac{Y_n - Y_{n+1}}{Y_n^* - Y_{n+1}}$$
                
                Donde $Y_n^*$ es la composición del vapor en equilibrio con el líquido que sale del plato.
                """)
        
        with col2:
            with st.expander(" Diagrama del Proceso", expanded=True):
                st.image("2.6 Rectificación de una Mezcla Binaria en una Torre Rellena..png", use_container_width=True)       
    
    # ======================== FOOTER ========================
    st.markdown("""
    <hr style="margin: 2rem 0 1rem 0; border-color: #1a5276;">
    <div style="text-align: center; color: #5d6d7e; font-size: 0.8rem;">
        <p>Universidad Central de Venezuela - Escuela de Ingeniería Química</p>
        <p>Laboratorio de Operaciones Unitarias | Centro de Simulación Virtual | © 2026</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# EJECUCIÓN
# =============================================================================
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)
