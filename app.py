import streamlit as st
import pandas as pd
import chardet

st.set_page_config(page_title="AutoTrasa", layout="wide")

st.title("🚚 AutoTrasa / FromAtoB")

uploaded_file = st.file_uploader("Wgraj plik CSV", type=["csv"])

if uploaded_file:
    # 1. Automatyczne wykrywanie kodowania
    raw_data = uploaded_file.read()
    result = chardet.detect(raw_data)
    charenc = result['encoding']
    
    st.write(f"Wykryte kodowanie pliku: **{charenc}**")
    
    try:
        # 2. Próba wczytania z wykrytym kodowaniem
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding=charenc)
        
        st.success("Sukces! Dane wczytane.")
        st.metric("Liczba klientów", len(df))
        st.dataframe(df.head())
        
    except Exception as e:
        st.error(f"Nadal występuje błąd. Szczegóły: {e}")
        # Ostatnia deska ratunku - wczytanie "na siłę" ignorując błędy znaków
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8', errors='replace')
        st.warning("Wczytano dane w trybie awaryjnym (polskie znaki mogą być zniekształcone).")
        st.dataframe(df.head())
else:
    st.info("Czekam na plik...")
