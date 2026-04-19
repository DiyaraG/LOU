import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import time
import base64

# =============================================================================
# VALORES POR DEFECTO
# =============================================================================
modo_auto = False
p_activa = True
p_magnitud = 0.045
p_tiempo = 80
modo_estres = False

# =============================================================================
# FUNCIONES DE CÁLCULO
# =============================================================================
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
    if geom == "Cilíndrico":
        area_t = np.pi * (r**2)
    elif geom == "Cónico":
        area_t = np.pi * (r/2)**2
    else:
        area_t = (2/3) * np.pi * (r**2)
    Kc = np.clip(10.0 * area_t, 8.0, 25.0)
    if op_tipo == "Llenado":
        kp = Kc * 1.2
        ki = kp / 5.0
        kd = kp * 0.15
    else:
        kp = Kc * 1.0
        ki = kp / 6.0
        kd = kp * 0.12
    kp = np.clip(kp, 12.0, 30.0)
    ki = np.clip(ki, 2.5, 8.0)
    kd = np.clip(kd, 0.5, 2.5)
    return round(kp, 2), round(ki, 3), round(kd, 2)

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

def resolver_sistema_robusto(dt, h_prev, sp, geom, r, h_t, q_p_val, e_sum, e_prev, modo_op, cd_val, kp, ki, kd, d_pulgadas):
    area_h = get_area_transversal(geom, r, h_prev, h_t)
    area_h = max(area_h, 0.0001)
    err = sp - h_prev
    a_o = np.pi * ((d_pulgadas * 0.0254) / 2)**2
    q_max = 2.0
    P = kp * err
    e_sum += err * dt
    e_sum = np.clip(e_sum, -50.0, 50.0)
    I = ki * e_sum
    D = kd * (err - e_prev) / dt if dt > 0 else 0
    D = np.clip(D, -5.0, 5.0)
    u_control = P + I + D
    if modo_op == "Llenado":
        q_entrada = np.clip(u_control, 0, q_max)
        q_salida = cd_val * a_o * np.sqrt(2 * 9.81 * max(h_prev, 0.005)) if h_prev > 0.005 else 0
        dh_dt = (q_entrada + q_p_val - q_salida) / area_h
        u_graficar = q_entrada
    else:
        q_salida = np.clip(-u_control, 0, q_max)
        q_entrada = q_p_val
        dh_dt = (q_entrada - q_salida) / area_h
        u_graficar = q_salida
    h_next = np.clip(h_prev + dh_dt * dt, 0, h_t)
    return h_next, u_graficar, err, e_sum, err

def get_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

# =============================================================================
# CONFIGURACIÓN DE LA PÁGINA + ESTILOS CRISTAL
# =============================================================================
st.set_page_config(page_title="LOU App - UCV", layout="wide", page_icon="🛠")

