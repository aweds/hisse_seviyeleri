"""Veri çekme katmanı (yfinance). Streamlit ve CLI'da çalışır."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

BIST_SUFFIX = ".IS"

# Streamlit context'inde miyiz? (CLI / GitHub Actions için False)
try:
    import streamlit as _st
    from streamlit.runtime.scriptrunner import get_script_run_ctx as _get_ctx
    _IN_STREAMLIT = _get_ctx() is not None
except Exception:
    _IN_STREAMLIT = False


def _cache(ttl: int):
    """Streamlit context'inde cache, değilse no-op."""
    if _IN_STREAMLIT:
        return _st.cache_data(ttl=ttl, show_spinner=False)
    return lambda f: f


def normalize_ticker(raw: str) -> str:
    t = (raw or "").strip().upper()
    if not t:
        return t
    if "." in t:
        return t
    return t + BIST_SUFFIX


@_cache(900)
def fetch_ohlcv(ticker: str, interval: str = "1d", period: str = "2y") -> pd.DataFrame:
    try:
        df = yf.download(
            ticker, period=period, interval=interval,
            auto_adjust=False, progress=False, threads=False,
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
