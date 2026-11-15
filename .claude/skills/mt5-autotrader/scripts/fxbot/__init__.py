"""fxbot - autonomous Forex & metals trading engine for MetaTrader 5.

The package is split so that every decision that touches money is plain,
deterministic, testable Python:

    indicators -> strategy -> risk -> engine -> broker (MetaTrader5 API)

The same strategy/risk/management functions drive both live trading and the
backtester, so what is validated is what gets traded.
"""
__version__ = "1.0.0"
