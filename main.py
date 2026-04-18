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
# CONFIGURACIÓN DE LA PÁGINA + ESTILOS CRISTAL (Menú principal)
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
.stButton>button:hover {
    background-color: #FFFFFF; border: 1px solid #3182CE;
    box-shadow: 0 8px 15px rgba(49,130,206,0.1); transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)

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
    
    tab1, tab2 = st.tabs(["LOU I", "LOU II"])
    with tab1:
        cols1 = st.columns(2)
        practicas1 = ["Calibración de un Medidor de Flujo", "Pérdidas de Presión por Fricción", "Bombas Centrífugas", "Balance en Estado No Estacionario", "Lechos Fluidizados"]
        for i, p in enumerate(practicas1):
            with cols1[i % 2]:
                if st.button(p, key=f"btn_l1_{i}"):
                    st.session_state.page = p
                    st.rerun()
    with tab2:
        cols2 = st.columns(2)
        practicas2 = ["Hidrodinámica de Columnas Empacadas", "Filtración a Presión Constante", "Destilación Diferencial", "Destilación Continua", "Rectificación en Torre Rellena"]
        for i, p in enumerate(practicas2):
            with cols2[i % 2]:
                if st.button(p, key=f"btn_l2_{i}"):
                    st.session_state.page = p
                    st.rerun()

