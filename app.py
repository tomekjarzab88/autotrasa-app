import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.distance import geodesic
from supabase import create_client, Client
from streamlit_geolocation import streamlit_geolocation
import time
import random
import re
import io
import math
import urllib.parse

# ==========================================
# 1. FUNDAMENT: STRAŻNIK STANU (STATE MANAGER)
# ==========================================
def init_session():
    """Inicjuje wszystkie zmienne, aby zapobiec AttributeError."""
    defaults = {
        'logged_in': False,
        'user_id': None,
        'trasa_wynikowa': None,
        'home_coords': (50.87, 20.63), # Domyślnie Kielce
        'nieobecnosci_daty': [],
        'db_loaded': False,
        'home_address_saved': "Kielce, Polska",
        'curr_gps': None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()

# ==========================================
# 2. POŁĄCZENIE Z CHMURĄ (SUPABASE)
# ==========================================
@st.cache_resource
def get_supabase_client():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        st.error("❌ Krytyczny błąd: Brak kluczy w Secrets!")
        return None

supabase = get_supabase_client()

# ==========================================
# 3. KONFIGURACJA UI I CSS
# ==========================================
st.set_page_config(page_title="A2B FlowRoute PRO v12", layout="wide", initial_sidebar_state="expanded")

COLOR_CYAN = "#00C2CB"
COLOR_NAVY_DARK = "#1A2238"
COLOR_BG = "#1F293D"
DAILY_COLORS = ['blue', 'green', 'red', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'darkpurple', 'darkorange']

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background-color: {COLOR_BG}; color: white; }}
    .stApp {{ background-color: {COLOR_BG}; color: white; }}
    [data-testid="stSidebar"] {{ background-color: {COLOR_NAVY_DARK} !important; min-width: 280px !important; }}
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important; border-radius: 8px !important; font-weight: 600 !important;
    }}
    .calendar-card {{
        background: rgba(255,255,255,0.05); border-left: 4px solid {COLOR_CYAN};
        padding: 12px; margin-bottom: 8px; border-radius: 8px; font-size: 0.9rem;
    }}
    .maps-link {{
        display: inline-block; padding: 12px 24px; background-color: #4285F4;
        color: white !important; text-decoration: none; border-radius: 8px;
        font-weight: bold; margin-bottom: 15px; text-align: center; width: 100%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3); transition: 0.3s;
    }}
    .maps-link:hover {{ transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.4); }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. LOGIKA BIZNESOWA I POMOCNICZA
# ==========================================
def save_data():
    """Automatyczny zapis do chmury."""
    if st.session_state.user_id and st.session_state.trasa_wynikowa is not None:
        try:
            data = {
                "user_id": st.session_state.user_id,
                "route_json": st.session_state.trasa_wynikowa.to_json(),
                "home_address": st.session_state.home_address_saved,
                "blocked_dates": [d.isoformat() for d in st.session_state.nieobecnosci_daty],
                "updated_at": datetime.now().isoformat()
            }
            supabase.table("user_data").upsert(data).execute()
            st.toast("✅ Dane zsynchronizowane z chmurą", icon="☁️")
        except: pass

def fix_polish(text):
    if not isinstance(text, str): return ""
    rep = {'GÛ': 'Gó', 'Û': 'ó', 'Ã³': 'ó', 'Ä…': 'ą', 'Ä™': 'ę', 'Å›': 'ś', 'Ä‡': 'ć', 'Åº': 'ź', 'Å¼': 'ż', 'Å‚': 'ł', 'Å„': 'ń'}
    for k, v in rep.items(): text = text.replace(k, v)
    return re.sub(r'[^\w\s,.-]', '', text).strip()

def create_gmaps_url(day_points, current_gps=None):
    """Generuje profesjonalny URL z sekwencją przystanków."""
    base = "https://www.google.com/maps/dir/"
    start = f"{current_gps[0]},{current_gps[1]}" if current_gps else "Moja+lokalizacja"
    stops = [start]
    for _, p in day_points.iterrows():
        stops.append(urllib.parse.quote(f"{p['street']}, {p['city']}, Polska"))
    return base + "/".join(stops)

