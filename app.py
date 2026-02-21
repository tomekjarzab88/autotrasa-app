import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="AutoTrasa - Planer Cyklu", layout="wide")

# --- INICJALIZACJA STANU SESJI ---
if 'dni_wolne_lista' not in st.session_state:
    st.session_state.dni_wolne_lista = []

# --- FUNKCJA SZUKANIA KOLUMN ---
def find_column(columns, patterns):
    for pattern in patterns:
        for col in columns:
            clean_col = col.lower().strip()
            clean_col = clean_col.replace('ą','a').replace('ę','e').replace('ś','s').replace('ć','c').replace('ó','o').replace('ń','n').replace('ł','l').replace('ź','z').replace('ż','z')
            if pattern in clean_col:
                return col
    return None

st.title("🚚 AutoTrasa / FromAtoB")

# --- PANEL BOCZNY (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Konfiguracja Cyklu")
    
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Ile wizyt u 1 klienta?", min_value=1, value=1)
    limit_dzienny = st.slider("🎯 Twój limit wizyt / dzień", 1, 30, 12)
    
    st.write("---")
    st.header("📈 Postęp Cyklu")
    # NOWOŚĆ: Pole do wpisania wykonanych wizyt
    wizyty_wykonane = st.number_input("Ile wizyt już ZROBIONO?", min_value=0, value=0)
    
    st.write("---")
    st.header("📅 Nieobecności")
    
    # KALENDARZ ZAKRESOWY
    wybrane_w_kalendarzu = st.date_input(
        "Zaznacz dni lub zakresy:",
        value=[],
        min_value=date(2025, 1, 1)
    )
    
    # POPRAWIONA LOGIKA DODAWANIA (Bezpieczna dla AttributeError)
    if st.button("➕ Dodaj zaznaczone do listy"):
        if isinstance(wybrane_w_kalendarzu, (list, tuple)):
            for d in wybrane_w_kalendarzu:
                if isinstance(d, (date, datetime)) and d not in st.session_state.dni_wolne_lista:
                    st.session_state.dni_wolne_lista.append(d)
        elif isinstance(wybrane_w_kalendarzu, (date, datetime)):
            if wybrane_w_kalendarzu not in st.session_state.dni_wolne_lista:
                st.session_state.dni_wolne_lista.append(wybrane_w_kalendarzu)
        st.rerun()

    # LISTA ZARZĄDZALNA Z POPRAWKĄ WYŚWIETLANIA
    if st.session_state.dni_wolne_lista:
        st.write("**Lista wolnych dni:**")
        # Sortujemy, żeby lista była czytelna
        st.session_state.dni_wolne_lista.sort()
        for i, d in enumerate(st.session_state.dni_wolne_lista):
            col_d, col_b = st.columns([3, 1])
            # Bezpieczne formatowanie
            data_str = d.strftime('%d.%m') if hasattr(d, 'strftime') else str(d)
            col_d.write(f"• {data_str}")
            if col_b.button("❌", key=f"del_{i}"):
                st.session_state.dni_wolne_lista.remove(d)
                st.rerun()
        
        if st.button("🗑️ Wyczyść wszystko"):
            st.session_state.dni_wolne_lista = []
            st.rerun()
    
    ile_wolnych = len(st.session_state.dni_wolne_lista)

# --- WCZYTYWANIE PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA (Realna pomoc w trakcie cyklu)
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze_pozostalo = max(0, dni_podstawa[typ_cyklu] - ile_wolnych)
        
        total_wizyt_cel = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, total_wizyt_cel - wizyty_wykonane)
        
        # Ile musisz robić dziennie od teraz, żeby zdążyć?
        wymagana_srednia = do_zrobienia / dni_robocze_pozostalo if dni_robocze_pozostalo > 0 else 0
        
        # --- DASHBOARD ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci w bazie", len(df))
        m2.metric("Dni do końca", dni_robocze_pozostalo)
        m3.metric("Zostało wizyt", do_zrobienia)
        
        procent_ukonczenia = (wizyty_wykonane / total_wizyt_cel * 100) if total_wizyt_cel > 0 else 0
        m4.metric("Postęp całkowity", f"{round(procent_ukonczenia, 1)}%")

        # --- ANALIZA GAUGE ---
        c_left, c_right = st.columns([2, 1])
        with c_left:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                title = {'text': "Wymagana średnia (by zdążyć)"},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#FF4B4B" if wymagana_srednia > limit_dzienny else "#0083B8"},
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.write("### 📝 Twój status")
            if wymagana_srednia > limit_dzienny:
                st.error(f"⚠️ UWAGA: Musisz robić średnio **{round(wymagana_srednia, 1)}** wizyt dziennie.")
                st.write(f"Przy Twoim limicie ({limit_dzienny}) braknie Ci czasu.")
            else:
                st.success(f"✅ Masz zapas! Twój limit {limit_dzienny} wizyt wystarczy.")
                if dni_robocze_pozostalo > 0:
                    zapas_total = int((limit_dzienny * dni_robocze_pozostalo) - do_zrobienia)
                    st.write(f"Możesz odpuścić łącznie **{zapas_total}** wizyt.")

        st.write("---")
        st.subheader("📍 Mapa Polski")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
        st_folium(m, width=1100, height=400)

    except Exception as e:
        st.error(f"Błąd: {e}")
