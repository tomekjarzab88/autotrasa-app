import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AutoTrasa - Twój Planer Cyklu", layout="wide")

st.title("🚚 AutoTrasa / FromAtoB")
st.subheader("Automatyczne planowanie tras i cyklu wizyt")

# PANEL BOCZNY - USTAWIENIA
with st.sidebar:
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał", "Pół roku"])
    wizyty_na_klienta = st.number_input("Ilość wizyt u 1 klienta w cyklu", min_value=1, value=1)
    limit_dzienny = st.slider("Limit wizyt dziennie", 5, 20, 10)
    
    st.header("📅 Twoja dostępność")
    dni_wolne = st.date_input("Zaznacz dni wolne (Urlop, L4, Szkolenia)", [])

# GŁÓWNY PANEL
col1, col2, col3 = st.columns(3)

# Symulacja danych do licznika live (na razie na sztywno)
total_klientow = 120
dni_robocze = 20 - len(dni_wolne)
potrzebne_wizyty = total_klientow * wizyty_na_klienta
realizacja = (limit_dzienny * dni_robocze) / potrzebne_wizyty * 100

with col1:
    st.metric("Dni robocze", f"{dni_robocze} dni")
with col2:
    st.metric("Potrzebne wizyty", potrzebne_wizyty)
with col3:
    st.metric("Realizacja Planu", f"{round(realizacja, 1)}%", delta=f"{round(realizacja-100, 1)}%")

# WGRYWANIE PLIKU
uploaded_file = st.file_file_uploader("Wgraj plik CSV z Farmaprom", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.success("Plik wgrany poprawnie!")
    st.write("Podgląd Twoich aptek:")
    st.dataframe(df.head()) # Pokazuje pierwsze kilka wierszy
