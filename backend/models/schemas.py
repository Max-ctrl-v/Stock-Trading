from pydantic import BaseModel
from typing import Optional


class StockQuote(BaseModel):
    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    sector: Optional[str] = None
    exchange: Optional[str] = None


class OHLCV(BaseModel):
    timestamp: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[int]


class StockData(BaseModel):
    quote: StockQuote
    history: OHLCV


class IndicatorValues(BaseModel):
    rsi: Optional[float] = None
    rsi_history: list[float] = []
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_history: list[float] = []
    macd_signal_history: list[float] = []
    macd_hist_history: list[float] = []
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_upper_history: list[float] = []
    bb_middle_history: list[float] = []
    bb_lower_history: list[float] = []
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    sma_20_history: list[float] = []
    sma_50_history: list[float] = []
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    ema_12_history: list[float] = []
    ema_26_history: list[float] = []
    atr: Optional[float] = None
    volume_sma: Optional[float] = None
    # Stochastic RSI
    stoch_rsi_k: Optional[float] = None
    stoch_rsi_d: Optional[float] = None
    stoch_rsi_k_history: list[float] = []
    stoch_rsi_d_history: list[float] = []
    # On-Balance Volume
    obv: Optional[float] = None
    obv_history: list[float] = []
    # Average Directional Index
    adx: Optional[float] = None
    adx_pos: Optional[float] = None
    adx_neg: Optional[float] = None
    adx_history: list[float] = []
    adx_pos_history: list[float] = []
    adx_neg_history: list[float] = []
    # VWAP
    vwap: Optional[float] = None
    vwap_history: list[float] = []
    # Ichimoku Cloud
    ichimoku_conv: Optional[float] = None
    ichimoku_base: Optional[float] = None
    ichimoku_a: Optional[float] = None
    ichimoku_b: Optional[float] = None
    ichimoku_conv_history: list[float] = []
    ichimoku_base_history: list[float] = []
    ichimoku_a_history: list[float] = []
    ichimoku_b_history: list[float] = []


class AnalysisResponse(BaseModel):
    ticker: str
    quote: StockQuote
    indicators: IndicatorValues
    timestamps: list[str] = []


class SignalDirection(BaseModel):
    direction: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float


class PositionSize(BaseModel):
    shares: int
    dollar_amount: float
    risk_amount: float
    risk_pct: float


class AIAnalysis(BaseModel):
    narrative: str
    conviction: int  # 1-10
    catalysts: list[str] = []
    risks: list[str] = []
    timeframe: str = ""


class SignalResponse(BaseModel):
    ticker: str
    quote: StockQuote
    indicators: IndicatorValues
    signal: SignalDirection
    position: PositionSize
    ai_analysis: Optional[AIAnalysis] = None
    ohlcv: Optional[OHLCV] = None
    timestamps: list[str] = []
    support_resistance: Optional[dict] = None
    fibonacci: Optional[dict] = None
    multi_timeframe: Optional[dict] = None


class ChartData(BaseModel):
    ohlcv: OHLCV
    indicators: IndicatorValues
    timestamps: list[str] = []


class NewsItem(BaseModel):
    headline: str
    summary: str = ""
    sentiment: str = "neutral"  # bullish, bearish, neutral


class NewsResponse(BaseModel):
    ticker: str
    sentiment: str  # bullish, bearish, neutral
    sentiment_score: float  # -1 to 1
    items: list[NewsItem] = []
    raw_analysis: str = ""


