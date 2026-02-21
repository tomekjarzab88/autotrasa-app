import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time
import random
import re
import io

# --- KONFIGURACJA ---
st.set_page_config(page_title="A2B FlowRoute PRO", layout="wide", initial_sidebar_state="expanded")

# --- KOLORYSTYKA ---
COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background-color: {COLOR_BG}; color: white; }}
    .stApp {{ background-color: {COLOR_BG}; color: white; }}
    [data-testid="stSidebar"] {{ background-color: {COLOR_NAVY_DARK} !important; min-width: 250px !important; }}
    div[data-testid="stMetric"] {{
        background-color: white; border-radius: 12px; padding: 15px !important;
        border-left: 5px solid {COLOR_CYAN}; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }}
    div[data-testid="stMetric"] label {{ color: #64748B !important; font-weight: 600; }}
    div[data-testid="stMetricValue"] {{ color: {COLOR_NAVY_DARK} !important; font-size: 1.8rem !important; }}
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important; border-radius: 8px !important; font-weight: bold !important; width: 100%;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCJA CZYSZCZENIA ADRESU ---
def clean_address(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items():
        text = text.replace(k, v)
    text = re.sub(r'[^\w\s,.-]', '', text)
    return text.strip()

if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR ---
with st.sidebar:
    try:
        st.image("assets/logo_a2b.png", use_container_width=True)
    except:
        st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    st.write("---")
    dni_input = st.date_input("Planuj wolne:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            label = f"{dni_input[0].strftime('%d.%m')}" if len(dni_input)==1 else f"{dni_input[0].strftime('%d.%m')} - {dni_input[1].strftime('%d.%m')}"
            st.session_state.nieobecnosci.append({'label': label, 'count': 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1])
        c1.caption(f"🏝️ {g['label']}")
        if c2.button("X", key=f"d_{i}"):
            st.session_state.nieobecnosci.pop(i); st.rerun()

# --- PANEL GŁÓWNY ---
st.markdown(f"<h1 style='margin:0;'>Dashboard A2B FlowRoute</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę (Excel .xlsx lub CSV)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_data = uploaded_file.read()
            detection = chardet.detect(raw_data)
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=detection['encoding'] if detection['confidence'] > 0.5 else 'utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)
        
        df = df.applymap(clean_address)
        
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_cel
        do_zrobienia = max(0, cel_total - zrobione)
        srednia = do_zrobienia / dni_n if dni_n > 0 else 0

        st.write("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci", len(df))
        m2.metric("Dni Netto", dni_n)
        m3.metric("Do celu", do_zrobienia)
        m4.metric("Realizacja", f"{round((zrobione/cel_total*100),1)}%" if cel_total>0 else "0%")

        st.write("---")
        st.subheader("📍 Mapa i Planowanie")
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

        if col_m and col_u:
            if st.button("🌍 GENERUJ MAPĘ (TEST 10 PUNKTÓW)"):
                with st.spinner("Przeszukiwanie bazy..."):
                    ua = f"A2B_Final_Fix_{random.randint(1,999)}"
                    geolocator = Nominatim(user_agent=ua, timeout=10)
                    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5)
                    
                    m = folium.Map(location=[52.0, 19.0], zoom_start=6, tiles="cartodbpositron")
                    found = 0
                    
                    debug_area = st.expander("🔍 Podgląd przetwarzania adresów")
                    test_df = df.head(10).copy()
                    
                    for i, row in test_df.iterrows():
                        city = str(row[col_m]).strip()
                        street = str(row[col_u]).strip()
                        addr = f"{street}, {city}, Polska"
                        debug_area.write(f"Sprawdzam: {addr}")
                        
                        loc = geocode(addr)
                        
                        if not loc and ' ' in street:
                            street_only = street.rsplit(' ', 1)[0]
                            loc = geocode(f"{street_only}, {city}, Polska")

                        if loc:
                            folium.CircleMarker(
                                location=[loc.latitude, loc.longitude],
                                radius=10, color=COLOR_CYAN, fill=True, fill_color=COLOR_CYAN,
                                popup=f"<b>{street}</b><br>{city}"
                            ).add_to(m)
                            found += 1
                        
                    if found > 0:
                        st_folium(m, width=1300, height=500)
                        st.success(f"Sukces! Naniesiono {found} punktów.")
                    else:
                        st.error("Nadal brak wyników. Sprawdź 'Podgląd przetwarzania'.")
        else:
            st.warning("Nie znaleziono kolumn Miasto/Ulica.")

    except Exception as e:
        st.error(f"Błąd: {e}")