# ==========================================
# 5. EKRAN LOGOWANIA
# ==========================================
if not st.session_state.logged_in:
    st.title("🛡️ A2B FlowRoute PRO")
    c1, _ = st.columns([1, 2])
    with c1:
        u_id = st.text_input("ID Użytkownika")
        pwd = st.text_input("Hasło", type="password")
        if st.button("Zaloguj do Systemu"):
            if u_id == "a2b_admin" and pwd == "polska2025":
                st.session_state.logged_in = True
                st.session_state.user_id = u_id
                st.rerun()
            else: st.error("❌ Nieprawidłowe dane logowania.")
    st.stop()

# ==========================================
# 6. WCZYTYWANIE DANYCH Z BAZY (TYLKO RAZ)
# ==========================================
if st.session_state.logged_in and not st.session_state.db_loaded:
    try:
        res = supabase.table("user_data").select("*").eq("user_id", st.session_state.user_id).execute()
        if res.data:
            saved = res.data[0]
            st.session_state.trasa_wynikowa = pd.read_json(saved['route_json'])
            st.session_state.home_address_saved = saved['home_address']
            st.session_state.nieobecnosci_daty = [date.fromisoformat(d) for d in saved.get('blocked_dates', [])]
        st.session_state.db_loaded = True
    except: pass

# ==========================================
# 7. SIDEBAR (LOGO, PARAMETRY, URLOPY)
# ==========================================
with st.sidebar:
    # LOGO (Zabezpieczone)
    try: st.image("assets/logo_a2b.png", use_container_width=True)
    except: st.markdown(f"<h2 style='color:{COLOR_CYAN}'>A2B FlowRoute</h2>", unsafe_allow_html=True)
    
    st.markdown(f"👤 **Operator:** {st.session_state.user_id}")
    
    # LOKALIZACJA GPS LIVE
    st.write("---")
    st.caption("📍 Twoja lokalizacja GPS")
    loc_data = streamlit_geolocation()
    if loc_data and loc_data.get('latitude'):
        st.session_state.curr_gps = (loc_data['latitude'], loc_data['longitude'])
        st.success("Sygnał GPS aktywny")
    
    dom_adres = st.text_input("Adres startowy (dom):", st.session_state.home_address_saved)
    
    st.write("---")
    # PARAMETRY
    tempo = st.slider("Wizyty dziennie", 1, 30, 12)
    wizyty_cel = st.number_input("Wizyt na klienta", 1, 5, 1)
    zrobione = st.number_input("Wizyty wykonane", 0, 1000, 0)
    
    st.write("---")
    # URLOPY / L4
    st.caption("📅 Zarządzanie czasem")
    dni_input = st.date_input("Dodaj urlop/L4/szkolenie:", value=(), min_value=date.today())
    if st.button("➕ Dodaj do kalendarza"):
        if isinstance(dni_input, (list, tuple)) and len(dni_input) > 0:
            if len(dni_input) == 2:
                s, e = dni_input
                st.session_state.nieobecnosci_daty.extend([s + timedelta(days=x) for x in range((e-s).days + 1)])
            else: st.session_state.nieobecnosci_daty.append(dni_input[0])
            st.session_state.nieobecnosci_daty = list(set(st.session_state.nieobecnosci_daty))
            save_data()
            st.rerun()

    if st.button("🗑️ RESETUJ WSZYSTKO"):
        st.session_state.trasa_wynikowa = None
        st.session_state.nieobecnosci_daty = []
        save_data()
        st.rerun()
    
    if st.button("Wyloguj"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# ==========================================
# 8. PANEL GŁÓWNY (LOGIKA GENEROWANIA)
# ==========================================
st.title("📅 Inteligentny Harmonogram A2B PRO")

# Wgrywanie pliku (tylko jeśli trasa nie istnieje lub chcemy nową)
up_file = st.file_uploader("📂 Wgraj nową bazę aptek", type=["xlsx", "csv"])

if up_file:
    try:
        with st.status("Przetwarzanie bazy danych...", expanded=True) as status:
            if up_file.name.endswith('.csv'):
                raw = up_file.read(); det = chardet.detect(raw); up_file.seek(0)
                df = pd.read_csv(up_file, sep=None, engine='python', encoding=det['encoding'] if det['confidence'] > 0.5 else 'utf-8-sig')
            else: df = pd.read_excel(up_file)
            
            # Czyszczenie i Geolokalizacja
            col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
            col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)
            
            if col_m and col_u:
                df['tmp'] = df[col_u].astype(str).str.upper() + df[col_m].astype(str).str.upper()
                df_clean = df.drop_duplicates(subset=['tmp']).copy()
                
                geolocator = Nominatim(user_agent=f"A2B_v12_{random.randint(1,999)}", timeout=10)
                geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                home_loc = geolocator.geocode(dom_adres)
                h_lat, h_lon = (home_loc.latitude, home_loc.longitude) if home_loc else (50.87, 20.63)
                
                coords = []
                for i, (_, row) in enumerate(df_clean.iterrows()):
                    st.write(f"📍 Mapowanie: {i+1}/{len(df_clean)} - {row[col_m]}")
                    loc = geocode(f"{row[col_u]}, {row[col_m]}, Polska")
                    if loc:
                        angle = math.atan2(loc.latitude - h_lat, loc.longitude - h_lon)
                        dist = geodesic((h_lat, h_lon), (loc.latitude, loc.longitude)).km
                        coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'angle': angle, 'dist': dist, 'addr': f"{row[col_u]}, {row[col_m]}", 'city': fix_polish(row[col_m]), 'street': fix_polish(row[col_u])})
                
                if coords:
                    pdf = pd.DataFrame(coords)
                    pdf = pdf.sort_values(by=['angle', 'dist'], ascending=[True, True]).reset_index(drop=True)
                    pdf['dzien_idx'] = pdf.index // tempo
                    
                    # Generowanie dat z omijaniem urlopów i weekendów
                    w_dates = []
                    curr = date.today() + timedelta(days=1)
                    while len(w_dates) <= pdf['dzien_idx'].max():
                        if curr.weekday() < 5 and curr not in st.session_state.nieobecnosci_daty:
                            w_dates.append(curr)
                        curr += timedelta(days=1)
                    
                    pdf['data_wizyty'] = pdf['dzien_idx'].map({i: w_dates[i] for i in range(len(w_dates))})
                    st.session_state.trasa_wynikowa = pdf
                    st.session_state.home_address_saved = dom_adres
                    save_data()
                    status.update(label="✅ Harmonogram wygenerowany!", state="complete")
                    st.rerun()
    except Exception as e: st.error(f"Błąd krytyczny: {e}")

