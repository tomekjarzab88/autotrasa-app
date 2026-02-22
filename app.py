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
import time
import random
import re
import io
import math

# --- 1. GLOBALNA INICJALIZACJA PAMIĘCI (ZAPOBIEGA BŁĘDOM ATTRIBUTEERROR) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'trasa_wynikowa' not in st.session_state: st.session_state.trasa_wynikowa = None
if 'home_coords' not in st.session_state: st.session_state.home_coords = None
if 'db_loaded' not in st.session_state: st.session_state.db_loaded = False
if 'home_address_saved' not in st.session_state: st.session_state.home_address_saved = "Kielce, Polska"

# --- 2. KONFIGURACJA SUPABASE ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("❌ Brak konfiguracji Secrets w Streamlit Cloud! Dodaj SUPABASE_URL i SUPABASE_KEY.")
    st.stop()

# --- 3. KONFIGURACJA STRONY ---
st.set_page_config(page_title="A2B FlowRoute PRO v11.1", layout="wide", initial_sidebar_state="expanded")

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
    .stButton>button {{
        background: linear-gradient(135deg, {COLOR_CYAN} 0%, #00A0A8 100%) !important;
        color: white !important; border-radius: 8px !important; font-weight: bold !important; width: 100%;
    }}
    .calendar-card {{
        background: rgba(255,255,255,0.05); border-left: 4px solid {COLOR_CYAN};
        padding: 10px; margin-bottom: 5px; border-radius: 5px;
    }}
    .maps-link {{
        display: inline-block; padding: 10px 20px; background-color: #4285F4;
        color: white !important; text-decoration: none; border-radius: 5px;
        font-weight: bold; margin-bottom: 15px; text-align: center; width: 100%;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNKCJE POMOCNICZE ---
def save_plan_to_db(user_id, df, home_addr):
    try:
        data = {
            "user_id": user_id,
            "route_json": df.to_json(),
            "home_address": home_addr,
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("user_data").upsert(data).execute()
    except Exception as e:
        st.sidebar.error(f"⚠️ Błąd zapisu: {e}")

def load_plan_from_db(user_id):
    try:
        res = supabase.table("user_data").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except:
        return None

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

def create_gmaps_url(home_coords, day_points):
    base_url = "https://www.google.com/maps/dir/"
    origin = f"{home_coords[0]},{home_coords[1]}"
    pts = "/".join([f"{p['lat']},{p['lon']}" for _, p in day_points.iterrows()])
    return f"{base_url}{origin}/{pts}"

# --- 5. SYSTEM LOGOWANIA ---
if not st.session_state.logged_in:
    st.title("🛡️ A2B FlowRoute PRO")
    st.subheader("Zaloguj się do swojego konta")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        u_id = st.text_input("ID Użytkownika")
        pwd = st.text_input("Hasło", type="password")
        
        if st.button("Zaloguj"):
            if u_id == "a2b_admin" and pwd == "polska2025":
                st.session_state.logged_in = True
                st.session_state.user_id = u_id
                st.rerun()
            else:
                st.error("Błędne dane logowania.")
    st.stop()

# --- 6. SYNCHRONIZACJA Z BAZĄ (TYLKO RAZ PO LOGOWANIU) ---
if st.session_state.logged_in and not st.session_state.db_loaded:
    saved = load_plan_from_db(st.session_state.user_id)
    if saved:
        try:
            st.session_state.trasa_wynikowa = pd.read_json(saved['route_json'])
            st.session_state.home_address_saved = saved['home_address']
        except:
            pass
    st.session_state.db_loaded = True

# --- 7. SIDEBAR ---
with st.sidebar:
    st.markdown(f"👤 **Użytkownik:** {st.session_state.user_id}")
    if st.button("Wyloguj się"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    st.write("---")
    dom_adres = st.text_input("📍 Twoje miejsce zamieszkania", st.session_state.home_address_saved)
    
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_cel = st.number_input("Wizyt na klienta", min_value=1, value=1)
    tempo = st.slider("Twoje tempo (wizyty/dzień)", 1, 30, 12)
    zrobione = st.number_input("Wizyty już wykonane", min_value=0, value=0)
    
    if st.button("🗑️ WYCZYŚĆ OBECNY PLAN"):
        st.session_state.trasa_wynikowa = None
        st.rerun()

# --- 8. PANEL GŁÓWNY ---
st.title("📅 Twój Inteligentny Kalendarz PRO")

uploaded_file = st.file_uploader("📂 Wgraj bazę aptek (XLSX / CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            raw = uploaded_file.read(); det = chardet.detect(raw); uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=det['encoding'] if det['confidence'] > 0.5 else 'utf-8-sig')
        else: df = pd.read_excel(uploaded_file)
        
        col_m = next((c for c in df.columns if 'miasto' in c.lower() or 'miejscowość' in c.lower()), None)
        col_u = next((c for c in df.columns if 'ulica' in c.lower() or 'adres' in c.lower()), None)

        if col_m and col_u:
            df['temp_addr'] = df[col_u].astype(str).str.upper() + df[col_m].astype(str).str.upper()
            df_clean = df.drop_duplicates(subset=['temp_addr']).copy()
            df_clean[col_m] = df_clean[col_m].apply(fix_polish)
            df_clean[col_u] = df_clean[col_u].apply(fix_polish)
            
            st.info(f"📋 Baza zawiera **{len(df_clean)}** unikalnych aptek.")

            if st.button("🚀 GENERUJ NOWY PLAN I ZAPISZ W CHMURZE"):
                coords = []
                bar = st.progress(0); counter = st.empty()
                geolocator = Nominatim(user_agent=f"A2B_v111_{random.randint(1,999)}", timeout=10)
                geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)
                
                home_loc = geolocator.geocode(dom_adres)
                if not home_loc: st.error("Błąd lokalizacji domu."); st.stop()
                h_lat, h_lon = home_loc.latitude, home_loc.longitude
                st.session_state.home_coords = (h_lat, h_lon)
                
                total = len(df_clean)
                for i, (_, row) in enumerate(df_clean.iterrows()):
                    addr = f"{row[col_u]}, {row[col_m]}, Polska"
                    bar.progress((i + 1) / total)
                    counter.markdown(f"#### 📍 Geolokalizacja: **{i+1}** / **{total}**")
                    try:
                        loc = geocode(addr)
                        if loc:
                            angle = math.atan2(loc.latitude - h_lat, loc.longitude - h_lon)
                            dist = geodesic((h_lat, h_lon), (loc.latitude, loc.longitude)).km
                            coords.append({'lat': loc.latitude, 'lon': loc.longitude, 'angle': angle, 'dist': dist, 'addr': addr, 'city': row[col_m], 'street': row[col_u]})
                    except: pass

                if coords:
                    pdf = pd.DataFrame(coords)
                    pdf = pdf.sort_values(by=['angle', 'dist'], ascending=[True, True]).reset_index(drop=True)
                    pdf['dzien_idx'] = pdf.index // tempo
                    working_dates = generate_working_dates(date.today(), int(pdf['dzien_idx'].max() + 1), [])
                    pdf['data_wizyty'] = pdf['dzien_idx'].map({i: working_dates[i] for i in range(len(working_dates))})
                    
                    st.session_state.trasa_wynikowa = pdf
                    save_plan_to_db(st.session_state.user_id, pdf, dom_adres)
                    st.success("☁️ Trasa zsynchronizowana z bazą danych!")
                    st.rerun()
    except Exception as e: st.error(f"Błąd przetwarzania: {e}")

# --- 9. WIZUALIZACJA (TYLKO JEŚLI DANE ISTNIEJĄ) ---
if st.session_state.get('trasa_wynikowa') is not None:
    res = st.session_state.trasa_wynikowa
    all_dates = sorted(res['data_wizyty'].unique())
    
    t1, t2 = st.tabs(["🗺️ Mapa Pracy", "📅 Harmonogram z Nawigacją"])
    
    with t1:
        m = folium.Map(location=[52.0, 19.0], zoom_start=6, tiles="cartodbpositron")
        # Jeśli mamy współrzędne domu, dodaj pinezkę
        if st.session_state.get('home_coords'):
            folium.Marker(location=st.session_state.home_coords, icon=folium.Icon(color='red', icon='home')).add_to(m)
            
        for _, row in res.iterrows():
            color = DAILY_COLORS[all_dates.index(row['data_wizyty']) % len(DAILY_COLORS)]
            folium.CircleMarker(location=[row['lat'], row['lon']], radius=10, color=color, fill=True, popup=f"{row['data_wizyty']}").add_to(m)
        st_folium(m, width=1300, height=600, key="main_map")
    
    with t2:
        for d in all_dates:
            day_pts = res[res['data_wizyty'] == d]
            with st.expander(f"📅 {d.strftime('%A, %d.%m.%Y')} — ({len(day_pts)} wizyt)"):
                # Próba uzyskania home_coords do nawigacji
                h_c = st.session_state.get('home_coords', (50.87, 20.63))
                gmaps_url = create_gmaps_url(h_c, day_pts)
                st.markdown(f'<a href="{gmaps_url}" target="_blank" class="maps-link">🚗 URUCHOM NAWIGACJĘ GOOGLE MAPS</a>', unsafe_allow_html=True)
                for _, p in day_pts.iterrows():
                    st.markdown(f"<div class='calendar-card'>📍 <b>{p['street']}</b>, {p['city']}</div>", unsafe_allow_html=True)
