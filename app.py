import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# 1. Musi być na samym początku
st.set_page_config(page_title="AutoTrasa PRO", layout="wide")

# 2. PROSTY I SKUTECZNY CSS
st.markdown("""
    <style>
    /* Główne tło */
    .stApp { background-color: #F0F2F6; }
    
    /* Nagłówek */
    .main-header {
        background: linear-gradient(90deg, #00416A 0%, #E4E5E6 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
    }
    
    /* Stylizacja bocznego panelu */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h1, h2, h3, p {
        color: white !important;
    }
    
    /* Karty wyników */
    div[data-testid="metric-container"] {
        background-color: white;
        border: 2px solid #00416A;
        padding: 15px;
        border-radius: 15px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIKA SESJI ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR (PANEL BOCZNY) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063822.png", width=100)
    st.markdown("# AutoTrasa Pro")
    st.write("---")
    
    st.subheader("Ustawienia")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty na 1 klienta", min_value=1, value=1)
    limit_dzienny = st.slider("Twój limit dzienny", 1, 30, 12)
    
    st.write("---")
    st.subheader("Postępy")
    wizyty_wykonane = st.number_input("Wizyty zrobione", min_value=0, value=0)
    
    st.write("---")
    st.subheader("Dni Wolne")
    wybrane = st.date_input("Kalendarz:", value=(), min_value=date(2025, 1, 1))
    
    if st.button("➕ DODAJ"):
        if isinstance(wybrane, (list, tuple)) and len(wybrane) > 0:
            if len(wybrane) == 2:
                start, end = wybrane
                dni = [start + timedelta(days=x) for x in range((end-start).days + 1)]
                st.session_state.nieobecnosci.append({'label': f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}", 'dni': dni})
            else:
                d = wybrane[0]
                st.session_state.nieobecnosci.append({'label': f"{d.strftime('%d.%m')}", 'dni': [d]})
            st.rerun()

    suma_wolnych = 0
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1])
        c1.write(f"📅 {g['label']}")
        if c2.button("X", key=f"del_{i}"):
            st.session_state.nieobecnosci.pop(i)
            st.rerun()
        suma_wolnych += len(g['dni'])

# --- PANEL GŁÓWNY ---
st.markdown('<div class="main-header"><h1>🚚 PLANER TRASY I CYKLU</h1><p>Wersja Professional v3.2</p></div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę (CSV)", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, cel_total - wizyty_wykonane)
        wymagana_srednia = do_zrobienia / dni_n if dni_n > 0 else 0
        
        # KARTY
        st.write("### 📊 Podsumowanie operacyjne")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci", f"{len(df)}")
        m2.metric("Dni Netto", f"{dni_n}")
        m3.metric("Do zrobienia", f"{do_zrobienia}")
        postep = round((wizyty_wykonane/cel_total*100), 1) if cel_total > 0 else 0
        m4.metric("Postęp %", f"{postep}%")

        # WYKRES
        st.write("---")
        c_l, c_r = st.columns([2, 1])
        with c_l:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                title = {'text': "Wymagana średnia (wizyty/dzień)"},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "red" if wymagana_srednia > limit_dzienny else "green"},
                    'threshold': {'line': {'color': "black", 'width': 4}, 'value': limit_dzienny}
                }
            ))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_r:
            st.write("### 🔍 Status")
            if wymagana_srednia > limit_dzienny:
                st.error(f"Zbyt mały limit! Brakuje Ci **{int(do_zrobienia - (limit_dzienny * dni_n))}** wizyt.")
            else:
                st.success(f"Działasz z zapasem **{int((limit_dzienny * dni_n) - do_zrobienia)}** wizyt.")

        # MAPA
        st.write("---")
        st.write("### 📍 Mapa Twoich punktów")
        st_folium(folium.Map(location=[52.0688, 19.4797], zoom_start=6), width=1300, height=500)

    except Exception as e:
        st.error(f"Błąd: {e}")
else:
    st.warning("Wgraj plik CSV, aby zobaczyć dashboard.")
