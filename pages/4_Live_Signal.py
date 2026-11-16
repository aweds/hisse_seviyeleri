import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import (
    kama, stochastic_rsi, wilders_smoothing, macd, ema, 
    bollinger_bands, calculate_adx, calculate_vwap, calculate_obv, calculate_supertrend,
    alma, fisher_transform, connors_rsi, coppock_curve, mass_index
)
from levels import rsi

st.set_page_config(page_title="Canlı Sinyal", page_icon="🚨", layout="wide")
st.title("🚨 Canlı Piyasa Sinyal Panosu")
st.caption("Gelişmiş filtrelerle piyasayı tarayın ve portföyünüzü kontrol edin.")

# --- KENAR ÇUBUĞU AYARLARI ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    st.markdown("**Ana Gösterge**")
    gosterge_secimi = st.radio("Gösterge", ["RSI", "Stoch RSI"])
    esik = st.number_input("Aşırı Satım Eşiği", value=30)
    
    st.markdown("**Trend Filtreleri**")
    use_kama = st.checkbox("Fiyat > KAMA", value=True)
    use_wilders = st.checkbox("Fiyat > Wilders", value=False)
    use_ema50 = st.checkbox("Fiyat > EMA 50", value=False)
    use_alma = st.checkbox("Fiyat > ALMA (10)", value=False)
    use_supertrend = st.checkbox("Supertrend Yönü = Al", value=False)
    use_coppock = st.checkbox("Coppock Curve > 0", value=False)
    
    st.markdown("**Momentum Filtreleri**")
    use_stoch_below_rsi = st.checkbox("Stoch RSI < RSI", value=True)
    use_macd = st.checkbox("MACD > Sinyal", value=False)
    use_fisher = st.checkbox("Fisher > Sinyal Çizgisi", value=False)
    use_crsi = st.checkbox("Connors RSI < 20", value=False)
    
    st.markdown("**Hacim & Volatilite**")
    use_volume = st.checkbox("Hacim > Ort. Hacim", value=False)
    use_vwap = st.checkbox("Fiyat > VWAP", value=False)
    use_obv = st.checkbox("OBV > 20 Günlük Ort.", value=False)
    use_bollinger = st.checkbox("Fiyat > Bollinger Orta Bandı", value=False)
    use_adx = st.checkbox("ADX > 25", value=False)
    use_mass = st.checkbox("Mass Index < 27", value=False)
    
    st.markdown("---")
    st.markdown("**Risk Yönetimi**")
    sermaye = st.number_input("Yeni Alımlar İçin Sermaye (TL)", value=100000)
    risk_pct = st.number_input("İşlem Başı Risk (%)", value=2.0)
    stop_loss_pct = st.number_input("Yeni Alım Stop-Loss (%)", value=10.0)
    take_profit_pct = st.number_input("Kâr Al Hedefi (%)", value=25.0)
    
    st.markdown("---")
    varsayilan_liste = "PATEK, ARDYZ, THYAO, ASELS, TKFEN, EREGL, SISE, KCHOL"
    hisse_listesi = st.text_area("Yeni Taranacak Hisseler", value=varsayilan_liste)

# --- 1. BÖLÜM: PORTFÖY ---
st.subheader("💼 Portföyüm (Açık Pozisyonlar)")
st.caption("Elinizdeki hisseleri ekleyin, sistem satış sinyali versin.")

if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = pd.DataFrame([{"Hisse": "", "Lot": 0, "Alış Fiyatı": 0.0}])

edited_df = st.data_editor(
    st.session_state["portfolio"],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Hisse": st.column_config.TextColumn("Hisse Kodu", required=True),
        "Lot": st.column_config.NumberColumn("Lot", min_value=1, format="%d"),
        "Alış Fiyatı": st.column_config.NumberColumn("Maliyet (TL)", min_value=0.01, format="%.2f")
    }
)
st.session_state["portfolio"] = edited_df
st.divider()

# --- 2. BÖLÜM: TARAMA MOTORU ---
tara = st.button("🔄 Piyasayı Tara ve Portföyü Kontrol Et", type="primary", use_container_width=True)

