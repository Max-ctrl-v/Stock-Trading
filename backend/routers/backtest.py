from fastapi import APIRouter, HTTPException
from backend.services.backtest import run_backtest
from backend.models.schemas import BacktestResult, BacktestTrade

router = APIRouter()


@router.get("/{ticker}", response_model=BacktestResult)
async def backtest_ticker(
    ticker: str,
    period: str = "1y",
    slippage: float = 0.001,
    commission: float = 1.0,
):
    try:
        result = run_backtest(ticker, period, slippage=slippage, commission=commission)
        return BacktestResult(
            ticker=result["ticker"],
            period=result["period"],
            total_trades=result["total_trades"],
            win_rate=result["win_rate"],
            total_return_pct=result["total_return_pct"],
            max_drawdown_pct=result["max_drawdown_pct"],
            avg_trade_pct=result["avg_trade_pct"],
            trades=[BacktestTrade(**t) for t in result["trades"]],
            equity_curve=result["equity_curve"],
            slippage_pct=result["slippage_pct"],
            commission_per_trade=result["commission_per_trade"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Backtest failed for {ticker}: {str(e)}")
