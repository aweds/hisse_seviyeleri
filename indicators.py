import numpy as np
import pandas as pd

# --- MEVCUT GÖSTERGELER ---

def stochastic_rsi(series: pd.Series, length: int = 14, smooth_k: int = 3) -> pd.Series:
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
    return stoch_rsi.rolling(smooth_k).mean()

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
    return sma + (std * num_std), sma, sma - (std * num_std)

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
    return df['dx'].ewm(alpha=alpha, adjust=False).mean(), df['+di'], df['-di']

def calculate_vwap(df: pd.DataFrame):
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    return (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()

def calculate_obv(df: pd.DataFrame):
    return (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()

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

# --- YENİ NESİL AZ BİLİNEN GÖSTERGELER ---

def alma(series: pd.Series, length: int = 10, sigma: float = 6.0, offset: float = 0.85) -> pd.Series:
    m = offset * (length - 1)
    s = length / sigma
    alma_vals = pd.Series(index=series.index, dtype=float)
    for i in range(length - 1, len(series)):
        window = series.iloc[i - length + 1 : i + 1]
        weights = np.exp(-((np.arange(length) - m) ** 2) / (2 * s * s))
        alma_vals.iloc[i] = np.sum(weights * window) / np.sum(weights)
    return alma_vals

def fisher_transform(df: pd.DataFrame, length: int = 10):
    high, low = df["High"], df["Low"]
    hl2 = (high + low) / 2
    max_hl = hl2.rolling(length).max()
    min_hl = hl2.rolling(length).min()
    normalized = 2 * ((hl2 - min_hl) / (max_hl - min_hl) - 0.5)
    normalized = normalized.clip(-0.999, 0.999) # log(0) hatasını önler
    fisher = np.log((1 + normalized) / (1 - normalized))
    fisher_signal = fisher.ewm(span=3, adjust=False).mean()
    return fisher, fisher_signal

def connors_rsi(series: pd.Series, rsi_length: int = 3, streak_length: int = 2, rank_length: int = 100) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/rsi_length, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/rsi_length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_part = 100 - (100 / (1 + rs))
    
    # Basitleştirilmiş Streak RSI
    streak = np.sign(delta)
    streak_rsi = streak.rolling(streak_length).mean() * 50 + 50 
    
    roc = series.pct_change()
    rank_part = roc.rolling(rank_length).rank(pct=True) * 100
    return (rsi_part + streak_rsi + rank_part) / 3

def coppock_curve(series: pd.Series, wma_length: int = 10, roc1: int = 11, roc2: int = 14) -> pd.Series:
    roc_sum = series.pct_change(roc1) * 100 + series.pct_change(roc2) * 100
    weights = np.arange(1, wma_length + 1)
    return roc_sum.rolling(wma_length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def mass_index(df: pd.DataFrame, ema_length: int = 9) -> pd.Series:
    high_low = df["High"] - df["Low"]
    ema1 = high_low.ewm(span=ema_length, adjust=False).mean()
    ema2 = ema1.ewm(span=ema_length, adjust=False).mean()
    mass = ema1 / ema2
    return mass.rolling(25).sum()
