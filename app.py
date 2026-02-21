import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="AutoTrasa - Planer Cyklu", layout="wide")

# --- FUNKCJA INTELIGENTNEGO SZUKANIA KOLUMN ---
def find_column(columns, patterns):
    for pattern in patterns:
        for col in columns:
            clean_col = col.lower().strip()
            clean_col = clean_col.replace('ą','a').replace('ę','e').replace('ś','s').replace('ć','c').replace('ó','o').replace('ń','n').replace('ł','l').replace('ź','z').replace('ż','z')
            if pattern in clean_col:
                return col
    return None

st.title("🚚 AutoTrasa / FromAtoB")

# --- KONTEKST CZASOWY ---
dzis = date.today()
st.info(f"📅 Dzisiaj jest: **{dzis.strftime('%d.%m.%Y')}**")

# --- PANEL BOCZNY (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Ile wizyt u 1 klienta w cyklu?", min_value=1, value=1)
    
    st.header("📅 Twoja dostępność")
    dni_wolne = st.date_input(
        "Zaznacz dni nieobecności (L4, Szkolenia, Urlopy)", 
        value=[dzis],
        min_value=date(2025, 1, 1) # Rozszerzony zakres wstecz
    )
    
    # --- NOWOŚĆ: WIZUALNA LISTA WYBRANYCH DNI ---
    if dni_wolne:
        st.write("---")
        st.subheader("🗓️ Wybrane daty:")
        if isinstance(dni_wolne, list):
            for d in sorted(dni_wolne):
                prefix = "🔴" if d < dzis else "🔵"
                status = " (Przeszłość)" if d < dzis else " (Planowane)"
                st.write(f"{prefix} {d.strftime('%d.%m.%Y')}{status}")
            ile_wolnych = len(dni_wolne)
        else:
            st.write(f"🔵 {dni_wolne.strftime('%d.%m.%Y')}")
            ile_wolnych = 1
        st.write(f"**Suma dni wolnych: {ile_wolnych}**")

# --- WCZYTYWANIE PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV z bazą klientów", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        col_miasto = find_column(df.columns, ['miasto', 'miejscowosc', 'city', 'town'])
        col_ulica = find_column(df.columns, ['ulica', 'adres', 'street', 'addr', 'ul.'])
        col_id = find_column(df.columns, ['akronim', 'id', 'nazwa', 'kod'])

        # --- LIMIT DZIENNY ---
        st.write("---")
        col_slider, col_empty = st.columns([1, 2])
        with col_slider:
            limit_dzienny = st.slider("🎯 Twój dzienny limit wizyt", 5, 25, 10)

        # OBLICZENIA
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = dni_podstawa[typ_cyklu] - ile_wolnych
        total_wizyt_do_zrobienia = len(df) * wizyty_na_klienta
        twoja_wydajnosc_suma = limit_dzienny * dni_robocze
        realizacja_procent = (twoja_wydajnosc_suma / total_wizyt_do_zrobienia * 100) if total_wizyt_do_zrobienia > 0 else 0
        wymagana_srednia = total_wizyt_do_zrobienia / dni_robocze if dni_robocze > 0 else 0

        # --- DASHBOARD ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci w bazie", len(df))
        m2.metric("Dni robocze netto", dni_robocze)
        m3.metric("Wizyty w cyklu", total_wizyt_do_zrobienia)
        m4.metric("Realizacja Planu", f"{round(realizacja_procent, 1)}%")

        # --- WYKRES GAUGE ---
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = wymagana_srednia,
            title = {'text': f"Wymagana średnia (Cel: {limit_dzienny})"},
            gauge = {
                'axis': {'range': [None, 25]},
                'bar': {'color': "#0083B8"},
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

        # --- MAPA I TABELA ---
        st.write("---")
        st.subheader("📍 Podgląd lokalizacji")
        if col_miasto and col_ulica:
            st.success(f"Zmapowano adresy: {col_ulica}, {col_miasto}")
            # Mapa (uproszczona dla szybkości ładowania)
            m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
            st_folium(m, width=1100, height=400)
        
        st.write("### 📋 Baza klientów")
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Błąd: {e}")
