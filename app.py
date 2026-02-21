import streamlit as st
import pandas as pd
import chardet
from datetime import datetime, date
import plotly.graph_objects as go
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="AutoTrasa - Planer Cyklu", layout="wide")

# --- INICJALIZACJA STANU SESJI DLA DNI WOLNYCH ---
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
    
    # 1. PARAMETRY CYKLU
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Ile wizyt u 1 klienta?", min_value=1, value=1)
    limit_dzienny = st.slider("🎯 Twój limit wizyt / dzień", 1, 30, 12)
    
    st.write("---")
    st.header("📅 Zarządzanie nieobecnościami")
    
    # 2. DODAWANIE DNI WOLNYCH
    data_do_dodania = st.date_input("Wybierz datę:", value=date.today())
    if st.button("➕ Dodaj ten dzień do listy"):
        if data_do_dodania not in st.session_state.dni_wolne_lista:
            st.session_state.dni_wolne_lista.append(data_do_dodania)
            st.rerun()

    # 3. LISTA I USUWANIE DNI
    if st.session_state.dni_wolne_lista:
        st.write("**Lista zaplanowanych wolnych:**")
        for i, d in enumerate(sorted(st.session_state.dni_wolne_lista)):
            col_date, col_btn = st.columns([3, 1])
            col_date.write(f"• {d.strftime('%d.%m.%Y')}")
            if col_btn.button("❌", key=f"del_{i}"):
                st.session_state.dni_wolne_lista.remove(d)
                st.rerun()
    
    ile_wolnych = len(st.session_state.dni_wolne_lista)
    st.write(f"**Suma dni wolnych: {ile_wolnych}**")

# --- WCZYTYWANIE PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV z bazą klientów", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA MATEMATYCZNE
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = dni_podstawa[typ_cyklu] - ile_wolnych
        total_wizyt_cel = len(df) * wizyty_na_klienta
        twoja_wydajnosc_suma = limit_dzienny * dni_robocze
        
        realizacja_procent = (twoja_wydajnosc_suma / total_wizyt_cel * 100) if total_wizyt_cel > 0 else 0
        wymagana_srednia = total_wizyt_cel / dni_robocze if dni_robocze > 0 else 0

        # --- GŁÓWNY DASHBOARD ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci", len(df))
        m2.metric("Dni netto", max(0, dni_robocze))
        m3.metric("Wizyty (Cel)", total_wizyt_cel)
        
        diff = round(realizacja_procent - 100, 1)
        m4.metric("Realizacja Planu", f"{round(realizacja_procent, 1)}%", delta=f"{diff}%")

        # --- WYKRES ---
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
                brakuje = int(total_wizyt_cel - twoja_wydajnosc_suma)
                st.error(f"Zabraknie Ci **{max(0, brakuje)}** wizyt.")
            else:
                zapas = int(twoja_wydajnosc_suma - total_wizyt_cel)
                st.success(f"Masz **{max(0, zapas)}** wizyt zapasu.")

        st.write("---")
        st.subheader("📍 Mapa (Podgląd)")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
        st_folium(m, width=1100, height=400)

    except Exception as e:
        st.error(f"Błąd: {e}")
