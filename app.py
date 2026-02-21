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

# FUNKCJA BEZPIECZNEGO WCZYTYWANIA
def load_data(file):
    encodings = ['utf-8', 'cp1250', 'iso-8859-2', 'latin1']
    for enc in encodings:
        try:
            file.seek(0)
            return pd.read_csv(file, sep=None, engine='python', encoding=enc)
        except Exception:
            continue
    return None

# WGRYWANIE PLIKU
uploaded_file = st.file_uploader("Wgraj plik CSV z Farmaprom", type=["csv"])

if uploaded_file:
    df = load_data(uploaded_file)
    
    if df is not None:
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
        st.error("Nie udało się odczytać pliku. Sprawdź, czy format CSV jest poprawny.")
else:
    st.info("Wgraj plik CSV, aby zobaczyć statystyki cyklu.")
