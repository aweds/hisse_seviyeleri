"""İleri düzey göstergeler (KAMA, Stoch RSI, Wilder)."""
import numpy as np
import pandas as pd

def stochastic_rsi(series: pd.Series, length: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> pd.Series:
    """Stochastic RSI hesaplar (0-100 arası)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    rsi_min = rsi.rolling(length).min()
    rsi_max = rsi.rolling(length).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
    
    # K ve D yumuşatması
    k = stoch_rsi.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k  # Genelde K değeri kullanılır

def kama(series: pd.Series, length: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average (KAMA) hesaplar."""
    vol = series.diff().abs().rolling(length).sum()
    change = (series - series.shift(length)).abs()
    
    # Verimlilik Oranı (Efficiency Ratio)
    er = change / vol.replace(0, np.nan)
    er = er.fillna(0)
    
    # Düzleştirme Sabiti (Smoothing Constant)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    
    # KAMA Hesaplama
    kama_vals = np.zeros(len(series))
    kama_vals[:] = np.nan
    
    # İlk değer için SMA kullan
    if len(series) > length:
        kama_vals[length] = series.iloc[1:length+1].mean()
        
    for i in range(length + 1, len(series)):
        kama_vals[i] = kama_vals[i-1] + sc.iloc[i] * (series.iloc[i] - kama_vals[i-1])
        
    return pd.Series(kama_vals, index=series.index)

def wilders_smoothing(series: pd.Series, length: int = 14) -> pd.Series:
    """Wilder's Smoothing (RMA - Wilder Hareketli Ortalaması)."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()
