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
        min_value=date(2024, 1, 1)
    )
    st.caption("Podpowiedź: Możesz wybierać daty wstecz i w przyszłość.")

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

        # --- NOWA OPCJA: LIMIT DZIENNY U GÓRY ---
        st.write("---")
        col_slider, col_empty = st.columns([1, 2])
        with col_slider:
            limit_dzienny = st.slider("🎯 Twój dzienny limit wizyt", 5, 25, 10)

        # OBLICZENIA MATEMATYCZNE
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        ile_wolnych = len(dni_wolne) if isinstance(dni_wolne, (list, tuple)) else 1
        
        dni_robocze = dni_podstawa[typ_cyklu] - ile_wolnych
        total_wizyt_do_zrobienia = len(df) * wizyty_na_klienta
        twoja_wydajnosc_suma = limit_dzienny * dni_robocze
        
        realizacja_procent = (twoja_wydajnosc_suma / total_wizyt_do_zrobienia * 100) if total_wizyt_do_zrobienia > 0 else 0
        wymagana_srednia = total_wizyt_do_zrobienia / dni_robocze if dni_robocze > 0 else 0

        # --- DASHBOARD STATYSTYK ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci w bazie", len(df))
        m2.metric("Dni robocze", dni_robocze)
        m3.metric("Suma wizyt w cyklu", total_wizyt_do_zrobienia)
        
        # Kolor delty dla realizacji
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
                    'axis': {'range': [None, 25]},
                    'bar': {'color': "#0083B8"},
                    'steps': [
                        {'range': [0, 10], 'color': "#e8f5e9"},
                        {'range': [10, limit_dzienny], 'color': "#fff3e0"},
                        {'range': [limit_dzienny, 25], 'color': "#ffebee"}
                    ],
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.write("### 📝 Status")
            if realizacja_procent < 100:
                st.error(f"Brakuje Ci **{int(total_wizyt_do_zrobienia - twoja_wydajnosc_suma)}** wizyt do zamknięcia cyklu. Zwiększ limit dzienny lub ogranicz dni wolne.")
            else:
                st.success(f"Masz zapas **{int(twoja_wydajnosc_suma - total_wizyt_do_zrobienia)}** wizyt. Możesz zaplanować dodatkowe działania!")

        st.write("---")
        
        # --- MAPA ---
        st.subheader("📍 Mapa Twoich Punktów")
        if col_miasto and col_ulica:
            m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
            st_folium(m, width=1200, height=450)
            
            if st.button("🚀 GENERUJ TRASĘ"):
                st.balloons()
                st.info("Algorytm grupuje teraz apteki geograficznie...")
        
        st.write("### 📋 Podgląd bazy")
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Błąd: {e}")
