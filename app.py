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
st.set_page_config(page_title="A2B FlowRoute PRO", layout="wide", initial_sidebar_state="expanded")

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
    [data-testid="stSidebar"] {{ background-color: {COLOR_NAVY_DARK} !important; min-width: 260px !important; }}
    div[data-testid="stMetric"] {{
        background-color: white; border-radius: 12px; padding: 15px !important;
        border-left: 5px solid {COLOR_CYAN}; box-shadow: 0 4px 10px rgba(0,0,0,0.2);
    }}
    div[data-testid="stMetricValue"] {{ color: {COLOR_NAVY_DARK} !important; font-size: 1.6rem !important; }}
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important; border-radius: 8px !important; font-weight: bold !important; width: 100%;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA SESJI ---
if 'nieobecnosci' not in st.session_state: st.session_state.nieobecnosci = []
if 'trasa_wynikowa' not in st.session_state: st.session_state.trasa_wynikowa = None
if 'current_file' not in st.session_state: st.session_state.current_file = None

# --- FUNKCJE POMOCNICZE ---
def fix_polish(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

def sort_points_logically(df_day):
    """Sortuje punkty od północy do południa dla płynności trasy."""
    return df_day.sort_values(by=['lat'], ascending=False)

# --- SIDEBAR ---
with st.sidebar:
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    
    st.write("---")
    dni_input = st.date_input("Planuj wolne:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ WOLNE"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            label = f"{dni_input[0].strftime('%d.%m')}" if len(dni_input)==1 else f"{dni_input[0].strftime('%d.%m')} - {dni_input[1].strftime('%d.%m')}"
            st.session_state.nieobecnosci.append({'label': label, 'count': 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    if st.button("🗑️ RESETUJ WSZYSTKO"):
        st.session_state.nieobecnosci = []
        st.session_state.trasa_wynikowa = None
        st.rerun()

# --- PANEL GŁÓWNY ---
st.title("🚀 Logistyka i Planowanie Trasy")

uploaded_file = st.file_uploader("📂 Wgraj bazę (Excel lub CSV)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    if st.session_state.current_file != uploaded_file.name:
        st.session_state.trasa_wynikowa = None
        st.session_state.current_file = uploaded_file.name

    try:
        if uploaded_file.name.endswith('.csv'):
            raw = uploaded_file.read(); det = chardet.detect(raw); uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=det['encoding'] if det['confidence'] > 0.5 else 'utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

        if col_m and col_u:
            df_clean = df.drop_duplicates(subset=[col_m, col_u]).copy()
            df_clean[col_m] = df_clean[col_m].apply(fix_polish)
            df_clean[col_u] = df_clean[col_u].apply(fix_polish)
            
            dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
            dni_n = max(1, dni_p[typ_cyklu] - suma_wolnych)
            
            st.info(f"📊 Baza unikalna: **{len(df_clean)}** aptek | Dni pracy: **{dni_n}**")

            # --- SEKCJA GENEROWANIA Z LICZNIKIEM ---
            if st.button("🗺️ GENERUJ OPTYMALNY PLAN"):
                coords = []
                
                # Kontener na postęp (Widoczny licznik X / Y)
                progress_container = st.container()
                with progress_container:
                    st.write("### ⏳ Trwa przetwarzanie...")
                    bar = st.progress(0)
                    counter_text = st.empty() # Miejsce na tekst "14 / 136"
                
                ua = f"A2B_Final_Engine_{random.randint(1,9999)}"
                geolocator = Nominatim(user_agent=ua, timeout=10)
                geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                
                total = len(df_clean)
                for i, (_, row) in enumerate(df_clean.iterrows()):
                    addr = f"{row[col_u]}, {row[col_m]}, Polska"
                    
                    # Aktualizacja licznika i paska (Real-time)
                    current_idx = i + 1
                    bar.progress(current_idx / total)
                    counter_text.markdown(f"#### 📍 Geolokalizacja: **{current_idx}** / **{total}** aptek")
                    
                    try:
                        loc = geocode(addr)
                        if not loc and ' ' in str(row[col_u]):
                            loc = geocode(f"{str(row[col_u]).rsplit(' ', 1)[0]}, {row[col_m]}, Polska")
                        if loc:
                            coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'addr': addr, 'city': row[col_m], 'street': row[col_u]})
                    except: pass

                if coords:
                    pdf = pd.DataFrame(coords)
                    n_clusters = min(dni_n, len(pdf))
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    pdf['dzien'] = kmeans.fit_predict(pdf[['lat', 'lon']])
                    
                    # Sortowanie wewnątrz dni dla ekonomii przejazdu
                    optimized_list = []
                    for d in range(n_clusters):
                        optimized_list.append(sort_points_logically(pdf[pdf['dzien'] == d]))
                    
                    st.session_state.trasa_wynikowa = pd.concat(optimized_list)
                    st.success("✅ Sukces! Plan został utworzony.")
                    st.rerun()

            # --- WYŚWIETLANIE (ZAKOTWICZONE) ---
            if st.session_state.trasa_wynikowa is not None:
                res = st.session_state.trasa_wynikowa
                
                t1, t2, t3 = st.tabs(["🗺️ Mapa Logistyczna", "📅 Plan Dnia", "📥 Eksport"])
                
                with t1:
                    m = folium.Map(location=[res['lat'].mean(), res['lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                    for _, row in res.iterrows():
                        color = DAILY_COLORS[int(row['dzien']) % len(DAILY_COLORS)]
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']], radius=10, color=color, fill=True, fill_color=color,
                            popup=f"Dzień {int(row['dzien'])+1}: {row['addr']}"
                        ).add_to(m)
                    st_folium(m, width=1300, height=600, key="fixed_map_v95")
                
                with t2:
                    d_sel = st.selectbox("Wybierz dzień:", range(1, int(res['dzien'].max())+2))
                    day_df = res[res['dzien'] == (d_sel-1)]
                    st.markdown(f"### 📍 Dzień {d_sel} - {len(day_df)} aptek")
                    st.table(day_df[['street', 'city']])
                
                with t3:
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='openpyxl') as wr:
                        res.to_excel(wr, index=False, sheet_name='Plan_A2B')
                    st.download_button(label="📥 POBIERZ PLAN (EXCEL)", data=out.getvalue(), file_name=f"Plan_A2B_{date.today()}.xlsx")

        else: st.error("Nie znaleziono kolumn z adresem.")
    except Exception as e: st.error(f"Błąd: {e}")
