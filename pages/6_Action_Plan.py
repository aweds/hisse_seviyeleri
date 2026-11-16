import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import (
    kama, stochastic_rsi, wilders_smoothing, macd, ema, 
    bollinger_bands, calculate_adx, calculate_vwap, calculate_obv, calculate_supertrend,
    alma, fisher_transform, connors_rsi, coppock_curve, mass_index
)
from levels import rsi

st.set_page_config(page_title="Aksiyon Paneli", page_icon="🎯", layout="wide")
st.title("🎯 Canlı Aksiyon ve Teşhis Paneli")
st.caption("Seçtiğiniz filtrelerin anlık durumunu görün ve sistemin neden AL/SAT verdiğini (veya vermediğini) teşhis edin.")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Analiz Ayarları")
    raw = st.text_input("Hisse Kodu", "ARDYZ")
    
    zaman_dilimi = st.selectbox("Zaman Dilimi", ["Günlük (1d)", "Saatlik (1h)", "15 Dakika (15m)"], index=0)
    if zaman_dilimi == "Günlük (1d)":
        interval, period = "1d", "1y"
    elif zaman_dilimi == "Saatlik (1h)":
        interval, period = "1h", "6mo"
    else:
        interval, period = "15m", "1mo"

    st.markdown("---")
    gosterge_secimi = st.radio("Ana Gösterge", ["RSI", "Stoch RSI"])
    esik = st.number_input("Aşırı Satım Eşiği (Altı)", value=30)
    
    st.markdown("**Filtreler (Sadece Teyit Etmek İstediklerinizi Seçin)**")
    use_kama = st.checkbox("Fiyat > KAMA", value=True)
    use_ema50 = st.checkbox("Fiyat > EMA 50", value=False)
    use_wilders = st.checkbox("Fiyat > Wilders", value=False)
    use_alma = st.checkbox("Fiyat > ALMA", value=False)
    use_supertrend = st.checkbox("Supertrend = Al", value=False)
    
    use_stoch_below_rsi = st.checkbox("Stoch RSI < RSI", value=False)
    use_macd = st.checkbox("MACD > Sinyal", value=False)
    use_fisher = st.checkbox("Fisher > Sinyal", value=False)
    
    use_volume = st.checkbox("Hacim > Ortalama", value=False)
    use_vwap = st.checkbox("Fiyat > VWAP", value=False)
    use_obv = st.checkbox("OBV > 20 Barlık Ortalama", value=False)
    
    st.markdown("---")
    st.markdown("**Risk Yönetimi (Lot Hesabı İçin)**")
    sermaye = st.number_input("Sermaye (TL)", value=100000)
    risk_pct = st.number_input("İşlem Başı Risk (%)", value=2.0)
    stop_loss_pct = st.number_input("Stop-Loss (%)", value=10.0)
    take_profit_pct = st.number_input("Kâr Al Hedefi (%)", value=25.0)

# --- HESAPLAMA MOTORU ---
ticker = normalize_ticker(raw)
df = fetch_ohlcv(ticker, interval=interval, period=period)

if df.empty or len(df) < 50:
    st.error("Yetersiz veri. Lütfen hisse kodunu veya zaman dilimini kontrol edin.")
    st.stop()

# Göstergeleri Hesapla
df["RSI"] = rsi(df, 14)
df["KAMA"] = kama(df["Close"], 10)
df["EMA50"] = ema(df["Close"], 50)
df["Wilders"] = wilders_smoothing(df["Close"], 14)
df["Stoch_RSI"] = stochastic_rsi(df["Close"], 14)
df["ALMA"] = alma(df["Close"], 10)
df["Supertrend"], df["ST_Direction"] = calculate_supertrend(df)
df["MACD"], df["MACD_Signal"] = macd(df["Close"])
df["Fisher"], df["Fisher_Signal"] = fisher_transform(df)
df["Vol_SMA"] = df["Volume"].rolling(20).mean()
df["VWAP"] = calculate_vwap(df)
df["OBV"] = calculate_obv(df)

son_bar = df.iloc[-1]
onceki_bar = df.iloc[-2]

current_ind = son_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else son_bar["RSI"]
prev_ind = onceki_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else onceki_bar["RSI"]

# --- SİNYAL VE TEŞHİS LİSTESİ ---
sinyal_var = (prev_ind < esik) and (current_ind >= esik)
teshisler = []

# Ana Gösterge Teşhisi
teshisler.append({
    "Gösterge": gosterge_secimi,
    "Durum": "✅ Uygun" if sinyal_var else "❌ Uygun Değil",
    "Mevcut Değer": f"Dün: {prev_ind:.1f} | Bugün: {current_ind:.1f}",
    "Şart": f"{esik} seviyesini yukarı kesmeli"
})

