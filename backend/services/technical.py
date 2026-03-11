import pandas as pd
import ta


def compute_indicators(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 20:
        return _empty_indicators()

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # RSI (14)
    rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD (12, 26, 9)
    macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()
    macd_hist = macd_obj.macd_diff()

    # Bollinger Bands (20, 2)
    bb_obj = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_upper = bb_obj.bollinger_hband()
    bb_middle = bb_obj.bollinger_mavg()
    bb_lower = bb_obj.bollinger_lband()

    # Moving Averages
    sma_20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma_50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    sma_200 = ta.trend.SMAIndicator(close, window=200).sma_indicator()
    ema_12 = ta.trend.EMAIndicator(close, window=12).ema_indicator()
    ema_26 = ta.trend.EMAIndicator(close, window=26).ema_indicator()

    # ATR (14)
    atr_series = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # Volume SMA (20)
    vol_sma = ta.trend.SMAIndicator(volume.astype(float), window=20).sma_indicator()

    # Stochastic RSI (14, 14, 3, 3)
    stoch_rsi_obj = ta.momentum.StochRSIIndicator(close, window=14, smooth1=3, smooth2=3)
    stoch_rsi_k = stoch_rsi_obj.stochrsi_k()
    stoch_rsi_d = stoch_rsi_obj.stochrsi_d()

    # On-Balance Volume (OBV)
    obv_series = ta.volume.OnBalanceVolumeIndicator(close, volume.astype(float)).on_balance_volume()

    # Average Directional Index (ADX, 14)
    adx_obj = ta.trend.ADXIndicator(high, low, close, window=14)
    adx_series = adx_obj.adx()
    adx_pos = adx_obj.adx_pos()
    adx_neg = adx_obj.adx_neg()

    # VWAP (cumulative for the dataset)
    typical_price = (high + low + close) / 3
    cum_vol = volume.astype(float).cumsum()
    cum_tp_vol = (typical_price * volume.astype(float)).cumsum()
    vwap_series = cum_tp_vol / cum_vol.replace(0, float("nan"))

    # Ichimoku Cloud
    ichi_obj = ta.trend.IchimokuIndicator(high, low, window1=9, window2=26, window3=52)
    ichi_conv = ichi_obj.ichimoku_conversion_line()  # Tenkan-sen
    ichi_base = ichi_obj.ichimoku_base_line()  # Kijun-sen
    ichi_a = ichi_obj.ichimoku_a()  # Senkou Span A
    ichi_b = ichi_obj.ichimoku_b()  # Senkou Span B

    def safe_last(series):
        vals = series.dropna()
        return round(float(vals.iloc[-1]), 4) if len(vals) > 0 else None

    def safe_list(series, n=60):
        vals = series.tail(n).fillna(0).tolist()
        return [round(float(v), 4) for v in vals]

    return {
        "rsi": safe_last(rsi_series),
        "rsi_history": safe_list(rsi_series),
        "macd_line": safe_last(macd_line),
        "macd_signal": safe_last(macd_signal),
        "macd_histogram": safe_last(macd_hist),
        "macd_history": safe_list(macd_line),
        "macd_signal_history": safe_list(macd_signal),
        "macd_hist_history": safe_list(macd_hist),
        "bb_upper": safe_last(bb_upper),
        "bb_middle": safe_last(bb_middle),
        "bb_lower": safe_last(bb_lower),
        "bb_upper_history": safe_list(bb_upper),
        "bb_middle_history": safe_list(bb_middle),
        "bb_lower_history": safe_list(bb_lower),
        "sma_20": safe_last(sma_20),
        "sma_50": safe_last(sma_50),
        "sma_200": safe_last(sma_200),
        "sma_20_history": safe_list(sma_20),
        "sma_50_history": safe_list(sma_50),
        "ema_12": safe_last(ema_12),
        "ema_26": safe_last(ema_26),
        "ema_12_history": safe_list(ema_12),
        "ema_26_history": safe_list(ema_26),
        "atr": safe_last(atr_series),
        "volume_sma": safe_last(vol_sma),
        # Stochastic RSI
        "stoch_rsi_k": safe_last(stoch_rsi_k),
        "stoch_rsi_d": safe_last(stoch_rsi_d),
        "stoch_rsi_k_history": safe_list(stoch_rsi_k),
        "stoch_rsi_d_history": safe_list(stoch_rsi_d),
        # OBV
        "obv": safe_last(obv_series),
        "obv_history": safe_list(obv_series),
        # ADX
        "adx": safe_last(adx_series),
        "adx_pos": safe_last(adx_pos),
        "adx_neg": safe_last(adx_neg),
        "adx_history": safe_list(adx_series),
        "adx_pos_history": safe_list(adx_pos),
        "adx_neg_history": safe_list(adx_neg),
        # VWAP
        "vwap": safe_last(vwap_series),
        "vwap_history": safe_list(vwap_series),
        # Ichimoku Cloud
        "ichimoku_conv": safe_last(ichi_conv),
        "ichimoku_base": safe_last(ichi_base),
        "ichimoku_a": safe_last(ichi_a),
        "ichimoku_b": safe_last(ichi_b),
        "ichimoku_conv_history": safe_list(ichi_conv),
        "ichimoku_base_history": safe_list(ichi_base),
        "ichimoku_a_history": safe_list(ichi_a),
        "ichimoku_b_history": safe_list(ichi_b),
    }


def _empty_indicators() -> dict:
    return {
        "rsi": None, "rsi_history": [],
        "macd_line": None, "macd_signal": None, "macd_histogram": None,
        "macd_history": [], "macd_signal_history": [], "macd_hist_history": [],
        "bb_upper": None, "bb_middle": None, "bb_lower": None,
        "bb_upper_history": [], "bb_middle_history": [], "bb_lower_history": [],
        "sma_20": None, "sma_50": None, "sma_200": None,
        "sma_20_history": [], "sma_50_history": [],
        "ema_12": None, "ema_26": None,
        "ema_12_history": [], "ema_26_history": [],
        "atr": None, "volume_sma": None,
        "stoch_rsi_k": None, "stoch_rsi_d": None,
        "stoch_rsi_k_history": [], "stoch_rsi_d_history": [],
        "obv": None, "obv_history": [],
        "adx": None, "adx_pos": None, "adx_neg": None,
        "adx_history": [], "adx_pos_history": [], "adx_neg_history": [],
        "vwap": None, "vwap_history": [],
        "ichimoku_conv": None, "ichimoku_base": None,
        "ichimoku_a": None, "ichimoku_b": None,
        "ichimoku_conv_history": [], "ichimoku_base_history": [],
        "ichimoku_a_history": [], "ichimoku_b_history": [],
    }
