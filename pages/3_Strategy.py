import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import (
    kama, stochastic_rsi, wilders_smoothing, macd, ema, 
    bollinger_bands, calculate_adx, calculate_vwap, calculate_obv, calculate_supertrend,
    alma, fisher_transform, connors_rsi, coppock_curve, mass_index
)
from levels import rsi

st.set_page_config(page_title="Strateji Testi", page_icon="🧪", layout="wide")
st.title("🧪 Bilimsel Strateji Backtest")
st.caption("Tüm Profesyonel İndikatörler ve Zaman Dilimi Seçenekleri")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Strateji Ayarları")
    raw = st.text_input("Hisse", "ARDYZ")
    
    # ZAMAN DİLİMİ SEÇİMİ
    zaman_dilimi = st.selectbox("Zaman Dilimi (Periyot)", ["Günlük (1d)", "Saatlik (1h)", "15 Dakika (15m)"], index=0)
    
    # Veri periyodunu zaman dilimine göre otomatik ayarla
    if zaman_dilimi == "Günlük (1d)":
        interval, period = "1d", "2y"
    elif zaman_dilimi == "Saatlik (1h)":
        interval, period = "1h", "1y"
    else:
        interval, period = "15m", "60d" # Yahoo Finance 15m için max 60 gün verir

    st.markdown("---")
    gosterge_secimi = st.radio("Ana Gösterge", ["RSI", "Stoch RSI"])
    varsayilan_esik = 30
    esik = st.number_input("Aşırı Satım Eşiği (Altı)", value=varsayilan_esik)
    ind_length = st.number_input("Gösterge Periyodu (Bar)", value=14)
    
    st.markdown("**Trend Filtreleri**")
    use_kama = st.checkbox("Fiyat > KAMA (10)", value=True)
    use_wilders = st.checkbox("Fiyat > Wilders (14)", value=False)
    use_ema50 = st.checkbox("Fiyat > EMA 50", value=False)
    use_alma = st.checkbox("Fiyat > ALMA (10)", value=False)
    use_supertrend = st.checkbox("Supertrend Yönü = Al", value=False)
    use_coppock = st.checkbox("Coppock Curve > 0", value=False)
    
    st.markdown("**Momentum Filtreleri**")
    use_stoch_below_rsi = st.checkbox("Stoch RSI < RSI", value=True)
    use_macd = st.checkbox("MACD > Sinyal Çizgisi", value=False)
    use_fisher = st.checkbox("Fisher > Sinyal Çizgisi", value=False)
    use_crsi = st.checkbox("Connors RSI < 20", value=False)
    
    st.markdown("**Hacim & Volatilite Filtreleri**")
    use_volume = st.checkbox("Hacim > Ortalama Hacim (20 Bar)", value=False)
    use_vwap = st.checkbox("Fiyat > VWAP", value=False)
    use_obv = st.checkbox("OBV > 20 Barlık Ortalaması", value=False)
    use_bollinger = st.checkbox("Fiyat > Bollinger Orta Bandı", value=False)
    use_adx = st.checkbox("ADX > 25 (Güçlü Trend)", value=False)
    use_mass = st.checkbox("Mass Index < 27 (Sıkışma)", value=False)
    
    st.markdown("---")
    st.markdown("**💰 Sermaye ve Risk**")
    baslangic_sermayesi = st.number_input("Başlangıç Sermayesi (TL)", value=18000, step=1000)
    komisyon_pct = st.number_input("Komisyon Oranı (Tek Yön) %", value=0.0, step=0.1)
    
    st.markdown("**Çıkış Stratejisi**")
    hold_days = st.number_input("Maksimum Bar (Gün/Saat/Dk)", value=15, help="Seçilen zaman dilimine göre kaç bar sonra çıkılacağını belirler.")
    stop_loss_pct = st.number_input("Zarar Durdur (Stop-Loss) %", value=10.0, step=1.0)
    take_profit_pct = st.number_input("Kâr Al (Take-Profit) %", value=25.0, step=1.0)
    
    run = st.button("▶️ Stratejiyi Test Et", type="primary", use_container_width=True)

