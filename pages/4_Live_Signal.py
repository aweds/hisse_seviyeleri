import pandas as pd
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import kama, stochastic_rsi, wilders_smoothing
from levels import rsi

st.set_page_config(page_title="Canlı Sinyal", page_icon="🚨", layout="wide")
st.title("🚨 Canlı Piyasa Sinyal Panosu")
st.caption("Hem yeni fırsatları tarayın hem de elinizdeki hisselerin durumunu kontrol edin.")

# --- KENAR ÇUBUĞU AYARLARI ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    st.markdown("**Filtreler**")
    gosterge_secimi = st.radio("Gösterge", ["RSI", "Stoch RSI"])
    esik = st.number_input("Aşırı Satım Eşiği", value=30)
    use_kama = st.checkbox("KAMA Filtresi (Fiyat > KAMA)", value=True)
    use_wilders = st.checkbox("Wilders Filtresi (Fiyat > Wilders)", value=True)
    
    st.markdown("---")
    st.markdown("**Risk Yönetimi**")
    sermaye = st.number_input("Yeni Alımlar İçin Sermaye (TL)", value=100000)
    risk_pct = st.number_input("İşlem Başı Risk (%)", value=2.0)
    stop_loss_pct = st.number_input("Yeni Alım Stop-Loss (%)", value=10.0)
    take_profit_pct = st.number_input("Kâr Al Hedefi (%)", value=25.0)
    
    st.markdown("---")
    varsayilan_liste = "PATEK, ARDYZ, THYAO, ASELS, TKFEN, EREGL"
    hisse_listesi = st.text_area("Yeni Taranacak Hisseler", value=varsayilan_liste)

# --- 1. BÖLÜM: PORTFÖY (ELİMİZDEKİ HİSSELER) ---
st.subheader("💼 Portföyüm (Açık Pozisyonlar)")
st.caption("Aşağıdaki tabloya elinizde tuttuğunuz hisseleri ekleyin. Sistem satış sinyali verecektir.")

# Varsayılan boş portföy tablosu (Hafızada tutulur)
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = pd.DataFrame([
        {"Hisse": "ARDYZ", "Lot": 100, "Alış Fiyatı": 50.0}
    ])

# Kullanıcının tabloyu düzenlemesine izin ver
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
    # A) PORTFÖY KONTROLÜ
    portfoy_sonuclari = []
    if not edited_df.empty:
        for _, row in edited_df.iterrows():
            if pd.isna(row["Hisse"]) or pd.isna(row["Lot"]) or pd.isna(row["Alış Fiyatı"]):
                continue
                
            ticker = normalize_ticker(str(row["Hisse"]))
            df = fetch_ohlcv(ticker, interval="1d", period="1y")
            
            if df.empty: continue
                
            son_fiyat = df["Close"].iloc[-1]
            maliyet = row["Alış Fiyatı"]
            lot = row["Lot"]
            
            # Kâr/Zarar Hesapla
            kar_zarar_tl = (son_fiyat - maliyet) * lot
            kar_zarar_pct = ((son_fiyat / maliyet) - 1) * 100
            
            # Satış Kuralları
            stop_seviyesi = maliyet * (1 - stop_loss_pct / 100)
            hedef_seviyesi = maliyet * (1 + take_profit_pct / 100)
            
            aksiyon = "TUT"
            sebep = "Trend devam ediyor."
            renk = "normal"
            
            if son_fiyat <= stop_seviyesi:
                aksiyon = "SAT (Stop-Loss)"
                sebep = "Fiyat zarar durdur seviyesinin altına indi!"
                renk = "inverse" # Kırmızı
            elif son_fiyat >= hedef_seviyesi:
                aksiyon = "SAT (Kâr Al)"
                sebep = "Fiyat kâr al hedefine ulaştı!"
                renk = "off" # Yeşil
            else:
                # Eğer hedefe veya stopa yakın değilse göstergelere bak
                df["RSI"] = rsi(df, 14)
                son_rsi = df["RSI"].iloc[-1]
                if son_rsi > 75:
                    aksiyon = "DİKKAT (Aşırı Alım)"
                    sebep = "RSI çok yüksek, düzeltme gelebilir."
            
            portfoy_sonuclari.append({
                "Hisse": ticker.replace(".IS", ""),
                "Lot": lot,
                "Maliyet": maliyet,
                "Son Fiyat": round(son_fiyat, 2),
                "Kâr/Zarar (TL)": round(kar_zarar_tl, 2),
                "Kâr/Zarar (%)": round(kar_zarar_pct, 2),
                "Aksiyon": aksiyon,
                "Açıklama": sebep
            })

    # B) YENİ FIRSAT TARAMASI
    yeni_firsatlar = []
    hisseler = [h.strip().upper() for h in hisse_listesi.split(",") if h.strip()]
    
    progress = st.progress(0, text="Piyasa taranıyor...")
    
    for i, raw_ticker in enumerate(hisseler):
        ticker = normalize_ticker(raw_ticker)
        df = fetch_ohlcv(ticker, interval="1d", period="1y")
        
        if df.empty or len(df) < 50: continue
            
        df["RSI"] = rsi(df, 14)
        df["Stoch_RSI"] = stochastic_rsi(df["Close"], 14)
        df["KAMA"] = kama(df["Close"], 10)
        df["Wilders"] = wilders_smoothing(df["Close"], 14)
        
        son_bar = df.iloc[-1]
        onceki_bar = df.iloc[-2]
        
        current_ind = son_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else son_bar["RSI"]
        prev_ind = onceki_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else onceki_bar["RSI"]
        
        ind_sinyali = (prev_ind < esik) and (current_ind >= esik)
        kama_ok = (son_bar["Close"] > son_bar["KAMA"]) if use_kama else True
        wilders_ok = (son_bar["Close"] > son_bar["Wilders"]) if use_wilders else True
        
        durum = "BEKLE"
        if ind_sinyali and kama_ok and wilders_ok:
            durum = "AL"
        elif current_ind < esik:
            durum = "İZLE"
            
        fiyat = son_bar["Close"]
        stop_fiyat = fiyat * (1 - stop_loss_pct / 100)
        
        # Portföyde bu hisse zaten var mı?
        zaten_var = ticker.replace(".IS", "") in [p["Hisse"] for p in portfoy_sonuclari]
        
        if durum == "AL" and not zaten_var:
            risk_tutari = sermaye * (risk_pct / 100)
            birim_risk = fiyat - stop_fiyat
            lot = int(risk_tutari / birim_risk) if birim_risk > 0 else 0
            
            yeni_firsatlar.append({
                "Hisse": ticker.replace(".IS", ""),
                "Son Fiyat": round(fiyat, 2),
                "Sinyal": durum,
                "Önerilen Lot": lot,
                "Stop Fiyatı": round(stop_fiyat, 2)
            })
            
        progress.progress((i + 1) / len(hisseler), text=f"{ticker} tarandı...")
        
    progress.empty()

    # --- SONUÇLARI EKRANA YAZDIR ---
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
                
            st.dataframe(
                p_df.style.map(color_actions, subset=["Aksiyon"]),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Portföyünüzde hisse bulunmuyor.")

    with col2:
        st.markdown("### 🎯 Yeni Alım Fırsatları")
        if yeni_firsatlar:
            st.dataframe(pd.DataFrame(yeni_firsatlar), use_container_width=True, hide_index=True)
        else:
            st.info("Şu an yeni bir AL sinyali yok.")