# Trend Filtreleri
if use_kama:
    kama_ok = son_bar["Close"] > son_bar["KAMA"]
    teshisler.append({"Gösterge": "KAMA", "Durum": "✅ Uygun" if kama_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | KAMA: {son_bar['KAMA']:.2f}", "Şart": "Fiyat > KAMA"})
if use_ema50:
    ema_ok = son_bar["Close"] > son_bar["EMA50"]
    teshisler.append({"Gösterge": "EMA 50", "Durum": "✅ Uygun" if ema_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA50: {son_bar['EMA50']:.2f}", "Şart": "Fiyat > EMA 50"})
if use_wilders:
    w_ok = son_bar["Close"] > son_bar["Wilders"]
    teshisler.append({"Gösterge": "Wilders", "Durum": "✅ Uygun" if w_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | Wilders: {son_bar['Wilders']:.2f}", "Şart": "Fiyat > Wilders"})
if use_alma:
    alma_ok = son_bar["Close"] > son_bar["ALMA"]
    teshisler.append({"Gösterge": "ALMA", "Durum": "✅ Uygun" if alma_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | ALMA: {son_bar['ALMA']:.2f}", "Şart": "Fiyat > ALMA"})
if use_supertrend:
    st_ok = son_bar["ST_Direction"] == 1
    teshisler.append({"Gösterge": "Supertrend", "Durum": "✅ Uygun" if st_ok else "❌ Uygun Değil", "Mevcut Değer": "Al Yönünde" if st_ok else "Sat Yönünde", "Şart": "Supertrend Yönü = Al"})

# Momentum Filtreleri
if use_stoch_below_rsi:
    stoch_rsi_ok = son_bar["Stoch_RSI"] < son_bar["RSI"]
    teshisler.append({"Gösterge": "Stoch < RSI", "Durum": "✅ Uygun" if stoch_rsi_ok else "❌ Uygun Değil", "Mevcut Değer": f"Stoch: {son_bar['Stoch_RSI']:.1f} | RSI: {son_bar['RSI']:.1f}", "Şart": "Stoch RSI < RSI"})
if use_macd:
    macd_ok = son_bar["MACD"] > son_bar["MACD_Signal"]
    teshisler.append({"Gösterge": "MACD", "Durum": "✅ Uygun" if macd_ok else "❌ Uygun Değil", "Mevcut Değer": f"MACD: {son_bar['MACD']:.2f} | Sinyal: {son_bar['MACD_Signal']:.2f}", "Şart": "MACD > Sinyal"})
if use_fisher:
    fisher_ok = son_bar["Fisher"] > son_bar["Fisher_Signal"]
    teshisler.append({"Gösterge": "Fisher", "Durum": "✅ Uygun" if fisher_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fisher: {son_bar['Fisher']:.2f} | Sinyal: {son_bar['Fisher_Signal']:.2f}", "Şart": "Fisher > Sinyal"})

# Hacim Filtreleri
if use_volume:
    vol_ok = son_bar["Volume"] > son_bar["Vol_SMA"]
    teshisler.append({"Gösterge": "Hacim", "Durum": "✅ Uygun" if vol_ok else "❌ Uygun Değil", "Mevcut Değer": f"Hacim: {son_bar['Volume']:,.0f} | Ort: {son_bar['Vol_SMA']:,.0f}", "Şart": "Hacim > 20 Barlık Ort."})
if use_vwap:
    vwap_ok = son_bar["Close"] > son_bar["VWAP"]
    teshisler.append({"Gösterge": "VWAP", "Durum": "✅ Uygun" if vwap_ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | VWAP: {son_bar['VWAP']:.2f}", "Şart": "Fiyat > VWAP"})
if use_obv:
    obv_ok = son_bar["OBV"] > df["OBV"].rolling(20).mean().iloc[-1]
    teshisler.append({"Gösterge": "OBV", "Durum": "✅ Uygun" if obv_ok else "❌ Uygun Değil", "Mevcut Değer": f"OBV: {son_bar['OBV']:,.0f}", "Şart": "OBV > 20 Barlık Ort."})

# --- EKRAN ÇIKTISI ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 📌 Mevcut Durum")
    st.info(f"**Hisse:** {ticker}\n\n**Periyot:** {zaman_dilimi}\n\n**Güncel Fiyat:** {son_bar['Close']:.2f} TL")
    
    # Tüm şartlar uyuyor mu?
    tum_sartlar_uygun = all("✅" in t["Durum"] for t in teshisler)
    
    if tum_sartlar_uygun:
        st.success("### 🟢 AL SİNYALİ VAR!\nSeçtiğiniz tüm filtreler uyuşuyor. İşlem yapabilirsiniz.")
        
        fiyat = son_bar["Close"]
        stop_fiyat = fiyat * (1 - stop_loss_pct / 100)
        hedef_fiyat = fiyat * (1 + take_profit_pct / 100)
        
        risk_tutari = sermaye * (risk_pct / 100)
        birim_risk = fiyat - stop_fiyat
        lot = int(risk_tutari / birim_risk) if birim_risk > 0 else 0
        
        st.markdown(f"""
        *   **Giriş Fiyatı:** {fiyat:.2f} TL
        *   **Stop-Loss:** {stop_fiyat:.2f} TL
        *   **Kâr Al:** {hedef_fiyat:.2f} TL
        *   **Alınacak Lot:** {lot}
        *   **Risk (TL):** {risk_tutari:,.0f} TL
        """)
    else:
        st.warning("### 🟡 BEKLEMEDE\nSeçtiğiniz filtrelerin bazıları şu an uygun değil. Detaylar sağdadır.")

with col2:
    st.markdown("### 🔍 Teşhis Tablosu (Hangi Filtre Neden Uymuyor?)")
    teshis_df = pd.DataFrame(teshisler)
    
    # Renklendirme fonksiyonu
    def renklendir(val):
        if "✅" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
        elif "❌" in str(val): return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
        return ''
        
    st.dataframe(
        teshis_df.style.map(renklendir, subset=["Durum"]),
        use_container_width=True,
        hide_index=True
    )