class PortfolioPosition(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    added_at: str = ""


class PortfolioHolding(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    added_at: str = ""


class PortfolioGroup(BaseModel):
    ticker: str
    total_shares: float
    avg_cost: float
    current_price: float
    total_value: float
    total_cost: float
    pnl: float
    pnl_pct: float
    positions: list[PortfolioHolding] = []


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    holdings: list[PortfolioHolding] = []
    groups: list[PortfolioGroup] = []


class Settings(BaseModel):
    account_size: float = 10000.0
    risk_pct: float = 2.5


# --- Watchlist Models ---

class WatchlistItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    signal_direction: str = "HOLD"
    confidence: float = 0.0
    added_at: str = ""


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem] = []
    updated_at: str = ""


# --- Screener Models ---

class ScreenerPick(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_5d_pct: float = 0.0
    screener_score: float = 0.0
    signal_direction: str = "HOLD"
    confidence: float = 0.0
    volume_ratio: float = 0.0
    ai_thesis: str = ""
    sub_scores: dict = {}


class ScreenerResponse(BaseModel):
    status: str = "empty"  # "ready", "scanning", "empty"
    scanned_at: str = ""
    total_scanned: int = 0
    progress: int = 0
    picks: list[ScreenerPick] = []


# --- Alert Models ---

class AlertRule(BaseModel):
    id: str = ""
    ticker: str
    condition: str = "above"  # "above" or "below"
    target_price: float
    active: bool = True
    triggered: bool = False
    created_at: str = ""


class AlertsResponse(BaseModel):
    alerts: list[AlertRule] = []
    triggered: list[AlertRule] = []


# --- Trade Journal Models ---

class TradeEntry(BaseModel):
    id: str = ""
    ticker: str
    direction: str = "BUY"
    entry_price: float
    exit_price: Optional[float] = None
    shares: float
    entry_date: str = ""
    exit_date: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    notes: str = ""
    tags: list[str] = []
    status: str = "open"  # "open" or "closed"


class JournalStats(BaseModel):
    total_trades: int = 0
    closed_trades: int = 0
    win_rate: float = 0.0
    avg_gain_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    total_pnl: float = 0.0


class JournalResponse(BaseModel):
    trades: list[TradeEntry] = []
    stats: JournalStats = JournalStats()


# --- Backtest Models ---

class BacktestTrade(BaseModel):
    entry_date: str
    exit_date: str
    direction: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    reason: str = ""


class BacktestResult(BaseModel):
    ticker: str
    period: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade_pct: float = 0.0
    trades: list[BacktestTrade] = []
    equity_curve: list[float] = []


# --- Market / Sector Models ---

class SectorPerformance(BaseModel):
    name: str
    ticker: str
    change_1d_pct: float = 0.0
    change_1w_pct: float = 0.0
    change_1m_pct: float = 0.0


class MarketOverview(BaseModel):
    sectors: list[SectorPerformance] = []
    indices: dict = {}  # SPY, QQQ, DIA, IWM, VIX
    updated_at: str = ""


# --- Portfolio Analytics Models ---

class AllocationItem(BaseModel):
    ticker: str
    market_value: float
    pct: float
    sector: Optional[str] = None


class AllocationResponse(BaseModel):
    items: list[AllocationItem] = []
    by_sector: dict = {}  # sector -> pct


class CorrelationResponse(BaseModel):
    tickers: list[str] = []
    matrix: list[list[float]] = []


class BetaItem(BaseModel):
    ticker: str
    beta: float
    weight: float


class PortfolioBetaResponse(BaseModel):
    portfolio_beta: float
    holdings: list[BetaItem] = []


class PnlSnapshot(BaseModel):
    date: str
    total_value: float
    total_cost: float
    total_pnl: float


class PnlHistoryResponse(BaseModel):
    snapshots: list[PnlSnapshot] = []


class DividendItem(BaseModel):
    ticker: str
    annual_dividend: float = 0.0
    dividend_yield: float = 0.0
    ex_date: Optional[str] = None
    shares: float = 0.0
    annual_income: float = 0.0


class DividendResponse(BaseModel):
    holdings: list[DividendItem] = []
    total_annual_income: float = 0.0


class TaxLot(BaseModel):
    shares: float
    cost_per_share: float
    date: str
    total_cost: float


class TaxLotHolding(BaseModel):
    ticker: str
    lots: list[TaxLot] = []
    fifo_cost_basis: float = 0.0
    lifo_cost_basis: float = 0.0


class TaxLotResponse(BaseModel):
    holdings: list[TaxLotHolding] = []


class PositionAge(BaseModel):
    ticker: str
    added_at: str
    days_held: int
    weeks_held: float


class PositionAgingResponse(BaseModel):
    positions: list[PositionAge] = []
    avg_days_held: float = 0.0


class RebalanceAction(BaseModel):
    ticker: str
    current_pct: float
    target_pct: float
    diff_pct: float
    action: str  # "BUY" or "SELL"
    dollar_amount: float


class RebalanceResponse(BaseModel):
    actions: list[RebalanceAction] = []
    total_value: float = 0.0


class ExposureWarning(BaseModel):
    ticker: str
    pct: float
    limit_pct: float = 20.0
    over_limit: bool = False


class ExposureResponse(BaseModel):
    holdings: list[ExposureWarning] = []
    warnings: list[str] = []


class PnlBreakdownItem(BaseModel):
    ticker: str
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class PnlBreakdownResponse(BaseModel):
    unrealized: list[PnlBreakdownItem] = []
    total_unrealized: float = 0.0
    total_realized: float = 0.0


# --- Scanner Models ---

class UnusualVolumeItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    avg_volume: int = 0
    volume_ratio: float = 0.0


class UnusualVolumeResponse(BaseModel):
    count: int = 0
    threshold: float = 3.0
    items: list[UnusualVolumeItem] = []


class GapItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    gap_pct: float = 0.0
    gap_direction: str = "UP"
    prev_close: float = 0.0
    open_price: float = 0.0
    volume_ratio: float = 0.0


class GapResponse(BaseModel):
    count: int = 0
    min_gap_pct: float = 2.0
    items: list[GapItem] = []


class FiftyTwoWeekItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    pct_from_high: float = 0.0
    pct_from_low: float = 0.0
    proximity_type: str = "HIGH"


class FiftyTwoWeekResponse(BaseModel):
    count: int = 0
    proximity_pct: float = 5.0
    items: list[FiftyTwoWeekItem] = []


class EarningsMoverItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    earnings_date: str = ""
    move_pct: float = 0.0
    move_direction: str = "UP"
    volume_ratio: float = 0.0
    pre_earnings_price: float = 0.0


class EarningsMoversResponse(BaseModel):
    count: int = 0
    min_move_pct: float = 5.0
    items: list[EarningsMoverItem] = []


class IPOItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    ipo_date: str = ""
    ipo_price: float = 0.0
    change_since_ipo_pct: float = 0.0
    days_since_ipo: int = 0
    volume: int = 0
    market_cap: Optional[float] = None


class IPOResponse(BaseModel):
    count: int = 0
    items: list[IPOItem] = []


class InsiderBuyItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    insider_buys_count: int = 0
    total_shares_bought: int = 0
    total_value: float = 0.0
    latest_buy_date: str = ""
    notable_insiders: list[str] = []


class InsiderBuyResponse(BaseModel):
    count: int = 0
    items: list[InsiderBuyItem] = []


class ShortInterestItem(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    short_pct_of_float: float = 0.0
    shares_short: int = 0
    short_ratio: float = 0.0
    short_change_mom: float = 0.0
    avg_volume: int = 0


class ShortInterestResponse(BaseModel):
    count: int = 0
    min_short_pct: float = 10.0
    items: list[ShortInterestItem] = []


class ScreenerPreset(BaseModel):
    key: str
    name: str
    description: str = ""


# --- Support/Resistance & Fibonacci Models ---

class SupportResistanceResponse(BaseModel):
    ticker: str
    support_levels: list[float] = []
    resistance_levels: list[float] = []
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None


class FibonacciLevel(BaseModel):
    ratio: float
    label: str
    price: float


class FibonacciResponse(BaseModel):
    ticker: str
    swing_high: float
    swing_low: float
    levels: list[FibonacciLevel] = []
    trend: str = "neutral"


# --- Signal History Models ---

class SignalHistoryRecord(BaseModel):
    id: str = ""
    ticker: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    timestamp: str = ""
    outcome: Optional[str] = None  # "correct", "incorrect", "expired"
    outcome_price: Optional[float] = None
    outcome_date: Optional[str] = None


class SignalAccuracyStats(BaseModel):
    total: int = 0
    correct: int = 0
    incorrect: int = 0
    expired: int = 0
    pending: int = 0
    accuracy_pct: float = 0.0


class SignalHistoryResponse(BaseModel):
    records: list[SignalHistoryRecord] = []
    stats: SignalAccuracyStats = SignalAccuracyStats()


# --- Custom Thresholds Models ---

class CustomThresholdValues(BaseModel):
    ticker: str
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    signal_score_threshold: float = 10.0
    use_custom: bool = False


class CustomThresholdUpdate(BaseModel):
    rsi_oversold: Optional[float] = None
    rsi_overbought: Optional[float] = None
    signal_score_threshold: Optional[float] = None


class CustomThresholdsListResponse(BaseModel):
    thresholds: dict = {}


# --- Multi-Timeframe Confirmation ---

class TimeframeSignal(BaseModel):
    timeframe: str
    direction: str
    confidence: float
    rsi: Optional[float] = None


class MultiTimeframeConfirmation(BaseModel):
    daily: Optional[TimeframeSignal] = None
    weekly: Optional[TimeframeSignal] = None
    aligned: bool = False
    alignment_bonus: float = 0.0


# --- Recommendation Models ---

class RecommendationPick(BaseModel):
    ticker: str
    name: str = ""
    price: float = 0.0
    score_30d: float = 0.0
    score_6m: float = 0.0
    combined_score: float = 0.0
    rsi: Optional[float] = None
    change_5d_pct: float = 0.0
    change_1m_pct: float = 0.0
    pct_from_52w_low: float = 0.0
    volume_ratio: float = 0.0
    ai_reasoning: str = ""
    timeframe_short: str = "30 days"
    timeframe_long: str = "6 months"


class RecommendationsResponse(BaseModel):
    status: str = "empty"
    scanned_at: str = ""
    total_scanned: int = 0
    picks: list[RecommendationPick] = []


# --- Sell Signal Models ---

class SellSignal(BaseModel):
    ticker: str
    action: str = "HOLD"
    urgency: int = 1
    current_pnl_pct: float = 0.0
    rsi: Optional[float] = None
    vs_sma50: str = ""
    near_52w_high: bool = False
    ai_reasoning: str = ""
    factors: list[str] = []


class SellSignalsResponse(BaseModel):
    signals: list[SellSignal] = []
    analyzed_at: str = ""
