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
st.set_page_config(page_title="A2B FlowRoute", layout="wide")

# --- KOLORYSTYKA PRO ---
COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLOR_BG}; color: white; }}
    [data-testid="stSidebar"] {{ background-color: {COLOR_NAVY_DARK} !important; }}
    div[data-testid="stMetric"] {{
        background-color: white;
        border-radius: 15px;
        padding: 20px;
        border-left: 5px solid {COLOR_CYAN};
    }}
    .stButton>button {{
        background: {COLOR_CYAN} !important;
        color: white !important;
        border-radius: 10px;
        font-weight: bold;
    }}
    </style>
    """, unsafe_allow_html=True)

if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR Z TWOIM LOGO ---
with st.sidebar:
    # Wyświetlamy Twoje nowe logo z folderu assets
    try:
        st.image("assets/logo_a2b.png", use_container_width=True)
    except:
        st.error("Brak pliku logo_a2b.png w folderze assets")
    
    st.write("---")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    st.write("---")
    dni = st.date_input("Dodaj wolne/urlop:", value=(), min_value=date(2025, 1, 1))
    if st.button("DODAJ DO PLANU"):
        if isinstance(dni, (list, tuple)) and len(dni) > 0:
            label = f"{dni[0].strftime('%d.%m')}" if len(dni)==1 else f"{dni[0].strftime('%d.%m')} - {dni[1].strftime('%d.%m')}"
            count = 1 if len(dni)==1 else (dni[1]-dni[0]).days + 1
            st.session_state.nieobecnosci.append({'label': label, 'count': count})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1])
        c1.write(f"🏝️ {g['label']}")
        if c2.button("X", key=f"d_{i}"):
            st.session_state.nieobecnosci.pop(i); st.rerun()

# --- PANEL GŁÓWNY ---
st.title("🚀 Dashboard A2B FlowRoute")

uploaded_file = st.file_uploader("Wgraj bazę klientów (CSV)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig') # auto-detekcja
    
    # Obliczenia
    dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
    dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
    cel_total = len(df) * wizyty_cel
    do_zrobienia = max(0, cel_total - zrobione)
    wymagana = do_zrobienia / dni_n if dni_n > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Klienci", len(df))
    m2.metric("Dni netto", dni_n)
    m3.metric("Zostało wizyt", do_zrobienia)
    m4.metric("Realizacja", f"{round((zrobione/cel_total*100),1)}%" if cel_total>0 else "0%")

    # --- MAPA Z KROPKAMI ---
    st.write("---")
    st.subheader("📍 Twoje punkty na mapie")
    
    # Szukamy kolumn adresowych
    col_miasto = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
    col_ulica = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

    if col_miasto and col_ulica:
        if st.button("🌍 POKAŻ PUNKTY NA MAPIE"):
            with st.spinner("Lokalizuję apteki..."):
                geolocator = Nominatim(user_agent="a2b_flowroute")
                m = folium.Map(location=[52.0, 19.0], zoom_start=6, tiles="cartodbpositron")
                
                # Na próbę bierzemy 15 punktów, żeby nie trwało to wieki
                for _, row in df.head(15).iterrows():
                    adres = f"{row[col_ulica]}, {row[col_miasto]}, Polska"
                    loc = geolocator.geocode(adres)
                    if loc:
                        folium.CircleMarker(
                            location=[loc.latitude, loc.longitude],
                            radius=8,
                            color=COLOR_CYAN,
                            fill=True,
                            fill_color=COLOR_CYAN,
                            popup=f"{row[col_ulica]}"
                        ).add_to(m)
                st_folium(m, width=1300, height=500)
    else:
        st.warning("Nie znalazłem kolumn 'Miasto' lub 'Ulica' w Twoim pliku CSV.")
