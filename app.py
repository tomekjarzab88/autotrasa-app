import streamlit as st
import pandas as pd
import chardet
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="AutoTrasa - Kompletny Planer", layout="wide")

# --- FUNKCJA INTELIGENTNEGO SZUKANIA KOLUMN ---
def find_column(columns, patterns):
    for pattern in patterns:
        for col in columns:
            clean_col = col.lower().strip()
            # Usuwanie polskich znaków do porównania
            clean_col = clean_col.replace('ą','a').replace('ę','e').replace('ś','s').replace('ć','c').replace('ó','o').replace('ń','n').replace('ł','l').replace('ź','z').replace('ż','z')
            if pattern in clean_col:
                return col
    return None

st.title("🚚 AutoTrasa / FromAtoB")

# --- KONTEKST CZASOWY ---
dzis = datetime.now().date()
st.info(f"📅 Dzisiaj jest: **{dzis.strftime('%d.%m.%Y')}**")

# --- PANEL BOCZNY (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    
    st.header("📅 Twoja dostępność")
    dni_wolne = st.date_input("Zaznacz dni wolne/szkolenia", value=[], min_value=dzis)
    st.caption("Kliknij datę, aby dodać ją do listy dni wolnych.")

# --- WCZYTYWANIE PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV (np. export z Farmaprom)", type=["csv"])

if uploaded_file:
    # Wykrywanie kodowania
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # 1. Automatyczne rozpoznawanie kolumn
        col_miasto = find_column(df.columns, ['miasto', 'miejscowosc', 'city', 'town'])
        col_ulica = find_column(df.columns, ['ulica', 'adres', 'street', 'addr', 'ul.'])
        col_id = find_column(df.columns, ['akronim', 'id', 'nazwa', 'kod'])

        # 2. Obliczenia Biznesowe
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = dni_podstawa[typ_cyklu] - len(dni_wolne)
        total_wizyt = len(df) * wizyty_na_klienta
        srednia_dzienna = total_wizyt / dni_robocze if dni_robocze > 0 else 0

        # --- 📊 DASHBOARD STATYSTYK ---
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.metric("Klienci w bazie", len(df))
            st.metric("Dni robocze", dni_robocze)
        with c2:
            st.metric("Suma wizyt", total_wizyt)
            st.metric("Średnia / dzień", round(srednia_dzienna, 1))
        with c3:
            # Wykres Gauge (Licznik)
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = srednia_dzienna,
                title = {'text': "Wymagana średnia dzienna"},
                gauge = {
                    'axis': {'range': [None, 25]},
                    'bar': {'color': "#0083B8"},
                    'steps': [
                        {'range': [0, 10], 'color': "#e8f5e9"},
                        {'range': [10, 15], 'color': "#fff3e0"},
                        {'range': [15, 25], 'color': "#ffebee"}
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 18}
                }
            ))
            fig.update_layout(height=230, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        # --- 🔍 ANALIZA ADRESÓW ---
        st.write("---")
        st.subheader("🔍 Analiza struktury pliku")
        
        if col_miasto and col_ulica:
            st.success(f"✅ Rozpoznano adresy: **{col_ulica}** w mieście **{col_miasto}**.")
            
            # Tworzenie pełnego adresu do geolokalizacji
            df['full_address'] = df[col_ulica].astype(str) + ", " + df[col_miasto].astype(str) + ", Polska"
            
            # SEKCJA MAPY (PRZYGOTOWANIE)
            if st.button("🚀 GENERUJ TRASY I MAPĘ"):
                st.write("Łączenie z bazą współrzędnych...")
                st.dataframe(df[[col_id, 'full_address']].head(10))
                st.info("W następnym kroku dodamy wyświetlanie kropek na mapie Polski!")
        else:
            st.error("❌ Nie udało się automatycznie rozpoznać kolumn z adresem (Miasto/Ulica).")

        st.write("### 📋 Podgląd danych wejściowych")
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Coś poszło nie tak: {e}")
