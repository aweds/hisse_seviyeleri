import pandas as pd
import plotly.express as px
import streamlit as st

from data import fetch_ohlcv, normalize_ticker
from backtest import run_backtest, summarize

st.set_page_config(page_title="Backtest", page_icon="📊", layout="wide")
st.title("📊 Destek/Direnç Backtest")
st.caption("Geçmişte tespit edilen seviyelerin tutma / kırılma oranları")

with st.sidebar:
    st.header("⚙️ Parametreler")
    raw = st.text_input("Hisse", "PATEK")
    period = st.selectbox("Periyot", ["1y", "2y", "5y", "10y"], index=1)
    horizon = st.slider("Forward horizon (bar)", 5, 60, 20)
    swing_window = st.slider("Swing penceresi", 2, 7, 3)
    tol_mult = st.slider("Kümeleme toleransı (×ATR)", 0.1, 2.0, 0.5, 0.1)
    touch_mult = st.slider("Temas toleransı (×ATR)", 0.1, 1.0, 0.25, 0.05)
    break_mult = st.slider("Kırılım toleransı (×ATR)", 0.25, 2.0, 0.75, 0.05)
    run = st.button("▶️ Backtest çalıştır", type="primary", use_container_width=True)

ticker = normalize_ticker(raw)

if run:
    df = fetch_ohlcv(ticker, interval="1d", period=period)
    if df.empty or len(df) < 150:
        st.error("Yetersiz veri (en az ~150 bar gerekli). Daha uzun periyot deneyin.")
        st.stop()

    progress = st.progress(0.0, text="Backtest çalışıyor...")
    results = run_backtest(
        df,
        horizon=horizon,
        swing_window=swing_window,
        tol_mult=tol_mult,
        touch_mult=touch_mult,
        break_mult=break_mult,
        progress_cb=lambda p: progress.progress(
            min(1.0, max(0.0, p)), text=f"Backtest... %{int(p*100)}"
        ),
    )
    progress.empty()

    if results.empty:
        st.warning("Hiç test üretilmedi. Parametreleri / periyodu değiştirin.")
        st.stop()

    st.session_state["bt_results"] = results
    st.session_state["bt_ticker"] = ticker

if "bt_results" in st.session_state:
    results = st.session_state["bt_results"]
    ticker = st.session_state.get("bt_ticker", ticker)

    st.subheader(f"📌 {ticker} — Sonuçlar")

    total = len(results)
    held = int(results["held"].sum())
    broken = int(results["broken"].sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Test", total)
    c2.metric("Tutma %", f"{100*held/max(1,total):.1f}%", f"{held}")
    c3.metric("Kırılma %", f"{100*broken/max(1,total):.1f}%", f"{broken}")
    c4.metric("Ort. Bar→Temas", f"{results['bars_to_touch'].mean():.1f}")

    sums = summarize(results)

    st.markdown("#### Genel Özet")
    st.dataframe(sums["Genel"], use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Destek vs Direnç")
        st.dataframe(sums["Tür"], use_container_width=True, hide_index=True)
    with col2:
        st.markdown("#### Güç Kovaları")
        st.dataframe(sums["Güç"], use_container_width=True, hide_index=True)

    st.markdown("#### Kaynak Bazında (en az 3 test)")
    kaynak = sums["Kaynak"][sums["Kaynak"]["Test"] >= 3].sort_values("Test", ascending=False)
    st.dataframe(kaynak, use_container_width=True, hide_index=True)

    if not kaynak.empty:
        fig = px.bar(
            kaynak.sort_values("Tutma %").tail(15),
            x="Tutma %", y="Kaynak", orientation="h",
            color="Test", text="Test",
            title="Kaynak bazında tutma oranı (%)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Zaman Serisi (aylık)")
    results = results.copy()
    results["month"] = pd.to_datetime(results["date_detected"]).dt.to_period("M").astype(str)
    monthly = (
        results.groupby(["month", "held"]).size()
        .unstack(fill_value=0).reset_index()
    )
    monthly.columns = ["Ay", "Kırılan", "Tutan"][: len(monthly.columns)]
    st.dataframe(monthly, use_container_width=True, hide_index=True)

    csv = results.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "⬇️ Ham sonuçları CSV indir",
        data=csv, file_name=f"{ticker}_backtest.csv", mime="text/csv",
    )