if tara:
    portfoy_sonuclari = []
    if not edited_df.empty:
        for _, row in edited_df.iterrows():
            if pd.isna(row["Hisse"]) or pd.isna(row["Lot"]) or pd.isna(row["Alış Fiyatı"]) or row["Lot"] == 0:
                continue
            ticker = normalize_ticker(str(row["Hisse"]))
            df = fetch_ohlcv(ticker, interval="1d", period="1y")
            if df.empty: continue
                
            son_fiyat = df["Close"].iloc[-1]
            maliyet = row["Alış Fiyatı"]
            lot = row["Lot"]
            
            kar_zarar_tl = (son_fiyat - maliyet) * lot
            kar_zarar_pct = ((son_fiyat / maliyet) - 1) * 100
            
            stop_seviyesi = maliyet * (1 - stop_loss_pct / 100)
            hedef_seviyesi = maliyet * (1 + take_profit_pct / 100)
            
            aksiyon = "TUT"
            sebep = "Trend devam ediyor."
            
            if son_fiyat <= stop_seviyesi:
                aksiyon = "SAT (Stop-Loss)"
                sebep = "Fiyat zarar durdur seviyesinin altına indi!"
            elif son_fiyat >= hedef_seviyesi:
                aksiyon = "SAT (Kâr Al)"
                sebep = "Fiyat kâr al hedefine ulaştı!"
            else:
                df["RSI"] = rsi(df, 14)
                if df["RSI"].iloc[-1] > 75:
                    aksiyon = "DİKKAT"
                    sebep = "RSI çok yüksek (Aşırı Alım)."
            
            portfoy_sonuclari.append({
                "Hisse": ticker.replace(".IS", ""),
                "Lot": lot,
                "Maliyet": maliyet,
                "Son Fiyat": round(son_fiyat, 2),
                "Kâr/Zarar (TL)": round(kar_zarar_tl, 2),
                "Getiri (%)": round(kar_zarar_pct, 2),
                "Aksiyon": aksiyon,
                "Açıklama": sebep
            })

    yeni_firsatlar = []
    hisseler = [h.strip().upper() for h in hisse_listesi.split(",") if h.strip()]
    progress = st.progress(0, text="Piyasa taranıyor...")
    
    for i, raw_ticker in enumerate(hisseler):
        ticker = normalize_ticker(raw_ticker)
        df = fetch_ohlcv(ticker, interval="1d", period="1y")
        
        if df.empty or len(df) < 50: continue
            
        # İndikatörleri Hesapla
        df["RSI"] = rsi(df, 14)
        df["Stoch_RSI"] = stochastic_rsi(df["Close"], 14)
        df["KAMA"] = kama(df["Close"], 10)
        df["Wilders"] = wilders_smoothing(df["Close"], 14)
        df["EMA50"] = ema(df["Close"], 50)
        df["MACD"], df["MACD_Signal"] = macd(df["Close"])
        df["Vol_SMA"] = df["Volume"].rolling(20).mean()
        
        df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = bollinger_bands(df["Close"])
        df["ADX"], df["+DI"], df["-DI"] = calculate_adx(df)
        df["VWAP"] = calculate_vwap(df)
        df["OBV"] = calculate_obv(df)
        df["Supertrend"], df["ST_Direction"] = calculate_supertrend(df)
        
        df["ALMA"] = alma(df["Close"], 10)
        df["Fisher"], df["Fisher_Signal"] = fisher_transform(df)
        df["CRSI"] = connors_rsi(df["Close"])
        df["Coppock"] = coppock_curve(df["Close"])
        df["Mass_Index"] = mass_index(df)
        
        son_bar = df.iloc[-1]
        onceki_bar = df.iloc[-2]
        
        current_ind = son_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else son_bar["RSI"]
        prev_ind = onceki_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else onceki_bar["RSI"]
        
        ind_sinyali = (prev_ind < esik) and (current_ind >= esik)
        
        kama_cond = (son_bar["Close"] > son_bar["KAMA"]) if use_kama else True
        wilders_cond = (son_bar["Close"] > son_bar["Wilders"]) if use_wilders else True
        ema50_cond = (son_bar["Close"] > son_bar["EMA50"]) if use_ema50 else True
        alma_cond = (son_bar["Close"] > son_bar["ALMA"]) if use_alma else True
        supertrend_cond = (son_bar["ST_Direction"] == 1) if use_supertrend else True
        coppock_cond = (son_bar["Coppock"] > 0) if use_coppock else True
        
        stoch_rsi_cond = (son_bar["Stoch_RSI"] < son_bar["RSI"]) if use_stoch_below_rsi else True
        
        if use_macd:
            macd_cross = (df["MACD"] > df["MACD_Signal"]) & (df["MACD"].shift(1) <= df["MACD_Signal"].shift(1))
            macd_recent_cross = macd_cross.rolling(window=3).max().fillna(0).astype(bool)
            macd_cond = (son_bar["MACD"] > son_bar["MACD_Signal"]) or macd_recent_cross.iloc[-1]
        else:
            macd_cond = True

        fisher_cond = (son_bar["Fisher"] > son_bar["Fisher_Signal"]) if use_fisher else True
        crsi_cond = (son_bar["CRSI"] < 20) if use_crsi else True
        
        volume_cond = (son_bar["Volume"] > son_bar["Vol_SMA"]) if use_volume else True
        vwap_cond = (son_bar["Close"] > son_bar["VWAP"]) if use_vwap else True
        obv_cond = (son_bar["OBV"] > df["OBV"].rolling(20).mean().iloc[-1]) if use_obv else True
        bollinger_cond = (son_bar["Close"] > son_bar["BB_Mid"]) if use_bollinger else True
        adx_cond = (son_bar["ADX"] > 25) if use_adx else True
        mass_cond = (son_bar["Mass_Index"] < 27) if use_mass else True
        
        durum = "BEKLE"
        if (ind_sinyali and kama_cond and wilders_cond and stoch_rsi_cond and macd_cond 
            and ema50_cond and volume_cond and bollinger_cond and adx_cond and vwap_cond 
            and obv_cond and supertrend_cond and alma_cond and fisher_cond and crsi_cond 
            and coppock_cond and mass_cond):
            durum = "AL"
        elif current_ind < esik:
            durum = "İZLE"
            
        fiyat = son_bar["Close"]
        stop_fiyat = fiyat * (1 - stop_loss_pct / 100)
        
        zaten_var = ticker.replace(".IS", "") in [p["Hisse"] for p in portfoy_sonuclari]
        
        if durum == "AL" and not zaten_var:
            risk_tutari = sermaye * (risk_pct / 100)
            birim_risk = fiyat - stop_fiyat
            lot = int(risk_tutari / birim_risk) if birim_risk > 0 else 0
            
            yeni_firsatlar.append({
                "Hisse": ticker.replace(".IS", ""),
                "Son Fiyat": round(fiyat, 2),
                "Önerilen Lot": lot,
                "Stop Fiyatı": round(stop_fiyat, 2)
            })
            
        progress.progress((i + 1) / len(hisseler), text=f"{ticker} tarandı...")
        
    progress.empty()

    st.subheader("📊 Tarama Sonuçları")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💼 Portföy Durumu")
        if portfoy_sonuclari:
            p_df = pd.DataFrame(portfoy_sonuclari)
            def color_actions(val):
                if "SAT" in str(val): return 'background-color: #ffcccc; color: #990000; font-weight: bold'
                elif "DİKKAT" in str(val): return 'background-color: #fff3cd; color: #856404'
                return 'background-color: #d4edda; color: #155724'
            st.dataframe(p_df.style.map(color_actions, subset=["Aksiyon"]), use_container_width=True, hide_index=True)
        else:
            st.info("Portföyünüzde hisse bulunmuyor.")

    with col2:
        st.markdown("### 🎯 Yeni Alım Fırsatları")
        if yeni_firsatlar:
            st.dataframe(pd.DataFrame(yeni_firsatlar), use_container_width=True, hide_index=True)
        else:
            st.info("Şu an tüm filtreleri sağlayan bir AL sinyali yok.")
