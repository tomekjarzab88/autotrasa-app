import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="AutoTrasa - Planer Cyklu", layout="wide")

# --- INICJALIZACJA STANU SESJI ---
if 'nieobecnosci' not in st.session_state:
    st.session_state.nieobecnosci = [] # Przechowujemy tu słowniki {'typ': 'zakres/dzien', 'daty': [...]}

# --- PANEL BOCZNY ---
with st.sidebar:
    st.header("⚙️ Konfiguracja Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Ile wizyt u 1 klienta?", min_value=1, value=1)
    limit_dzienny = st.slider("🎯 Twój limit wizyt / dzień", 1, 30, 12)
    
    st.write("---")
    st.header("📈 Postęp Cyklu")
    wizyty_wykonane = st.number_input("Ile wizyt już ZROBIONO?", min_value=0, value=0)
    
    st.write("---")
    st.header("📅 Nieobecności")
    
    wybrane = st.date_input("Zaznacz dni lub zakresy:", value=[], min_value=date(2025, 1, 1))
    
    if st.button("➕ Dodaj do listy"):
        if isinstance(wybrane, list) and len(wybrane) == 2:
            # Dodawanie zakresu
            start, end = wybrane
            dni_w_zakresie = []
            curr = start
            while curr <= end:
                dni_w_zakresie.append(curr)
                curr += timedelta(days=1)
            st.session_state.nieobecnosci.append({'label': f"{start.strftime('%d.%m')} - {end.strftime('%d.%m')}", 'dni': dni_w_zakresie})
        elif isinstance(wybrane, list) and len(wybrane) == 1:
            # Pojedynczy dzień z kalendarza
            d = wybrane[0]
            st.session_state.nieobecnosci.append({'label': f"{d.strftime('%d.%m')}", 'dni': [d]})
        elif isinstance(wybrane, date):
            st.session_state.nieobecnosci.append({'label': f"{wybrane.strftime('%d.%m')}", 'dni': [wybrane]})
        st.rerun()

    # WYŚWIETLANIE I USUWANIE GRUP
    suma_dni_wolnych = 0
    if st.session_state.nieobecnosci:
        st.write("**Twoje wolne:**")
        for i, grupa in enumerate(st.session_state.nieobecnosci):
            col_l, col_b = st.columns([3, 1])
            col_l.write(f"• {grupa['label']}")
            if col_b.button("❌", key=f"group_{i}"):
                st.session_state.nieobecnosci.pop(i)
                st.rerun()
            suma_dni_wolnych += len(grupa['dni'])
        
        if st.button("🗑️ Wyczyść wszystko"):
            st.session_state.nieobecnosci = []
            st.rerun()
    
    st.write(f"**Suma dni wolnych: {suma_dni_wolnych}**")

# --- WCZYTYWANIE PLIKU I OBLICZENIA ---
uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = max(0, dni_podstawa[typ_cyklu] - suma_dni_wolnych)
        
        total_wizyt_cel = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, total_wizyt_cel - wizyty_wykonane)
        wymagana_srednia = do_zrobienia / dni_robocze if dni_robocze > 0 else 0

        # DASHBOARD
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci", len(df))
        m2.metric("Dni robocze netto", dni_robocze)
        m3.metric("Zostało wizyt", do_zrobienia)
        procent = (wizyty_wykonane / total_wizyt_cel * 100) if total_wizyt_cel > 0 else 0
        m4.metric("Postęp", f"{round(procent, 1)}%")

        # WYKRES GAUGE
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
            st.write("### 📝 Status")
            if wymagana_srednia > limit_dzienny:
                st.error(f"Musisz robić **{round(wymagana_srednia, 1)}** wizyt/dzień.")
            else:
                st.success(f"Limit **{limit_dzienny}** jest OK.")

        st_folium(folium.Map(location=[52.0688, 19.4797], zoom_start=6), width=1100, height=400)

    except Exception as e:
        st.error(f"Błąd: {e}")
