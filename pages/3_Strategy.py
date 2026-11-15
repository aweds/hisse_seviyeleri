import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from indicators import kama, stochastic_rsi, wilders_smoothing
from levels import rsi

st.set_page_config(page_title="Strateji Testi", page_icon="🧪", layout="wide")
st.title("🧪 Bilimsel Strateji Backtest")
st.caption("Sermaye, Lot, Komisyon ve Kâr/Zarar Simülasyonu")

# --- KENAR ÇUBUĞU (SIDEBAR) AYARLARI ---
with st.sidebar:
    st.header("⚙️ Strateji Ayarları")
    raw = st.text_input("Hisse", "ARDYZ")
    period = st.selectbox("Test Periyodu", ["1y", "2y", "5y"], index=1)
    
    st.markdown("---")
    gosterge_secimi = st.radio("Kullanılacak Gösterge", ["RSI", "Stoch RSI"])
    varsayilan_esik = 30
    esik = st.number_input("Aşırı Satım Eşiği (Altı)", value=varsayilan_esik)
    ind_length = st.number_input("Gösterge Periyodu", value=14)
    
    st.markdown("**Filtreler**")
    use_kama = st.checkbox("Fiyat KAMA'nın üzerinde olsun", value=True)
    kama_length = st.number_input("KAMA Periyodu", value=10, disabled=not use_kama)
    use_wilders = st.checkbox("Fiyat Wilders'ın üzerinde olsun", value=True)
    wilders_length = st.number_input("Wilders Periyodu", value=14, disabled=not use_wilders)
    
    # YENİ EKLENEN FİLTRE
    use_stoch_below_rsi = st.checkbox("Stoch RSI < RSI şartı", value=False, help="Yükselişin daha yeni başladığını teyit etmek için.")
    
    st.markdown("---")
    st.markdown("**💰 Sermaye ve Risk**")
    baslangic_sermayesi = st.number_input("Başlangıç Sermayesi (TL)", value=100000, step=10000)
    komisyon_pct = st.number_input("Komisyon Oranı (Tek Yön) %", value=0.1, step=0.1)
    
    st.markdown("**Çıkış Stratejisi**")
    hold_days = st.number_input("Maksimum Gün", value=15)
    stop_loss_pct = st.number_input("Zarar Durdur (Stop-Loss) %", value=10.0, step=1.0)
    take_profit_pct = st.number_input("Kâr Al (Take-Profit) %", value=25.0, step=1.0)
    
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
    
    current_ind = df["RSI"] if gosterge_secimi == "RSI" else df["Stoch_RSI"]
    base_signal = (current_ind.shift(1) < esik) & (current_ind >= esik)
    
    kama_condition = df["Close"] > df["KAMA"] if use_kama else pd.Series(True, index=df.index)
    wilders_condition = df["Close"] > df["Wilders"] if use_wilders else pd.Series(True, index=df.index)
    
    # YENİ FİLTRE MANTIĞI
    stoch_vs_rsi_condition = (df["Stoch_RSI"] < df["RSI"]) if use_stoch_below_rsi else pd.Series(True, index=df.index)
    
    df["Signal"] = base_signal & kama_condition & wilders_condition & stoch_vs_rsi_condition
    
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
            days_held = i - entry_idx
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
            elif days_held >= hold_days:
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
                    "Giriş Tarihi": df.index[entry_idx].strftime("%Y-%m-%d"),
                    "Çıkış Tarihi": current_date.strftime("%Y-%m-%d"),
                    "Giriş Fiyatı": round(entry_price, 2),
                    "Çıkış Fiyatı": round(exit_price, 2),
                    "Lot": lot,
                    "Net Kâr/Zarar (TL)": round(net_kar_tl, 2),
                    "Getiri (%)": round(getiri_pct, 2),
                    "Çıkış Nedeni": exit_reason,
                    "Gün": days_held,
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
        st.warning("Hiç işlem üretilmedi.")
        st.stop()
        
    nihai_portfoy = kasa_nakit
    if in_position:
        nihai_portfoy += (lot * df["Close"].iloc[-1])
        
    st.session_state["bt_res_df"] = res_df
    st.session_state["bt_ticker"] = ticker
    st.session_state["bt_baslangic"] = baslangic_sermayesi
    st.session_state["bt_nihai"] = nihai_portfoy
    st.session_state["bt_ind_name"] = gosterge_secimi
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
    
    st.subheader(f"📌 {ticker} — Portföy Sonuçları")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Başlangıç Sermayesi", f"{baslangic:,.0f} TL")
    c2.metric("Son Portföy Değeri", f"{nihai_portfoy:,.0f} TL", f"%{toplam_getiri:.1f}")
    c3.metric("Toplam Net Kâr", f"{toplam_kar:,.0f} TL")
    c4.metric("Başarı Oranı", f"%{win_rate:.1f}", f"{len(res_df)} Kapanan İşlem")

    act = st.session_state["bt_active_details"]
    durum_text = "AÇIK POZİSYON VAR (Hisse Sende)" if in_position else "BEKLEMEDE (Nakit Var)"
    st.markdown(f"### 🎯 Son Durum ve Aksiyon Planı — **{durum_text}**")
    st.info(f"**Güncel Fiyat:** {act['entry']:.2f} TL | **Kasadaki Nakit:** {act['kasa']:,.0f} TL")
    
    colA, colB, colC = st.columns(3)
    colA.error(f"🛑 **Stop-Loss**\n\nFiyat: {act['stop']:.2f} TL\n\nZarar: -%{((act['stop']/act['entry'])-1)*-100:.1f}")
    colB.success(f"🎯 **Kâr Al**\n\nFiyat: {act['target']:.2f} TL\n\nKâr: +%{((act['target']/act['entry'])-1)*100:.1f}")
    colC.info(f"📦 **Lot & Potansiyel**\n\nMevcut/Alınacak Lot: {act['lot']}\n\nHedefteki Kâr: {act['lot'] * (act['target']-act['entry']):,.0f} TL")

    st.markdown("### 📈 Sermaye Büyüme Grafiği")
    eq_df = res_df[["Çıkış Tarihi", "Portföy Değeri"]].copy()
    eq_df.loc[-1] = ["Başlangıç", baslangic]
    eq_df.index = eq_df.index + 1
    eq_df = eq_df.sort_index()
    
    fig_eq = px.line(eq_df, x="Çıkış Tarihi", y="Portföy Değeri", markers=True, title="Bileşik Getiri")
    fig_eq.update_traces(line_color="#2e7d32", line_width=3)
    st.plotly_chart(fig_eq, use_container_width=True)

    st.markdown("#### Detaylı İşlem Defteri (TL ve Lot Bazında)")
    st.dataframe(res_df, use_container_width=True, hide_index=True)
