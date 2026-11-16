import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import (
    stochastic_rsi, macd, fisher_transform, connors_rsi, 
    calculate_adx, mass_index, coppock_curve, alma, bollinger_bands
)
from levels import rsi

st.set_page_config(page_title="Gösterge Tablosu", page_icon="📋", layout="wide")
st.title("📋 Son 3 Günlük Gösterge Tablosu")
st.caption("Filtrelerinizi hızlıca taramak için göstergelerin son 3 günlük değişimini inceleyin.")

# --- KENAR ÇUBUĞU AYARLARI ---
with st.sidebar:
    st.header("⚙️ Tablo Ayarları")
    
    varsayilan_liste = "PATEK, ARDYZ, THYAO, ASELS, TKFEN, EREGL, SISE, KCHOL, GARAN, AKBNK"
    hisse_listesi = st.text_area("Hisseleri Virgülle Ayırın", value=varsayilan_liste, height=150)
    
    st.markdown("---")
    
    # Hangi göstergeleri görmek istiyor?
    secilen_gostergeler = st.multiselect(
        "Görüntülenecek Göstergeler",
        options=["RSI", "Stoch RSI", "MACD", "Fisher Transform", "Connors RSI", "ADX", "Mass Index"],
        default=["RSI", "Stoch RSI"]
    )
    
    st.markdown("**Sinyal Eşiği**")
    esik_degeri = st.number_input("Aşırı Satım/Çıkış Eşiği", value=30, min_value=-100, max_value=100, help="MACD veya Fisher için 0, RSI için 30 girin.")
    
    st.markdown("**Gösterge Periyodu**")
    periyot = st.number_input("Periyot (Gün)", value=14, min_value=2, max_value=50)
    
    tara = st.button("🔄 Tabloyu Güncelle", type="primary", use_container_width=True)

# --- TABLO OLUŞTURMA ---
if tara:
    if not secilen_gostergeler:
        st.warning("Lütfen en az bir gösterge seçin.")
        st.stop()
        
    hisseler = [h.strip().upper() for h in hisse_listesi.split(",") if h.strip()]
    sonuclar = []
    
    progress = st.progress(0, text="Veriler çekiliyor ve göstergeler hesaplanıyor...")
    
    for i, raw_ticker in enumerate(hisseler):
        ticker = normalize_ticker(raw_ticker)
        
        # Göstergelerin oturması için 1 yıllık veri çekiyoruz (özellikle CRSI ve Mass için)
        df = fetch_ohlcv(ticker, interval="1d", period="1y")
        
        if df.empty or len(df) < 60:
            continue
            
        # Seçilen göstergeleri hesapla
        if "RSI" in secilen_gostergeler:
            df["RSI"] = rsi(df, periyot)
        if "Stoch RSI" in secilen_gostergeler:
            df["Stoch RSI"] = stochastic_rsi(df["Close"], periyot)
        if "MACD" in secilen_gostergeler:
            df["MACD"], df["MACD_Signal"] = macd(df["Close"])
        if "Fisher Transform" in secilen_gostergeler:
            df["Fisher Transform"], df["Fisher_Signal"] = fisher_transform(df, periyot)
        if "Connors RSI" in secilen_gostergeler:
            df["Connors RSI"] = connors_rsi(df["Close"], rsi_length=3)
        if "ADX" in secilen_gostergeler:
            df["ADX"], _, _ = calculate_adx(df, periyot)
        if "Mass Index" in secilen_gostergeler:
            df["Mass Index"] = mass_index(df)
            
        # Son 3 günün verisini al
        son_3_gun = df.tail(3).copy()
        
        # NaN değerleri temizle (Göstergelerin hesaplanamadığı ilk günler)
        son_3_gun = son_3_gun.dropna(subset=secilen_gostergeler)
        
        if len(son_3_gun) == 3:
            # Tarihleri al (T-2, T-1, Bugün)
            d_2 = son_3_gun.index[0].strftime("%d %b")
            d_1 = son_3_gun.index[1].strftime("%d %b")
            d_0 = son_3_gun.index[2].strftime("%d %b")
            
            row = {"Hisse": ticker.replace(".IS", "")}
            
            for g in secilen_gostergeler:
                row[f"{g} ({d_2})"] = round(son_3_gun[g].iloc[0], 2)
                row[f"{g} ({d_1})"] = round(son_3_gun[g].iloc[1], 2)
                row[f"{g} ({d_0})"] = round(son_3_gun[g].iloc[2], 2)
                
            sonuclar.append(row)
            
        progress.progress((i + 1) / len(hisseler), text=f"{ticker} işlendi...")
        
    progress.empty()
    
    if sonuclar:
        df_res = pd.DataFrame(sonuclar)
        
        # Hücre Renklendirme Fonksiyonu (Kesişimleri boyar)
        def highlight_crossover(row):
            styles = [''] * len(row)
            
            for g in secilen_gostergeler:
                cols = [f"{g} ({d})" for d in [df_res.columns[1][-6:], df_res.columns[2][-6:], df_res.columns[3][-6:]]]
                # Dinamik sütun isimlerini bul (Tarihler değişebilir)
                g_cols = [c for c in df_res.columns if c.startswith(f"{g} (")]
                
                if len(g_cols) == 3:
                    dun = row[g_cols[1]]
                    bugun = row[g_cols[2]]
                    
                    # AL Sinyali (Dün eşiğin altında, bugün üstüne çıktı)
                    if dun < esik_degeri and bugun >= esik_degeri:
                        styles[df_res.columns.get_loc(g_cols[2])] = 'background-color: #2e7d32; color: white; font-weight: bold'
                    # SAT Sinyali (Dün üst sınırın üstünde, bugün altına indi)
                    elif dun > (100 - esik_degeri) and bugun <= (100 - esik_degeri):
                        styles[df_res.columns.get_loc(g_cols[2])] = 'background-color: #c62828; color: white; font-weight: bold'
                        
            return styles

        st.subheader("📊 Gösterge Değerleri")
        st.info(f"💡 **Yeşil Hücreler:** {esik_degeri} seviyesinden yukarı dönüşü (AL) gösterir. **Kırmızı Hücreler:** {100 - esik_degeri} seviyesinden aşağı dönüşü (SAT) gösterir.")
        
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
        st.warning("Veri çekilemedi veya hisse listesi boş. Lütfen hisse kodlarını kontrol edin.")
