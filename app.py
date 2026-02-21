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
from sklearn.cluster import KMeans
import numpy as np
import io

# --- KONFIGURACJA ---
st.set_page_config(page_title="A2B FlowRoute SPEED", layout="wide", initial_sidebar_state="expanded")

# --- KOLORYSTYKA ---
COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"
DAILY_COLORS = ['blue', 'green', 'red', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'darkpurple', 'darkorange']

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
    div[data-testid="stMetricValue"] {{ color: {COLOR_NAVY_DARK} !important; font-size: 1.6rem !important; }}
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important; border-radius: 8px !important; font-weight: bold !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCJE POMOCNICZE I CACHE ---
def clean_address(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

@st.cache_data(show_spinner=False)
def get_coordinates(df_to_geo, col_u, col_m):
    """Ta funkcja 'pamięta' wyniki. Raz zrobione, nie wymaga ponownego czekania."""
    ua = f"A2B_Fast_Logistics_{random.randint(1,9999)}"
    geolocator = Nominatim(user_agent=ua, timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)
    
    coords = []
    total = len(df_to_geo)
    
    # Tworzymy kontener na postęp (widoczny tylko podczas pierwszego ładowania)
    p_bar = st.progress(0)
    s_text = st.empty()
    
    for i, (_, row) in enumerate(df_to_geo.iterrows()):
        addr = f"{row[col_u]}, {row[col_m]}, Polska"
        try:
            loc = geocode(addr)
            if loc:
                coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'addr': addr, 'city': row[col_m], 'street': row[col_u]})
        except:
            pass
        p_bar.progress((i + 1) / total)
        s_text.text(f"Geolokalizacja: {i+1} / {total} punktów...")
    
    p_bar.empty()
    s_text.empty()
    return pd.DataFrame(coords)

# --- INICJALIZACJA SESJI ---
if 'nieobecnosci' not in st.session_state: st.session_state.nieobecnosci = []

# --- SIDEBAR ---
with st.sidebar:
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    typ_cyklu = st.selectbox("Okres", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt / klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo", 1, 30, 12)
    
    st.write("---")
    dni_input = st.date_input("Dodaj wolne:", value=(), min_value=date.today())
    if st.button("➕ DODAJ"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            count = 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1
            st.session_state.nieobecnosci.append({'label': f"Wolne {len(st.session_state.nieobecnosci)+1}", 'count': count})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    st.caption(f"Razem wolne: {suma_wolnych} dni")

# --- PANEL GŁÓWNY ---
st.title("🚀 A2B FlowRoute - Asystent Logistyczny")

uploaded_file = st.file_uploader("📂 Wgraj bazę (Excel lub CSV)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw_data = uploaded_file.read(); det = chardet.detect(raw_data); uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=det['encoding'] if det['confidence'] > 0.5 else 'utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)
        
        if col_m and col_u:
            df_unique = df.drop_duplicates(subset=[col_m, col_u]).copy()
            df_unique[col_m] = df_unique[col_m].apply(clean_address)
            df_unique[col_u] = df_unique[col_u].apply(clean_address)
            
            # Parametry trasy
            dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
            dni_n = max(1, dni_p[typ_cyklu] - suma_wolnych)
            
            st.info(f"📍 Baza: **{len(df_unique)}** aptek | Planowanie na: **{dni_n}** dni.")
            
            if st.button("🗺️ GENERUJ I OPTYMALIZUJ TRASĘ"):
                with st.spinner("Przetwarzanie danych..."):
                    # POBIERANIE KOORDYNATÓW (Z CACHE)
                    points_df = get_coordinates(df_unique, col_u, col_m)
                    
                    if not points_df.empty:
                        # KLASTROWANIE NA DNI
                        n_clusters = min(dni_n, len(points_df))
                        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                        points_df['dzien'] = kmeans.fit_predict(points_df[['lat', 'lon']])
                        
                        # Sortowanie wewnątrz dni (północ -> południe), aby trasa miała sens
                        points_df = points_df.sort_values(by=['dzien', 'lat'], ascending=[True, False])
                        
                        # WYŚWIETLANIE
                        t1, t2 = st.tabs(["🗺️ MAPA ZONALNA", "📅 PLANER DNIOWY"])
                        
                        with t1:
                            m = folium.Map(location=[points_df['lat'].mean(), points_df['lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                            for _, row in points_df.iterrows():
                                color = DAILY_COLORS[int(row['dzien']) % len(DAILY_COLORS)]
                                folium.CircleMarker(
                                    location=[row['lat'], row['lon']], radius=10, color=color, fill=True, fill_color=color,
                                    popup=f"Dzień {int(row['dzien'])+1}: {row['addr']}"
                                ).add_to(m)
                            st_folium(m, width=1200, height=600)
                        
                        with t2:
                            for d in range(n_clusters):
                                with st.expander(f"📍 DZIEŃ {d+1}"):
                                    day_pts = points_df[points_df['dzien'] == d]
                                    st.table(day_pts[['street', 'city']])
                    else:
                        st.error("Błąd lokalizacji adresów.")
        else:
            st.error("W pliku brakuje kolumn Miasto lub Ulica.")
    except Exception as e:
        st.error(f"Błąd: {e}")
