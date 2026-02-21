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
st.set_page_config(page_title="A2B FlowRoute - Stabilny", layout="wide", initial_sidebar_state="expanded")

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

# --- INICJALIZACJA SESJI (KLUCZ DO STABILNOŚCI) ---
if 'nieobecnosci' not in st.session_state: st.session_state.nieobecnosci = []
if 'final_df' not in st.session_state: st.session_state.final_df = None
if 'file_id' not in st.session_state: st.session_state.file_id = None

# --- FUNKCJE POMOCNICZE ---
def clean_address(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

@st.cache_data(show_spinner=False)
def get_coordinates_cached(data_json, col_u, col_m):
    """Lokalizuje adresy i zapamiętuje wyniki."""
    df_to_geo = pd.read_json(data_json)
    ua = f"A2B_Final_Logistics_{random.randint(1,9999)}"
    geolocator = Nominatim(user_agent=ua, timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)
    
    coords = []
    for _, row in df_to_geo.iterrows():
        addr = f"{row[col_u]}, {row[col_m]}, Polska"
        try:
            loc = geocode(addr)
            if not loc and ' ' in str(row[col_u]):
                loc = geocode(f"{str(row[col_u]).rsplit(' ', 1)[0]}, {row[col_m]}, Polska")
            if loc:
                coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'addr': addr, 'city': row[col_m], 'street': row[col_u]})
        except: pass
    return pd.DataFrame(coords)

# --- SIDEBAR ---
with st.sidebar:
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    
    st.write("---")
    dni_input = st.date_input("Dodaj wolne:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ WOLNE"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            count = 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1
            st.session_state.nieobecnosci.append({'label': f"Wolne {len(st.session_state.nieobecnosci)+1}", 'count': count})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    if st.button("🗑️ WYCZYŚĆ PLAN"):
        st.session_state.nieobecnosci = []
        st.session_state.final_df = None
        st.rerun()

# --- PANEL GŁÓWNY ---
st.title("🚀 Planowanie Trasy A2B")

uploaded_file = st.file_uploader("📂 Wgraj bazę (Excel lub CSV)", type=["csv", "xlsx", "xls"])

# Resetuj dane, jeśli wgrano nowy plik
if uploaded_file:
    if st.session_state.file_id != uploaded_file.name:
        st.session_state.final_df = None
        st.session_state.file_id = uploaded_file.name

if uploaded_file:
    try:
        # Odczyt danych
        if uploaded_file.name.endswith('.csv'):
            raw = uploaded_file.read(); det = chardet.detect(raw); uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=det['encoding'] if det['confidence'] > 0.5 else 'utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)
        
        if col_m and col_u:
            df_unique = df.drop_duplicates(subset=[col_m, col_u]).copy()
            df_unique[col_m] = df_unique[col_m].apply(clean_address)
            df_unique[col_u] = df_unique[col_u].apply(clean_address)
            
            # Statystyki
            dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
            dni_n = max(1, dni_p[typ_cyklu] - suma_wolnych)
            
            st.info(f"📊 Znaleziono **{len(df_unique)}** unikalnych aptek. Plan na **{dni_n}** dni pracy.")

            # PRZYCISK GENEROWANIA - Zapisuje wynik do session_state
            if st.button("🌍 GENERUJ OPTYMALNĄ TRASĘ"):
                with st.status("Przetwarzanie logistyki (może potrwać kilka minut)...", expanded=True) as status:
                    # Zamieniamy na JSON do cache'owania
                    df_json = df_unique[[col_u, col_m]].to_json()
                    points_df = get_coordinates_cached(df_json, col_u, col_m)
                    
                    if not points_df.empty:
                        # Grupowanie (Logistyka)
                        n_clusters = min(dni_n, len(points_df))
                        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                        points_df['dzien'] = kmeans.fit_predict(points_df[['lat', 'lon']])
                        
                        # Sortowanie dla porządku
                        points_df = points_df.sort_values(by=['dzien', 'lat'], ascending=[True, False])
                        
                        # ZAPIS DO SESJI - To sprawia, że mapa nie zniknie
                        st.session_state.final_df = points_df
                        status.update(label="✅ Trasa gotowa!", state="complete")
                    else:
                        st.error("Nie udało się zlokalizować adresów.")

            # WYŚWIETLANIE WYNIKÓW (TYLKO JEŚLI SĄ W SESJI)
            if st.session_state.final_df is not None:
                res = st.session_state.final_df
                
                t1, t2 = st.tabs(["🗺️ Mapa Rejonów", "📅 Rozpiska na Dni"])
                
                with t1:
                    m = folium.Map(location=[res['lat'].mean(), res['lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                    for _, row in res.iterrows():
                        color = DAILY_COLORS[int(row['dzien']) % len(DAILY_COLORS)]
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']], radius=9, 
                            color=color, fill=True, fill_color=color,
                            popup=f"Dzień {int(row['dzien'])+1}: {row['addr']}"
                        ).add_to(m)
                    st_folium(m, width=1300, height=600, key="fixed_map")
                
                with t2:
                    for d in range(int(res['dzien'].max()) + 1):
                        day_data = res[res['dzien'] == d]
                        with st.expander(f"📍 DZIEŃ {d+1} ({len(day_data)} wizyt)"):
                            st.table(day_data[['street', 'city']])
                            
        else: st.error("Brak kolumn adresowych.")
    except Exception as e: st.error(f"Błąd: {e}")
