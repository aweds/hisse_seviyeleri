import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import kama, stochastic_rsi
from levels import rsi

st.set_page_config(page_title="Strateji Testi", page_icon="🧪", layout="wide")
st.title("🧪 Bilimsel Strateji Backtest")
st.caption("RSI / Stoch RSI Aşırı Satım Dönüşü + KAMA Filtresi stratejisinin geçmiş performansı")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Strateji Ayarları")
    raw = st.text_input("Hisse", "PATEK")
    period = st.selectbox("Test Periyodu", ["1y", "2y", "5y"], index=1)
    
    st.markdown("---")
    
    # Gösterge Seçimi Sidebar'a taşındı
    gosterge_secimi = st.radio("Kullanılacak Gösterge", ["RSI", "Stoch RSI"])
    
    st.markdown("**1. Gösterge Kuralı**")
    # Eşik değerini seçime göre otomatik ayarla (RSI için 30, Stoch için 20)
    varsayilan_esik = 30 if gosterge_secimi == "RSI" else 20
    esik = st.number_input("Aşırı Satım Eşiği (Altı)", value=varsayilan_esik)
    
    ind_length = st.number_input("İndikatör Periyodu", value=14)
    
    st.markdown("**2. KAMA Kuralı**")
    kama_length = st.number_input("KAMA Periyodu", value=10)
    
    st.markdown("**3. Hedef**")
    hold_days = st.number_input("Kaç gün sonra satılsın?", value=10)
    
    run = st.button("▶️ Stratejiyi Test Et", type="primary", use_container_width=True)

ticker = normalize_ticker(raw)

# --- HESAPLAMA KISMI ---
if run:
    df = fetch_ohlcv(ticker, interval="1d", period=period)
    if df.empty or len(df) < 100:
        st.error("Yetersiz veri.")
        st.stop()
        
    # Göstergeleri hesapla
    df["RSI"] = rsi(df, ind_length)
    df["KAMA"] = kama(df["Close"], kama_length)
    df["Stoch_RSI"] = stochastic_rsi(df["Close"], ind_length)
    
    if gosterge_secimi == "RSI":
        current_ind = df["RSI"]
    else:
        current_ind = df["Stoch_RSI"]
        
    # Sinyal Mantığı
    df["Signal"] = (
        (current_ind.shift(1) < esik) & 
        (current_ind >= esik) & 
        (df["Close"] > df["KAMA"])
    )
    
    signals = df[df["Signal"]].index
    
    if len(signals) == 0:
        st.warning("Seçilen kriterlere uyan hiçbir alım sinyali bulunamadı. Eşik değerlerini düşürmeyi deneyin.")
        st.stop()
        
    # Sonuçları hesapla
    results = []
    for sig_date in signals:
        idx = df.index.get_loc(sig_date)
        if idx + hold_days < len(df):
            entry_price = df["Close"].iloc[idx]
            exit_price = df["Close"].iloc[idx + hold_days]
            getiri = (exit_price - entry_price) / entry_price * 100
            
            results.append({
                "Tarih": sig_date.strftime("%Y-%m-%d"),
                "Giriş Fiyatı": round(entry_price, 2),
                f"{hold_days} Gün Sonraki Fiyat": round(exit_price, 2),
                "Getiri (%)": round(getiri, 2),
                "Başarılı mı?": "Evet" if getiri > 0 else "Hayır"
            })
            
    res_df = pd.DataFrame(results)
    
    if res_df.empty:
        st.warning("Sinyal bulundu ama test edilecek kadar ilerisi yok (veri sonu).")
        st.stop()
        
    # Sonuçları hafızaya (session_state) kaydet
    st.session_state["bt_res_df"] = res_df
    st.session_state["bt_ticker"] = ticker
    st.session_state["bt_hold_days"] = hold_days
    st.session_state["bt_ind_name"] = gosterge_secimi

# --- EKRANA ÇİZİM KISMI (Hafızadaki veriyi okur) ---
if "bt_res_df" in st.session_state:
    res_df = st.session_state["bt_res_df"]
    ticker = st.session_state["bt_ticker"]
    hold_days = st.session_state["bt_hold_days"]
    ind_name = st.session_state["bt_ind_name"]
    
    # Sonuç Metrikleri
    win_rate = (res_df["Getiri (%)"] > 0).mean() * 100
    avg_return = res_df["Getiri (%)"].mean()
    
    st.subheader(f"📌 {ticker} — {ind_name} Strateji Sonuçları")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Sinyal", len(res_df))
    c2.metric("Başarı Oranı (Win Rate)", f"%{win_rate:.1f}")
    c3.metric(f"Ort. Getiri ({hold_days} Gün)", f"%{avg_return:.2f}")
    
    st.markdown("#### Detaylı İşlem Geçmişi")
    st.dataframe(res_df, use_container_width=True, hide_index=True)
    
    # Grafik
    fig = px.histogram(
        res_df, x="Getiri (%)", nbins=20, 
        title="İşlem Başına Getiri Dağılımı",
        color="Başarılı mı?", color_discrete_map={"Evet": "#2e7d32", "Hayır": "#c62828"}
    )
    st.plotly_chart(fig, use_container_width=True)

    # Bilgi Notu
    st.info("💡 **Not:** Bu tablo, seçtiğiniz gösterge ve ayarlarla geçmişte üretilen **tüm sinyalleri** gösterir. Yüzde 100 doğruluk yoktur, amaç stratejinin geçmişteki istatistiğini görmektir.")
