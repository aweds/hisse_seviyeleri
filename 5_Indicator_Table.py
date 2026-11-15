import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import stochastic_rsi
from levels import rsi

st.set_page_config(page_title="Gösterge Tablosu", page_icon="📋", layout="wide")
st.title("📋 Son 3 Günlük Gösterge Tablosu")
st.caption("Filtrelerinizi hızlıca taramak için RSI ve Stoch RSI değerlerinin son 3 günlük değişimi.")

# --- KENAR ÇUBUĞU AYARLARI ---
with st.sidebar:
    st.header("⚙️ Takip Listesi")
    
    varsayilan_liste = "PATEK, ARDYZ, THYAO, ASELS, TKFEN, EREGL, SISE, KCHOL, GARAN, AKBNK"
    hisse_listesi = st.text_area("Hisseleri Virgülle Ayırın", value=varsayilan_liste, height=200)
    
    st.markdown("---")
    st.markdown("**Gösterge Periyodu**")
    periyot = st.number_input("Periyot (Gün)", value=14, min_value=2, max_value=50)
    
    tara = st.button("🔄 Tabloyu Güncelle", type="primary", use_container_width=True)

# --- TABLO OLUŞTURMA ---
if tara:
    hisseler = [h.strip().upper() for h in hisse_listesi.split(",") if h.strip()]
    sonuclar = []
    
    progress = st.progress(0, text="Veriler çekiliyor...")
    
    for i, raw_ticker in enumerate(hisseler):
        ticker = normalize_ticker(raw_ticker)
        
        # Veriyi çek (Göstergelerin oturması için 3 aylık yeterli)
        df = fetch_ohlcv(ticker, interval="1d", period="3mo")
        
        if df.empty or len(df) < periyot + 5:
            continue
            
        # Göstergeleri hesapla
        df["RSI"] = rsi(df, periyot)
        df["Stoch_RSI"] = stochastic_rsi(df["Close"], periyot)
        
        # Son 3 günün verisini al
        son_3_gun = df.tail(3)
        
        if len(son_3_gun) == 3:
            rsi_vals = son_3_gun["RSI"].values
            stoch_vals = son_3_gun["Stoch_RSI"].values
            
            # Tarihleri al (T-2, T-1, Bugün)
            d_2 = son_3_gun.index[0].strftime("%d %b")
            d_1 = son_3_gun.index[1].strftime("%d %b")
            d_0 = son_3_gun.index[2].strftime("%d %b")
            
            sonuclar.append({
                "Hisse": ticker.replace(".IS", ""),
                f"RSI ({d_2})": round(rsi_vals[0], 1),
                f"RSI ({d_1})": round(rsi_vals[1], 1),
                f"RSI ({d_0})": round(rsi_vals[2], 1),
                f"Stoch ({d_2})": round(stoch_vals[0], 1),
                f"Stoch ({d_1})": round(stoch_vals[1], 1),
                f"Stoch ({d_0})": round(stoch_vals[2], 1),
            })
            
        progress.progress((i + 1) / len(hisseler), text=f"{ticker} işlendi...")
        
    progress.empty()
    
    if sonuclar:
        # DataFrame oluştur
        df_res = pd.DataFrame(sonuclar)
        
        # Hücre Renklendirme Fonksiyonu (Kesişimleri boyar)
        def highlight_crossover(row):
            styles = [''] * len(row)
            
            # RSI Sütunlarını al (3, 4, 5. indeksler)
            rsi_cols = [col for col in df_res.columns if "RSI (" in col and "Stoch" not in col]
            stoch_cols = [col for col in df_res.columns if "Stoch (" in col]
            
            # RSI Kesişim Kontrolü (Dün < 30, Bugün >= 30)
            if len(rsi_cols) == 3:
                if row[rsi_cols[1]] < 30 and row[rsi_cols[2]] >= 30:
                    styles[df_res.columns.get_loc(rsi_cols[2])] = 'background-color: #2e7d32; color: white; font-weight: bold'
                elif row[rsi_cols[1]] > 70 and row[rsi_cols[2]] <= 70:
                    styles[df_res.columns.get_loc(rsi_cols[2])] = 'background-color: #c62828; color: white; font-weight: bold'
                    
            # Stoch RSI Kesişim Kontrolü (Dün < 30, Bugün >= 30)
            if len(stoch_cols) == 3:
                if row[stoch_cols[1]] < 30 and row[stoch_cols[2]] >= 30:
                    styles[df_res.columns.get_loc(stoch_cols[2])] = 'background-color: #2e7d32; color: white; font-weight: bold'
                elif row[stoch_cols[1]] > 70 and row[stoch_cols[2]] <= 70:
                    styles[df_res.columns.get_loc(stoch_cols[2])] = 'background-color: #c62828; color: white; font-weight: bold'
                    
            return styles

        st.subheader("📊 Gösterge Değerleri")
        st.info("💡 **Yeşil Hücreler:** Aşırı satımdan (30) yukarı dönüşü (AL sinyali) gösterir. **Kırmızı Hücreler:** Aşırı alımdan (70) aşağı dönüşü (SAT sinyali) gösterir.")
        
        # Tabloyu stillendirerek göster
        st.dataframe(
            df_res.style.apply(highlight_crossover, axis=1),
            use_container_width=True,
            hide_index=True
        )
        
        # İndirme butonu
        csv = df_res.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            "⬇️ Tabloyu CSV Olarak İndir",
            data=csv,
            file_name="gosterge_tablosu.csv",
            mime="text/csv"
        )
    else:
        st.warning("Veri çekilemedi veya hisse listesi boş.")
