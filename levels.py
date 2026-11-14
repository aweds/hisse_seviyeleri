"""Destek / direnç ve işlem planı hesaplama motoru."""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Göstergeler
# --------------------------------------------------------------------------
def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def trend_label(df: pd.DataFrame) -> str:
    close = df["Close"]
    n = len(close)
    if n < 50:
        return "Belirsiz"
    sma_fast = close.rolling(50).mean().iloc[-1]
    sma_slow = close.rolling(200).mean().iloc[-1] if n >= 200 else close.mean()
    last = close.iloc[-1]
    if pd.isna(sma_fast) or pd.isna(sma_slow):
        return "Belirsiz"
    if last > sma_slow and sma_fast > sma_slow:
        return "Yükseliş"
    if last < sma_slow and sma_fast < sma_slow:
        return "Düşüş"
    return "Yatay"


# --------------------------------------------------------------------------
# Pivot noktaları
# --------------------------------------------------------------------------
def pivot_classic(h: float, l: float, c: float) -> dict[str, float]:
    p = (h + l + c) / 3.0
    return {
        "P": p,
        "R1": 2 * p - l, "S1": 2 * p - h,
        "R2": p + (h - l), "S2": p - (h - l),
        "R3": h + 2 * (p - l), "S3": l - 2 * (h - p),
    }


def pivot_fibonacci(h: float, l: float, c: float) -> dict[str, float]:
    p = (h + l + c) / 3.0
    rng = h - l
    return {
        "P": p,
        "R1": p + 0.382 * rng, "S1": p - 0.382 * rng,
        "R2": p + 0.618 * rng, "S2": p - 0.618 * rng,
        "R3": p + 1.000 * rng, "S3": p - 1.000 * rng,
    }


def camarilla(h: float, l: float, c: float) -> dict[str, float]:
    rng = (h - l) * 1.1
    return {
        "H1": c + rng / 12, "H2": c + rng / 6,
        "H3": c + rng / 4,  "H4": c + rng / 2,
        "L1": c - rng / 12, "L2": c - rng / 6,
        "L3": c - rng / 4,  "L4": c - rng / 2,
    }


