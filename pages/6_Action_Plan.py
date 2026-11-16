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
st.caption("Seçtiğiniz filtrelerin anlık durumunu görün, AL / TUT / SAT sinyallerini teşhis edin.")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Analiz Ayarları")
    raw = st.text_input("Hisse Kodu", "ASELS")
    
    zaman_dilimi = st.selectbox("Zaman Dilimi", ["Günlük (1d)", "Saatlik (1h)", "15 Dakika (15m)"], index=0)
    if zaman_dilimi == "Günlük (1d)":
        interval, period = "1d", "1y"
    elif zaman_dilimi == "Saatlik (1h)":
        interval, period = "1h", "6mo"
    else:
        interval, period = "15m", "1mo"

    st.markdown("---")
    st.markdown("**Ana Göstergeler (AL için)**")
    use_rsi = st.checkbox("RSI Kullan", value=False)
    rsi_esik = st.number_input("RSI Aşırı Satım Eşiği", value=30, key="rsi_esik")
    
    use_stoch = st.checkbox("Stoch RSI Kullan", value=False)
    stoch_esik = st.number_input("Stoch RSI Aşırı Satım Eşiği", value=20, key="stoch_esik")

    st.markdown("---")
    st.markdown("**Trend Filtreleri**")
    use_kama = st.checkbox("Fiyat > KAMA", value=True)
    
    # YENİ EMA SEÇENEKLERİ
    use_ema20 = st.checkbox("Fiyat > EMA 20", value=False)
    use_ema50 = st.checkbox("Fiyat > EMA 50", value=False)
    use_ema100 = st.checkbox("Fiyat > EMA 100", value=False)
    use_ema200 = st.checkbox("Fiyat > EMA 200", value=False)
    use_golden_cross = st.checkbox("Altın Kesişim (EMA 20 > EMA 50)", value=False)
    
    use_wilders = st.checkbox("Fiyat > Wilders", value=False)
    use_alma = st.checkbox("Fiyat > ALMA", value=False)
    use_supertrend = st.checkbox("Supertrend = Al", value=False)
    
    st.markdown("**Momentum & Hacim Filtreleri**")
    use_macd = st.checkbox("MACD > Sinyal", value=False)
    use_volume = st.checkbox("Hacim > Ortalama", value=True)
    use_obv = st.checkbox("OBV > 20 Barlık Ortalama", value=False)
    
    st.markdown("---")
    st.markdown("**💼 Pozisyon Durumu**")
    has_position = st.checkbox("Elimde Bu Hisseden Var", value=False)
    if has_position:
        entry_price = st.number_input("Alış Maliyetim (TL)", value=100.0)
        entry_lot = st.number_input("Lot Sayısı", value=100)
    
    st.markdown("---")
    st.markdown("**Risk Yönetimi**")
    sermaye = st.number_input("Toplam Sermaye (TL)", value=100000)
    risk_pct = st.number_input("İşlem Başı Risk (%)", value=2.0)
    stop_loss_pct = st.number_input("Stop-Loss (%)", value=10.0)
    take_profit_pct = st.number_input("Kâr Al Hedefi (%)", value=25.0)

# --- HESAPLAMA MOTORU ---
ticker = normalize_ticker(raw)
df = fetch_ohlcv(ticker, interval=interval, period=period)

if df.empty or len(df) < 50:
    st.error("Yetersiz veri.")
    st.stop()

# Göstergeleri Hesapla
df["RSI"] = rsi(df, 14)
df["Stoch_RSI"] = stochastic_rsi(df["Close"], 14)
df["KAMA"] = kama(df["Close"], 10)

# Tüm EMA'ları hesapla
df["EMA20"] = ema(df["Close"], 20)
df["EMA50"] = ema(df["Close"], 50)
df["EMA100"] = ema(df["Close"], 100)
df["EMA200"] = ema(df["Close"], 200)

df["Wilders"] = wilders_smoothing(df["Close"], 14)
df["ALMA"] = alma(df["Close"], 10)
df["Supertrend"], df["ST_Direction"] = calculate_supertrend(df)
df["MACD"], df["MACD_Signal"] = macd(df["Close"])
df["Vol_SMA"] = df["Volume"].rolling(20).mean()
df["OBV"] = calculate_obv(df)

