# Subject — Financial forecasting (MLOps, difficulty 7/10)

## Goal
Forecasting service for financial time series, exposed as an application, kept current by an automated end-to-end pipeline.
- Graded: MLOps (production chain). Not graded: model performance. Coach: ≤1–2 days for a working model, then move on.
- "Simple, versioned, monitored, deployed, auto-retrainable model ≫ sophisticated model in a notebook."
- No finance knowledge needed; at level 1 it is a time-indexed number series with a natural (daily) update rate.

## Mandatory statements
- App must state explicitly: **not investment advice**.
- Short-term prices ≈ random walk; beating a naive baseline is unlikely and expected. Document this honestly — it is part of the job.

## Data
Per security per trading day: open, high, low, close, volume (OHLCV). Tabular, light, free, decades of history.

| Source | Access | Note |
|---|---|---|
| yfinance (`github.com/ranaroussi/yfinance`) | no key | |
| Stooq (`stooq.com/db/h/`) | no key, bulk history files | |
| Finnhub (`finnhub.io/docs/api`) | free key, ~60 calls/min | |
| Twelve Data (`twelvedata.com/docs`) | free key, ~800 req/day | |
| Alpha Vantage | free key, ~25 req/day | subject: unsuitable for a pipeline |
| FRED (`fred.stlouisfed.org/docs/api/fred/`) | free key | macro indicators |
| Frankfurter (`frankfurter.dev`) | no key | exchange rates |
| SEC EDGAR | free | US company fundamentals |

## Scope levels (choose; level 1 is the complete minimum)
**L1 — one security, one complete chain**
- Forecast the one-day change of a single security; chain ingestion → deployment actually complete.
- Baselines documented from the start: persistence (tomorrow = today) and historical mean of changes. Very hard to beat.
- Replay historical data to simulate daily quote arrival → observe the full loop without waiting.
- Trading calendar: weekends, public holidays, suspensions.

**L2 — scale and evaluation discipline**
- Several dozen securities; one global model vs. one model per security.
- Sliding-window backtesting, retrain at each step, always compared to baselines.
- Features from history (moving averages, past changes, recent volatility) under temporal consistency (no look-ahead).
- Uncertainty: prediction interval instead of a point value.

**L3 — feedback loop and observability**
- Close the loop: auto-collect next day's actual quote, measure production performance, keep history.
- Tell volatile market regime apart from genuine model degradation.
- Monitoring segmented by security or sector.
- Automated retraining per a rule the group defines, including discarding a model that regresses.

## Bibliography (subject PDF)
- Breck et al., *The ML Test Score* (production-readiness rubric)
- ml-ops.org (principles, patterns)
- Evidently: data drift in ML (`evidentlyai.com/ml-in-production/data-drift`)
- Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (`otexts.com/fpp3`) — backtesting, baselines
- Nixtla statsforecast (fast baselines); AutoARIMA (named as a relevant model)
- Bailey et al., *Probability of Backtest Overfitting* (SSRN 2326253)
- López de Prado, *10 Reasons Most ML Funds Fail* (SSRN 3031282)
- scikit-learn `TimeSeriesSplit` (time-series CV)
- `bashtage/arch` (volatility models); `rsheftel/pandas_market_calendars` (trading calendars)
