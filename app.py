import streamlit as st
import pandas as pd
import chardet

st.set_page_config(page_title="AutoTrasa - Twój Planer Cyklu", layout="wide")

# --- STYLE WIZUALNE ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🚚 AutoTrasa / FromAtoB")
st.subheader("Automatyczne planowanie tras i cyklu wizyt")

# --- PANEL BOCZNY (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Ustawienia Cyklu")
    typ_cyklu = st.selectbox("Długość cyklu", ["Miesiąc", "2 Miesiące", "Kwartał", "Pół roku"])
    wizyty_na_klienta = st.number_input("Ilość wizyt u 1 klienta w cyklu", min_value=1, value=1)
    limit_dzienny = st.slider("Limit wizyt dziennie", 5, 25, 10)
    
    st.header("📅 Twoja dostępność")
    dni_wolne = st.date_input("Zaznacz dni wolne / szkolenia / L4", [])
    
    st.info("Podpowiedź: System automatycznie przeliczy trasę omijając te dni.")

# --- WGRYWANIE I ANALIZA PLIKU ---
uploaded_file = st.file_uploader("Wgraj plik CSV z Farmaprom", type=["csv"])

if uploaded_file:
    # Wykrywanie kodowania (to co zadziałało wcześniej)
    raw_data = uploaded_file.read()
    result = chardet.detect(raw_data)
    charenc = result['encoding']
    uploaded_file.seek(0)
    
    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        # OBLICZENIA BIZNESOWE
        total_klientow = len(df)
        
        # Przyjmujemy średnio 21 dni roboczych w miesiącu minus wybrane dni wolne
        dni_w_miesiacu = 21 
        if typ_cyklu == "2 Miesiące": dni_w_miesiacu = 42
        elif typ_cyklu == "Kwartał": dni_w_miesiacu = 63
        elif typ_cyklu == "Pół roku": dni_w_miesiacu = 126
        
        dni_robocze = dni_w_miesiacu - len(dni_wolne)
        potrzebne_wizyty = total_klientow * wizyty_na_klienta
        mozliwe_wizyty_suma = limit_dzienny * dni_robocze
        
        realizacja = (mozliwe_wizyty_suma / potrzebne_wizyty) * 100 if potrzebne_wizyty > 0 else 0

        # --- DASHBOARD STATYSTYK ---
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Liczba klientów", total_klientow)
        with col2:
            st.metric("Dni robocze", f"{dni_robocze}")
        with col3:
            st.metric("Suma wizyt", potrzebne_wizyty)
        with col4:
            color = "normal" if realizacja >= 100 else "inverse"
            st.metric("Realizacja Planu", f"{round(realizacja, 1)}%", delta=f"{round(realizacja-100, 1)}%", delta_color=color)

        if realizacja < 100:
            st.warning(f"⚠️ Przy tym limicie ({limit_dzienny}/dzień) nie zrealizujesz całego planu! Brakuje {potrzebne_wizyty - mozliwe_wizyty_suma} wizyt. Zwiększ limit lub ogranicz dni wolne.")
        else:
            st.success("✅ Świetnie! Twój plan mieści się w wyznaczonym czasie.")

        st.write("---")
        st.write("### 📋 Podgląd bazy do planowania:")
        st.dataframe(df.head(20))

    except Exception as e:
        st.error(f"Wystąpił problem z formatem danych: {e}")
else:
    st.info("👈 Skonfiguruj parametry w panelu bocznym i wgraj plik CSV, aby rozpocząć.")
