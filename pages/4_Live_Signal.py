import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

from data import fetch_ohlcv, normalize_ticker
from indicators import kama, stochastic_rsi, wilders_smoothing
from levels import rsi

st.set_page_config(page_title="Canlı Sinyal", page_icon="🚨", layout="wide")
st.title("🚨 Canlı Piyasa Sinyal Panosu")
st.caption("Her akşam piyasa kapandıktan sonra (veya gün içi) bu sayfayı açıp güncel sinyalleri kontrol edin.")

# --- AYARLAR ---
with st.sidebar:
    st.header("⚙️ Canlı Tarama Ayarları")
    
    # Takip listesi
    varsayilan_liste = "PATEK, ARDYZ, THYAO, ASELS, TKFEN, EREGL"
    hisse_listesi = st.text_area("Takip Listesi (Virgülle ayırın)", value=varsayilan_liste)
    
    st.markdown("---")
    gosterge_secimi = st.radio("Gösterge", ["RSI", "Stoch RSI"])
    esik = st.number_input("Aşırı Satım Eşiği", value=30)
    use_kama = st.checkbox("KAMA Filtresi (Fiyat > KAMA)", value=True)
    use_wilders = st.checkbox("Wilders Filtresi (Fiyat > Wilders)", value=True)
    
    st.markdown("---")
    st.markdown("**Sermaye & Risk**")
    sermaye = st.number_input("Toplam Sermaye (TL)", value=100000)
    risk_pct = st.number_input("İşlem Başı Risk (%)", value=2.0)
    stop_loss_pct = st.number_input("Stop-Loss (%)", value=10.0)
    
    tara = st.button("🔄 Piyasayı Tara", type="primary", use_container_width=True)

# --- TARAMA MOTORU ---
if tara:
    hisseler = [h.strip().upper() for h in hisse_listesi.split(",") if h.strip()]
    sonuclar = []
    
    progress = st.progress(0, text="Veriler çekiliyor...")
    
    for i, raw_ticker in enumerate(hisseler):
        ticker = normalize_ticker(raw_ticker)
        
        # Son 1 yıllık veriyi çek (Göstergelerin oturması için yeterli)
        df = fetch_ohlcv(ticker, interval="1d", period="1y")
        
        if df.empty or len(df) < 50:
            continue
            
        # Göstergeleri hesapla
        df["RSI"] = rsi(df, 14)
        df["Stoch_RSI"] = stochastic_rsi(df, 14)
        df["KAMA"] = kama(df["Close"], 10)
        df["Wilders"] = wilders_smoothing(df["Close"], 14)
        
        # Son iki günün verisine bak (Dönüş olmuş mu?)
        son_bar = df.iloc[-1]
        onceki_bar = df.iloc[-2]
        
        current_ind = son_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else son_bar["RSI"]
        prev_ind = onceki_bar["Stoch_RSI"] if gosterge_secimi == "Stoch RSI" else onceki_bar["RSI"]
        
        # Sinyal Mantığı
        ind_sinyali = (prev_ind < esik) and (current_ind >= esik)
        kama_ok = (son_bar["Close"] > son_bar["KAMA"]) if use_kama else True
        wilders_ok = (son_bar["Close"] > son_bar["Wilders"]) if use_wilders else True
        
        durum = "BEKLE"
        aciklama = "Şartlar oluşmadı."
        
        if ind_sinyali and kama_ok and wilders_ok:
            durum = "AL"
            aciklama = "Aşırı satımdan dönüş ve trend filtreleri uygun!"
        elif ind_sinyali and not (kama_ok and wilders_ok):
            durum = "DİKKAT"
            aciklama = "Gösterge döndü ama trend filtreleri (KAMA/Wilders) uygun değil."
        elif current_ind < esik:
            durum = "İZLE"
            aciklama = "Aşırı satım bölgesinde, dönüş bekleniyor."
            
        # Fiyat ve Lot Hesabı
        fiyat = son_bar["Close"]
        stop_fiyat = fiyat * (1 - stop_loss_pct / 100)
        
        # Lot hesabı (Riske göre)
        risk_tutari = sermaye * (risk_pct / 100)
        birim_risk = fiyat - stop_fiyat
        lot = int(risk_tutari / birim_risk) if birim_risk > 0 else 0
        
        sonuclar.append({
            "Hisse": ticker.replace(".IS", ""),
            "Son Fiyat": round(fiyat, 2),
            "Gösterge": round(current_ind, 1),
            "Sinyal": durum,
            "Açıklama": aciklama,
            "Önerilen Lot": lot,
            "Stop Fiyatı": round(stop_fiyat, 2)
        })
        
        progress.progress((i + 1) / len(hisseler), text=f"{ticker} tarandı...")
        
    progress.empty()
    
    if sonuclar:
        st.session_state["scan_results"] = pd.DataFrame(sonuclar)
    else:
        st.error("Veri çekilemedi.")

# --- EKRANA ÇİZİM ---
if "scan_results" in st.session_state:
    res_df = st.session_state["scan_results"]
    
    st.subheader("📊 Tarama Sonuçları")
    
    # Sadece "AL" verenleri en üste çıkar
    res_df["Sinyal_Oncelik"] = res_df["Sinyal"].map({"AL": 1, "DİKKAT": 2, "İZLE": 3, "BEKLE": 4})
    res_df = res_df.sort_values("Sinyal_Oncelik").drop(columns=["Sinyal_Oncelik"])
    
    # Renklendirme Fonksiyonu
    def renklendir(val):
        if val == "AL": return 'background-color: #2e7d32; color: white; font-weight: bold'
        elif val == "DİKKAT": return 'background-color: #f39c12; color: white; font-weight: bold'
        elif val == "İZLE": return 'background-color: #3498db; color: white'
        return 'background-color: #7f8c8d; color: white'
    
    # Tabloyu göster
    st.dataframe(
        res_df.style.map(renklendir, subset=["Sinyal"]),
        use_container_width=True,
        hide_index=True
    )
    
    # AL veren hisseler için özel kartlar
    al_verenler = res_df[res_df["Sinyal"] == "AL"]
    
    if not al_verenler.empty:
        st.success(f"🎯 **DİKKAT! {len(al_verenler)} Hisse AL Sinyali Verdi.** Aşağıdaki seviyeleri aracı kurumunuza girebilirsiniz.")
        
        for _, row in al_verenler.iterrows():
            with st.expander(f"🔥 {row['Hisse']} — Alım Emri Detayı", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Alış Fiyatı", f"{row['Son Fiyat']} TL")
                c2.metric("Stop-Loss (Zarar Durdur)", f"{row['Stop Fiyatı']} TL")
                c3.metric("Alınacak Lot", row['Önerilen Lot'])
                
                st.info(f"**Nasıl İşlem Yapılır?** Borsa açıldığında (10:00) bu hisseden **{row['Önerilen Lot']} lot** alış emri girin. Eğer fiyat **{row['Stop Fiyatı']} TL**'ye düşerse zararı durdurmak için satış emri verin. (Riskiniz: {sermaye * (risk_pct/100):,.0f} TL)")
    else:
        st.info("Şu an AL sinyali veren hisse bulunmuyor. Piyasayı izlemeye devam edin.")
