import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import (
    kama, stochastic_rsi, wilders_smoothing, macd, ema, 
    bollinger_bands, calculate_adx, calculate_vwap, calculate_obv, calculate_supertrend,
    alma, fisher_transform, connors_rsi, coppock_curve, mass_index
)
from levels import rsi

# Sayfa düzenini geniş ekrana uygun hale getir
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
    
    st.markdown("**Trend Filtreleri**")
    use_kama = st.checkbox("Fiyat > KAMA", value=True)
    use_ema50 = st.checkbox("Fiyat > EMA 50", value=False)
    use_wilders = st.checkbox("Fiyat > Wilders", value=False)
    use_alma = st.checkbox("Fiyat > ALMA", value=False)
    use_supertrend = st.checkbox("Supertrend = Al", value=False)
    use_coppock = st.checkbox("Coppock Curve > 0", value=False)
    use_adx = st.checkbox("ADX > 25 (Güçlü Trend)", value=False)
    
    st.markdown("**Momentum & Volatilite Filtreleri**")
    use_stoch_below_rsi = st.checkbox("Stoch RSI < RSI", value=False)
    use_macd = st.checkbox("MACD > Sinyal", value=False)
    use_fisher = st.checkbox("Fisher > Sinyal", value=False)
    use_crsi = st.checkbox("Connors RSI < 20", value=False)
    use_bollinger = st.checkbox("Fiyat > Bollinger Orta Bandı", value=False)
    use_mass = st.checkbox("Mass Index < 27 (Sıkışma)", value=False)
    
    st.markdown("**Hacim Filtreleri**")
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

# Yeni Eklenenler
df["BB_Upper"], df["BB_Mid"], df["BB_Lower"] = bollinger_bands(df["Close"])
df["ADX"], _, _ = calculate_adx(df)
df["CRSI"] = connors_rsi(df["Close"])
df["Coppock"] = coppock_curve(df["Close"])
df["Mass_Index"] = mass_index(df)

son_bar = df.iloc[-1]
onceki_bar = df.iloc[-2]

current_ind = son_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else son_bar["RSI"]
prev_ind = onceki_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else onceki_bar["RSI"]

# --- SİNYAL VE TEŞHİS LİSTESİ ---
sinyal_var = (prev_ind < esik) and (current_ind >= esik)
teshisler = []

# Ana Gösterge Teşhisi
teshisler.append({"Gösterge": gosterge_secimi, "Durum": "✅ Uygun" if sinyal_var else "❌ Uygun Değil", "Mevcut Değer": f"Dün: {prev_ind:.1f} | Bugün: {current_ind:.1f}", "Şart": f"{esik} seviyesini yukarı kesmeli"})