ticker = normalize_ticker(raw)

# --- HESAPLAMA KISMI ---
if run:
    df = fetch_ohlcv(ticker, interval=interval, period=period)
    
    if df.empty or len(df) < 100:
        st.error(f"Yetersiz veri. {zaman_dilimi} için en az 100 bar gerekiyor. Lütfen daha uzun bir periyot seçin.")
        st.stop()
        
    # Tüm İndikatörleri Hesapla
    df["RSI"] = rsi(df, ind_length)
    df["KAMA"] = kama(df["Close"], 10)
    df["Wilders"] = wilders_smoothing(df["Close"], 14)
    df["Stoch_RSI"] = stochastic_rsi(df["Close"], ind_length)
    df["EMA50"] = ema(df["Close"], 50)
    df["MACD"], df["MACD_Signal"] = macd(df["Close"])
    df["Vol_SMA"] = df["Volume"].rolling(20).mean()
    
    df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = bollinger_bands(df["Close"])
    df["ADX"], df["+DI"], df["-DI"] = calculate_adx(df)
    df["VWAP"] = calculate_vwap(df)
    df["OBV"] = calculate_obv(df)
    df["Supertrend"], df["ST_Direction"] = calculate_supertrend(df)
    
    # Yeni İndikatörler
    df["ALMA"] = alma(df["Close"], 10)
    df["Fisher"], df["Fisher_Signal"] = fisher_transform(df)
    df["CRSI"] = connors_rsi(df["Close"])
    df["Coppock"] = coppock_curve(df["Close"])
    df["Mass_Index"] = mass_index(df)
    
    # Sinyal Mantığı
    current_ind = df["RSI"] if gosterge_secimi == "RSI" else df["Stoch_RSI"]
    base_signal = (current_ind.shift(1) < esik) & (current_ind >= esik)
    
    # Filtre Şartları
    kama_cond = (df["Close"] > df["KAMA"]) if use_kama else pd.Series(True, index=df.index)
    wilders_cond = (df["Close"] > df["Wilders"]) if use_wilders else pd.Series(True, index=df.index)
    ema50_cond = (df["Close"] > df["EMA50"]) if use_ema50 else pd.Series(True, index=df.index)
    alma_cond = (df["Close"] > df["ALMA"]) if use_alma else pd.Series(True, index=df.index)
    supertrend_cond = (df["ST_Direction"] == 1) if use_supertrend else pd.Series(True, index=df.index)
    coppock_cond = (df["Coppock"] > 0) if use_coppock else pd.Series(True, index=df.index)
    
    stoch_rsi_cond = (df["Stoch_RSI"] < df["RSI"]) if use_stoch_below_rsi else pd.Series(True, index=df.index)
    
    if use_macd:
        macd_cross = (df["MACD"] > df["MACD_Signal"]) & (df["MACD"].shift(1) <= df["MACD_Signal"].shift(1))
        macd_recent_cross = macd_cross.rolling(window=3).max().fillna(0).astype(bool)
        macd_cond = (df["MACD"] > df["MACD_Signal"]) | macd_recent_cross
    else:
        macd_cond = pd.Series(True, index=df.index)

    fisher_cond = (df["Fisher"] > df["Fisher_Signal"]) if use_fisher else pd.Series(True, index=df.index)
    crsi_cond = (df["CRSI"] < 20) if use_crsi else pd.Series(True, index=df.index)
    
    volume_cond = (df["Volume"] > df["Vol_SMA"]) if use_volume else pd.Series(True, index=df.index)
    vwap_cond = (df["Close"] > df["VWAP"]) if use_vwap else pd.Series(True, index=df.index)
    obv_cond = (df["OBV"] > df["OBV"].rolling(20).mean()) if use_obv else pd.Series(True, index=df.index)
    bollinger_cond = (df["Close"] > df["BB_Mid"]) if use_bollinger else pd.Series(True, index=df.index)
    adx_cond = (df["ADX"] > 25) if use_adx else pd.Series(True, index=df.index)
    mass_cond = (df["Mass_Index"] < 27) if use_mass else pd.Series(True, index=df.index)
    
    # Nihai Sinyal
    df["Signal"] = (
        base_signal & kama_cond & wilders_cond & stoch_rsi_cond & 
        macd_cond & ema50_cond & volume_cond & 
        bollinger_cond & adx_cond & vwap_cond & obv_cond & supertrend_cond &
        alma_cond & fisher_cond & crsi_cond & coppock_cond & mass_cond
    )
    
    results = []
    in_position = False
    entry_idx = None
    entry_price = 0
    stop_price = 0
    target_price = 0
    lot = 0
    maliyet = 0
    
    kasa_nakit = baslangic_sermayesi
    komisyon_orani = komisyon_pct / 100.0
    
    for i in range(len(df)):
        current_date = df.index[i]
        
        if in_position:
            bars_held = i - entry_idx
            low_price = df["Low"].iloc[i]
            high_price = df["High"].iloc[i]
            close_price = df["Close"].iloc[i]
            open_price = df["Open"].iloc[i]
            
            exit_triggered = False
            exit_price = 0
            exit_reason = ""
            
            if low_price <= stop_price:
                exit_price = open_price if open_price <= stop_price else stop_price
                exit_reason = "Stop-Loss"
                exit_triggered = True
            elif high_price >= target_price:
                exit_price = open_price if open_price >= target_price else target_price
                exit_reason = "Kâr Al"
                exit_triggered = True
            elif bars_held >= hold_days:
                exit_price = close_price
                exit_reason = "Süre Doldu"
                exit_triggered = True
                
            if exit_triggered:
                satis_tutari = lot * exit_price
                komisyon_satis = satis_tutari * komisyon_orani
                net_ele_gecen = satis_tutari - komisyon_satis
                net_kar_tl = net_ele_gecen - maliyet
                getiri_pct = (net_kar_tl / maliyet) * 100
                kasa_nakit += net_ele_gecen
                
                results.append({
                    "Giriş Zamanı": df.index[entry_idx].strftime("%Y-%m-%d %H:%M"),
                    "Çıkış Zamanı": current_date.strftime("%Y-%m-%d %H:%M"),
                    "Giriş Fiyatı": round(entry_price, 2),
                    "Çıkış Fiyatı": round(exit_price, 2),
                    "Lot": lot,
                    "Net Kâr/Zarar (TL)": round(net_kar_tl, 2),
                    "Getiri (%)": round(getiri_pct, 2),
                    "Çıkış Nedeni": exit_reason,
                    "Bar Süresi": bars_held,
                    "Portföy Değeri": round(kasa_nakit, 2)
                })
                in_position = False
                continue
                
        if not in_position and df["Signal"].iloc[i]:
            entry_price = df["Close"].iloc[i]
            alinabilecek_lot = int(kasa_nakit / (entry_price * (1 + komisyon_orani)))
            
            if alinabilecek_lot > 0:
                in_position = True
                entry_idx = i
                lot = alinabilecek_lot
                stop_price = entry_price * (1 - stop_loss_pct / 100)
                target_price = entry_price * (1 + take_profit_pct / 100)
                maliyet = lot * entry_price * (1 + komisyon_orani)
                kasa_nakit -= maliyet

    res_df = pd.DataFrame(results)
    
    if res_df.empty:
        st.warning("Hiç işlem üretilmedi. Filtreleri gevşetmeyi deneyin.")
        st.stop()
        
    nihai_portfoy = kasa_nakit
    if in_position:
        nihai_portfoy += (lot * df["Close"].iloc[-1])
        
    st.session_state["bt_res_df"] = res_df
    st.session_state["bt_ticker"] = ticker
    st.session_state["bt_baslangic"] = baslangic_sermayesi
    st.session_state["bt_nihai"] = nihai_portfoy
    st.session_state["bt_ind_name"] = f"{gosterge_secimi} ({zaman_dilimi})"
    st.session_state["bt_in_position"] = in_position
    st.session_state["bt_active_details"] = {
        "entry": entry_price if in_position else df["Close"].iloc[-1],
        "stop": stop_price if in_position else df["Close"].iloc[-1] * (1 - stop_loss_pct / 100),
        "target": target_price if in_position else df["Close"].iloc[-1] * (1 + take_profit_pct / 100),
        "lot": lot if in_position else int(kasa_nakit / df["Close"].iloc[-1]),
        "kasa": kasa_nakit
    }

