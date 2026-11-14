"""Veri çekme katmanı (yfinance)."""
from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

BIST_SUFFIX = ".IS"


def normalize_ticker(raw: str) -> str:
    """'patek' -> 'PATEK.IS' ; 'PATEK.IS' -> 'PATEK.IS' ; 'AAPL' -> 'AAPL'."""
    t = (raw or "").strip().upper()
    if not t:
        return t
    if "." in t:          # sembol zaten uzantılı (AAPL, PATEK.IS, XU100.IS ...)
        return t
    return t + BIST_SUFFIX


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ohlcv(ticker: str, interval: str = "1d", period: str = "2y") -> pd.DataFrame:
    """OHLCV verisini indirir. Hata durumunda boş DataFrame döner."""
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns=str.title)

    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in df.columns:
            df[col] = pd.NA

    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df = df.dropna(subset=["High", "Low", "Close"])
    df.index = pd.to_datetime(df.index)
    return df