# Trend Filtreleri
if use_kama:
    teshisler.append({"Gösterge": "KAMA", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["KAMA"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | KAMA: {son_bar['KAMA']:.2f}", "Şart": "Fiyat > KAMA"})
if use_ema50:
    teshisler.append({"Gösterge": "EMA 50", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["EMA50"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | EMA50: {son_bar['EMA50']:.2f}", "Şart": "Fiyat > EMA 50"})
if use_wilders:
    teshisler.append({"Gösterge": "Wilders", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["Wilders"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | Wilders: {son_bar['Wilders']:.2f}", "Şart": "Fiyat > Wilders"})
if use_alma:
    teshisler.append({"Gösterge": "ALMA", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["ALMA"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | ALMA: {son_bar['ALMA']:.2f}", "Şart": "Fiyat > ALMA"})
if use_supertrend:
    teshisler.append({"Gösterge": "Supertrend", "Durum": "✅ Uygun" if son_bar["ST_Direction"] == 1 else "❌ Uygun Değil", "Mevcut Değer": "Al Yönünde" if son_bar["ST_Direction"] == 1 else "Sat Yönünde", "Şart": "Supertrend Yönü = Al"})
if use_coppock:
    teshisler.append({"Gösterge": "Coppock", "Durum": "✅ Uygun" if son_bar["Coppock"] > 0 else "❌ Uygun Değil", "Mevcut Değer": f"Değer: {son_bar['Coppock']:.2f}", "Şart": "Coppock > 0"})
if use_adx:
    teshisler.append({"Gösterge": "ADX", "Durum": "✅ Uygun" if son_bar["ADX"] > 25 else "❌ Uygun Değil", "Mevcut Değer": f"ADX: {son_bar['ADX']:.1f}", "Şart": "ADX > 25"})

# Momentum Filtreleri
if use_stoch_below_rsi:
    teshisler.append({"Gösterge": "Stoch < RSI", "Durum": "✅ Uygun" if son_bar["Stoch_RSI"] < son_bar["RSI"] else "❌ Uygun Değil", "Mevcut Değer": f"Stoch: {son_bar['Stoch_RSI']:.1f} | RSI: {son_bar['RSI']:.1f}", "Şart": "Stoch RSI < RSI"})
if use_macd:
    teshisler.append({"Gösterge": "MACD", "Durum": "✅ Uygun" if son_bar["MACD"] > son_bar["MACD_Signal"] else "❌ Uygun Değil", "Mevcut Değer": f"MACD: {son_bar['MACD']:.2f} | Sinyal: {son_bar['MACD_Signal']:.2f}", "Şart": "MACD > Sinyal"})
if use_fisher:
    teshisler.append({"Gösterge": "Fisher", "Durum": "✅ Uygun" if son_bar["Fisher"] > son_bar["Fisher_Signal"] else "❌ Uygun Değil", "Mevcut Değer": f"Fisher: {son_bar['Fisher']:.2f} | Sinyal: {son_bar['Fisher_Signal']:.2f}", "Şart": "Fisher > Sinyal"})
if use_crsi:
    teshisler.append({"Gösterge": "Connors RSI", "Durum": "✅ Uygun" if son_bar["CRSI"] < 20 else "❌ Uygun Değil", "Mevcut Değer": f"CRSI: {son_bar['CRSI']:.1f}", "Şart": "CRSI < 20"})
if use_bollinger:
    teshisler.append({"Gösterge": "Bollinger", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["BB_Mid"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | Orta Bant: {son_bar['BB_Mid']:.2f}", "Şart": "Fiyat > Orta Bant"})
if use_mass:
    teshisler.append({"Gösterge": "Mass Index", "Durum": "✅ Uygun" if son_bar["Mass_Index"] < 27 else "❌ Uygun Değil", "Mevcut Değer": f"Değer: {son_bar['Mass_Index']:.1f}", "Şart": "Mass < 27"})

# Hacim Filtreleri
if use_volume:
    teshisler.append({"Gösterge": "Hacim", "Durum": "✅ Uygun" if son_bar["Volume"] > son_bar["Vol_SMA"] else "❌ Uygun Değil", "Mevcut Değer": f"Hacim: {son_bar['Volume']:,.0f} | Ort: {son_bar['Vol_SMA']:,.0f}", "Şart": "Hacim > 20 Barlık Ort."})
if use_vwap:
    teshisler.append({"Gösterge": "VWAP", "Durum": "✅ Uygun" if son_bar["Close"] > son_bar["VWAP"] else "❌ Uygun Değil", "Mevcut Değer": f"Fiyat: {son_bar['Close']:.2f} | VWAP: {son_bar['VWAP']:.2f}", "Şart": "Fiyat > VWAP"})
if use_obv:
    teshisler.append({"Gösterge": "OBV", "Durum": "✅ Uygun" if son_bar["OBV"] > df["OBV"].rolling(20).mean().iloc[-1] else "❌ Uygun Değil", "Mevcut Değer": f"OBV: {son_bar['OBV']:,.0f}", "Şart": "OBV > 20 Barlık Ort."})

# --- EKRAN ÇIKTISI (Genişletilmiş Sütunlar) ---
# Sol taraf %30, Sağ taraf %70 (1'e 2.5 oran) genişlik kaplar
col1, col2 = st.columns([1, 2.5])

with col1:
    st.markdown("### 📌 Mevcut Durum")
    st.info(f"**Hisse:** {ticker}\n\n**Periyot:** {zaman_dilimi}\n\n**Güncel Fiyat:** {son_bar['Close']:.2f} TL")
    
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
    
    def renklendir(val):
        if "✅" in str(val): return 'background-color: #d4edda; color: #155724; font-weight: bold'
        elif "❌" in str(val): return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
        return ''
        
    # Tabloya height parametresi ekleyerek sayfa içinde daha derli toplu durmasını sağladık
    st.dataframe(
        teshis_df.style.map(renklendir, subset=["Durum"]),
        use_container_width=True,
        hide_index=True,
        height=600 # Tablo yüksekliğini artırarak kaydırmayı (slide) sayfa içine yaydık
    )