# --- EKRANA ÇİZİM KISMI ---
if "bt_res_df" in st.session_state:
    res_df = st.session_state["bt_res_df"]
    ticker = st.session_state["bt_ticker"]
    baslangic = st.session_state["bt_baslangic"]
    nihai_portfoy = st.session_state["bt_nihai"]
    ind_name = st.session_state["bt_ind_name"]
    in_position = st.session_state["bt_in_position"]
    
    toplam_kar = nihai_portfoy - baslangic
    toplam_getiri = (toplam_kar / baslangic) * 100
    win_rate = (res_df["Net Kâr/Zarar (TL)"] > 0).mean() * 100
    
    st.subheader(f"📌 {ticker} — {ind_name} Portföy Sonuçları")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Başlangıç Sermayesi", f"{baslangic:,.0f} TL")
    c2.metric("Son Portföy Değeri", f"{nihai_portfoy:,.0f} TL", f"%{toplam_getiri:.1f}")
    c3.metric("Toplam Net Kâr", f"{toplam_kar:,.0f} TL")
    c4.metric("Başarı Oranı", f"%{win_rate:.1f}", f"{len(res_df)} İşlem")

    act = st.session_state["bt_active_details"]
    durum_text = "AÇIK POZİSYON VAR" if in_position else "BEKLEMEDE"
    st.markdown(f"### 🎯 Son Durum ve Aksiyon Planı — **{durum_text}**")
    st.info(f"**Güncel Fiyat:** {act['entry']:.2f} TL | **Kasadaki Nakit:** {act['kasa']:,.0f} TL")
    
    colA, colB, colC = st.columns(3)
    colA.error(f"🛑 **Stop-Loss**\n\nFiyat: {act['stop']:.2f} TL\n\nZarar: -%{((act['stop']/act['entry'])-1)*-100:.1f}")
    colB.success(f"🎯 **Kâr Al**\n\nFiyat: {act['target']:.2f} TL\n\nKâr: +%{((act['target']/act['entry'])-1)*100:.1f}")
    colC.info(f"📦 **Lot & Potansiyel**\n\nMevcut/Alınacak Lot: {act['lot']}\n\nHedefteki Kâr: {act['lot'] * (act['target']-act['entry']):,.0f} TL")

    st.markdown("### 📈 Sermaye Büyüme Grafiği")
    eq_df = res_df[["Çıkış Zamanı", "Portföy Değeri"]].copy()
    eq_df.loc[-1] = ["Başlangıç", baslangic]
    eq_df.index = eq_df.index + 1
    eq_df = eq_df.sort_index()
    
    fig_eq = px.line(eq_df, x="Çıkış Zamanı", y="Portföy Değeri", markers=True, title="Bileşik Getiri")
    fig_eq.update_traces(line_color="#2e7d32", line_width=3)
    st.plotly_chart(fig_eq, use_container_width=True)

    st.markdown("#### Detaylı İşlem Defteri")
    st.dataframe(res_df, use_container_width=True, hide_index=True)
