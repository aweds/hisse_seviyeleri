"""Streamlit arayüzü."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from levels import atr, build_level_table, build_trade_plan, rsi, trend_label
# YENİ EKLENEN GÖSTERGELER
from indicators import kama, stochastic_rsi, wilders_smoothing

st.set_page_config(
    page_title="BIST Destek/Direnç & İşlem Planı",
    page_icon="📈",
    layout="wide",
)

# --------------------------------------------------------------------------
# Kenar çubuğu (Sidebar)
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Ayarlar")
    raw_ticker = st.text_input("Hisse Kodu", value="PATEK", help="Örn: PATEK, THYAO, ASELS")
    tf = st.selectbox("Zaman Dilimi", ["Günlük", "Haftalık", "Aylık"], index=0)

    interval, period = {
        "Günlük": ("1d", "2y"),
        "Haftalık": ("1wk", "5y"),
        "Aylık": ("1mo", "10y"),
    }[tf]

    st.divider()
    st.subheader("Seviye Motoru")
    swing_window = st.slider("Swing penceresi", 2, 7, 3)
    tolerance_mult = st.slider("Kümeleme toleransı (×ATR)", 0.1, 2.0, 0.5, 0.1)
    max_per_side = st.slider("Taraf başına seviye", 3, 15, 8)

    st.divider()
    st.subheader("Pozisyon Boyutlandırma")
    capital = st.number_input("Sermaye (TL)", min_value=1_000.0, value=100_000.0, step=10_000.0)
    risk_pct = st.number_input("İşlem başına risk (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)

    st.divider()
    if st.button("🔄 Veriyi Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

ticker = normalize_ticker(raw_ticker)

# --------------------------------------------------------------------------
# Veri
# --------------------------------------------------------------------------
with st.spinner(f"{ticker} verisi indiriliyor..."):
    df = fetch_ohlcv(ticker, interval=interval, period=period)

st.title("📈 Destek / Direnç & İşlem Planı")
st.caption(f"Sembol: **{ticker}** · Zaman dilimi: **{tf}** · Veri: yfinance")

if df.empty or len(df) < 20:
    st.error(
        f"**{ticker}** için yeterli veri alınamadı.\n\n"
        "• Sembolü kontrol edin (BIST için `.IS` otomatik eklenir).\n"
        "• İnternet bağlantınızı kontrol edin.\n"
        "• Birkaç dakika sonra tekrar deneyin (rate limit)."
    )
    st.stop()

# --------------------------------------------------------------------------
# Göstergeleri Hesapla (Tüm veri için, grafikte son 220 barı kullanacağız)
# --------------------------------------------------------------------------
df["RSI_14"] = rsi(df, 14)
df["KAMA_10"] = kama(df["Close"], 10)
df["Wilders_14"] = wilders_smoothing(df["Close"], 14)
df["StochRSI"] = stochastic_rsi(df["Close"])

# --------------------------------------------------------------------------
# Özet metrikler
# --------------------------------------------------------------------------
price = float(df["Close"].iloc[-1])
prev = float(df["Close"].iloc[-2]) if len(df) > 1 else price
chg = (price / prev - 1.0) * 100.0
atr_val = float(atr(df).iloc[-1])
rsi_val = float(df["RSI_14"].iloc[-1])
stoch_val = float(df["StochRSI"].iloc[-1])
trend = trend_label(df)

# Üst Metrikler
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Son Fiyat", f"{price:,.2f} TL", f"{chg:+.2f}%")
c2.metric("ATR (14)", f"{atr_val:,.2f} TL", f"{atr_val / price * 100:.1f}%")
c3.metric("RSI (14)", f"{rsi_val:.1f}")
c4.metric("Stoch RSI", f"{stoch_val:.1f}")
c5.metric("Trend", trend)
c6.metric("Veri Sayısı", f"{len(df)} bar")

# --------------------------------------------------------------------------
# Hesaplama (Destek/Direnç ve Plan)
# --------------------------------------------------------------------------
levels_df = build_level_table(
    df, tolerance_mult=tolerance_mult, swing_window=swing_window, max_per_side=max_per_side
)

if levels_df.empty:
    st.warning("Seviye üretilemedi. Parametreleri değiştirmeyi deneyin.")
    st.stop()

plan_df, meta = build_trade_plan(df, levels_df, capital=capital, risk_pct=risk_pct)

# --------------------------------------------------------------------------
# Grafik (Altlı Üstlü - Fiyat & RSI)
# --------------------------------------------------------------------------
st.subheader("🕯️ Fiyat Grafiği, Seviyeler ve Göstergeler")
sub = df.tail(220)

# 2 satırlı grafik oluştur (Üst: Fiyat, Alt: RSI/Stoch)
fig = make_subplots(
    rows=2, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.03,
    row_heights=[0.75, 0.25]
)

# --- ÜST GRAFİK: MUM VE ÇİZGİLER ---
fig.add_trace(
    go.Candlestick(
        x=sub.index,
        open=sub["Open"], high=sub["High"], low=sub["Low"], close=sub["Close"],
        name="Fiyat",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1
)

# KAMA Çizgisi
fig.add_trace(go.Scatter(
    x=sub.index, y=sub["KAMA_10"], mode='lines', name='KAMA (10)', 
    line=dict(color='#f39c12', width=2)
), row=1, col=1)

# Wilders Çizgisi
fig.add_trace(go.Scatter(
    x=sub.index, y=sub["Wilders_14"], mode='lines', name='Wilders (14)', 
    line=dict(color='#8e44ad', width=1.5, dash='dot')
), row=1, col=1)

# Destek/Direnç Çizgileri
for _, row in levels_df.iterrows():
    color = "#2e7d32" if row["Tür"] == "Destek" else "#c62828"
    dash = "solid" if row["Güç"] >= 60 else "dot"
    fig.add_hline(
        y=row["Seviye (TL)"],
        line=dict(color=color, width=1.2, dash=dash),
        annotation_text=f'{row["Seviye (TL)"]:.2f}',
        annotation_position="right",
        annotation_font_size=10,
        annotation_font_color=color,
        row=1, col=1
    )

# --- ALT GRAFİK: RSI VE STOCH RSI ---
fig.add_trace(go.Scatter(
    x=sub.index, y=sub["RSI_14"], mode='lines', name='RSI (14)', 
    line=dict(color='#3498db', width=1.5)
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=sub.index, y=sub["StochRSI"], mode='lines', name='Stoch RSI', 
    line=dict(color='#e67e22', width=1.5)
), row=2, col=1)

# RSI Aşırı Alım/Satım Çizgileri (30 ve 70)
fig.add_hline(y=70, line_dash="dash", line_color="#c62828", opacity=0.5, row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="#2e7d32", opacity=0.5, row=2, col=1)

# Grafik Genel Ayarları
fig.update_layout(
    height=850,
    xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=70, t=20, b=10),
    showlegend=True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_white",
)
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------
# Seviye tablosu
# --------------------------------------------------------------------------
st.subheader("📊 Destek & Direnç Tablosu")
st.caption("Güç skoru: kümedeki farklı kaynak sayısı ve temas sayısına göre 0–100 arası.")

st.dataframe(
    levels_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Güç": st.column_config.ProgressColumn(
            "Güç", min_value=0, max_value=100, format="%d"
        ),
        "Seviye (TL)": st.column_config.NumberColumn(format="%.2f"),
        "Mesafe (%)": st.column_config.NumberColumn(format="%+.2f%%"),
    },
)

csv = levels_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
st.download_button(
    "⬇️ Seviye tablosunu CSV indir",
    data=csv,
    file_name=f"{ticker}_seviyeler.csv",
    mime="text/csv",
)

# --------------------------------------------------------------------------
# İşlem planı
# --------------------------------------------------------------------------
st.subheader("🎯 Alım / Satım Planı")

st.dataframe(
    plan_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Stop-Loss (TL)": st.column_config.NumberColumn(format="%.2f"),
        "Hedef 1 (TL)": st.column_config.NumberColumn(format="%.2f"),
        "Hedef 2 (TL)": st.column_config.NumberColumn(format="%.2f"),
        "R/R": st.column_config.NumberColumn(format="%.2f"),
    },
)

col_a, col_b = st.columns(2)
with col_a:
    st.success(
        f"**Ana Destek:** {meta['primary_support']:,.2f} TL  \n"
        f"**Ana Direnç:** {meta['primary_resistance']:,.2f} TL  \n"
        f"**Sonraki Direnç:** {meta['next_resistance']:,.2f} TL"
    )
with col_b:
    st.info(
        f"**Önerilen Stop:** {meta['stop']:,.2f} TL  \n"
        f"**Alım Bölgesi:** {meta['entry_low']:,.2f} – {meta['entry_high']:,.2f} TL  \n"
        f"**Risk/Birim:** {meta['atr']:,.2f} TL (1×ATR)"
    )

plan_csv = plan_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
st.download_button(
    "⬇️ İşlem planını CSV indir",
    data=plan_csv,
    file_name=f"{ticker}_islem_plani.csv",
    mime="text/csv",
)

# --------------------------------------------------------------------------
# Metodoloji + uyarı
# --------------------------------------------------------------------------
with st.expander("🧠 Metodoloji — seviyeler ve göstergeler nasıl hesaplanıyor?"):
    st.markdown(
        """
