import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# --- KONFIGURACJA PREMIUM ---
st.set_page_config(page_title="A2B FlowRoute - Asystent Trasy", layout="wide")

# --- CUSTOM CSS (Style z Twojego obrazu) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #F4F7F9;
    }

    /* Pasek boczny - Deep Navy */
    [data-testid="stSidebar"] {
        background-color: #1A2238 !important;
        border-right: 1px solid #2D3748;
    }

    /* Karty Dashboardu - White Cards */
    div[data-testid="stMetric"] {
        background: white;
        border-radius: 12px !important;
        padding: 20px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
        border-left: 5px solid #22B1CC !important;
    }

    /* Nagłówek aplikacji */
    .header-container {
        background-color: #1A2238;
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Przycisk A2B Style */
    .stButton>button {
        background-color: #22B1CC !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        width: 100%;
        height: 45px;
    }

    /* Inputy i Selektory */
    .stSelectbox, .stNumberInput {
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- STAN SESJI ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR (A2B FlowRoute Style) ---
with st.sidebar:
    # Stylizowane LOGO A2B
    st.markdown("""
        <div style='text-align: center; padding: 10px; border: 2px solid #22B1CC; border-radius: 10px; margin-bottom: 20px;'>
            <h1 style='color: #22B1CC; margin: 0; font-size: 28px;'>A2B</h1>
            <p style='color: white; margin: 0; font-size: 14px; letter-spacing: 2px;'>FLOWROUTE</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<p style='color: #94A3B8; text-align: center;'>Asystent Twojej Trasy</p>", unsafe_allow_html=True)
    st.write("---")
    
    st.subheader("⚙️ Twój Cykl")
    typ_cyklu = st.selectbox("Czas trwania", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    twoje_tempo = st.slider("Twoje tempo (wizyty/dzień)", 1, 30, 12)
    
    st.write("---")
    st.subheader("📉 Postęp dnia")
    zrobione = st.number_input("Ile wizyt już za Tobą?", min_value=0, value=0)
    
    st.write("---")
    st.subheader("📅 Planowane Wolne")
    wybrane_daty = st.date_input("Zaznacz dni:", value=(), min_value=date(2025, 1, 1))
    
    if st.button("DODAJ DO PLANU"):
        if isinstance(wybrane_daty, (list, tuple)) and len(wybrane_daty) > 0:
            if len(wybrane_daty) == 2:
                s, e = wybrane_daty
                dni = [s + timedelta(days=x) for x in range((e-s).days + 1)]
                st.session_state.nieobecnosci.append({'label': f"{s.strftime('%d.%m')} - {e.strftime('%d.%m')}", 'count': len(dni)})
            else:
                st.session_state.nieobecnosci.append({'label': wybrane_daty[0].strftime('%d.%m'), 'count': 1})
            st.rerun()

    # Lista wolnych
    suma_wolnych = 0
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"<span style='color: #94A3B8; font-size: 0.9rem;'>🏝️ {g['label']}</span>", unsafe_allow_html=True)
        if c2.button("✕", key=f"d_{i}"):
            st.session_state.nieobecnosci.pop(i)
            st.rerun()
        suma_wolnych += g['count']

# --- PANEL GŁÓWNY ---
st.markdown("""
    <div class='header-container'>
        <div>
            <h2 style='margin:0; color: white;'>Cześć! Ruszamy w drogę? 👋</h2>
            <p style='margin:0; color: #22B1CC; opacity: 0.9;'>A2B FlowRoute - Twój optymalny asystent trasy</p>
        </div>
        <div style='text-align: right;'>
            <p style='margin:0; font-size: 1.2rem; font-weight: bold;'>v5.0 PRO</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę klientów (CSV)", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA (Przyjazne)
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, cel_total - zrobione)
        srednia_na_dzien = do_zrobienia / dni_n if dni_n > 0 else 0
        
        # --- METRYKI (A2B Style) ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci w bazie", f"{len(df)}", "Osoby/Punkty")
        m2.metric("Dni robocze", f"{dni_n}", "Pozostało")
        m3.metric("Zostało wizyt", f"{do_zrobienia}", "Cel")
        postep_proc = round((zrobione/cel_total*100), 1) if cel_total > 0 else 0
        m4.metric("Twój Postęp", f"{postep_proc}%", "W cyklu")

        # --- WYKRES GAUGE & ANALIZA ---
        st.write("---")
        cl, cr = st.columns([2, 1])
        
        with cl:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = srednia_na_dzien,
                title = {'text': "WYMAGANE TEMPO (WIZYTY / DZIEŃ)", 'font': {'color': '#1A2238'}},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#22B1CC"},
                    'bgcolor': "white",
                    'threshold': {'line': {'color': "#1A2238", 'width': 4}, 'value': twoje_tempo}
                }
            ))
            fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            
        with cr:
            st.markdown("### 💡 Wskazówki FlowRoute")
            if srednia_na_dzien > twoje_tempo:
                st.error(f"""
                **Trzeba nieco przyspieszyć!** Twoje tempo ({twoje_tempo}) jest niższe niż wymagane ({round(srednia_na_dzien,1)}). 
                Sugerujemy dodanie wizyty dziennie lub zmianę wolnych dni.
                """)
            else:
                st.success(f"""
                **Jedziesz idealnie!** Utrzymując tempo {twoje_tempo} wizyt dziennie, skończysz cykl z zapasem **{int((twoje_tempo * dni_n) - do_zrobienia)}** wizyt.
                Masz czas na spokojną kawę! ☕
                """)

        # --- MAPA ---
        st.write("---")
        st.subheader("📍 Twoja dzisiejsza mapa")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6, tiles="cartodbpositron")
        st_folium(m, width=1300, height=500)

    except Exception as e:
        st.error(f"Problem z plikiem: {e}")