son_bar = df.iloc[-1]
onceki_bar = df.iloc[-2]

# --- SİNYAL VE TEŞHİS LİSTESİ ---
teshisler = []
al_sartlari_uygun = True

# Herhangi bir filtre seçili mi kontrolü
herhangi_bir_filtre = (use_rsi or use_stoch or use_kama or use_ema20 or use_ema50 or 
                       use_ema100 or use_ema200 or use_golden_cross or use_wilders or 
                       use_alma or use_supertrend or use_macd or use_volume or use_obv)

# 1. RSI Kontrolü
if use_rsi:
    rsi_kesisti = (onceki_bar["RSI"] < rsi_esik) and (son_bar["RSI"] >= rsi_esik)
    if not rsi_kesisti: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "RSI", "Durum": "✅ Uygun" if rsi_kesisti else "❌ Uygun Değil", "Mevcut Değer": f"Dün: {onceki_bar['RSI']:.1f} | Bugün: {son_bar['RSI']:.1f}", "Şart": f"{rsi_esik} seviyesini yukarı kesmeli"})

# 2. Stoch RSI Kontrolü
if use_stoch:
    stoch_kesisti = (onceki_bar["Stoch_RSI"] < stoch_esik) and (son_bar["Stoch_RSI"] >= stoch_esik)
    if not stoch_kesisti: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "Stoch RSI", "Durum": "✅ Uygun" if stoch_kesisti else "❌ Uygun Değil", "Mevcut Değer": f"Dün: {onceki_bar['Stoch_RSI']:.1f} | Bugün: {son_bar['Stoch_RSI']:.1f}", "Şart": f"{stoch_esik} seviyesini yukarı kesmeli"})

