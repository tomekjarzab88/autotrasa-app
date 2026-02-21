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
st.set_page_config(page_title="A2B FlowRoute LOGISTICS", layout="wide", initial_sidebar_state="expanded")

# --- KOLORYSTYKA ---
COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"
# Rozszerzona paleta kolorów dla 20+ dni
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
        color: white !important; border-radius: 8px !important; font-weight: bold !important; width: 100%;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA SESJI ---
if 'nieobecnosci' not in st.session_state: st.session_state.nieobecnosci = []
if 'trasa_data' not in st.session_state: st.session_state.trasa_data = None

# --- FUNKCJE POMOCNICZE ---
def clean_address(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

# --- SIDEBAR ---
with st.sidebar:
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (dziennie)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    st.write("---")
    dni_input = st.date_input("Planuj wolne:", value=(), min_value=date(2025, 1, 1))
    if st.button("➕ DODAJ WOLNE"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            label = f"{dni_input[0].strftime('%d.%m')}" if len(dni_input)==1 else f"{dni_input[0].strftime('%d.%m')} - {dni_input[1].strftime('%d.%m')}"
            st.session_state.nieobecnosci.append({'label': label, 'count': 1 if len(dni_input)==1 else (dni_input[1]-dni_input[0]).days + 1})
            st.rerun()

    suma_wolnych = sum(g['count'] for g in st.session_state.nieobecnosci)
    for i, g in enumerate(st.session_state.nieobecnosci):
        c1, c2 = st.columns([4, 1]); c1.caption(f"🏝️ {g['label']}")
        if c2.button("X", key=f"d_{i}"): st.session_state.nieobecnosci.pop(i); st.rerun()

# --- PANEL GŁÓWNY ---
st.markdown(f"<h1 style='margin:0;'>Optymalizacja Trasy dla {date.today().year}</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Wgraj bazę (Excel lub CSV)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    try:
        # 1. WCZYTYWANIE
        if uploaded_file.name.endswith('.csv'):
            raw_data = uploaded_file.read(); detection = chardet.detect(raw_data); uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=detection['encoding'] if detection['confidence'] > 0.5 else 'utf-8-sig')
        else:
            df = pd.read_excel(uploaded_file)
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)
        
        if col_m and col_u:
            df_unique = df.drop_duplicates(subset=[col_m, col_u]).copy()
            df_unique[col_m] = df_unique[col_m].apply(clean_address)
            df_unique[col_u] = df_unique[col_u].apply(clean_address)
            
            dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
            dni_n = max(1, dni_p[typ_cyklu] - suma_wolnych)
            
            st.info(f"📊 Baza: **{len(df_unique)}** punktów. Czas planowania: ok. **{round(len(df_unique)*1.3/60, 1)} min**.")
            
            # 2. PRZYCISK STARTU
            if st.button("🚀 URUCHOM OPTYMALIZACJĘ (348 PUNKTÓW)"):
                with st.container():
                    st.warning("⚠️ Nie zamykaj tej strony! Trwa geolokalizacja...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    ua = f"A2B_Final_Logistics_{random.randint(1,999)}"
                    geolocator = Nominatim(user_agent=ua, timeout=10)
                    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                    
                    coords = []
                    for idx, row in df_unique.iterrows():
                        addr = f"{row[col_u]}, {row[col_m]}, Polska"
                        try:
                            loc = geocode(addr)
                            if loc:
                                coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'addr': addr, 'city': row[col_m], 'street': row[col_u]})
                        except:
                            pass
                        
                        progress = len(coords) / len(df_unique)
                        progress_bar.progress(progress)
                        status_text.text(f"Przetworzono: {len(coords)} / {len(df_unique)} punktów...")

                    if coords:
                        points_df = pd.DataFrame(coords)
                        n_clusters = min(dni_n, len(points_df))
                        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                        points_df['dzien'] = kmeans.fit_predict(points_df[['lat', 'lon']])
                        
                        st.session_state.trasa_data = points_df
                        st.rerun()

            # 3. WYŚWIETLANIE GOTOWEJ TRASY (Jeśli jest w sesji)
            if st.session_state.trasa_data is not None:
                df_res = st.session_state.trasa_data
                
                st.success(f"✅ Plan gotowy! Podzielono {len(df_res)} punktów na {int(df_res['dzien'].max()+1)} dni roboczych.")
                
                tab1, tab2, tab3 = st.tabs(["🗺️ Mapa Logistyczna", "📅 Plan Dnia", "📥 Eksport danych"])
                
                with tab1:
                    m = folium.Map(location=[df_res['lat'].mean(), df_res['lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                    for _, row in df_res.iterrows():
                        color = DAILY_COLORS[int(row['dzien']) % len(DAILY_COLORS)]
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']],
                            radius=8, color=color, fill=True, fill_color=color,
                            popup=f"Dzień {int(row['dzien'])+1}: {row['addr']}"
                        ).add_to(m)
                    st_folium(m, width=1300, height=600)
                
                with tab2:
                    col_day = st.selectbox("Wybierz dzień do podglądu:", range(1, int(df_res['dzien'].max()+2)))
                    day_df = df_res[df_res['dzien'] == (col_day-1)]
                    st.write(f"### 📍 Zadania na Dzień {col_day} ({len(day_df)} wizyt)")
                    st.table(day_df[['street', 'city']])
                
                with tab3:
                    # Eksport do Excela
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_res.to_excel(writer, index=False, sheet_name='Plan_A2B')
                    st.download_button(
                        label="📥 POBIERZ PEŁNY PLAN (EXCEL)",
                        data=output.getvalue(),
                        file_name=f"plan_trasy_{date.today()}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

        else:
            st.error("W pliku brakuje kolumn Miasto lub Ulica.")
    except Exception as e:
        st.error(f"Coś poszło nie tak: {e}")
else:
    st.info("👋 Wgraj plik z aptekami. A2B FlowRoute przeanalizuje 348 adresów i ułoży z nich 17 dniowych pętli.")