# ==========================================
# 9. WIDOKI WYNIKOWE (MAPA I HARMONOGRAM)
# ==========================================
if st.session_state.trasa_wynikowa is not None:
    res = st.session_state.trasa_wynikowa
    all_dates = sorted(res['data_wizyty'].unique())
    
    t1, t2 = st.tabs(["🗺️ Mapa Operacyjna", "📅 Twój Plan i Nawigacja"])
    
    with t1:
        m = folium.Map(location=[res['lat'].mean(), res['lon'].mean()], zoom_start=8, tiles="cartodbpositron")
        # Start (Dom)
        folium.Marker(location=st.session_state.get('home_coords', (50.87, 20.63)), icon=folium.Icon(color='red', icon='home'), popup="START").add_to(m)
        for _, row in res.iterrows():
            color = DAILY_COLORS[all_dates.index(row['data_wizyty']) % len(DAILY_COLORS)]
            folium.CircleMarker(location=[row['lat'], row['lon']], radius=9, color=color, fill=True, popup=f"{row['data_wizyty']}").add_to(m)
        st_folium(m, width=1300, height=600, key="v12_master_map")
    
    with t2:
        for d in all_dates:
            day_pts = res[res['data_wizyty'] == d]
            with st.expander(f"📅 {d.strftime('%A, %d.%m.%Y')} — ({len(day_pts)} wizyt)"):
                g_url = create_gmaps_url(day_pts, st.session_state.curr_gps)
                st.markdown(f'<a href="{g_url}" target="_blank" class="maps-link">🚗 URUCHOM NAWIGACJĘ LIVE (START Z GPS)</a>', unsafe_allow_html=True)
                for _, p in day_pts.iterrows():
                    st.markdown(f"<div class='calendar-card'>📍 <b>{p['street']}</b>, {p['city']}</div>", unsafe_allow_html=True)