# 3. Trend ve Filtreler
if use_kama:
    ok = son_bar["Close"] > son_bar["KAMA"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "KAMA", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | KAMA: {son_bar['KAMA']:.2f}", "Şart": "Fiyat > KAMA"})

# EMA Kontrolleri
if use_ema20:
    ok = son_bar["Close"] > son_bar["EMA20"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "EMA 20", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA20: {son_bar['EMA20']:.2f}", "Şart": "Fiyat > EMA 20"})

if use_ema50:
    ok = son_bar["Close"] > son_bar["EMA50"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "EMA 50", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA50: {son_bar['EMA50']:.2f}", "Şart": "Fiyat > EMA 50"})

if use_ema100:
    ok = son_bar["Close"] > son_bar["EMA100"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "EMA 100", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA100: {son_bar['EMA100']:.2f}", "Şart": "Fiyat > EMA 100"})

if use_ema200:
    ok = son_bar["Close"] > son_bar["EMA200"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "EMA 200", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA200: {son_bar['EMA200']:.2f}", "Şart": "Fiyat > EMA 200"})

if use_golden_cross:
    ok = son_bar["EMA20"] > son_bar["EMA50"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "Altın Kesişim", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"EMA20: {son_bar['EMA20']:.2f} | EMA50: {son_bar['EMA50']:.2f}", "Şart": "EMA 20 > EMA 50"})

# Diğer Filtreler
if use_wilders:
    ok = son_bar["Close"] > son_bar["Wilders"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "Wilders", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | Wilders: {son_bar['Wilders']:.2f}", "Şart": "Fiyat > Wilders"})
if use_alma:
    ok = son_bar["Close"] > son_bar["ALMA"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "ALMA", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | ALMA: {son_bar['ALMA']:.2f}", "Şart": "Fiyat > ALMA"})
if use_supertrend:
    ok = son_bar["ST_Direction"] == 1
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "Supertrend", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": "Al Yönünde" if ok else "Sat Yönünde", "Şart": "Supertrend Yönü = Al"})
if use_macd:
    ok = son_bar["MACD"] > son_bar["MACD_Signal"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "MACD", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"MACD: {son_bar['MACD']:.2f} | Sinyal: {son_bar['MACD_Signal']:.2f}", "Şart": "MACD > Sinyal"})
if use_volume:
    ok = son_bar["Volume"] > son_bar["Vol_SMA"]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "Hacim", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"Hacim: {son_bar['Volume']:,.0f} | Ort: {son_bar['Vol_SMA']:,.0f}", "Şart": "Hacim > 20 Barlık Ort."})
if use_obv:
    ok = son_bar["OBV"] > df["OBV"].rolling(20).mean().iloc[-1]
    if not ok: al_sartlari_uygun = False
    teshisler.append({"Gösterge": "OBV", "Durum": "✅ Uygun" if ok else "❌ Uygun Değil", "Mevcut Değer": f"OBV: {son_bar['OBV']:,.0f}", "Şart": "OBV > 20 Barlık Ort."})

# --- POZİSYON DURUMUNA GÖRE KARAR MEKANİZMASI ---
fiyat = son_bar["Close"]

# --- EKRAN ÇIKTISI ---
col1, col2 = st.columns([1, 2.5])

with col1:
    st.markdown("### 📌 Mevcut Durum")
    st.info(f"**Hisse:** {ticker}\n\n**Periyot:** {zaman_dilimi}\n\n**Güncel Fiyat:** {fiyat:.2f} TL")
    
    if not herhangi_bir_filtre:
        st.warning("### ⚠️ FİLTRE SEÇİLMEDİ\nLütfen sol menüden en az bir gösterge veya trend filtresi seçin.")
    
    elif has_position:
        # --- SAT / TUT MANTIĞI ---
        stop_fiyat = entry_price * (1 - stop_loss_pct / 100)
        hedef_fiyat = entry_price * (1 + take_profit_pct / 100)
        anlik_kar_zarar = (fiyat - entry_price) * entry_lot
        anlik_yuzde = ((fiyat / entry_price) - 1) * 100
        
        st.markdown(f"**Alış:** {entry_price:.2f} TL | **Lot:** {entry_lot}")
        if anlik_kar_zarar >= 0:
            st.success(f"Kâr: +{anlik_kar_zarar:,.2f} TL (%{anlik_yuzde:.2f})")
        else:
            st.error(f"Zarar: {anlik_kar_zarar:,.2f} TL (%{anlik_yuzde:.2f})")
            
        # SAT Sinyali Kontrolleri
        sat_nedenleri = []
        if fiyat <= stop_fiyat:
            sat_nedenleri.append("Fiyat Stop-Loss seviyesinin altında!")
        if fiyat >= hedef_fiyat:
            sat_nedenleri.append("Fiyat Kâr Al hedefine ulaştı!")
        
        if use_rsi and (onceki_bar["RSI"] > 70) and (son_bar["RSI"] < 70):
            sat_nedenleri.append("RSI 70'in altına indi (Momentum kaybı).")
        if use_stoch and (onceki_bar["Stoch_RSI"] > 80) and (son_bar["Stoch_RSI"] < 80):
            sat_nedenleri.append("Stoch RSI 80'in altına indi (Aşırı alımdan çıkış).")
        if use_golden_cross and (onceki_bar["EMA20"] >= onceki_bar["EMA50"]) and (son_bar["EMA20"] < son_bar["EMA50"]):
            sat_nedenleri.append("Ölüm Kesişimi (EMA 20, EMA 50'nin altına indi).")
            
        if sat_nedenleri:
            st.error("### 🔴 SAT SİNYALİ!\n" + "\n".join(f"- {n}" for n in sat_nedenleri))
        else:
            st.warning("### 🟡 TUT SİNYALİ\nTrend devam ediyor. Pozisyonu koruyabilirsiniz.")
            
    else:
        # --- AL / BEKLE MANTIĞI ---
        if al_sartlari_uygun:
            st.success("### 🟢 AL SİNYALİ VAR!\nSeçtiğiniz tüm filtreler uyuşuyor. İşlem yapabilirsiniz.")
            
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
            st.warning("### ⚪ BEKLEMEDE\nAlım şartları henüz oluşmadı. Detaylar sağdadır.")

with col2:
    st.markdown("### 🔍 Teşhis Tablosu (Hangi Filtre Neden Uymuyor?)")
    if teshisler:
        teshis_df = pd.DataFrame(teshisler)
        
        def renklendir(val):
            if "✅" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
            elif "❌" in str(val): return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
            return ''
            
        st.dataframe(
            teshis_df.style.map(renklendir, subset=["Durum"]),
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.info("Teşhis edilecek bir filtre seçilmedi.")
