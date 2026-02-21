import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="AutoTrasa - Planer Cyklu", layout="wide")

# --- CUSTOM CSS (Dla lepszego wyglądu) ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stSidebar"] {
        background-color: #1e293b;
        color: white;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #0083B8;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA STANU ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- PANEL BOCZNY (Stylizowany) ---
with st.sidebar:
    # Dodajmy obrazek nagłówka (możesz tu wstawić URL do swojego logo)
    st.image("https://img.icons8.com/fluency/96/delivery-tracking.png", width=80)
    st.title("AutoTrasa v3.0")
    st.write("---")
    
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    limit_dzienny = st.slider("🎯 Limit dzienny", 1, 30, 12)
    
    st.write("---")
    st.header("📈 Postęp")
    wizyty_wykonane = st.number_input("Zrobiono wizyt:", min_value=0, value=0)
    
    st.write("---")
    st.header("📅 Wolne")
    wybrane = st.date_input("Wybierz daty:", value=(), min_value=date(2025, 1, 1))
    
    if st.button("➕ Dodaj wolne"):
        if isinstance(wybrane, (list, tuple)) and len(wybrane) > 0:
            if len(wybrane) == 2:
                start, end = wybrane
                dni = []
                curr = start
                while curr <= end:
                    dni.append(curr)
                    curr += timedelta(days=1)
                st.session_state.nieobecnosci.append({'label': f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}", 'dni': dni})
            else:
                d = wybrane[0]
                st.session_state.nieobecnosci.append({'label': f"{d.strftime('%d.%m')}", 'dni': [d]})
            st.rerun()

    suma_wolnych = 0
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1])
        c1.caption(f"📅 {g['label']}")
        if c2.button("X", key=f"del_{i}"):
            st.session_state.nieobecnosci.pop(i)
            st.rerun()
        suma_wolnych += len(g['dni'])

# --- GŁÓWNA TREŚĆ ---
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("🚚 Inteligentny Planer Trasy")
    st.write(f"Witaj! Dzisiaj mamy **{date.today().strftime('%d.%m.%Y')}**")

# --- WCZYTYWANIE I MATEMATYKA ---
uploaded_file = st.file_uploader("Wgraj bazę klientów (CSV)", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # Matematyka cyklu
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, cel_total - wizyty_wykonane)
        wymagana_srednia = do_zrobienia / dni_n if dni_n > 0 else 0
        
        # --- WIZUALIZACJA: KARTY ---
        st.write("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏢 Klienci", len(df))
        m2.metric("📆 Dni netto", dni_n)
        m3.metric("🎯 Pozostało wizyt", do_zrobienia)
        m4.metric("📊 Postęp", f"{round((wizyty_wykonane/cel_total*100),1)}%" if cel_total>0 else "0%")

        # --- WYKRES I ANALIZA ---
        c_left, c_right = st.columns([2, 1])
        with c_left:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                title = {'text': "Wymagana średnia / dzień"},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#FF4B4B" if wymagana_srednia > limit_dzienny else "#22C55E"},
                    'threshold': {'line': {'color': "#1E293B", 'width': 4}, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.markdown("### 📋 Raport Sytuacyjny")
            if wymagana_srednia > limit_dzienny:
                st.warning(f"Plan jest **zagrożony**. Musisz zwiększyć limit dzienny o {round(wymagana_srednia - limit_dzienny, 1)} wizyty.")
            else:
                st.success("Wszystko pod kontrolą! Twój limit pozwala na realizację planu z zapasem.")

        # --- MAPA SEKCJA ---
        st.write("---")
        st.subheader("📍 Mapa Twoich Klientów")
        # Tu wstawimy geolokalizację w następnym kroku
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6, tiles="cartodbpositron")
        st_folium(m, width=1300, height=500)

    except Exception as e:
        st.error(f"Coś poszło nie tak: {e}")
