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
    wizyty_wykonane = st.number_input("Ile wizyt już ZROBIONO?", min_value=0, value=0)
    
    st.write("---")
    st.header("📅 Nieobecności")
    
    # KALENDARZ ZAKRESOWY (można zaznaczyć wiele dni)
    wybrane_w_kalendarzu = st.date_input(
        "Zaznacz dni lub zakresy:",
        value=[],
        min_value=date(2025, 1, 1)
    )
    
    if st.button("➕ Dodaj zaznaczone do listy"):
        if isinstance(wybrane_w_kalendarzu, list):
            for d in wybrane_w_kalendarzu:
                if d not in st.session_state.dni_wolne_lista:
                    st.session_state.dni_wolne_lista.append(d)
        elif wybrane_w_kalendarzu:
            if wybrane_w_kalendarzu not in st.session_state.dni_wolne_lista:
                st.session_state.dni_wolne_lista.append(wybrane_w_kalendarzu)
        st.rerun()

    # LISTA ZARZĄDZALNA
    if st.session_state.dni_wolne_lista:
        st.write("**Lista wolnych dni:**")
        for i, d in enumerate(sorted(st.session_state.dni_wolne_lista)):
            col_d, col_b = st.columns([3, 1])
            col_d.write(f"• {d.strftime('%d.%m')}")
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
        
        # OBLICZENIA Z UWZGLĘDNIENIEM POSTĘPU
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = max(0, dni_podstawa[typ_cyklu] - ile_wolnych)
        
        total_wizyt_cel = len(df) * wizyty_na_klienta
        do_zrobienia = max(0, total_wizyt_cel - wizyty_wykonane)
        
        wydajnosc_pozostala = limit_dzienny * dni_robocze
        realizacja = (wydajnosc_pozostala / do_zrobienia * 100) if do_zrobienia > 0 else 100
        wymagana_srednia = do_zrobienia / dni_robocze if dni_robocze > 0 else 0

        # --- DASHBOARD ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Klienci", len(df))
        m2.metric("Pozostałe dni robocze", dni_robocze)
        m3.metric("Pozostało wizyt", do_zrobienia)
        
        procent_ukonczenia = (wizyty_wykonane / total_wizyt_cel * 100) if total_wizyt_cel > 0 else 0
        m4.metric("Zaawansowanie cyklu", f"{round(procent_ukonczenia, 1)}%")

        # --- ANALIZA ---
        c_left, c_right = st.columns([2, 1])
        with c_left:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = wymagana_srednia,
                title = {'text': "Wymagana średnia (na pozostałe dni)"},
                gauge = {
                    'axis': {'range': [None, 30]},
                    'bar': {'color': "#FF4B4B" if wymagana_srednia > limit_dzienny else "#0083B8"},
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': limit_dzienny}
                }
            ))
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        
        with c_right:
            st.write("### 📝 Status operacyjny")
            if wymagana_srednia > limit_dzienny:
                st.error(f"Musisz zwiększyć limit do **{round(wymagana_srednia, 1)}**, żeby zdążyć.")
            else:
                zapas = int(wydajnosc_suma - do_zrobienia) if 'wydajnosc_suma' in locals() else 0
                st.success("Twój limit dzienny jest wystarczający.")
            
            st.info(f"Suma wizyt w całym cyklu: {total_wizyt_cel}")

        st.write("---")
        st.subheader("📍 Mapa i Dane")
        m = folium.Map(location=[52.0688, 19.4797], zoom_start=6)
        st_folium(m, width=1100, height=400)
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Błąd: {e}")
