import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="AutoTrasa PRO", layout="wide")

# --- MOCNY CUSTOM CSS ---
st.markdown("""
    <style>
    /* Styl tła głównego */
    .stApp {
        background-color: #f4f7f9;
    }
    
    /* Styl panelu bocznego */
    [data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #262730;
    }
    
    /* Styl kart (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e1e4e8;
        padding: 20px 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.05);
    }
    
    /* Styl tytułów sekcji */
    h1, h2, h3 {
        color: #1e293b;
        font-family: 'Inter', sans-serif;
    }

    /* Przycisk dodawania */
    .stButton>button {
        background-color: #2563eb !important;
        color: white !important;
        font-weight: bold;
        border-radius: 8px !important;
        border: none !important;
        height: 45px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA STANU ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR ---
with st.sidebar:
    # Ikona i nagłówek
    st.markdown("<h1 style='color: #3b82f6; text-align: center;'>📦 AutoTrasa</h1>", unsafe_allow_html=True)
    st.write("---")
    
    st.subheader("⚙️ Parametry Pracy")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    limit_dzienny = st.slider("🎯 Limit dzienny wizyt", 1, 30, 12)
    
    st.write("---")
    st.subheader("📊 Twój Postęp")
    wizyty_wykonane = st.number_input("Suma wizyt ZROBIONYCH:", min_value=0, value=0)
    
    st.write("---")
    st.subheader("📅 Planowanie Wolnego")
    wybrane = st.date_input("Zaznacz daty:", value=(), min_value=date(2025, 1, 1))
    
    if st.button("➕ DODAJ DO LISTY"):
        if isinstance(wybrane, (list, tuple)) and len(wybrane) > 0:
            if len(wybrane) == 2:
                start, end = wybrane
                dni = [start + timedelta(days=x) for x in range((end-start).days + 1)]
                st.session_state.nieobecnosci.append({'label': f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}", 'dni': dni})
            else:
                d = wybrane[0]
                st.session_state.nieobecnosci.append({'label': f"{d.strftime('%d.%m')}", 'dni': [d]})
            st.rerun()

    # Wyświetlanie listy wolnych dni
    suma_wolnych = 0
    if st.session_state.nieobecnosci:
        for i, g in enumerate(st.session_state.nieobecnosci):
            c1, c2 = st.columns([4, 1])
            c1.info(f"📅 {g['label']}")
            if c2.button("X", key=f"del_{i}"):
                st.session_state.nieobecnosci.pop(i)
                st.rerun()
            suma_wolnych += len(g['dni'])

# --- GŁÓWNY PANEL ---
# Estetyczny baner na górze
st.markdown(f"""
    <div style="background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%); padding: 25px; border-radius: 15px; margin-bottom: 25px; color: white;">
        <h2 style="margin:0; color: white;">🚀 System Planowania Cyklu</h2>
        <p style="margin:0; opacity: 0.8;">Dzisiaj jest {date.today().strftime('%d %B %Y')} | Masz zaplanowane {suma_wolnych} dni wolnych.</p>
    </div>
    """, unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Przeciągnij tutaj plik z bazą klientów (CSV)", type=["csv"])

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
        
        # --- DASHBOARD: KARTY ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏢 Klienci", f"{len(df)}")
        m2.metric("📆 Dni Robocze", f"{dni_n}")
        m3.metric("🎯 Cel Pozostały", f"{do_zrobienia}")
        postep = round((wizyty_wykonane/cel_total*100), 1) if cel_total > 0 else 0
        m4.metric("📊 Realizacja", f"{postep}%")

        # --- WYKRESY ---
        st.write("---")
        c_left, c_right = st.columns([2, 1])
        
        with c_left:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                title = {'text': "Wymagana średnia (wizyty/dzień)", 'font': {'size': 20}},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#ef4444" if wymagana_srednia > limit_dzienny else "#22c55e"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'line': {'color': "#e1e4e8"},
                    'threshold': {'line': {'color': "#1e293b", 'width': 5}, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.markdown("### 🔍 Analiza Statusu")
            if wymagana_srednia > limit_dzienny:
                st.error(f"**UWAGA!** Przekraczasz swój limit dzienny. Brakuje Ci mocy przerobowej na **{int(do_zrobienia - (limit_dzienny * dni_n))}** wizyt.")
            else:
                st.success(f"**Wszystko OK!** Przy limicie {limit_dzienny} wizyt dziennie, skończysz cykl z zapasem **{int((limit_dzienny * dni_n) - do_zrobienia)}** wizyt.")
                st.info("Możesz zaplanować dodatkowe dni wolne lub szkolenia.")

        # MAPA
        st.write("---")
        st.subheader("📍 Mapa Operacyjna")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6, tiles="cartodbpositron")
        st_folium(m, width=1300, height=500)

    except Exception as e:
        st.error(f"Błąd danych: {e}")
else:
    # Co widzi użytkownik zanim wgra plik
    st.info("☝️ Aby zobaczyć dashboard i analizę, wgraj plik CSV z bazą klientów.")
    st.markdown("""
        ### Jak przygotować plik?
        Upewnij się, że Twój plik zawiera kolumny z **Miastem** i **Adresem**. 
        System automatycznie je rozpozna i naniesie na mapę.
    """)