# --------------------------------------------------------------------------
# Swing (fractal) seviyeleri & hacim POC
# --------------------------------------------------------------------------
def swing_levels(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[dict]:
    h = df["High"].to_numpy(dtype=float)
    l = df["Low"].to_numpy(dtype=float)
    n = len(h)
    out: list[dict] = []
    if n < left + right + 1:
        return out
    for i in range(left, n - right):
        wh = h[i - left: i + right + 1]
        wl = l[i - left: i + right + 1]
        if h[i] == wh.max() and (wh == h[i]).sum() == 1:
            out.append({"price": float(h[i]), "source": "Swing High"})
        if l[i] == wl.min() and (wl == l[i]).sum() == 1:
            out.append({"price": float(l[i]), "source": "Swing Low"})
    return out


def volume_poc(df: pd.DataFrame, bins: int = 40, lookback: int = 250) -> float | None:
    sub = df.tail(lookback)
    price = sub["Close"].to_numpy(dtype=float)
    vol = sub["Volume"].fillna(0).to_numpy(dtype=float)
    if price.size == 0 or vol.sum() <= 0:
        return None
    hist, edges = np.histogram(price, bins=bins, weights=vol)
    idx = int(hist.argmax())
    return float((edges[idx] + edges[idx + 1]) / 2.0)


# --------------------------------------------------------------------------
# Ham seviye listesi + kümeleme
# --------------------------------------------------------------------------
def build_raw_levels(
    df: pd.DataFrame,
    ma_periods: tuple[int, ...] = (20, 50, 100, 200),
    swing_window: int = 3,
) -> list[dict]:
    last = df.iloc[-1]
    h, l, c = float(last["High"]), float(last["Low"]), float(last["Close"])

    raw: list[dict] = []
    for name, val in pivot_classic(h, l, c).items():
        raw.append({"price": val, "source": f"Pivot Klasik {name}"})
    for name, val in pivot_fibonacci(h, l, c).items():
        raw.append({"price": val, "source": f"Pivot Fib {name}"})
    for name, val in camarilla(h, l, c).items():
        raw.append({"price": val, "source": f"Camarilla {name}"})

    raw.extend(swing_levels(df, swing_window, swing_window))

    for p in ma_periods:
        if len(df) >= p:
            ma = df["Close"].rolling(p).mean().iloc[-1]
            if pd.notna(ma):
                raw.append({"price": float(ma), "source": f"SMA{p}"})

    poc = volume_poc(df)
    if poc is not None:
        raw.append({"price": poc, "source": "Hacim POC"})

    yr = df.tail(252)
    if not yr.empty:
        raw.append({"price": float(yr["High"].max()), "source": "52H Zirve"})
        raw.append({"price": float(yr["Low"].min()), "source": "52H Dip"})

    return [r for r in raw if np.isfinite(r["price"]) and r["price"] > 0]


def cluster_levels(raw: list[dict], tolerance: float) -> list[dict]:
    """Yakın seviyeleri tek bir bölgede birleştirir (tek-bağ kümeleme)."""
    items = sorted(raw, key=lambda x: x["price"])
    clusters: list[dict] = []
    for it in items:
        if clusters and abs(it["price"] - clusters[-1]["price"]) <= tolerance:
            cl = clusters[-1]
            cl["_prices"].append(it["price"])
            cl["sources"].append(it["source"])
            cl["price"] = float(np.mean(cl["_prices"]))
        else:
            clusters.append(
                {"price": it["price"], "_prices": [it["price"]], "sources": [it["source"]]}
            )

    for cl in clusters:
        cl["touches"] = len(cl["_prices"])
        cl["unique_sources"] = sorted(set(cl["sources"]))
    return clusters


def strength_score(cl: dict) -> int:
    s = len(cl["unique_sources"])
    t = cl["touches"]
    return int(min(100, 15 * s + 8 * t))


# --------------------------------------------------------------------------
# Seviye tablosu
# --------------------------------------------------------------------------
def build_level_table(
    df: pd.DataFrame,
    tolerance_mult: float = 0.5,
    swing_window: int = 3,
    max_per_side: int = 8,
) -> pd.DataFrame:
    price = float(df["Close"].iloc[-1])
    a = float(atr(df).iloc[-1])
    if not np.isfinite(a) or a <= 0:
        a = price * 0.02

    tol = max(a * tolerance_mult, price * 0.001)
    clusters = cluster_levels(build_raw_levels(df, swing_window=swing_window), tol)

    rows = []
    for cl in clusters:
        p = cl["price"]
        if not np.isfinite(p) or p <= 0:
            continue
        rows.append(
            {
                "Seviye (TL)": round(p, 2),
                "Tür": "Destek" if p < price else "Direnç",
                "Güç": strength_score(cl),
                "Kaynaklar": ", ".join(cl["unique_sources"]),
                "Mesafe (%)": round((p / price - 1.0) * 100, 2),
            }
        )

    tbl = pd.DataFrame(rows)
    if tbl.empty:
        return tbl

    sup = tbl[tbl["Tür"] == "Destek"].sort_values("Güç", ascending=False).head(max_per_side)
    res = tbl[tbl["Tür"] == "Direnç"].sort_values("Güç", ascending=False).head(max_per_side)
    out = pd.concat([sup, res]).sort_values("Seviye (TL)", ascending=False)
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------
# İşlem planı
# --------------------------------------------------------------------------
def _lot(capital: float, risk_pct: float, entry: float, stop: float) -> int:
    per = entry - stop
    if per <= 0:
        return 0
    return int((capital * risk_pct / 100.0) // per)


def _first_strong(frame: pd.DataFrame, min_score: int = 40) -> pd.Series | None:
    if frame.empty:
        return None
    strong = frame[frame["Güç"] >= min_score]
    return strong.iloc[0] if not strong.empty else frame.iloc[0]


def build_trade_plan(
    df: pd.DataFrame,
    levels_df: pd.DataFrame,
    capital: float = 100_000.0,
    risk_pct: float = 1.0,
) -> tuple[pd.DataFrame, dict]:
    price = float(df["Close"].iloc[-1])
    a = float(atr(df).iloc[-1])
    if not np.isfinite(a) or a <= 0:
        a = price * 0.02

    sup = levels_df[levels_df["Tür"] == "Destek"].sort_values("Seviye (TL)", ascending=False)
    res = levels_df[levels_df["Tür"] == "Direnç"].sort_values("Seviye (TL)", ascending=True)

    s_row = _first_strong(sup.reset_index(drop=True))
    r_row = _first_strong(res.reset_index(drop=True))

    s1 = float(s_row["Seviye (TL)"]) if s_row is not None else price - 2 * a
    r1 = float(r_row["Seviye (TL)"]) if r_row is not None else price + 2 * a

    above = res[res["Seviye (TL)"] > r1 + 1e-9]
    r2 = float(above.iloc[0]["Seviye (TL)"]) if not above.empty else r1 + 2 * a

    rows = []

    # --- 1) Destekten alım (pullback) ---
    e_low, e_high = s1 - 0.25 * a, s1 + 0.25 * a
    stop = s1 - 1.0 * a
    rr1 = (r1 - s1) / (s1 - stop) if s1 > stop else np.nan
    rows.append(
        {
            "Senaryo": "🟢 Destekten Alım (Pullback)",
            "Giriş Bölgesi (TL)": f"{e_low:,.2f} – {e_high:,.2f}",
            "Stop-Loss (TL)": round(stop, 2),
            "Hedef 1 (TL)": round(r1, 2),
            "Hedef 2 (TL)": round(r2, 2),
            "R/R": round(rr1, 2) if np.isfinite(rr1) else None,
            "Önerilen Lot": _lot(capital, risk_pct, s1, stop),
        }
    )

    # --- 2) Direnç kırılımı (breakout) ---
    b_entry = r1 + 0.25 * a
    b_stop = r1 - 1.0 * a
    b_t1 = r2
    b_t2 = r2 + (r2 - r1)
    rr2 = (b_t1 - b_entry) / (b_entry - b_stop) if b_entry > b_stop else np.nan
    rows.append(
        {
            "Senaryo": "🔵 Direnç Kırılımı (Breakout)",
            "Giriş Bölgesi (TL)": f"{b_entry:,.2f} + (hacim teyidi)",
            "Stop-Loss (TL)": round(b_stop, 2),
            "Hedef 1 (TL)": round(b_t1, 2),
            "Hedef 2 (TL)": round(b_t2, 2),
            "R/R": round(rr2, 2) if np.isfinite(rr2) else None,
            "Önerilen Lot": _lot(capital, risk_pct, b_entry, b_stop),
        }
    )

    meta = {
        "price": price,
        "atr": a,
        "primary_support": s1,
        "primary_resistance": r1,
        "next_resistance": r2,
        "stop": stop,
        "entry_low": e_low,
        "entry_high": e_high,
    }
    return pd.DataFrame(rows), meta
