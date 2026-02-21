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

# --- KONFIGURACJA ---
st.set_page_config(page_title="A2B FlowRoute PRO", layout="wide", initial_sidebar_state="expanded")

# --- KOLORYSTYKA I COMPACT CSS ---
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
    .absence-item {{ background: rgba(255,255,255,0.05); padding: 5px 10px; border-radius: 5px; margin-bottom: 2px; font-size: 0.85rem; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCJA NAPRAWCZA DLA POLSKICH ZNAKÓW ---
def fix_polish_chars(text):
    if not isinstance(text, str): return text
    # Mapa najczęstszych błędów kodowania (mojibake)
    corrections = {
        'GÛ': 'Gó', 'Û': 'ó', 'ą': 'ą', 'ę': 'ę', 'ś': 'ś', 'ć': 'ć', 'ź': 'ź', 'ż': 'ż', 'ł': 'ł', 'ń': 'ń', 'ó': 'ó',
        'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'
    }
    for wrong, right in corrections.items():
        text = text.replace(wrong, right)
    return text

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
    dni_input = st.date_input("Dodaj wolne/urlop:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ DO PLANU"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            label = f"{dni_input[0].strftime('%d.%m')}" if len(dni_input)==1 else f"{dni_input[0].strftime('%d.%m')} - {dni_input[1].strftime('%d.%m')}"
            count = 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1
            st.session_state.nieobecnosci.append({'label': label, 'count': count})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"<div class='absence-item'>🏝️ {g['label']}</div>", unsafe_allow_html=True)
        if c2.button("✕", key=f"del_{i}"):
            st.session_state.nieobecnosci.pop(i); st.rerun()

# --- PANEL GŁÓWNY ---
st.markdown(f"<h1 style='margin:0;'>Dashboard A2B FlowRoute</h1><p style='color:#8A9AB8;'>v7.8 | Stabilizacja znaków PL</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę klientów (CSV)", type=["csv"])

if uploaded_file:
    # INTELIGENTNE CZYTANIE PLIKU
    raw_data = uploaded_file.read()
    detection = chardet.detect(raw_data)
    encoding_guess = detection['encoding']
    uploaded_file.seek(0)
    
    try:
        # Próbujemy najpierw utf-8-sig (Excel), potem to co zgadł chardet, na końcu windows-1250
        try:
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=encoding_guess)
            
        # NAPRAWA ZNAKÓW W CAŁEJ TABELI
        df = df.applymap(fix_polish_chars)
        
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_cel
        do_zrobienia = max(0, cel_total - zrobione)
        srednia = do_zrobienia / dni_n if dni_n > 0 else 0

        st.write("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Liczba Klientów", len(df))
        m2.metric("Dni Robocze", dni_n)
        m3.metric("Pozostało Wizyt", do_zrobienia)
        realizacja = round((zrobione/cel_total*100),1) if cel_total>0 else 0
        m4.metric("Realizacja Cyklu", f"{realizacja}%")

        st.write("---")
        cl, cr = st.columns([2, 1])
        with cl:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number", value = srednia,
                number = {'font': {'color': COLOR_CYAN}},
                title = {'text': "WYMAGANE TEMPO", 'font': {'color': 'white', 'size': 16}},
                gauge = {'axis': {'range': [None, 30]}, 'bar': {'color': COLOR_CYAN}, 'threshold': {'line': {'color': "red", 'width': 4}, 'value': tempo}}
            ))
            fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig, use_container_width=True)
            
        with cr:
            st.markdown(f"<div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:15px; border:1px solid {COLOR_CYAN}40;'>", unsafe_allow_html=True)
            st.subheader("💡 Wskazówki")
            if srednia > tempo:
                st.error(f"⚠️ Wymagane tempo ({round(srednia,1)}) > Twój plan ({tempo}).")
            else:
                st.success(f"✅ Zapas czasu: {int((tempo * dni_n) - do_zrobienia)} wizyt.")
            st.markdown("</div>", unsafe_allow_html=True)

        st.write("---")
        st.subheader("📍 Mapa Operacyjna")
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

        if col_m and col_u:
            if st.button("🌍 GENERUJ MAPĘ"):
                with st.spinner("Geolokalizacja w toku..."):
                    ua = f"A2B_Flow_Fix_{random.randint(1,100)}"
                    geolocator = Nominatim(user_agent=ua, timeout=10)
                    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                    
                    m = folium.Map(location=[52.0, 19.0], zoom_start=6, tiles="cartodbpositron")
                    found = 0
                    
                    progress_bar = st.progress(0)
                    points_to_map = df.head(15) # Testowo 15 punktów
                    
                    for i, row in points_to_map.iterrows():
                        city = str(row[col_m]).strip()
                        street = str(row[col_u]).strip()
                        full_address = f"{street}, {city}, Polska"
                        
                        loc = geocode(full_address)
                        if loc:
                            folium.CircleMarker(
                                location=[loc.latitude, loc.longitude], radius=8,
                                color=COLOR_CYAN, fill=True, fill_color=COLOR_CYAN,
                                popup=f"<b>{street}</b><br>{city}"
                            ).add_to(m)
                            found += 1
                        progress_bar.progress((i + 1) / len(points_to_map))
                    
                    if found > 0:
                        st_folium(m, width=1300, height=500)
                        st.success(f"Zlokalizowano {found} punktów!")
                    else:
                        st.error(f"Błąd! Nie znaleziono adresu: {full_address}. Sprawdź czy miasto i ulica są w osobnych kolumnach.")
        else:
            st.warning("Brak kolumn adresowych.")

    except Exception as e:
        st.error(f"Błąd: {e}")
else:
    st.info("👋 Wgraj plik CSV.")
