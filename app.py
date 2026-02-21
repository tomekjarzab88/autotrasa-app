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
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    
    st.header("📅 Twoja dostępność")
    # Kalendarz odblokowany wstecz (min_value 2025)
    dni_wolne = st.date_input(
        "Zaznacz dni nieobecności", 
        value=[dzis],
        min_value=date(2025, 1, 1)
    )
    
    # Wyświetlanie listy wybranych dni (to o co prosiłeś)
    lista_dat = []
    if dni_wolne:
        if isinstance(dni_wolne, list):
            lista_dat = [d for d in dni_wolne if isinstance(d, (date, datetime))]
        else:
            lista_dat = [dni_wolne]
        
        st.write("---")
        st.subheader("🗓️ Wybrane dni:")
        for d in sorted(lista_dat):
            st.write(f"• {d.strftime('%d.%m.%Y')}")
    
    ile_wolnych = len(lista_dat)

# --- WCZYTYWANIE PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # Rozpoznawanie kolumn
        col_miasto = find_column(df.columns, ['miasto', 'miejscowosc', 'city', 'town'])
        col_ulica = find_column(df.columns, ['ulica', 'adres', 'street', 'addr', 'ul.'])
        
        # --- SUWAK LIMITU DZIENNEGO (to o co prosiłeś) ---
        st.write("---")
        limit_dzienny = st.slider("🎯 Twój dzienny limit wizyt (moc przerobowa)", 1, 30, 12)

        # OBLICZENIA
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = dni_podstawa[typ_cyklu] - ile_wolnych
        total_wizyt = len(df) * wizyty_na_klienta
        wymagana_srednia = total_wizyt / dni_robocze if dni_robocze > 0 else 0
        realizacja = (limit_dzienny * dni_robocze / total_wizyt * 100) if total_wizyt > 0 else 0

        # --- DASHBOARD ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Klienci", len(df))
        c2.metric("Dni netto", dni_robocze)
        c3.metric("Wymagana śr.", round(wymagana_srednia, 1))
        c4.metric("Realizacja Planu", f"{round(realizacja, 1)}%")

        # WYKRES GAUGE
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = wymagana_srednia,
            title = {'text': "Wymagana średnia dzienna"},
            gauge = {
                'axis': {'range': [None, 30]},
                'bar': {'color': "#0083B8"},
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        
        # MAPA
        st.subheader("📍 Mapa Polski")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
        st_folium(m, width=1100, height=400)
        
        st.write("### 📋 Podgląd danych")
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Wystąpił błąd: {e}")
