import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- KONFIGURACJA ---
st.set_page_config(page_title="A2B FlowRoute PRO", layout="wide", initial_sidebar_state="expanded")

# --- KOLORYSTYKA I COMPACT CSS ---
COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"

st.markdown(f"""
    <style>
    /* Globalne tło i czcionka */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        background-color: {COLOR_BG};
    }}
    .stApp {{ background-color: {COLOR_BG}; color: white; }}

    /* KOMPAKTOWY SIDEBAR */
    [data-testid="stSidebar"] {{
        background-color: {COLOR_NAVY_DARK} !important;
        min-width: 250px !important;
        max-width: 300px !important;
    }}
    
    /* Zmniejszenie paddingu na górze sidebaru */
    [data-testid="stSidebarContent"] {{
        padding-top: 1rem !important;
    }}

    /* Zmniejszenie odstępów między elementami w sidebarze */
    [data-testid="stSidebarContent"] .stVerticalBlock {{
        gap: 0.4rem !important;
    }}

    /* Odstępy przy liniach poziomej */
    hr {{
        margin: 0.5rem 0 !important;
        opacity: 0.2;
    }}

    /* Stylizacja kart metryk (Dashboard) */
    div[data-testid="stMetric"] {{
        background-color: white;
        border-radius: 12px;
        padding: 15px !important;
        border-left: 5px solid {COLOR_CYAN};
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }}
    div[data-testid="stMetric"] label {{ color: #64748B !important; font-weight: 600; }}
    div[data-testid="stMetricValue"] {{ color: {COLOR_NAVY_DARK} !important; font-size: 1.8rem !important; }}

    /* Przyciski */
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
        transition: 0.3s;
    }}
    .stButton>button:hover {{ transform: scale(1.02); box-shadow: 0 0 10px {COLOR_CYAN}80; }}

    /* Styl listy nieobecności */
    .absence-item {{
        background: rgba(255,255,255,0.05);
        padding: 5px 10px;
        border-radius: 5px;
        margin-bottom: 2px;
        font-size: 0.85rem;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- LOGIKA SESJI ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR ---
with st.sidebar:
    # Logo z folderu assets
    try:
        st.image("assets/logo_a2b.png", use_container_width=True)
    except:
        st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    
    # Parametry (Zagęszczone)
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    st.write("---")
    
    # Wolne (Kompaktowe)
    dni_input = st.date_input("Dodaj wolne/urlop:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ DO PLANU"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            if len(dni_input) == 2:
                s, e = dni_input
                count = (e - s).days + 1
                label = f"{s.strftime('%d.%m')} - {e.strftime('%d.%m')}"
            else:
                count = 1
                label = f"{dni_input[0].strftime('%d.%m')}"
            st.session_state.nieobecnosci.append({'label': label, 'count': count})
            st.rerun()

    # Wyświetlanie listy wolnych dni
    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    if st.session_state.nieobecnosci:
        st.markdown(f"<p style='font-size:0.8rem; color:{COLOR_CYAN}'>PLANOWANE WOLNE ({suma_wolnych} dni):</p>", unsafe_allow_html=True)
        for i, g in enumerate(st.session_state.nieobecnosci):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"<div class='absence-item'>🏝️ {g['label']}</div>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{i}"):
                st.session_state.nieobecnosci.pop(i)
                st.rerun()

# --- PANEL GŁÓWNY ---
st.markdown(f"""
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <h1 style='margin:0;'>Dashboard A2B FlowRoute</h1>
        <div style='background:{COLOR_CYAN}; color:white; padding:5px 15px; border-radius:20px; font-weight:bold;'>PRO v7.5</div>
    </div>
    <p style='color:#8A9AB8; margin-top:0;'>Optymalizacja trasy dla Przedstawicieli</p>
    """, unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę klientów (CSV)", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_cel
        do_zrobienia = max(0, cel_total - zrobione)
        srednia = do_zrobienia / dni_n if dni_n > 0 else 0

        # METRYKI
        st.write("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Liczba Klientów", len(df))
        m2.metric("Dni Robocze", dni_n)
        m3.metric("Pozostało Wizyt", do_zrobienia)
        realizacja = round((zrobione/cel_total*100),1) if cel_total>0 else 0
        m4.metric("Realizacja Cyklu", f"{realizacja}%")

        # ANALIZA I WYKRES
        st.write("---")
        cl, cr = st.columns([2, 1])
        
        with cl:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = srednia,
                number = {'font': {'color': COLOR_CYAN}},
                title = {'text': "WYMAGANE TEMPO (WIZYTY/DZIEŃ)", 'font': {'color': 'white', 'size': 16}},
                gauge = {
                    'axis': {'range': [None, 30], 'tickcolor': "white"},
                    'bar': {'color': COLOR_CYAN},
                    'bgcolor': "rgba(255,255,255,0.1)",
                    'threshold': {'line': {'color': "red", 'width': 4}, 'value': tempo}
                }
            ))
            fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig, use_container_width=True)
            
        with cr:
            st.markdown(f"<div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; border:1px solid {COLOR_CYAN}40;'>", unsafe_allow_html=True)
            st.subheader("💡 Wskazówki")
            if srednia > tempo:
                st.error(f"⚠️ Musisz przyspieszyć! Wymagane tempo ({round(srednia,1)}) jest wyższe niż Twój plan ({tempo}).")
            else:
                st.success(f"✅ Świetne tempo! Masz zapas czasu. Możesz zrealizować dodatkowe {int((tempo * dni_n) - do_zrobienia)} wizyt.")
            st.markdown("</div>", unsafe_allow_html=True)

        # MAPA
        st.write("---")
        st.subheader("📍 Twoje punkty na mapie")
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

        if col_m and col_u:
            if st.button("🌍 GENERUJ MAPĘ PUNKTÓW"):
                with st.spinner("Przetwarzam lokalizacje..."):
                    geolocator = Nominatim(user_agent="a2b_flowroute_pro")
                    m = folium.Map(location=[52.0, 19.0], zoom_start=6, tiles="cartodbpositron")
                    
                    # Bierzemy pierwsze 20 punktów do testu (żeby nie blokować API)
                    for _, row in df.head(20).iterrows():
                        adres = f"{row[col_u]}, {row[col_m]}, Polska"
                        loc = geolocator.geocode(adres)
                        if loc:
                            folium.CircleMarker(
                                location=[loc.latitude, loc.longitude],
                                radius=7,
                                color=COLOR_CYAN,
                                fill=True,
                                fill_color=COLOR_CYAN,
                                popup=f"<b>{row[col_u]}</b><br>{row[col_m]}"
                            ).add_to(m)
                    st_folium(m, width=1300, height=500)
        else:
            st.warning("Nie znaleziono kolumn adresowych w pliku.")

    except Exception as e:
        st.error(f"Błąd danych: {e}")
else:
    st.info("👋 Witaj w A2B FlowRoute! Wgraj plik CSV, aby zaplanować swoją trasę.")
