import streamlit as st
import pandas as pd

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

# WGRYWANIE PLIKU
uploaded_file = st.file_uploader("Wgraj plik CSV z Farmaprom", type=["csv"])

if uploaded_file:
    try:
        # Próba 1: Standardowe kodowanie
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8')
    except UnicodeDecodeError:
        # Próba 2: Polskie kodowanie (jeśli próba 1 zawiedzie)
        uploaded_file.seek(0) # wróć na początek pliku
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='cp1250')

    total_klientow = len(df)
    dni_robocze = 20 - len(dni_wolne)
    potrzebne_wizyty = total_klientow * wizyty_na_klienta
    
    mozliwe_wizyty = limit_dzienny * dni_robocze
    realizacja = (mozliwe_wizyty / potrzebne_wizyty) * 100 if potrzebne_wizyty > 0 else 0

    # GŁÓWNY PANEL STATYSTYK
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Dni robocze", f"{dni_robocze} dni")
    with col2:
        st.metric("Liczba klientów w pliku", total_klientow)
    with col3:
        st.metric("Realizacja Planu", f"{round(realizacja, 1)}%", delta=f"{round(realizacja-100, 1)}%")

    st.success("Plik wgrany poprawnie!")
    st.write("### Podgląd Twoich danych:")
    st.dataframe(df.head(10)) 
else:
    st.info("Wgraj plik CSV, aby zobaczyć statystyki cyklu.")
