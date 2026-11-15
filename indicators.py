import numpy as np
import pandas as pd

def stochastic_rsi(series: pd.Series, length: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> pd.Series:
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
    k = stoch_rsi.rolling(smooth_k).mean()
    return k

def kama(series: pd.Series, length: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    vol = series.diff().abs().rolling(length).sum()
    change = (series - series.shift(length)).abs()
    er = change / vol.replace(0, np.nan)
    er = er.fillna(0)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    kama_vals = np.zeros(len(series))
    kama_vals[:] = np.nan
    if len(series) > length:
        kama_vals[length] = series.iloc[1:length+1].mean()
    for i in range(length + 1, len(series)):
        kama_vals[i] = kama_vals[i-1] + sc.iloc[i] * (series.iloc[i] - kama_vals[i-1])
    return pd.Series(kama_vals, index=series.index)

def wilders_smoothing(series: pd.Series, length: int = 14) -> pd.Series:
    return series.ewm(alpha=1.0 / length, adjust=False).mean()

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def ema(series: pd.Series, length: int = 50) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, sma, lower_band

def calculate_adx(df: pd.DataFrame, period: int = 14):
    df = df.copy()
    df['h_l'] = df['High'] - df['Low']
    df['h_pc'] = (df['High'] - df['Close'].shift(1)).abs()
    df['l_pc'] = (df['Low'] - df['Close'].shift(1)).abs()
    df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis=1)
    df['up_move'] = df['High'] - df['High'].shift(1)
    df['down_move'] = df['Low'].shift(1) - df['Low']
    df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    alpha = 1 / period
    df['tr_smooth'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()
    df['+di'] = 100 * (df['+dm'].ewm(alpha=alpha, adjust=False).mean() / df['tr_smooth'])
    df['-di'] = 100 * (df['-dm'].ewm(alpha=alpha, adjust=False).mean() / df['tr_smooth'])
    df['dx'] = (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])) * 100
    df['adx'] = df['dx'].ewm(alpha=alpha, adjust=False).mean()
    return df['adx'], df['+di'], df['-di']

def calculate_vwap(df: pd.DataFrame):
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()
    return vwap

def calculate_obv(df: pd.DataFrame):
    obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
    return obv

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    hl2 = (df['High'] + df['Low']) / 2
    df['tr'] = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    upper_band = hl2 + (multiplier * df['atr'])
    lower_band = hl2 - (multiplier * df['atr'])
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    supertrend.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = -1
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > upper_band.iloc[i-1]: direction.iloc[i] = 1
        elif df['Close'].iloc[i] < lower_band.iloc[i-1]: direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i-1]: lower_band.iloc[i] = lower_band.iloc[i-1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i-1]: upper_band.iloc[i] = upper_band.iloc[i-1]
        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]
    return supertrend, direction
