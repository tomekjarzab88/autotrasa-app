import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

# --- KONFIGURACJA PREMIUM ---
st.set_page_config(page_title="AutoTrasa Enterprise", layout="wide", initial_sidebar_state="expanded")

# --- ZAAWANSOWANY CSS (MODERN UI) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Tło i ogólny vibe */
    .stApp {
        background-color: #F8FAFC;
    }

    /* Nowoczesny Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    
    /* Karty Metryk (WOW effect) */
    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #E2E8F0;
        padding: 20px !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
    }
    
    /* Stylowanie przycisków */
    .stButton>button {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
    }

    /* Elegancki nagłówek */
    .hero-section {
        background: white;
        padding: 30px;
        border-radius: 20px;
        border: 1px solid #E2E8F0;
        margin-bottom: 30px;
        display: flex;
        align-items: center;
        gap: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INICJALIZACJA ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = []

# --- SIDEBAR PRO ---
with st.sidebar:
    # Uśmiechnięty profesjonalista w aucie (elegancki rysunek)
    st.image("https://img.freepik.com/free-vector/businessman-driving-car_24877-50204.jpg?t=st=1716120000&exp=1716123600&hmac=elegant_drawing", use_container_width=True)
    
    st.markdown("<h2 style='color: white; text-align: center; margin-bottom: 0;'>AutoTrasa</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94A3B8; text-align: center; font-size: 0.8rem;'>System Zarządzania Cyklem Sprzedaży</p>", unsafe_allow_html=True)
    st.write("---")
    
    with st.expander("💼 PARAMETRY CYKLU", expanded=True):
        typ_cyklu = st.selectbox("Długość", ["Miesiąc", "2 Miesiące", "Kwartał"])
        wizyty_na_klienta = st.number_input("Wizyt u 1 klienta", min_value=1, value=1)
        limit_dzienny = st.slider("Limit dzienny", 1, 30, 12)

    with st.expander("📈 REALIZACJA"):
        wizyty_wykonane = st.number_input("Zrobione wizyty", min_value=0, value=0)

    st.write("---")
    st.markdown("<p style='color: white; font-weight: 600;'>📅 PLANOWANIE WOLNEGO</p>", unsafe_allow_html=True)
    wybrane = st.date_input("Zaznacz daty:", value=(), min_value=date(2025, 1, 1))
    
    if st.button("DODAJ DO HARMONOGRAMU"):
        if isinstance(wybrane, (list, tuple)) and len(wybrane) > 0:
            if len(wybrane) == 2:
                start, end = wybrane
                dni = [start + timedelta(days=x) for x in range((end-start).days + 1)]
                st.session_state.nieobecnosci.append({'label': f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}", 'dni': dni})
            else:
                d = wybrane[0]
                st.session_state.nieobecnosci.append({'label': f"{d.strftime('%d.%m')}", 'dni': [d]})
            st.rerun()

    # Wyświetlanie listy (nowoczesne tagi)
    suma_wolnych = 0
    for i, g in enumerate(st.session_state.nieobecnosci):
        with st.container():
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"<span style='color: #CBD5E1; font-size: 0.85rem;'>• {g['label']}</span>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{i}"):
                st.session_state.nieobecnosci.pop(i)
                st.rerun()
            suma_wolnych += len(g['dni'])

# --- GŁÓWNY DASHBOARD ---
# Hero Section
st.markdown(f"""
    <div class="hero-section">
        <div style="font-size: 40px;">🏢</div>
        <div>
            <h1 style="margin:0; font-size: 1.8rem; font-weight: 600;">Panel Kontrolny Cyklu</h1>
            <p style="margin:0; color: #64748B;">Zoptymalizuj swoją trasę i monitoruj KPI w czasie rzeczywistym.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# File Uploader w formie eleganckiej strefy
uploaded_file = st.file_uploader("", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA LOGICZNE
        dni_p = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_n = max(0, dni_p[typ_cyklu] - suma_wolnych)
        cel_total = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, cel_total - wizyty_wykonane)
        wymagana_srednia = do_zrobienia / dni_n if dni_n > 0 else 0
        
        # --- TOP METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci w bazie", f"{len(df)}", "Baza")
        m2.metric("Dni robocze", f"{dni_n}", "Netto")
        m3.metric("Pozostało wizyt", f"{do_zrobienia}", "Cel")
        postep = round((wizyty_wykonane/cel_total*100), 1) if cel_total > 0 else 0
        m4.metric("Realizacja", f"{postep}%", f"{wizyty_wykonane} / {cel_total}")

        # --- WYKRES GAUGE & ANALIZA ---
        st.write("---")
        c_left, c_right = st.columns([2, 1])
        
        with c_left:
            # Gauge w stylu Modern
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                number = {'font': {'color': "#1E293B", 'size': 50}},
                title = {'text': "WYMAGANA WYDAJNOŚĆ DZIENNA", 'font': {'size': 14, 'color': '#64748B'}},
                gauge = {
                    'axis': {'range': [None, 30], 'tickwidth': 1},
                    'bar': {'color': "#3B82F6"},
                    'bgcolor': "white",
                    'borderwidth': 0,
                    'threshold': {'line': {'color': "#EF4444", 'width': 4}, 'thickness': 0.8, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=350, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.markdown("### 🛠️ Rekomendacje AI")
            if wymagana_srednia > limit_dzienny:
                st.warning(f"""
                **Wykryto przeciążenie planu.** Średnia wymagana ({round(wymagana_srednia,1)}) przekracza Twój limit ({limit_dzienny}). 
                Sugerujemy dodanie 1 dnia roboczego lub zwiększenie limitu o {round(wymagana_srednia - limit_dzienny,1)} wizyt.
                """)
            else:
                st.success(f"""
                **Plan zoptymalizowany.** Utrzymując obecne tempo, zrealizujesz cykl z wyprzedzeniem. 
                Masz zapas operacyjny wynoszący {int((limit_dzienny * dni_n) - do_zrobienia)} wizyt.
                """)

        # --- MAPA ---
        st.write("---")
        st.markdown("<h3 style='margin-bottom: 20px;'>📍 Rozkład geograficzny punktów</h3>", unsafe_allow_html=True)
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6, tiles="cartodbpositron")
        st_folium(m, width=1300, height=550)

    except Exception as e:
        st.error(f"Krytyczny błąd przetwarzania: {e}")
else:
    # Ekran powitalny (Empty State)
    st.info("Wgraj bazę danych (CSV), aby aktywować analizę inteligentną.")