**Ham seviye kaynakları**
- **Pivot Klasik** (P, R1–R3, S1–S3)
- **Pivot Fibonacci** (0.382 / 0.618 / 1.000)
- **Camarilla** (H1–H4, L1–L4)
- **Swing High / Swing Low** — `n` barlık fractal penceresi
- **SMA 20 / 50 / 100 / 200** — dinamik destek-direnç
- **Hacim POC** — son 250 barın hacim ağırlıklı tepe fiyatı
- **52 hafta zirve / dip**

**Göstergeler**
- **KAMA (Kaufman Adaptive Moving Average):** Piyasa yatayken yavaşlar, trend başladığında hızlanır. Fiyatın KAMA üzerinde olması güçlü yükseliş trendine işaret eder.
- **Wilders Smoothing:** Fiyat hareketlerini yumuşatarak ana trendi gösterir.
- **RSI ve Stoch RSI:** Aşırı alım (70 üzeri) ve aşırı satım (30 altı) bölgelerini gösterir. Stoch RSI, RSI'ın son 14 gün içindeki konumunu yüzdelik olarak ifade eder.

**Kümeleme:** Birbirine `tolerans × ATR` mesafesinden yakın seviyeler tek bölgede birleştirilir.
**Güç skoru:** `min(100, 15 × farklı_kaynak + 8 × temas_sayısı)`
**İşlem planı:** En güçlü destek/direnç bölgeleri seçilir; stop `1×ATR` uzağa, hedefler karşı taraftaki bölgelere konur. Lot = `(Sermaye × Risk%) / (Giriş − Stop)`.
        """
    )

st.warning(
    "⚠️ **Yasal Uyarı:** Bu uygulama yalnızca eğitim/analiz amaçlıdır ve **yatırım tavsiyesi değildir**. "
    "Seviyeler ve göstergeler geçmiş fiyat verisinden türetilir; geleceği garanti etmez. "
    "Yatırım kararlarınızı kendi araştırmanız ve bir yatırım danışmanı ile birlikte verin."
)