st.markdown("""
<style>
@keyframes wave { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
.stApp {
    background-image: linear-gradient(rgba(255,255,255,0.8), rgba(240,242,245,0.85)),
                      url("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg");
    background-size: cover; background-position: center; background-attachment: fixed;
    color: #2D3748;
}
.title-container {
    background: rgba(255,255,255,0.6); border: 1px solid rgba(200,210,230,0.5);
    border-radius: 15px; padding: 20px; margin-bottom: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.05); backdrop-filter: blur(5px);
    display: flex; align-items: center; justify-content: space-between;
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

# =============================================================================
# LÓGICA DE NAVEGACIÓN
# =============================================================================
if 'page' not in st.session_state:
    st.session_state.page = 'Inicio'

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

    # Caso 1: Balance en Estado No Estacionario (simulación compleja)
    if nombre == "Balance en Estado No Estacionario":
        
        # ======================== MARCO TEÓRICO ========================
        col_teoria1, col_teoria2, col_teoria3 = st.columns(3)

        with col_teoria1:
            with st.expander("📚 Fundamento teórico: Ecuaciones de Conservación y Descarga", expanded=False):
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
            with st.expander("🎯 Teoría: Estrategia de control PID Robusto", expanded=False):
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
            with st.expander("📊 Criterios de Desempeño (IAE/ITAE)", expanded=False):
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
        
        with st.sidebar.expander("Dimensiones de Salida", expanded=True):
            d_pulgadas = st.number_input("Diámetro del Orificio (pulgadas)", value=1.0, min_value=0.1, step=0.1)
            d_metros = d_pulgadas * 0.0254
            area_orificio = np.pi * (d_metros / 2)**2
            st.caption(f"Área calculada: {area_orificio:.6f} m²")
        
        with st.sidebar.expander("🛡️ Escenario de Perturbación ($Q_p$)"):
            p_activa = st.toggle("Simular Falla/Fuga Externas", value=True)
            if p_activa:
                p_magnitud = st.number_input("Magnitud Qp [m³/s]", value=0.045, format="%.4f")
                p_tiempo = st.slider("Inicio de perturbación [s]", 0, 500, 80)
                modo_estres = st.toggle("🔥 Activar Modo Estrés", help="La perturbación cambiará según el nivel")
            else:
                p_magnitud = 0.0
                p_tiempo = 0
                modo_estres = False
        
        with st.sidebar.expander("Parámetros del Controlador PID Robusto"):
            kp_sug, ki_sug, kd_sug = calcular_pid_adaptativo(geom_tanque, r_max, h_total)
            modo_auto = st.checkbox("🎯 Modo Robusto (Auto-sintonía optimizada)", value=True)
            if modo_auto:
                st.success("💡 Usando sintonización robusta")
                kp_val = st.number_input("Kp (robusto)", value=kp_sug, key="kp_asist")
                ki_val = st.number_input("Ki (robusto)", value=ki_sug, format="%.3f", key="ki_asist")
                kd_val = st.number_input("Kd (robusto)", value=kd_sug, format="%.3f", key="kd_asist")
            else:
                kp_val = st.number_input("Kp", value=15.0, step=1.0, key="kp_man")
                ki_val = st.number_input("Ki", value=3.0, step=0.5, format="%.3f", key="ki_man")
                kd_val = st.number_input("Kd", value=1.5, step=0.2, format="%.3f", key="kd_man")
            tiempo_ensayo = st.slider("Tiempo de simulación [s]", 60, 600, 300)
        
        with st.sidebar.expander("📊 Cargar Datos Experimentales"):
            st.caption("⚠️ Ingresa el nivel en **centímetros (cm)**")
            df_exp_default = pd.DataFrame({
                "Tiempo (s)": [0, 60, 120, 180, 240, 300],
                "Nivel Medido (cm)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            })
            datos_usr = st.data_editor(df_exp_default, num_rows="dynamic")
            mostrar_ref = st.checkbox("Mostrar referencia en gráfica", value=True)
        
        st.sidebar.markdown("---")
        col_btn1, col_btn2 = st.sidebar.columns(2)
        with col_btn1:
            iniciar_sim = st.button("▶️ Iniciar Simulación Robusta", use_container_width=True, type="primary")
        with col_btn2:
            if st.button("🔄 Reset", use_container_width=True, type="secondary"):
                st.session_state.ejecutando = False
                st.rerun()
    
        if 'ejecutando' not in st.session_state:
            st.session_state.ejecutando = False
    
        # ======================== BIBLIOTECA TÉCNICA EN BARRA LATERAL ========================
        st.sidebar.markdown("---")
        st.sidebar.subheader("📚 Biblioteca Técnica")
        
        with st.sidebar.container(border=True):
            nombre_pdf = "Guia_Practica_UCV.pdf"
            if os.path.exists(nombre_pdf):
                with open(nombre_pdf, "rb") as f:
                    st.sidebar.download_button(
                        label="📥 Descargar Guía de Práctica (PDF)",
                        data=f,
                        file_name="Guia_Practica_EIQ_UCV.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                st.sidebar.caption("📖 Guía completa de la práctica de laboratorio")
            else:
                st.sidebar.warning("⚠️ Archivo 'Guia_Practica_UCV.pdf' no encontrado en el directorio")
                st.sidebar.caption("💡 Coloca el PDF en la misma carpeta que el script")
        
        st.sidebar.markdown("---")
    
        # ======================== INICIALIZACIÓN ========================
        if iniciar_sim:
            st.session_state.ejecutando = True
            try:
                if modo_auto:
                    st.session_state['kp_ejecucion'] = kp_val
                    st.session_state['ki_ejecucion'] = ki_val
                    st.session_state['kd_ejecucion'] = kd_val
                    st.session_state['cd_final'] = 0.61
                else:
                    st.session_state['kp_ejecucion'] = kp_val
                    st.session_state['ki_ejecucion'] = ki_val
                    st.session_state['kd_ejecucion'] = kd_val
                    st.session_state['cd_final'] = 0.61
            except:
                st.session_state['kp_ejecucion'] = 18.0
                st.session_state['ki_ejecucion'] = 3.5
                st.session_state['kd_ejecucion'] = 1.5
                st.session_state['cd_final'] = 0.61
    
        # ======================== SIMULACIÓN PRINCIPAL ========================
        if not st.session_state.ejecutando:
            st.info("💡 Ajusta los parámetros en la barra lateral y pulsa 'Iniciar Simulación Robusta'")
        else:
            col_graf, col_met = st.columns([2, 1])
            
            with col_graf:
                st.subheader("Monitor del Proceso - Control Robusto Anti-Perturbaciones")
                placeholder_tanque = st.empty()
                st.subheader("Tendencia Temporal")
                placeholder_grafico = st.empty()
                st.subheader("⚙️ Acción del Controlador")
                placeholder_u = st.empty()
                st.markdown("---")
                st.subheader("⚙️ Estado de Operación: Válvula de Control")
                placeholder_valvula = st.empty()
                st.markdown("---")
                st.subheader("📊 Comparativa: Modelo Teórico vs Datos Experimentales")
                placeholder_comparativa = st.empty()
            
            with col_met:
                st.subheader("Métricas de Control Robusto")
                kp_show = st.session_state.get('kp_ejecucion', 18.0)
                ki_show = st.session_state.get('ki_ejecucion', 3.5)
                kd_show = st.session_state.get('kd_ejecucion', 1.5)
                cd_show = st.session_state.get('cd_final', 0.61)
                st.write(f"**Parámetros Activos:** Kp={kp_show} | Ki={ki_show} | Kd={kd_show} | Cd={cd_show:.3f}")
                placeholder_iae = st.empty()
                placeholder_itae = st.empty()
                m_h = st.empty()
                m_e = st.empty()
                m_h.metric("Nivel PV [m]", "0.000")
                m_e.metric("Error [m]", "0.000")
    
            # Preparación
            status_placeholder = st.empty()
            dt = 1.0
            vector_t = np.arange(0, tiempo_ensayo, dt)
            h_log, u_log, e_log = [], [], []
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
                status_placeholder.markdown("**💧 CONTROL ROBUSTO ACTIVADO - PROCESANDO...**")
                
                if p_activa and t_act >= p_tiempo:
                    if modo_estres:
                        factor = 1.5 if valor_presente < sp_nivel else 0.5
                        q_p_inst = p_magnitud * factor
                    else:
                        q_p_inst = p_magnitud
                else:
                    q_p_inst = 0.0
                
                k_p = st.session_state.get('kp_ejecucion', 18.0)
                k_i = st.session_state.get('ki_ejecucion', 3.5)
                k_d = st.session_state.get('kd_ejecucion', 1.5)
                
                h_corrida, u_inst, e_inst, err_int, err_pasado = resolver_sistema_robusto(
                    dt, h_corrida, sp_nivel, geom_tanque, r_max, h_total, q_p_inst,
                    err_int, err_pasado, op_tipo, cd_para_simular, k_p, k_i, k_d, d_pulgadas
                )
                
                valor_presente = h_corrida
                error_presente = e_inst
                iae_acumulado += abs(e_inst) * dt
                itae_acumulado += (t_act * abs(e_inst)) * dt
                
                h_log.append(h_corrida)
                u_log.append(u_inst)
                e_log.append(e_inst)
                
                m_h.metric("Nivel PV [m]", f"{valor_presente:.3f}")
                m_e.metric("Error [m]", f"{error_presente:.4f}")
                placeholder_iae.metric("IAE (Error Acumulado)", f"{iae_acumulado:.2f}")
                placeholder_itae.metric("ITAE (Criterio Tesis)", f"{itae_acumulado:.2f}")
                
                # VISUALIZACIÓN DEL TANQUE
                fig_t, ax_t = plt.subplots(figsize=(7, 5))
                ax_t.set_axis_off()
                ax_t.set_xlim(-r_max*3, r_max*3)
                ax_t.set_ylim(-0.8, h_total*1.3)
                color_agua = '#3498db'
                
                if geom_tanque == "Cilíndrico":
                    c_in_x, c_in_y = -r_max, h_total*0.8
                    c_out_x, c_out_y = r_max, 0.1
                    ax_t.plot([-r_max, -r_max, r_max, r_max], [h_total, 0, 0, h_total], color='#2c3e50', lw=5, zorder=2)
                    ax_t.add_patch(plt.Rectangle((-r_max, 0), 2*r_max, valor_presente, color=color_agua, alpha=0.85, zorder=1, edgecolor='#2980b9', linewidth=1.5))
                    if 0 < valor_presente < h_total:
                        ax_t.axhline(y=valor_presente, color='white', linestyle='-', linewidth=2, alpha=0.8, zorder=3)
                elif geom_tanque == "Cónico":
                    c_in_x, c_in_y = -(r_max/h_total)*(h_total*0.8), h_total*0.8
                    c_out_x, c_out_y = 0, 0
                    ax_t.plot([-r_max, 0, r_max], [h_total, 0, h_total], color='#2c3e50', lw=5, zorder=2)
                    if valor_presente > 0:
                        radio_superficie = (r_max / h_total) * valor_presente
                        vertices = [[-radio_superficie, valor_presente], [radio_superficie, valor_presente], [0, 0]]
                        ax_t.add_patch(plt.Polygon(vertices, color=color_agua, alpha=0.85, zorder=1, edgecolor='#2980b9', linewidth=1.5))
                        ax_t.plot([-radio_superficie, radio_superficie], [valor_presente, valor_presente], color='white', linewidth=2, alpha=0.8, zorder=3)
                else:  # Esférico
                    import math
                    c_in_y = h_total * 0.7
                    c_in_x = -math.sqrt(abs(r_max**2 - (c_in_y - r_max)**2))
                    c_out_x, c_out_y = 0, 0
                    agua_esf = plt.Circle((0, r_max), r_max, color=color_agua, alpha=0.85, zorder=1, edgecolor='#2980b9', linewidth=1.5)
                    ax_t.add_patch(agua_esf)
                    recorte_nivel = plt.Rectangle((-r_max, 0), 2*r_max, valor_presente, transform=ax_t.transData)
                    agua_esf.set_clip_path(recorte_nivel)
                    ax_t.add_patch(plt.Circle((0, r_max), r_max, color='#2c3e50', fill=False, lw=5, zorder=2))
                    if 0 < valor_presente < 2*r_max:
                        radio_nivel = math.sqrt(r_max**2 - (valor_presente - r_max)**2)
                        ax_t.plot([-radio_nivel, radio_nivel], [valor_presente, valor_presente], color='white', linewidth=2, alpha=0.8, zorder=3)
                
                # Válvulas
                ax_t.add_patch(plt.Rectangle((c_in_x - 1.5, c_in_y - 0.1), 1.5, 0.2, color='silver', zorder=0))
                ax_t.add_patch(plt.Polygon([[c_in_x-1, c_in_y+0.2], [c_in_x-1, c_in_y-0.2], [c_in_x-0.6, c_in_y]], color='#2c3e50', zorder=2))
                ax_t.add_patch(plt.Polygon([[c_in_x-0.2, c_in_y+0.2], [c_in_x-0.2, c_in_y-0.2], [c_in_x-0.6, c_in_y]], color='#2c3e50', zorder=2))
                ax_t.text(c_in_x-0.6, c_in_y+0.4, "V-01", ha='center', fontsize=9, fontweight='bold')
                
                if geom_tanque == "Cilíndrico":
                    ax_t.add_patch(plt.Rectangle((c_out_x, c_out_y - 0.1), 1.5, 0.2, color='silver', zorder=0))
                    vs_x, vs_y = c_out_x + 0.8, c_out_y
                else:
                    ax_t.add_patch(plt.Rectangle((c_out_x - 0.1, -0.6), 0.2, 0.6, color='silver', zorder=0))
                    vs_x, vs_y = c_out_x, -0.4
                ax_t.add_patch(plt.Polygon([[vs_x-0.25, vs_y+0.2], [vs_x-0.25, vs_y-0.2], [vs_x, vs_y]], color='#2c3e50', zorder=2))
                ax_t.add_patch(plt.Polygon([[vs_x+0.25, vs_y+0.2], [vs_x+0.25, vs_y-0.2], [vs_x, vs_y]], color='#2c3e50', zorder=2))
                offset_t = 0.4 if geom_tanque == "Cilíndrico" else 0
                ax_t.text(vs_x + offset_t, vs_y - 0.5, "V-02 (CV)", ha='center', fontsize=9, fontweight='bold')
                
                ax_t.axhline(y=sp_nivel, color='red', ls='--', lw=2, zorder=3, alpha=0.8)
                ax_t.text(-r_max*2.8, sp_nivel + 0.05, f"SETPOINT: {sp_nivel:.2f}m", color='red', fontweight='bold', fontsize=9)
                ax_t.text(0, h_total * 1.2, f"PV: {valor_presente:.3f} m", ha='center', va='center', fontsize=11, fontweight='bold',
                          bbox=dict(facecolor='white', alpha=0.9, edgecolor='#1a5276', boxstyle='round,pad=0.5', lw=2))
                
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
                
                # Gráfica de acción de control
                fig_u, ax_u = plt.subplots(figsize=(8, 2.5))
                ax_u.step(vector_t[:i+1], u_log, color='#e67e22', where='post', label='Flujo de Control')
                if p_activa and p_tiempo > 0:
                    ax_u.axvline(x=p_tiempo, color='red', linestyle='--', alpha=0.5)
                ax_u.set_xlim(0, tiempo_ensayo)
                techo_dinamico = max(max(u_log), 0.1) * 1.2 if u_log else 0.7
                ax_u.set_ylim(0, techo_dinamico)
                ax_u.grid(True, alpha=0.2)
                ax_u.set_xlabel('Tiempo [s]')
                ax_u.set_ylabel('Flujo [m³/s]')
                ax_u.legend(loc='upper right', fontsize='x-small')
                placeholder_u.pyplot(fig_u)
                plt.close(fig_u)
                
                # Válvula
                fig_v, ax_v = plt.subplots(figsize=(8, 3))
                ax_v.plot(vector_t[:i+1], u_log, color='#2ecc71', lw=2.5)
                ax_v.fill_between(vector_t[:i+1], u_log, color='#2ecc71', alpha=0.15)
                ax_v.set_ylim(-0.1, 1.1)
                ax_v.set_yticks([0, 0.5, 1])
                ax_v.set_yticklabels(['CERRADA', '50%', 'ABIERTA'])
                ax_v.set_title("Apertura de Válvula de Control")
                placeholder_valvula.pyplot(fig_v)
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
            st.success(f"✅ Simulación Robusta completada - El controlador mantuvo el nivel ante las perturbaciones")
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
                "Control [m³/s]": u_log,
                "Error [m]": e_log,
                "Kp_Usado": [st.session_state.get('kp_ejecucion', 18.0)] * len(vector_t),
                "Ki_Usado": [st.session_state.get('ki_ejecucion', 3.5)] * len(vector_t),
                "Kd_Usado": [st.session_state.get('kd_ejecucion', 1.5)] * len(vector_t)
            })
            
            st.subheader("📋 Resumen de Datos y Estabilidad del Control Robusto")
            col_tab, col_res = st.columns([2, 1])
            with col_tab:
                st.dataframe(df_final.tail(10).style.format("{:.4f}"), use_container_width=True)
            with col_res:
                err_f = abs(sp_nivel - h_log[-1]) if len(h_log) > 0 else 0
                st.metric("Error Residual Final", f"{err_f:.4f} m")
                st.download_button(
                    label="📥 Descargar Reporte de Simulación Robusta (CSV)",
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

    # ==== PRACTICA 1 Calibración de un Medidor de Flujo =====
    
    elif nombre == "Calibración de un Medidor de Flujo":
        with st.expander(" Biblioteca Virtual - Descargar Práctica", expanded=True):
            pdf_path = "Manual de la Práctica 1. Calibración de un Medidor de Flujo..pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(label="📥 Descargar Guía (PDF)", data=f, file_name="Manual_Practica1_Calibracion.pdf", mime="application/pdf")
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
            with st.expander("📊 Diagrama del Proceso", expanded=True):
                st.image("1 CALIBRACIÓN DE UN MEDIDOR DE FLUJO.png", use_container_width=True)
    
    elif nombre == "Pérdidas de Presión por Fricción":
        st.info("Práctica: Pérdidas de Presión por Fricción - En desarrollo")
    
    elif nombre == "Bombas Centrífugas":
        st.info("Práctica: Bombas Centrífugas - En desarrollo")
    
    elif nombre == "Lechos Fluidizados":
        st.info("Práctica: Lechos Fluidizados - En desarrollo")
    
    elif nombre in ["Hidrodinámica de Columnas Empacadas", "Filtración a Presión Constante", 
                    "Destilación Diferencial", "Destilación Continua", "Rectificación en Torre Rellena"]:
        st.info(f"Práctica: {nombre} - En desarrollo")

    # ======================== FOOTER ========================
    st.markdown("""
    <hr style="margin: 2rem 0 1rem 0; border-color: #1a5276;">
    <div style="text-align: center; color: #5d6d7e; font-size: 0.8rem;">
        <p>Universidad Central de Venezuela - Escuela de Ingeniería Química</p>
        <p>Laboratorio de Operaciones Unitarias | Centro de Simulación Virtual | © 2025</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# EJECUCIÓN
# =============================================================================
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page)

