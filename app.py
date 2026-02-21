import streamlit as st
import pandas as pd
import chardet
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="AutoTrasa - Twój Planer Cyklu", layout="wide")

st.title("🚚 AutoTrasa / FromAtoB")

# --- DZISIEJSZA DATA ---
dzis = datetime.now().strftime("%d.%m.%Y")
st.info(f"📅 Dzisiaj jest: **{dzis}**")

# --- PANEL BOCZNY ---
with st.sidebar:
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał"])
    wizyty_na_klienta = st.number_input("Wizyty u 1 klienta", min_value=1, value=1)
    
    st.header("📅 Twoja dostępność")
    dni_wolne = st.date_input("Zaznacz dni wolne/L4/Urlop", [])

# --- WCZYTYWANIE ---
uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"])

if uploaded_file:
    raw_data = uploaded_file.read()
    charenc = chardet.detect(raw_data)['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        total_klientow = len(df)
        
        # Logika dni roboczych
        dni_podstawa = {"Miesiąc": 21, "2 Miesiące": 42, "Kwartał": 63}
        dni_robocze = dni_podstawa[typ_cyklu] - len(dni_wolne)
        
        suma_wizyt = total_klientow * wizyty_na_klienta
        # OBLICZANIE ŚREDNIEJ
        srednia_dzienna = suma_wizyt / dni_robocze if dni_robocze > 0 else 0

        # --- DASHBOARD ---
        c1, c2, c3 = st.columns([1, 1, 2])
        
        with c1:
            st.metric("Klienci w bazie", total_klientow)
            st.metric("Pozostałe dni robocze", dni_robocze)
            
        with c2:
            st.metric("Wszystkie wizyty", suma_wizyt)
            st.metric("Średnia wizyt / dzień", round(srednia_dzienna, 1))

        with c3:
            # WYKRES LICZNIKA (GAUGE)
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = srednia_dzienna,
                title = {'text': "Wymagana średnia dzienna"},
                gauge = {
                    'axis': {'range': [None, 25]},
                    'bar': {'color': "#0083B8"},
                    'steps': [
                        {'range': [0, 8], 'color': "#e8f5e9"},
                        {'range': [8, 12], 'color': "#fff3e0"},
                        {'range': [12, 25], 'color': "#ffebee"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 15 # Próg ostrzegawczy
                    }
                }
            ))
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        st.write("### 📋 Podgląd danych")
        st.dataframe(df.head(10))

    except Exception as e:
        st.error(f"Błąd: {e}")
