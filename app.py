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
    st.header("⚙️ Ustawienia Bazy")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Ile wizyt u 1 klienta w cyklu?", min_value=1, value=1)
    
    st.header("📅 Twoja dostępność")
    # Kalendarz
    dni_wolne = st.date_input(
        "Zaznacz dni nieobecności (L4, Szkolenia, Urlopy)", 
        value=[dzis],
        min_value=date(2025, 1, 1)
    )
    
    # --- PANCERNA LOGIKA WYŚWIETLANIA DAT ---
    lista_dat = []
    if dni_wolne:
        # Konwertujemy wszystko na listę, żeby pętla zawsze działała
        if isinstance(dni_wolne, list):
            lista_dat = dni_wolne
        elif isinstance(dni_wolne, (date, datetime)):
            lista_dat = [dni_wolne]
        
        st.write("---")
        st.subheader("🗓️ Zarejestrowane dni:")
        for d in sorted(lista_dat):
            # Sprawdzamy czy element listy jest faktycznie datą (Streamlit czasem wysyła puste zakresy)
            if isinstance(d, (date, datetime)):
                prefix = "🔴" if d < dzis else "🔵"
                st.write(f"{prefix} {d.strftime('%d.%m.%Y')}")
    
    ile_wolnych = len(lista_dat)
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

        # --- SUWAK LIMITU DZIENNEGO ---
        st.write("---")
        st.subheader("🚀 Twoja wydajność")
        limit_dzienny = st.select_slider(
            "Ustaw planowaną liczbę wizyt dziennych (Total):",
            options=list(range(1, 31)),
            value=12
        )

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
        m2.metric("Dni robocze netto", max(0, dni_robocze))
        m3.metric("Suma wizyt do zrobienia", total_wizyt_do_zrobienia)
        
        delta_val = round(realizacja_procent - 100, 1)
        m4.metric("Realizacja Planu", f"{round(realizacja_procent, 1)}%", delta=f"{delta_val}%")

        # --- WYKRES GAUGE ---
        c_left, c_right = st.columns([2, 1])
        with c_left:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = wymagana_srednia,
                delta = {'reference': limit_dzienny, 'increasing': {'color': "red"}, 'decreasing': {'color': "green"}},
                title = {'text': "Wymagana średnia vs Twój limit"},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#0083B8"},
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.write("### 📝 Analiza")
            if realizacja_procent < 100:
                brakuje = int(total_wizyt_do_zrobienia - twoja_wydajnosc_suma)
                st.error(f"Zabraknie Ci **{max(0, brakuje)}** wizyt.")
            else:
                zapas = int(twoja_wydajnosc_suma - total_wizyt_do_zrobienia)
                st.success(f"Masz **{max(0, zapas)}** wizyt zapasu
