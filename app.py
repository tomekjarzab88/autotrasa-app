import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic
import time
import random
import re
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
    .calendar-card {{
        background: rgba(255,255,255,0.05); border-left: 4px solid {COLOR_CYAN};
        padding: 10px; margin-bottom: 5px; border-radius: 5px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA SESJI ---
if 'nieobecnosci_daty' not in st.session_state: st.session_state.nieobecnosci_daty = []
if 'trasa_wynikowa' not in st.session_state: st.session_state.trasa_wynikowa = None
if 'current_file' not in st.session_state: st.session_state.current_file = None

# --- FUNKCJE ---
def fix_polish(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

def generate_working_dates(start_from, count, blocked_dates):
    working_days = []
    curr = start_from + timedelta(days=1)
    while len(working_days) < count:
        if curr.weekday() < 5 and curr not in blocked_dates:
            working_days.append(curr)
        curr += timedelta(days=1)
    return working_days

# --- SIDEBAR ---
with st.sidebar:
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.write("---")
    dom_adres = st.text_input("📍 Twoje miejsce zamieszkania", "Kielce, Polska")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (wizyty/dzień)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    st.write("---")
    dni_input = st.date_input("Zaznacz wolne/urlop:", value=(), min_value=date.today())
    if st.button("➕ DODAJ WOLNE"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            if len(dni_input) == 2:
                s, e = dni_input
                range_dates = [s + timedelta(days=x) for x in range((e-s).days + 1)]
                st.session_state.nieobecnosci_daty.extend(range_dates)
            else: st.session_state.nieobecnosci_daty.append(dni_input[0])
            st.session_state.nieobecnosci_daty = list(set(st.session_state.nieobecnosci_daty))
            st.rerun()

    if st.button("🗑️ RESETUJ WSZYSTKO"):
        st.session_state.nieobecnosci_daty = []
        st.session_state.trasa_wynikowa = None
        st.rerun()

# --- PANEL GŁÓWNY ---
st.title("📅 Kalendarz Trasy Optymalnej")

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
            
            n_punkty = len(df_clean)
            cel_wizyt = (n_punkty * wizyty_cel) - zrobione
            
            st.info(f"📋 Apteki: **{n_punkty}**. Do celu: **{cel_wizyt}** wizyt. Tempo: **{tempo}**/dzień.")

            if st.button("🚀 GENERUJ HARMONOGRAM (OD DOMU)"):
                coords = []
                bar = st.progress(0); counter = st.empty()
                
                ua = f"A2B_Engine_v104_{random.randint(1,9999)}"
                geolocator = Nominatim(user_agent=ua, timeout=10)
                geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                
                # Lokalizacja domu
                home_loc = geolocator.geocode(dom_adres)
                if not home_loc:
                    st.error("Nie znaleziono adresu zamieszkania. Wpisz miasto w Sidebarze.")
                    st.stop()
                home_coords = (home_loc.latitude, home_loc.longitude)
                
                total = len(df_clean)
                for i, (_, row) in enumerate(df_clean.iterrows()):
                    addr = f"{row[col_u]}, {row[col_m]}, Polska"
                    bar.progress((i + 1) / total)
                    counter.markdown(f"#### 📍 Geolokalizacja: **{i+1}** / **{total}**")
                    
                    try:
                        loc = geocode(addr)
                        if loc:
                            dist = geodesic(home_coords, (loc.latitude, loc.longitude)).km
                            coords.append({
                                'lat': loc.latitude, 'lon': loc.longitude, 
                                'dist': dist, 'addr': addr, 
                                'city': row[col_m], 'street': row[col_u]
                            })
                    except: pass

                if coords:
                    pdf = pd.DataFrame(coords)
                    # Sortowanie po dystansie od domu
                    pdf = pdf.sort_values(by='dist', ascending=True).reset_index(drop=True)
                    
                    # Sztywne paczki po 'tempo' wizyt
                    pdf['dzien_idx'] = pdf.index // tempo
                    n_dni = int(pdf['dzien_idx'].max() + 1)
                    
                    working_dates = generate_working_dates(date.today(), n_dni, st.session_state.nieobecnosci_daty)
                    date_map = {i: working_dates[i] for i in range(len(working_dates))}
                    pdf['data_wizyty'] = pdf['dzien_idx'].map(date_map)
                    
                    st.session_state.trasa_wynikowa = pdf
                    st.rerun()

            if st.session_state.trasa_wynikowa is not None:
                res = st.session_state.trasa_wynikowa
                all_dates = sorted(res['data_wizyty'].unique())
                
                t1, t2, t3 = st.tabs(["🗺️ Mapa", "📅 Harmonogram Zbiorczy", "📥 Eksport"])
                
                with t1:
                    m = folium.Map(location=[res['lat'].mean(), res['lon'].mean()], zoom_start=7, tiles="cartodbpositron")
                    folium.Marker(location=[home_coords[0], home_coords[1]], icon=folium.Icon(color='red', icon='home')).add_to(m)
                    for _, row in res.iterrows():
                        color = DAILY_COLORS[all_dates.index(row['data_wizyty']) % len(DAILY_COLORS)]
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']], radius=10, color=color, fill=True, fill_color=color,
                            popup=f"Data: {row['data_wizyty']}<br>Odległość: {round(row['dist'], 1)} km"
                        ).add_to(m)
                    st_folium(m, width=1300, height=600, key="fixed_map_v104")
                
                with t2:
                    for d in all_dates:
                        day_pts = res[res['data_wizyty'] == d]
                        with st.expander(f"📅 {d.strftime('%A, %d.%m.%Y')} — ({len(day_pts)} wizyt)"):
                            for _, p in day_pts.iterrows():
                                st.markdown(f"<div class='calendar-card'>📍 <b>{p['street']}</b>, {p['city']} ({round(p['dist'], 1)} km od domu)</div>", unsafe_allow_html=True)
                
                with t3:
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='openpyxl') as wr:
                        res[['data_wizyty', 'street', 'city', 'dist', 'addr']].to_excel(wr, index=False, sheet_name='Plan_A2B')
                    st.download_button(label="📥 POBIERZ PLAN (EXCEL)", data=out.getvalue(), file_name=f"Plan_A2B_{date.today()}.xlsx")
        else:
            st.error("Brak kolumn adresowych.")
            
    except Exception as e:
        st.error(f"Błąd: {e}")
