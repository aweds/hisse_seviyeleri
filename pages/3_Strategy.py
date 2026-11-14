import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import kama, stochastic_rsi, wilders_smoothing
from levels import rsi

st.set_page_config(page_title="Strateji Testi", page_icon="🧪", layout="wide")
st.title("🧪 Bilimsel Strateji Backtest")
st.caption("Stoch RSI + KAMA + Wilders + Stop-Loss & Kâr Al")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Strateji Ayarları")
    raw = st.text_input("Hisse", "PATEK")
    period = st.selectbox("Test Periyodu", ["1y", "2y", "5y"], index=1)
    
    st.markdown("---")
    
    gosterge_secimi = st.radio("Kullanılacak Gösterge", ["RSI", "Stoch RSI"])
    
    st.markdown("**1. Gösterge Kuralı**")
    varsayilan_esik = 30 if gosterge_secimi == "RSI" else 20
    esik = st.number_input("Aşırı Satım Eşiği (Altı)", value=varsayilan_esik)
    ind_length = st.number_input("Gösterge Periyodu", value=14)
    
    st.markdown("**2. Filtreler**")
    use_kama = st.checkbox("Fiyat KAMA'nın üzerinde olsun", value=True)
    kama_length = st.number_input("KAMA Periyodu", value=10, disabled=not use_kama)
    
    use_wilders = st.checkbox("Fiyat Wilders'ın üzerinde olsun", value=True)
    wilders_length = st.number_input("Wilders Periyodu", value=14, disabled=not use_wilders)
    
    st.markdown("---")
    st.markdown("**3. Risk Yönetimi (Çıkış Stratejisi)**")
    hold_days = st.number_input("Kaç gün sonra satılsın? (Maksimum)", value=10)
    stop_loss_pct = st.number_input("Zarar Durdur (Stop-Loss) %", value=5.0, step=1.0)
    take_profit_pct = st.number_input("Kâr Al (Take-Profit) %", value=10.0, step=1.0)
    
    run = st.button("▶️ Stratejiyi Test Et", type="primary", use_container_width=True)

ticker = normalize_ticker(raw)

# --- HESAPLAMA KISMI ---
if run:
    df = fetch_ohlcv(ticker, interval="1d", period=period)
    if df.empty or len(df) < 100:
        st.error("Yetersiz veri.")
        st.stop()
        
    df["RSI"] = rsi(df, ind_length)
    df["KAMA"] = kama(df["Close"], kama_length)
    df["Wilders"] = wilders_smoothing(df["Close"], wilders_length)
    df["Stoch_RSI"] = stochastic_rsi(df["Close"], ind_length)
    
    if gosterge_secimi == "RSI":
        current_ind = df["RSI"]
    else:
        current_ind = df["Stoch_RSI"]
        
    base_signal = (current_ind.shift(1) < esik) & (current_ind >= esik)
    
    kama_condition = df["Close"] > df["KAMA"] if use_kama else pd.Series(True, index=df.index)
    wilders_condition = df["Close"] > df["Wilders"] if use_wilders else pd.Series(True, index=df.index)
        
    df["Signal"] = base_signal & kama_condition & wilders_condition
    
    signals = df[df["Signal"]].index
    
    if len(signals) == 0:
        st.warning("Seçilen kriterlere uyan hiçbir alım sinyali bulunamadı.")
        st.stop()
        
    results = []
    for sig_date in signals:
        idx = df.index.get_loc(sig_date)
        if idx + hold_days < len(df):
            entry_price = df["Close"].iloc[idx]
            
            # Hedef ve Stop Fiyatlarını Hesapla
            stop_price = entry_price * (1 - stop_loss_pct / 100)
            target_price = entry_price * (1 + take_profit_pct / 100)
            
            exit_price = df["Close"].iloc[idx + hold_days]
            exit_reason = "Süre Doldu"
            days_held = hold_days
            
            # Gün gün ilerleyip Stop veya Target'a değdi mi kontrol et
            for i in range(1, hold_days + 1):
                low_price = df["Low"].iloc[idx + i]
                high_price = df["High"].iloc[idx + i]
                
                if low_price <= stop_price:
                    exit_price = stop_price
                    exit_reason = "Stop-Loss"
                    days_held = i
                    break
                elif high_price >= target_price:
                    exit_price = target_price
                    exit_reason = "Kâr Al"
                    days_held = i
                    break
            
            getiri = (exit_price - entry_price) / entry_price * 100
            
            results.append({
                "Tarih": sig_date.strftime("%Y-%m-%d"),
                "Giriş Fiyatı": round(entry_price, 2),
                "Çıkış Fiyatı": round(exit_price, 2),
                "Çıkış Nedeni": exit_reason,
                "Gün": days_held,
                "Getiri (%)": round(getiri, 2),
                "Başarılı mı?": "Evet" if getiri > 0 else "Hayır"
            })
            
    res_df = pd.DataFrame(results)
    
    if res_df.empty:
        st.warning("Sinyal bulundu ama test edilecek kadar ilerisi yok (veri sonu).")
        st.stop()
        
    st.session_state["bt_res_df"] = res_df
    st.session_state["bt_ticker"] = ticker
    st.session_state["bt_ind_name"] = gosterge_secimi

# --- EKRANA ÇİZİM KISMI ---
if "bt_res_df" in st.session_state:
    res_df = st.session_state["bt_res_df"]
    ticker = st.session_state["bt_ticker"]
    ind_name = st.session_state["bt_ind_name"]
    
    win_rate = (res_df["Getiri (%)"] > 0).mean() * 100
    avg_return = res_df["Getiri (%)"].mean()
    
    st.subheader(f"📌 {ticker} — {ind_name} Strateji Sonuçları")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Sinyal", len(res_df))
    c2.metric("Başarı Oranı (Win Rate)", f"%{win_rate:.1f}")
    c3.metric("Ort. Getiri", f"%{avg_return:.2f}")
    
    st.markdown("#### Detaylı İşlem Geçmişi")
    
    # Renklendirme tamamen kaldırıldı, hata vermez.
    st.dataframe(
        res_df, 
        use_container_width=True, 
        hide_index=True
    )
    
    fig = px.histogram(
        res_df, x="Getiri (%)", nbins=20, 
        title="İşlem Başına Getiri Dağılımı",
        color="Başarılı mı?", color_discrete_map={"Evet": "#2e7d32", "Hayır": "#c62828"}
    )
    st.plotly_chart(fig, use_container_width=True)