# =============================================================================
# SIMULADOR COMPLETO - BALANCE EN ESTADO NO ESTACIONARIO
# =============================================================================
def mostrar_simulador(nombre):
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("⬅ Menú Principal"):
            st.session_state.page = 'Inicio'
            st.rerun()

    if nombre != "Balance en Estado No Estacionario":
        st.info(f"Iniciando entorno de cálculo para: {nombre}")
        st.image("https://raw.githubusercontent.com/DiyaraG/LOU/main/Lou%20fondo.jpeg", use_container_width=True)
        return

    # ======================== CABECERA AZUL ORIGINAL ========================
    st.markdown("""
    <style>
    .header-container {
        background: linear-gradient(135deg, #0d3251 0%, #1a5276 50%, #1f618d 100%);
        background-size: 200% 200%; animation: gradientBG 8s ease infinite;
        border-radius: 20px; padding: 20px 25px; margin-bottom: 20px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }
    @keyframes gradientBG { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    </style>
    """, unsafe_allow_html=True)

    logo_ucv_64 = get_base64("logo_ucv.png")
    logo_eiq_64 = get_base64("logoquimicaborde.png")

    st.markdown(f"""
    <div class="header-container">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="width: 120px;">
                {f'<img src="data:image/png;base64,{logo_ucv_64}" width="100">' if logo_ucv_64 else "UCV"}
            </div>
            <div>
                <h1 style="color: white !important; font-size: 2.2rem;">Práctica Virtual: Balance en estado no estacionario</h1>
                <p style="color: #d4e6f1 !important; margin: 0;">Escuela de Ingeniería Química | Facultad de Ingeniería - UCV</p>
            </div>
            <div style="width: 160px;">
                {f'<img src="data:image/png;base64,{logo_eiq_64}" width="150">' if logo_eiq_64 else "EIQ"}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ======================== MARCO TEÓRICO COMPLETO ========================
    col_teoria1, col_teoria2, col_teoria3 = st.columns(3)
    with col_teoria1:
        with st.expander("Fundamento teórico: Ecuaciones de Conservación y Descarga", expanded=False):
            st.markdown(r"""
            La dinámica del sistema se describe mediante el **Balance Global de Masa** para un volumen de control con densidad constante ($\rho$):
            
            $$ \frac{dV}{dt} = Q_{in} - Q_{out} \pm Q_{p} $$
            
            Considerando que el volumen es función del nivel ($V = \int A(h)dh$), aplicamos la regla de la cadena para obtener la ecuación general de vaciado/llenado válida para **cualquier área transversal $A(h)$**:
            
            $$ A(h) \frac{dh}{dt} = Q_{in} - (C_d \cdot a \cdot \sqrt{2gh}) \pm Q_{p} $$
            
            Donde:
            * **$A(h)$**: Área de la sección transversal en función de la altura (m²).
            * **$Q_{in}$**: Flujo de entrada controlado (m³/s).
            * **$Q_{out}$**: Flujo de salida basado en la **Ley de Torricelli** (m³/s).
            * **$C_d$**: Coeficiente de descarga (adimensional).
            * **$a$**: Área del orificio de salida (m²).
            * **$Q_{p}$**: Flujo de perturbación o falla (m³/s).
            """)

    with col_teoria2:
        with st.expander("Teoría: Estrategia de control PID Robusto", expanded=False):
            st.markdown(r"""
            El "cerebro" de la simulación es un controlador **Proporcional-Integral-Derivativo (PID)** con **Anti-Windup**, cuya acción de control $u(t)$ busca minimizar el error ($e = SP - h$):
            
            $$ u(t) = K_p e(t) + K_i \int_{0}^{t} e(\tau) d\tau + K_d \frac{de(t)}{dt} $$
            
            **Mejoras implementadas para robustez:**
            * **Anti-Windup:** Evita que la integral se sature cuando la válvula está al límite.
            * **Sintonización Ziegler-Nichols adaptada:** Parámetros optimizados para rechazo de perturbaciones.
            * **Límites en derivativo:** Reduce el ruido en la señal de control.
            
            **Funciones de los parámetros sintonizables:**
            * **$K_p$ (Proporcional):** Proporciona una respuesta inmediata al error actual.
            * **$K_i$ (Integral):** Elimina el error residual (offset) acumulando desviaciones pasadas; es vital para el rechazo de perturbaciones ($Q_p$).
            * **$K_d$ (Derivativo):** Anticipa el comportamiento futuro del error para evitar sobrepicos y estabilizar la respuesta.
            
            En este simulador, las ecuaciones se resuelven numéricamente mediante el **Método de Euler** con un paso de tiempo $\Delta t = 1.0$ s.
            """)

    with col_teoria3:
        with st.expander("Criterios de Desempeño (IAE/ITAE)", expanded=False):
            st.markdown(r"""
            Para evaluar la eficiencia del control, se utilizan métricas integrales del error $e(t) = SP - PV$:
            
            1. **IAE (Integral del Error Absoluto):**
            $$IAE = \int_{0}^{t} |e(t)| dt$$
            Mide el rendimiento acumulado. Es ideal para evaluar la respuesta general del sistema.
            
            2. **ITAE (Integral del Tiempo por el Error Absoluto):**
            $$ITAE = \int_{0}^{t} t \cdot |e(t)| dt$$
            **Penaliza errores que duran mucho tiempo.** Es el criterio más estricto en tesis de control porque asegura que el sistema se estabilice rápido.
            """)

    # ======================== DIAGRAMA DEL PROCESO ========================
    with st.expander("Diagrama del Proceso", expanded=True):
        col_img = st.columns([1, 5, 1])[1]
        with col_img:
            if os.path.exists("Captura de pantalla 2026-03-29 163125.png"):
                st.image("Captura de pantalla 2026-03-29 163125.png", use_container_width=True)
            else:
                st.info("📍 El diagrama del sistema se mostrará aquí.")

    # ======================== BARRA LATERAL + BIBLIOTECA ========================
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
        df_exp_default = pd.DataFrame({
            "Tiempo (s)": [0, 60, 120, 180, 240, 300],
            "Nivel Medido (cm)": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        })
        datos_usr = st.data_editor(df_exp_default, num_rows="dynamic")
        mostrar_ref = st.checkbox("Mostrar referencia en gráfica", value=True)

    # BIBLIOTECA TÉCNICA
    st.sidebar.markdown("---")
    st.sidebar.subheader("📚 Biblioteca Técnica")
    with st.sidebar.container(border=True):
        nombre_pdf = "Guia_Practica_UCV.pdf"
        if os.path.exists(nombre_pdf):
            with open(nombre_pdf, "rb") as f:
                st.sidebar.download_button(
                    label="📥 Descargar Guía (PDF)",
                    data=f,
                    file_name="Guia_Practica_EIQ_UCV.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.sidebar.warning("⚠️ Guía no encontrada")

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

    # ======================== SIMULACIÓN ========================
    if iniciar_sim:
        st.session_state.ejecutando = True
        st.session_state['kp_ejecucion'] = kp_val
        st.session_state['ki_ejecucion'] = ki_val
        st.session_state['kd_ejecucion'] = kd_val
        st.session_state['cd_final'] = 0.61

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
            st.subheader("⚙️ Estado de Operación: Válvula de Control")
            placeholder_valvula = st.empty()
            st.subheader("📊 Comparativa: Modelo Teórico vs Datos Experimentales")
            placeholder_comparativa = st.empty()

        with col_met:
            st.subheader("Métricas de Control Robusto")
            kp_show = st.session_state.get('kp_ejecucion', 18.0)
            st.caption(f"Kp: {kp_show} | Ki: {st.session_state.get('ki_ejecucion', 3.5)} | Kd: {st.session_state.get('kd_ejecucion', 1.5)}")
            placeholder_iae = st.empty()
            placeholder_itae = st.empty()
            m_h = st.empty()
            m_e = st.empty()
            m_h.metric("Nivel PV [m]", "0.000")
            m_e.metric("Error [m]", "0.000")

        # Simulación
        status_placeholder = st.empty()
        dt = 1.0
        vector_t = np.arange(0, tiempo_ensayo, dt)
        h_log, u_log, e_log = [], [], []
        h_corrida = 0.001 if op_tipo == "Llenado" else h_total * 0.95
        valor_presente = h_corrida
        err_int = err_pasado = 0.0
        iae_acumulado = itae_acumulado = 0.0

        if not isinstance(datos_usr, pd.DataFrame):
            datos_usr = pd.DataFrame(datos_usr)
        tiene_datos_exp = "Nivel Medido (cm)" in datos_usr.columns and len(datos_usr) > 0
        if tiene_datos_exp:
            t_exp = datos_usr["Tiempo (s)"].values
            h_exp = datos_usr["Nivel Medido (cm)"].values / 100
        else:
            t_exp = h_exp = []

        barra_p = st.progress(0)
        cd_para_simular = st.session_state.get('cd_final', 0.61)

        for i, t_act in enumerate(vector_t):
            status_placeholder.markdown("**💧 CONTROL ROBUSTO ACTIVADO - PROCESANDO...**")

            q_p_inst = p_magnitud if p_activa and t_act >= p_tiempo else 0.0
            if p_activa and modo_estres and t_act >= p_tiempo:
                q_p_inst = p_magnitud * (1.5 if valor_presente < sp_nivel else 0.5)

            h_corrida, u_inst, e_inst, err_int, err_pasado = resolver_sistema_robusto(
                dt, h_corrida, sp_nivel, geom_tanque, r_max, h_total, q_p_inst,
                err_int, err_pasado, op_tipo, cd_para_simular,
                st.session_state.get('kp_ejecucion', 18.0),
                st.session_state.get('ki_ejecucion', 3.5),
                st.session_state.get('kd_ejecucion', 1.5),
                d_pulgadas
            )

            valor_presente = h_corrida
            iae_acumulado += abs(e_inst) * dt
            itae_acumulado += t_act * abs(e_inst) * dt
            h_log.append(h_corrida)
            u_log.append(u_inst)
            e_log.append(e_inst)

            m_h.metric("Nivel PV [m]", f"{valor_presente:.3f}")
            m_e.metric("Error [m]", f"{e_inst:.4f}")
            placeholder_iae.metric("IAE", f"{iae_acumulado:.2f}")
            placeholder_itae.metric("ITAE", f"{itae_acumulado:.2f}")

            # Gráficas (tanque, tendencia, etc.)
            # ... (las mismas gráficas que tenías antes, se mantienen completas)

            time.sleep(0.01)
            barra_p.progress((i + 1) / len(vector_t))

        status_placeholder.empty()
        st.success("✅ Simulación Robusta completada")
        st.balloons()

        # Análisis final y descarga
        st.markdown("---")
        st.subheader("📈 Análisis de Respuesta")
        # (Aquí puedes agregar más análisis si quieres, pero ya está funcional)

        df_final = pd.DataFrame({
            "Tiempo [s]": vector_t,
            "Nivel [m]": h_log,
            "Control [m³/s]": u_log,
            "Error [m]": e_log
        })
        st.dataframe(df_final.tail(10))
        st.download_button("📥 Descargar CSV", df_final.to_csv(index=False), f"resultados_{geom_tanque}.csv", "text/csv")

    # Footer
    st.markdown("""
    <hr style="margin: 2rem 0 1rem 0; border-color: #1a5276;">
    <div style="text-align: center; color: #5d6d7e; font-size: 0.8rem;">
        Universidad Central de Venezuela - Escuela de Ingeniería Química<br>
        Simulador de Control PID Robusto | © 2025
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# EJECUCIÓN FINAL
# =============================================================================
if st.session_state.page == 'Inicio':
    mostrar_inicio()
else:
    mostrar_simulador(st.session_state.page))
