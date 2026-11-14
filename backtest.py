"""Destek/direnç seviyelerinin geçmiş performansını ölçen backtest motoru."""
from __future__ import annotations

import numpy as np
import pandas as pd

from levels import atr, build_raw_levels, cluster_levels, strength_score


def _detect_clusters(df_slice: pd.DataFrame, tol: float, swing_window: int) -> list[dict]:
    raw = build_raw_levels(df_slice, swing_window=swing_window)
    clusters = cluster_levels(raw, tol)
    for cl in clusters:
        cl["strength"] = strength_score(cl)
    return clusters


def _is_new_vs_prev(curr: list[dict], prev: list[dict], tol: float) -> list[dict]:
    """Bu barda YENİ oluşan seviyeler (önceki barda yoktu)."""
    if not prev:
        return curr
    prev_prices = [p["price"] for p in prev]
    return [c for c in curr if not any(abs(c["price"] - pp) <= tol for pp in prev_prices)]


def _test_level(
    forward: pd.DataFrame,
    level_price: float,
    kind: str,  # "support" | "resistance"
    touch_tol: float,
    break_tol: float,
) -> dict:
    """Bir seviyenin forward barlarda test edilip tuttuğunu/kırıldığını ölçer."""
    res = {
        "tested": False, "held": False, "broken": False,
        "bars_to_touch": None, "bars_to_resolve": None, "post_move": 0.0,
    }
    if forward.empty:
        return res

    highs  = forward["High"].to_numpy(dtype=float)
    lows   = forward["Low"].to_numpy(dtype=float)
    closes = forward["Close"].to_numpy(dtype=float)

    if kind == "support":
        touch_mask = lows <= level_price + touch_tol
        break_mask = closes < level_price - break_tol
    else:
        touch_mask = highs >= level_price - touch_tol
        break_mask = closes > level_price + break_tol

    if not touch_mask.any():
        return res

    touch_idx = int(np.argmax(touch_mask))
    res["tested"] = True
    res["bars_to_touch"] = touch_idx + 1

    future_break = break_mask[touch_idx:]
    if future_break.any():
        res["broken"] = True
        rel = int(np.argmax(future_break))
        res["bars_to_resolve"] = touch_idx + rel + 1
        # Kırılım yönünde ne kadar ilerledi (%)
        res["post_move"] = (
            (closes[-1] - level_price) / level_price if kind == "support"
            else (level_price - closes[-1]) / level_price
        )
    else:
        res["held"] = True
        res["bars_to_resolve"] = len(forward)
        # Tepki yönünde ne kadar hareket etti (%)
        res["post_move"] = (
            (closes[-1] - level_price) / level_price if kind == "support"
            else (level_price - closes[-1]) / level_price
        )
    return res


def run_backtest(
    df: pd.DataFrame,
    horizon: int = 20,
    swing_window: int = 3,
    tol_mult: float = 0.5,
    touch_mult: float = 0.25,
    break_mult: float = 0.75,
    warmup: int = 60,
    progress_cb=None,
) -> pd.DataFrame:
    n = len(df)
    if n < warmup + horizon + 20:
        return pd.DataFrame()

    atr_series = atr(df)
    records: list[dict] = []
    prev_clusters: list[dict] = []

    for i in range(warmup, n - horizon):
        slice_df = df.iloc[: i + 1]
        a = float(atr_series.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue

        close_i = float(df["Close"].iloc[i])
        tol = max(a * tol_mult, close_i * 0.001)
        touch_tol = a * touch_mult
        break_tol = a * break_mult

        clusters = _detect_clusters(slice_df, tol, swing_window)
        new_clusters = _is_new_vs_prev(clusters, prev_clusters, tol)
        forward = df.iloc[i + 1 : i + 1 + horizon]

        for cl in new_clusters:
            p = cl["price"]
            if not np.isfinite(p) or p <= 0:
                continue
            if abs(p - close_i) / close_i < 0.001:
                continue

            kind = "support" if p < close_i else "resistance"
            t = _test_level(forward, p, kind, touch_tol, break_tol)
            if not t["tested"]:
                continue

            records.append({
                "date_detected": df.index[i],
                "level": round(p, 2),
                "kind": kind,
                "strength": cl["strength"],
                "sources": ", ".join(cl["unique_sources"]),
                "touches": cl["touches"],
                "held": t["held"],
                "broken": t["broken"],
                "bars_to_touch": t["bars_to_touch"],
                "bars_to_resolve": t["bars_to_resolve"],
                "post_move": round(t["post_move"], 4),
            })

        prev_clusters = clusters
        if progress_cb and (i - warmup) % 20 == 0:
            progress_cb((i - warmup) / max(1, n - horizon - warmup))

    return pd.DataFrame(records)


def _agg(g: pd.DataFrame) -> pd.Series:
    tested = len(g)
    held = int(g["held"].sum())
    broken = int(g["broken"].sum())
    held_g = g[g["held"]]
    broken_g = g[g["broken"]]
    return pd.Series({
        "Test": tested,
        "Tutan": held,
        "Kırılan": broken,
        "Tutma %": round(100 * held / tested, 1) if tested else 0.0,
        "Ort. Tepki %": round(100 * held_g["post_move"].mean(), 2) if len(held_g) else None,
        "Ort. Kırılım %": round(100 * broken_g["post_move"].mean(), 2) if len(broken_g) else None,
        "Ort. Bar→Temas": round(g["bars_to_touch"].mean(), 1) if len(g) else None,
    })


def summarize(results: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if results.empty:
        return out

    out["Genel"] = pd.DataFrame([_agg(results)])
    out["Tür"]   = results.groupby("kind").apply(_agg).reset_index()
    out["Kaynak"] = results.groupby("sources").apply(_agg).reset_index()

    bins = [0, 40, 55, 70, 100]
    labels = ["Zayıf (0-40)", "Orta (40-55)", "Güçlü (55-70)", "Çok Güçlü (70+)"]
    r = results.copy()
    r["bucket"] = pd.cut(r["strength"], bins=bins, labels=labels, include_lowest=True)
    out["Güç"] = r.groupby("bucket", observed=False).apply(_agg).reset_index()

    return out
